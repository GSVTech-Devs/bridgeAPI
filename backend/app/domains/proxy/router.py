from __future__ import annotations

import asyncio
import time
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.mongo_client import get_mongo_db
from app.core.redis_client import get_redis
from app.domains.apis.service import APINotFoundError, get_api_by_slug
from app.domains.jobs.models import JobStatus
from app.domains.jobs.runner import finalize_job
from app.domains.jobs.service import create_job, get_job_by_idempotency
from app.domains.logs.service import generate_correlation_id, write_request_log
from app.domains.metrics.service import record_metric
from app.domains.proxy.service import (
    DisabledAPIError,
    InactiveClientError,
    InvalidKeyError,
    PermissionDeniedError,
    RateLimitExceededError,
    build_upstream_headers,
    forward_to_upstream,
    validate_request,
)

router = APIRouter(tags=["proxy"])


def _job_http_response(job) -> Response:
    """Resposta HTTP que representa o estado atual de um job (usado em
    idempotência: repetir a mesma chamada não reprocessa)."""
    headers = {"x-correlation-id": job.correlation_id}
    if job.status == JobStatus.DONE.value:
        return Response(
            content=(job.result_body or "").encode("utf-8"),
            status_code=job.result_status_code or 200,
            headers=headers,
        )
    if job.status == JobStatus.TIMEOUT.value:
        return JSONResponse(
            {"job_id": str(job.id), "status": job.status, "error_code": job.error_code},
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            headers=headers,
        )
    if job.status == JobStatus.FAILED.value:
        return JSONResponse(
            {"job_id": str(job.id), "status": job.status, "error_code": job.error_code},
            status_code=status.HTTP_502_BAD_GATEWAY,
            headers=headers,
        )
    # pending/running
    return JSONResponse(
        {"job_id": str(job.id), "status": job.status, "status_url": f"/jobs/{job.id}"},
        status_code=status.HTTP_202_ACCEPTED,
        headers=headers,
    )


async def _dispatch(
    *,
    api_id: str,
    path: str,
    presented_key: str,
    request: Request,
    db: AsyncSession,
    redis,
    mongo_db,
) -> Response:
    """Dispatch comum. Execução híbrida: tenta síncrono até ``sync_timeout_s``;
    se exceder, vira job assíncrono (202 + status_url) e termina em background."""
    correlation_id = generate_correlation_id()

    try:
        api_key_obj, account, api = await validate_request(
            db, presented_key, api_id, redis
        )
    except InvalidKeyError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except InactiveClientError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except DisabledAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except RateLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        )

    # Idempotência: se já existe job para (conta, chave), devolve o estado dele.
    idempotency_key = request.headers.get("idempotency-key")
    if idempotency_key:
        existing = await get_job_by_idempotency(db, account.id, idempotency_key)
        if existing is not None:
            return _job_http_response(existing)

    # Webhook opcional: cliente pode pedir POST de callback quando o job concluir.
    callback_url = request.headers.get("x-bridge-callback")
    if callback_url and not callback_url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Bridge-Callback must be an http(s) URL",
        )

    incoming_headers = {k.lower(): v for k, v in request.headers.items()}
    upstream_headers = build_upstream_headers(
        api, incoming_headers, correlation_id, client_id=str(account.id)
    )
    params = dict(request.query_params)
    body = await request.body()

    # O forward roda num cliente HTTP PRÓPRIO (pode sobreviver ao request no
    # caminho assíncrono). Corremos o forward contra o limite síncrono.
    bg_client = httpx.AsyncClient(timeout=settings.upstream_timeout_s)
    start = time.monotonic()
    task = asyncio.create_task(
        forward_to_upstream(
            bg_client, api, path, request.method, upstream_headers, params, body or None
        )
    )
    done, _pending = await asyncio.wait({task}, timeout=settings.sync_timeout_s)

    # ---------------------------------------------------- caminho síncrono
    if task in done:
        try:
            upstream_response = task.result()
        except httpx.TimeoutException as exc:
            await bg_client.aclose()
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Upstream timed out: {exc}",
            )
        except Exception as exc:  # noqa: BLE001
            await bg_client.aclose()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Upstream error: {exc}"
            )

        latency_ms = (time.monotonic() - start) * 1000
        is_error = upstream_response.status_code >= 500
        return_status = 502 if is_error else upstream_response.status_code
        cost = api.cost_per_query if upstream_response.status_code == 200 else None
        await record_metric(
            db=db,
            account_id=account.id,
            api_id=api.id,
            key_id=api_key_obj.id,
            path=path,
            method=request.method,
            status_code=upstream_response.status_code,
            latency_ms=latency_ms,
            cost=cost,
        )

        if mongo_db is not None:
            await write_request_log(
                mongo_db,
                {
                    "correlation_id": correlation_id,
                    "client_id": str(account.id),
                    "api_id": str(api.id),
                    "key_id": str(api_key_obj.id),
                    "path": path,
                    "method": request.method,
                    "status_code": upstream_response.status_code,
                    "latency_ms": latency_ms,
                    "request_headers": incoming_headers,
                    "request_body": (body or b"").decode("utf-8", errors="replace"),
                    "response_headers": dict(upstream_response.headers),
                    "response_body": upstream_response.text[:4096],
                },
            )

        await bg_client.aclose()
        _STRIP_RESPONSE = {"transfer-encoding", "content-encoding", "content-length"}
        response_headers = {
            k: v
            for k, v in upstream_response.headers.items()
            if k.lower() not in _STRIP_RESPONSE
        }
        response_headers["x-correlation-id"] = correlation_id
        return Response(
            content=upstream_response.content,
            status_code=return_status,
            headers=response_headers,
        )

    # ---------------------------------------------------- caminho assíncrono
    snapshot = {
        "path": path,
        "method": request.method,
        "params": params,
        "request_headers": incoming_headers,
        "request_body": (body or b"").decode("utf-8", errors="replace"),
    }
    job = await create_job(
        db,
        correlation_id=correlation_id,
        account_id=account.id,
        api_id=api.id,
        key_id=api_key_obj.id,
        idempotency_key=idempotency_key,
        request_snapshot=snapshot,
        callback_url=callback_url,
    )
    meta = {
        "account_id": account.id,
        "api_id": api.id,
        "key_id": api_key_obj.id,
        "path": path,
        "method": request.method,
        "cost_per_query": api.cost_per_query,
        "correlation_id": correlation_id,
        "callback_url": callback_url,
        "start": start,
        "log_base": {
            "correlation_id": correlation_id,
            "client_id": str(account.id),
            "api_id": str(api.id),
            "key_id": str(api_key_obj.id),
            "path": path,
            "method": request.method,
            "request_headers": incoming_headers,
            "request_body": (body or b"").decode("utf-8", errors="replace"),
        },
    }
    loop = asyncio.get_running_loop()
    job_id = str(job.id)
    task.add_done_callback(
        lambda t: loop.create_task(finalize_job(job_id, t, meta, bg_client))
    )
    return JSONResponse(
        {"job_id": job_id, "status": "running", "status_url": f"/jobs/{job_id}"},
        status_code=status.HTTP_202_ACCEPTED,
        headers={"x-correlation-id": correlation_id},
    )


@router.api_route(
    "/apis/{slug}/{query}/{bridge_token}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def proxy_by_slug(
    slug: str,
    query: str,
    bridge_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    mongo_db=Depends(get_mongo_db),
) -> Response:
    try:
        api = await get_api_by_slug(db, slug)
    except APINotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API '{slug}' not found",
        )

    return await _dispatch(
        api_id=str(api.id),
        path=query,
        presented_key=bridge_token,
        request=request,
        db=db,
        redis=redis,
        mongo_db=mongo_db,
    )


def _presented_key_from_headers(request: Request) -> Optional[str]:
    """Lê a bridge key do cabeçalho: Authorization: Bearer <key> ou X-Bridge-Key.

    Usada quando o cliente não coloca o token na URL (comum em POST, onde a
    convenção é mandar a credencial no header Authorization)."""
    auth = request.headers.get("authorization")
    if auth and auth[:7].lower() == "bearer ":
        token = auth[7:].strip()
        if token:
            return token
    return request.headers.get("x-bridge-key")


@router.api_route(
    "/apis/{slug}/{query}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def proxy_by_slug_header_auth(
    slug: str,
    query: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    mongo_db=Depends(get_mongo_db),
) -> Response:
    """Mesma semântica de ``proxy_by_slug``, mas com a bridge key no header
    (Authorization: Bearer / X-Bridge-Key) em vez de no final da URL."""
    presented_key = _presented_key_from_headers(request)
    if not presented_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bridge key: send 'Authorization: Bearer <key>' or "
            "'X-Bridge-Key', or put the key in the URL path.",
        )

    try:
        api = await get_api_by_slug(db, slug)
    except APINotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API '{slug}' not found",
        )

    return await _dispatch(
        api_id=str(api.id),
        path=query,
        presented_key=presented_key,
        request=request,
        db=db,
        redis=redis,
        mongo_db=mongo_db,
    )


@router.api_route(
    "/proxy/{api_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def proxy(
    api_id: uuid.UUID,
    path: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    mongo_db=Depends(get_mongo_db),
) -> Response:
    presented_key: Optional[str] = request.headers.get("x-bridge-key")
    if not presented_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Bridge-Key header",
        )

    return await _dispatch(
        api_id=str(api_id),
        path=path,
        presented_key=presented_key,
        request=request,
        db=db,
        redis=redis,
        mongo_db=mongo_db,
    )

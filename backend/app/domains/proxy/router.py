from __future__ import annotations

import time
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.mongo_client import get_mongo_db
from app.core.redis_client import get_redis
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


async def get_http_client() -> httpx.AsyncClient:
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


@router.api_route(
    "/proxy/{api_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def proxy(
    api_id: uuid.UUID,
    path: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    http_client: httpx.AsyncClient = Depends(get_http_client),
    redis=Depends(get_redis),
    mongo_db=Depends(get_mongo_db),
) -> Response:
    correlation_id = generate_correlation_id()
    presented_key: Optional[str] = request.headers.get("x-bridge-key")
    if not presented_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Bridge-Key header",
        )

    try:
        api_key_obj, client, api = await validate_request(
            db, presented_key, str(api_id), redis
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

    incoming_headers = {k.lower(): v for k, v in request.headers.items()}
    upstream_headers = build_upstream_headers(api, incoming_headers)
    params = dict(request.query_params)
    body = await request.body()

    start = time.monotonic()

    try:
        upstream_response = await forward_to_upstream(
            http_client,
            api,
            path,
            request.method,
            upstream_headers,
            params,
            body or None,
        )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Upstream timed out: {exc}",
        )

    latency_ms = (time.monotonic() - start) * 1000
    is_error = upstream_response.status_code >= 500
    return_status = 502 if is_error else upstream_response.status_code
    cost = None if is_error else None  # cost_rule logic in future iteration

    await record_metric(
        db=db,
        client_id=client.id,
        api_id=api.id,
        key_id=api_key_obj.id,
        path=path,
        method=request.method,
        status_code=upstream_response.status_code,
        latency_ms=latency_ms,
        cost=cost,
    )

    if mongo_db is not None:
        incoming_headers = {k.lower(): v for k, v in request.headers.items()}
        await write_request_log(
            mongo_db,
            {
                "correlation_id": correlation_id,
                "client_id": str(client.id),
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

    response_headers = {
        k: v
        for k, v in upstream_response.headers.items()
        if k.lower() not in {"transfer-encoding", "content-encoding"}
    }
    response_headers["x-correlation-id"] = correlation_id
    return Response(
        content=upstream_response.content,
        status_code=return_status,
        headers=response_headers,
    )

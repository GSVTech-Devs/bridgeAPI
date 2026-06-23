from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.mongo_client import get_mongo_db
from app.domains.alerts.service import sync_api_status_alert
from app.domains.apis.models import ExternalAPI
from app.domains.apis.service import APINotFoundError
from app.domains.auth.router import get_current_user
from app.domains.auth.schemas import MeResponse
from app.domains.ingest.schemas import (
    IngestLogsRequest,
    IngestLogsResponse,
    ServiceTokenResponse,
)
from app.domains.ingest.service import (
    authenticate_service_token,
    generate_service_token,
    write_app_logs,
)
from app.domains.captcha.schemas import CaptchaConfigResponse, CaptchaReportRequest
from app.domains.captcha.service import (
    CaptchaNotFoundError,
    get_captcha_config_for_api,
    report_captcha_failure,
)
from app.domains.proxies.schemas import ProxyConfigResponse, ProxyReportRequest
from app.domains.proxies.service import (
    ProxyNotFoundError,
    get_proxy_config_for_api,
    report_proxy_failure,
)
from app.domains.status.schemas import StatusReportIn
from app.domains.status.service import record_status

router = APIRouter(tags=["ingest"])


async def require_service_token(
    x_service_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> ExternalAPI:
    """Autentica a API chamadora pelo header X-Service-Token."""
    if not x_service_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Service-Token header",
        )
    api = await authenticate_service_token(db, x_service_token)
    if api is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service token",
        )
    return api


@router.post("/ingest/logs", response_model=IngestLogsResponse)
async def ingest_logs(
    body: IngestLogsRequest,
    api: ExternalAPI = Depends(require_service_token),
    mongo_db=Depends(get_mongo_db),
) -> IngestLogsResponse:
    entries = [e.model_dump() for e in body.entries]
    accepted = 0
    if mongo_db is not None:
        accepted = await write_app_logs(mongo_db, str(api.id), entries)
    return IngestLogsResponse(accepted=accepted)


@router.post("/ingest/status")
async def ingest_status(
    body: StatusReportIn,
    api: ExternalAPI = Depends(require_service_token),
    mongo_db=Depends(get_mongo_db),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if mongo_db is not None:
        result = await record_status(mongo_db, str(api.id), body.model_dump())
        transition = result.get("transition")
        if transition is not None:
            # A saúde mudou: abre/resolve alerta da plataforma (escopo admin).
            await sync_api_status_alert(db, api.id, transition["to"])
    return {"ok": True, "status": body.status}


@router.get("/ingest/proxies", response_model=ProxyConfigResponse)
async def ingest_proxies(
    api: ExternalAPI = Depends(require_service_token),
    db: AsyncSession = Depends(get_db),
    x_bridge_client: str | None = Header(default=None),
) -> ProxyConfigResponse:
    """Config do pool de proxies da API (credenciais inclusas) — a SDK consome
    isto com cache curto, então a troca de proxy na plataforma reflete sem deploy.

    ``X-Bridge-Client`` (o cliente da chamada, propagado pela Bridge) habilita a
    resolução híbrida: usa o pool que o cliente configurou para esta API, senão
    o default da API."""
    return await get_proxy_config_for_api(db, api, client_id=x_bridge_client)


@router.post("/ingest/proxies/report")
async def ingest_proxy_report(
    body: ProxyReportRequest,
    api: ExternalAPI = Depends(require_service_token),
    db: AsyncSession = Depends(get_db),
    x_bridge_client: str | None = Header(default=None),
) -> dict:
    """A SDK reporta falha de um proxy → marca como failing/inactive na plataforma."""
    try:
        proxy = await report_proxy_failure(db, api, body, client_id=x_bridge_client)
    except ProxyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Proxy not in this API's pool"
        )
    return {"ok": True, "proxy_id": str(proxy.id), "status": proxy.status}


@router.get("/ingest/captcha", response_model=CaptchaConfigResponse)
async def ingest_captcha(
    api: ExternalAPI = Depends(require_service_token),
    db: AsyncSession = Depends(get_db),
    x_bridge_client: str | None = Header(default=None),
) -> CaptchaConfigResponse:
    """Provedores de captcha da API (chave + saldo) — resolvidos de forma híbrida
    pelo cliente da chamada (X-Bridge-Client), igual ao proxy."""
    return await get_captcha_config_for_api(db, api, client_id=x_bridge_client)


@router.post("/ingest/captcha/report")
async def ingest_captcha_report(
    body: CaptchaReportRequest,
    api: ExternalAPI = Depends(require_service_token),
    db: AsyncSession = Depends(get_db),
    x_bridge_client: str | None = Header(default=None),
) -> dict:
    """A SDK reporta falha/saldo de um provedor de captcha."""
    try:
        captcha = await report_captcha_failure(db, api, body, client_id=x_bridge_client)
    except CaptchaNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Captcha provider not in this API/owner scope",
        )
    return {"ok": True, "provider_id": str(captcha.id), "status": captcha.status}


@router.post(
    "/ingest/apis/{api_id}/token",
    response_model=ServiceTokenResponse,
)
async def create_service_token(
    api_id: str,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> ServiceTokenResponse:
    """Gera/rotaciona o service token de uma API (admin)."""
    try:
        api, raw_token = await generate_service_token(db, api_id)
    except APINotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API not found: {api_id}",
        )
    return ServiceTokenResponse(
        api_id=str(api.id),
        service_token=raw_token,
        prefix=api.service_token_prefix or "",
    )

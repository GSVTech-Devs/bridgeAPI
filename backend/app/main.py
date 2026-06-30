from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.domains.accounts.router import router as accounts_router
from app.domains.alerts.router import admin_router as alerts_admin_router
from app.domains.alerts.router import client_router as alerts_client_router
from app.domains.apis.router import router as apis_router
from app.domains.auth.router import router as auth_router
from app.domains.branding.router import router as branding_router
from app.domains.captcha.client_router import router as captcha_client_router
from app.domains.captcha.router import monitor_router as captcha_monitor_router
from app.domains.captcha.router import router as captcha_router
from app.domains.ingest.router import router as ingest_router
from app.domains.jobs.router import router as jobs_router
from app.domains.keys.router import router as keys_router
from app.domains.logs.router import router as logs_router
from app.domains.members.router import admin_router as members_admin_router
from app.domains.members.router import router as members_router
from app.domains.metrics.router import router as metrics_router
from app.domains.permissions.router import router as permissions_router
from app.domains.proxies.client_router import router as proxies_client_router
from app.domains.proxies.router import monitor_router as proxies_monitor_router
from app.domains.proxies.router import router as proxies_router
from app.domains.proxy.router import router as proxy_router
from app.domains.status.router import router as status_router

# Em produção desativamos a documentação interativa embutida (Swagger UI, ReDoc)
# e o schema OpenAPI público, que expõem o desenho completo da API.
app = FastAPI(
    title="Bridge API",
    description="Centralized API gateway — proxy and access management",
    version="0.1.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(members_router)
app.include_router(members_admin_router)
app.include_router(branding_router)
app.include_router(apis_router)
app.include_router(keys_router)
app.include_router(permissions_router)
app.include_router(logs_router)
app.include_router(metrics_router)
app.include_router(ingest_router)
app.include_router(status_router)
app.include_router(proxies_router)
app.include_router(proxies_client_router)
app.include_router(proxies_monitor_router)
app.include_router(captcha_router)
app.include_router(captcha_client_router)
app.include_router(captcha_monitor_router)
app.include_router(jobs_router)
app.include_router(alerts_admin_router)
app.include_router(alerts_client_router)
app.include_router(proxy_router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}

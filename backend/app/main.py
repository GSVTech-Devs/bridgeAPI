from fastapi import FastAPI

from app.domains.apis.router import router as apis_router
from app.domains.auth.router import router as auth_router
from app.domains.clients.router import router as clients_router
from app.domains.keys.router import router as keys_router
from app.domains.logs.router import router as logs_router
from app.domains.permissions.router import router as permissions_router
from app.domains.proxy.router import router as proxy_router

app = FastAPI(
    title="Bridge API",
    description="Centralized API gateway — proxy and access management",
    version="0.1.0",
)

app.include_router(auth_router)
app.include_router(clients_router)
app.include_router(apis_router)
app.include_router(keys_router)
app.include_router(permissions_router)
app.include_router(logs_router)
app.include_router(proxy_router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}

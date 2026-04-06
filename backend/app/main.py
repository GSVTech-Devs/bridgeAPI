from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.domains.apis.router import router as apis_router
from app.domains.auth.router import router as auth_router
from app.domains.clients.router import router as clients_router
from app.domains.keys.router import router as keys_router
from app.domains.logs.router import router as logs_router
from app.domains.metrics.router import router as metrics_router
from app.domains.permissions.router import router as permissions_router
from app.domains.proxy.router import router as proxy_router

app = FastAPI(
    title="Bridge API",
    description="Centralized API gateway — proxy and access management",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://172.16.254.21:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(clients_router)
app.include_router(apis_router)
app.include_router(keys_router)
app.include_router(permissions_router)
app.include_router(logs_router)
app.include_router(metrics_router)
app.include_router(proxy_router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}

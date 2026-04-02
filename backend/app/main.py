from fastapi import FastAPI

from app.domains.auth.router import router as auth_router
from app.domains.clients.router import router as clients_router

app = FastAPI(
    title="Bridge API",
    description="Centralized API gateway — proxy and access management",
    version="0.1.0",
)

app.include_router(auth_router)
app.include_router(clients_router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}

from fastapi import FastAPI

app = FastAPI(
    title="Bridge API",
    description="Centralized API gateway — proxy and access management",
    version="0.1.0",
)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}

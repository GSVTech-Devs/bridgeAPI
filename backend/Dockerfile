# ── Stage: development ────────────────────────────────────────────────────────
FROM python:3.12-slim AS development
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Stage: production ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS production
WORKDIR /app
# Install deps before copying source to maximise layer cache.
# Dummy stub lets setuptools resolve the package without the real source.
COPY pyproject.toml .
RUN mkdir -p app && touch app/__init__.py && \
    pip install --no-cache-dir . && \
    rm -rf app
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

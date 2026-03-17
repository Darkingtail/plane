# Multi-stage Dockerfile for Plane GitLab Bridge
FROM python:3.12-slim AS builder

ARG USE_CHINA_MIRROR=false
ARG PYPI_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy full source for build
COPY pyproject.toml ./
COPY app/ ./app/

RUN uv venv /build/.venv && \
    if [ "$USE_CHINA_MIRROR" = "true" ]; then \
        export UV_INDEX_URL="${PYPI_MIRROR}"; \
    fi && \
    UV_HTTP_TIMEOUT=300 uv pip install --no-cache .

# Runtime stage
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/.venv /app/.venv

COPY --chown=appuser:appuser . .

RUN mkdir -p /app/logs && chown -R appuser:appuser /app/logs

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080

CMD ["/app/.venv/bin/python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "2"]

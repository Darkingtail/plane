"""
Plane GitLab Bridge - FastAPI application entry point
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    import logging

    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Plane GitLab Bridge starting...")
    logger.info(f"Plane API: {settings.plane_base_url}")
    logger.info(f"Workspace: {settings.plane_workspace_slug}")

    yield

    # Shutdown
    from app.services.plane_service import plane_service

    await plane_service.close()


app = FastAPI(
    title="Plane GitLab Bridge",
    description="GitLab automation bridge for Plane project management",
    version="1.0.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

# Configure CORS
# Always include Plane frontend origins; merge with any configured origins
_cors_origins = list(settings.backend_cors_origins) + [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
]
# Deduplicate while preserving order
_seen: set = set()
_cors_origins_deduped = [o for o in _cors_origins if not (o in _seen or _seen.add(o))]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins_deduped,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from app.api.v1 import system
from app.api.v1.webhooks import plane_webhook
from app.api.v1.gitlab_settings import router as gitlab_settings_router

app.include_router(system.router, prefix="/api/v1")
app.include_router(plane_webhook.router, prefix="/api/v1")
app.include_router(gitlab_settings_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return JSONResponse(content={"status": "healthy", "service": "plane-gitlab-bridge", "version": "1.0.0"})


@app.get("/")
async def root():
    return {
        "service": "Plane GitLab Bridge",
        "version": "1.0.0",
        "docs": "/api/v1/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True, log_level="info")

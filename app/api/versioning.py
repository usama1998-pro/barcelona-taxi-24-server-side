from fastapi import APIRouter, FastAPI

from app.api.v1.router import build_v1_router

API_VERSION = "v1"
API_V1_PREFIX = f"/api/{API_VERSION}"


def mount_api(app: FastAPI) -> None:
    """Mount versioned routes at /api/v1/*."""
    app.include_router(build_v1_router(), prefix=API_V1_PREFIX)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.api.versioning import API_V1_PREFIX, mount_api
from app.core.config import settings
from app.core.database import create_db_engine
from app.core.logging_setup import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    app.state.db_engine = create_db_engine()
    yield
    app.state.db_engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="HTTP API for the taxi booking backend (FastAPI port)",
    version="1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mount_api(app)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})[
        "access-token"
    ] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": (
            "Paste only the access_token from "
            f"POST {API_V1_PREFIX}/auth/signin or {API_V1_PREFIX}/auth/signup."
        ),
    }
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_staff_admin
from app.modules.auth.types import AuthenticatedUser
from app.modules.logs.service import logs_service

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("")
async def list_logs(
    _: Annotated[AuthenticatedUser, Depends(require_staff_admin)],
    limit: Annotated[int | None, Query()] = None,
    file: Annotated[str | None, Query()] = None,
) -> dict:
    return logs_service.read_latest_lines(limit or 200, file)


@router.get("/files")
async def list_files(
    _: Annotated[AuthenticatedUser, Depends(require_staff_admin)],
) -> dict:
    from app.modules.logs.config import resolve_file_logger_config

    config = resolve_file_logger_config()
    return {
        "enabled": config.enabled,
        "activeFile": config.file_path,
        "files": logs_service.list_log_files(),
    }

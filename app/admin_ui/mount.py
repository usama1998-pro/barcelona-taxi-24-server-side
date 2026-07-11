from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

ADMIN_DIR = Path(__file__).resolve().parents[2] / "admin"


def mount_admin_ui(app: FastAPI) -> None:
    if not ADMIN_DIR.is_dir():
        return
    app.mount(
        "/my-portal",
        StaticFiles(directory=str(ADMIN_DIR), html=True),
        name="admin-ui",
    )

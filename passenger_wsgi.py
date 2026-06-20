"""
GoDaddy / Phusion Passenger entry point.

cPanel → Setup Python App:
  - Application root: this directory (barcelona-taxi-24-server-side)
  - Application startup file: passenger_wsgi.py
  - Application entry point: application

Passenger expects a WSGI callable named `application`. FastAPI is ASGI, so we
wrap it with a2wsgi.ASGIMiddleware.
"""

from __future__ import annotations

import os
import sys


def _app_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _maybe_use_godaddy_virtualenv() -> None:
    """
    On GoDaddy, Passenger may start with system Python unless we re-exec into the
    app virtualenv. Set PASSENGER_PYTHON in the environment/cPanel if auto-detect
    fails, e.g. ~/virtualenv/apps/barcelona-taxi-24-server-side/3.11/bin/python3
    """
    venv_python = os.environ.get("PASSENGER_PYTHON", "").strip()
    if not venv_python:
        home = os.environ.get("HOME", "")
        app_name = os.path.basename(_app_root())
        for version in ("3.12", "3.11", "3.10", "3.9"):
            candidate = os.path.join(
                home, "virtualenv", "apps", app_name, version, "bin", "python3"
            )
            if os.path.isfile(candidate):
                venv_python = candidate
                break
    if not venv_python:
        return
    if os.path.abspath(sys.executable) == os.path.abspath(venv_python):
        return
    os.execl(venv_python, venv_python, *sys.argv)


def _bootstrap_path_and_env() -> None:
    root = _app_root()
    if root not in sys.path:
        sys.path.insert(0, root)
    os.chdir(root)

    from dotenv import load_dotenv

    load_dotenv(os.path.join(root, ".env"))


_maybe_use_godaddy_virtualenv()
_bootstrap_path_and_env()

from a2wsgi import ASGIMiddleware  # noqa: E402

from app.main import app as fastapi_app  # noqa: E402

application = ASGIMiddleware(fastapi_app)

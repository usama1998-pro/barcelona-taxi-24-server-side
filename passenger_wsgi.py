"""
GoDaddy / Phusion Passenger entry point.

cPanel → Setup Python App:
  - Application startup file: passenger_wsgi.py
  - Application entry point: application
"""

from __future__ import annotations

import os
import sys

root = os.path.dirname(os.path.abspath(__file__))
if root not in sys.path:
    sys.path.insert(0, root)
os.chdir(root)

from dotenv import load_dotenv

load_dotenv(os.path.join(root, ".env"))

from a2wsgi import ASGIMiddleware

from app.core.database import ensure_app_db_engine
from app.core.logging_setup import setup_logging
from app.main import app as fastapi_app

setup_logging()
ensure_app_db_engine(fastapi_app)

application = ASGIMiddleware(fastapi_app)

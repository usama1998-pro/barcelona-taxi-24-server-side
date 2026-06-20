import os
import sys

root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, root)
os.chdir(root)

from a2wsgi import ASGIMiddleware
from app.main import app as fastapi_app

application = ASGIMiddleware(fastapi_app)
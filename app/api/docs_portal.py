"""Admin-gated API documentation.

Public FastAPI docs are disabled. The Swagger HTML shell is same-origin and
reads the portal token from localStorage. The OpenAPI schema endpoint returns a
plain 404 for anyone who is not a super admin (same shape as a missing route).
Unauthenticated browsers see a client-side Starlette-looking 404 page.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.rate_limit import ADMIN_RATE_LIMIT, check_rate_limit, client_ip
from app.core.security import extract_access_token
from app.db.session import get_session
from app.modules.auth.service import auth_service
from app.modules.auth.types import AuthenticatedUser

router = APIRouter(include_in_schema=False)

# Matches ADMIN_ACCESS_TOKEN_KEY in server-side/admin/js/config.js.
_ADMIN_TOKEN_KEY = "taxi_super_admin_access_token"

# Matches Starlette's default HTML 404 page.
_NOT_FOUND_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>404 Not Found</title>
</head>
<body>
<h1>404 Not Found</h1>
</body>
</html>
"""

_SWAGGER_HTML = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>404 Not Found</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
    <style>body { margin: 0; background: #fafafa; }</style>
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
    <script>
      (function () {
        var TOKEN_KEY = __TOKEN_KEY__;
        var NOT_FOUND = __NOT_FOUND__;
        function showNotFound() {
          document.open();
          document.write(NOT_FOUND);
          document.close();
        }
        function readToken() {
          try {
            var fromLs = localStorage.getItem(TOKEN_KEY);
            if (fromLs) return fromLs;
          } catch (e) {}
          return null;
        }
        var token = readToken();
        if (!token) {
          showNotFound();
          return;
        }
        document.title = 'API Docs';
        window.ui = SwaggerUIBundle({
          url: '/internal/openapi.json',
          dom_id: '#swagger-ui',
          deepLinking: true,
          presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
          layout: 'StandaloneLayout',
          requestInterceptor: function (req) {
            req.headers['Authorization'] = 'Bearer ' + token;
            return req;
          },
          responseInterceptor: function (res) {
            if (res.url && res.url.indexOf('/internal/openapi.json') !== -1 && res.status === 404) {
              showNotFound();
            }
            return res;
          },
        });
      })();
    </script>
  </body>
</html>
""".replace(
    "__TOKEN_KEY__",
    repr(_ADMIN_TOKEN_KEY),
).replace(
    "__NOT_FOUND__",
    repr(_NOT_FOUND_HTML),
)


def _token_from_request(
    request: Request,
    authorization: str | None,
) -> str | None:
    header = extract_access_token(authorization)
    if header:
        return header
    cookie = request.cookies.get(_ADMIN_TOKEN_KEY)
    if cookie and cookie.strip():
        return cookie.strip()
    return None


def _verify_super_admin_or_raise_404(
    request: Request,
    session: Session,
    authorization: str | None,
) -> AuthenticatedUser:
    check_rate_limit(f"admin:{client_ip(request)}", limit=ADMIN_RATE_LIMIT)
    token = _token_from_request(request, authorization)
    if not token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    try:
        user = auth_service.verify_bearer(session, f"Bearer {token}")
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found") from None
    if user.get("typ") != "user" or not user.get("is_admin") or not user.get("is_super_admin"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    return user


async def _require_super_admin_or_404(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedUser:
    return _verify_super_admin_or_raise_404(request, session, authorization)


@router.get("/internal/api-docs", response_class=HTMLResponse)
async def portal_api_docs() -> HTMLResponse:
    # HTML is same-origin; auth is enforced via localStorage + /internal/openapi.json.
    # Gating this route on a cookie broke logged-in admins (JWT-only in localStorage).
    return HTMLResponse(_SWAGGER_HTML)


@router.get("/internal/openapi.json")
async def portal_openapi(
    request: Request,
    _: Annotated[AuthenticatedUser, Depends(_require_super_admin_or_404)],
) -> JSONResponse:
    return JSONResponse(request.app.openapi())

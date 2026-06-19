from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter(tags=["root"])


@router.get("/", include_in_schema=True)
async def redirect_to_docs() -> RedirectResponse:
    return RedirectResponse(url="/docs", status_code=302)

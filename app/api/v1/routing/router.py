from fastapi import APIRouter

from app.modules.routing.schemas import PlacesSearchBody, RouteQuoteBody
from app.modules.routing.service import routing_service

router = APIRouter(prefix="/routing", tags=["routing"])


@router.post("/places")
async def places(body: PlacesSearchBody) -> list[dict[str, str]]:
    return await routing_service.search_places(body.input)


@router.post("/quote")
async def quote(body: RouteQuoteBody) -> dict[str, float | int]:
    return await routing_service.get_quote(body)

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.database import ping_database

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/db")
async def check_database(request: Request) -> dict[str, object]:
    engine = request.app.state.db_engine
    try:
        await ping_database(engine)
        return {"status": "ok", "database": {"status": "up"}}
    except Exception as error:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": {"status": "down", "message": str(error)},
            },
        )

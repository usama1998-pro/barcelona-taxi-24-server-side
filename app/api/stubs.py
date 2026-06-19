from fastapi import HTTPException


def not_implemented(endpoint: str) -> None:
    raise HTTPException(
        status_code=501,
        detail=f"Not implemented yet: {endpoint}",
    )

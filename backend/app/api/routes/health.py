"""Health endpoints for process availability and database connectivity."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.db import database

# Health routes are mounted at the API root for platform probes.
router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Report that the web process can serve requests."""
    return {"status": "ok"}


@router.get("/health/db")
def database_health() -> JSONResponse:
    """Report database connectivity separately from process availability."""
    if database.engine is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "database": "disconnected"},
        )
    try:
        with database.engine.connect():
            pass
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "database": "disconnected"},
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ok",
            "database": "connected",
            "session_factory": database.SessionLocal is not None,
        },
    )

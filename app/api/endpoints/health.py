from datetime import datetime, timezone
from fastapi import APIRouter
from app.core.config import settings
from app.models.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Service health status")
@router.get("/health/", response_model=HealthResponse, include_in_schema=False)
def health_check() -> HealthResponse:
    try:
        import pyogrio
        drivers = [d for d in ["ESRI Shapefile", "KML", "GeoJSON"] if d in pyogrio.list_drivers()]
    except Exception:
        drivers = ["pyshp", "xml"]

    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        timestamp=datetime.now(timezone.utc),
        drivers_available=drivers,
    )

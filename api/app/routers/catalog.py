from fastapi import APIRouter
from sqlalchemy import select

from app.config import get_settings
from app.deps import DbSession
from app.models import OccurrenceType
from app.schemas import OccurrenceTypeOut

router = APIRouter(tags=["catálogo"])


@router.get("/occurrence-types", response_model=list[OccurrenceTypeOut])
def list_occurrence_types(db: DbSession) -> list[OccurrenceType]:
    return list(
        db.scalars(
            select(OccurrenceType)
            .where(OccurrenceType.is_active)
            .order_by(OccurrenceType.sort_order, OccurrenceType.name)
        )
    )


@router.get("/meta")
def meta() -> dict:
    """Public settings the web client needs to stay in sync with the API."""
    settings = get_settings()
    return {
        "terms_version": settings.terms_version,
        "max_photos_per_occurrence": settings.max_photos_per_occurrence,
        "max_photo_mb": settings.max_photo_bytes // (1024 * 1024),
        "privacy_grid_meters": settings.privacy_grid_meters,
        "service_area": {
            "name": settings.service_area_name,
            # [min_lon, min_lat, max_lon, max_lat] or null when unrestricted.
            "bbox": settings.service_area(),
        },
    }

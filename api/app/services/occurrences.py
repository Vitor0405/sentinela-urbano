import re
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from geoalchemy2 import WKTElement
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.status import QUEUE_STATUSES
from app.models import (
    Occurrence,
    OccurrencePhoto,
    OccurrenceStatus,
    OccurrenceStatusHistory,
    OccurrenceType,
    PhotoKind,
    User,
    UserRole,
)
from app.schemas import (
    HistoryOut,
    MapItem,
    OccurrenceDetail,
    OccurrenceTypeOut,
    PhotoOut,
    ReporterOut,
    RiskOut,
    SensitiveNearby,
)
from app.security import new_tracking_token
from app.services.deadlines import ResponseClock, response_clock
from app.services.photos import ProcessedPhoto, store_photo
from app.services.privacy import obfuscate_coordinate
from app.services.risk import detect_chronic

BBox = tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat


def parse_bbox(raw: str | None) -> BBox | None:
    if not raw:
        return None
    try:
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in raw.split(","))
    except ValueError as exc:
        raise ValueError("bbox deve ser 'min_lon,min_lat,max_lon,max_lat'") from exc
    if not (-180 <= min_lon <= max_lon <= 180 and -90 <= min_lat <= max_lat <= 90):
        raise ValueError("bbox fora dos limites ou com mínimo maior que máximo")
    return min_lon, min_lat, max_lon, max_lat


def in_bbox(lat: float, lon: float, bbox: BBox) -> bool:
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def make_point(lat: float, lon: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


CUSTOM_LABEL_MIN = 3
CUSTOM_LABEL_MAX = 60
# Contact data or links do not belong in a risk description (privacy and spam).
_CONTACT = re.compile(r"(https?:|www\.|@|\d[\d .-]{6,}\d)", re.IGNORECASE)


def clean_custom_label(raw: str | None) -> str:
    """Normalize the resident's description of an "Outro" risk, or raise ValueError (pt-BR)."""
    label = " ".join((raw or "").split())
    if len(label) < CUSTOM_LABEL_MIN:
        raise ValueError(
            'Descreva o risco em poucas palavras (por exemplo, "caixa de isopor com água").'
        )
    if len(label) > CUSTOM_LABEL_MAX:
        raise ValueError(f"Use no máximo {CUSTOM_LABEL_MAX} caracteres para descrever o risco.")
    if _CONTACT.search(label):
        raise ValueError("A descrição do risco não pode ter telefone, e-mail ou link.")
    return label[0].upper() + label[1:]


def make_protocol(occurrence_id: int, when: datetime) -> str:
    return f"SU-{when.year}-{occurrence_id:06d}"


def can_view_private(user: User | None, occurrence: Occurrence) -> bool:
    if user is None:
        return False
    if user.role in (UserRole.AGENT, UserRole.MANAGER):
        return True
    return occurrence.author_id is not None and occurrence.author_id == user.id


@dataclass(frozen=True)
class NewOccurrence:
    type: OccurrenceType
    latitude: float
    longitude: float
    description: str
    is_anonymous: bool
    reporter_name: str | None
    reporter_contact: str | None
    observed_at: datetime | None = None
    client_submission_hash: str | None = None
    custom_type_label: str | None = None


def create_occurrence(
    db: Session,
    settings: Settings,
    data: NewOccurrence,
    photos: list[ProcessedPhoto],
    author: User | None,
) -> tuple[Occurrence, str, list[str]]:
    """Create the occurrence, its photos and first history entry (not committed).

    Returns (occurrence, clear tracking token, stored photo keys).
    The caller commits, and deletes the stored files if the commit fails.
    """
    token, token_hash = new_tracking_token()
    # A logged-in author is identified by the account; name/contact are only for visitors.
    name = contact = None
    if author is None and not data.is_anonymous:
        name = (data.reporter_name or "").strip() or None
        contact = (data.reporter_contact or "").strip() or None

    occurrence = Occurrence(
        type=data.type,
        location=make_point(data.latitude, data.longitude),
        description=data.description.strip(),
        custom_type_label=data.custom_type_label if data.type.is_other else None,
        status=OccurrenceStatus.OPEN,
        author_id=author.id if author else None,
        reporter_name=name,
        reporter_contact=contact,
        is_anonymous=data.is_anonymous,
        tracking_token_hash=token_hash,
        observed_at=data.observed_at,
        client_submission_hash=data.client_submission_hash,
    )
    db.add(occurrence)
    db.flush()
    occurrence.protocol = make_protocol(occurrence.id, datetime.now(ZoneInfo(settings.timezone)))
    # A spot that was already resolved and shows up again is a chronic point.
    occurrence.is_chronic = detect_chronic(db, occurrence)

    stored: list[str] = []
    for photo in photos:
        key = store_photo(settings.upload_dir, photo)
        stored.append(key)
        occurrence.photos.append(
            OccurrencePhoto(
                kind=PhotoKind.REPORT,
                storage_key=key,
                content_type=photo.content_type,
                width=photo.width,
                height=photo.height,
                size_bytes=len(photo.data),
                uploaded_by_id=author.id if author else None,
            )
        )
    occurrence.history.append(
        OccurrenceStatusHistory(
            from_status=None,
            to_status=OccurrenceStatus.OPEN,
            changed_by_id=author.id if author else None,
            note="Ocorrência registrada.",
        )
    )
    db.flush()
    return occurrence, token, stored


def clock_for(occurrence: Occurrence, deadline_days: int) -> ResponseClock:
    return response_clock(
        created_at=occurrence.created_at,
        notified_at=occurrence.notified_at,
        first_response_at=occurrence.first_response_at,
        deadline_days=deadline_days,
        now=datetime.now(UTC),
    )


def map_item(
    occurrence: Occurrence,
    settings: Settings,
    *,
    exact: bool,
    deadline_days: int | None = None,
) -> MapItem:
    if exact:
        lat, lon = occurrence.latitude, occurrence.longitude
    else:
        lat, lon = obfuscate_coordinate(
            occurrence.latitude,
            occurrence.longitude,
            cell_m=settings.privacy_grid_meters,
            ref_lat=settings.privacy_grid_ref_lat,
        )
    return MapItem(
        id=occurrence.id if exact else None,
        protocol=occurrence.protocol,
        type_code=occurrence.type.code,
        # The resident's free text stays off the public map.
        type_name=occurrence.type_label if exact else occurrence.type.name,
        status=occurrence.status,
        latitude=lat,
        longitude=lon,
        location_is_exact=exact,
        created_at=occurrence.created_at,
        confirmations=occurrence.confirmation_count or 0,
        **_clock_fields(occurrence, deadline_days),
    )


def _clock_fields(occurrence: Occurrence, deadline_days: int | None) -> dict:
    if deadline_days is None or occurrence.status not in QUEUE_STATUSES:
        return {}
    clock = clock_for(occurrence, deadline_days)
    return {
        "days_without_response": clock.days_without_response,
        "response_overdue": clock.overdue,
    }


def photo_out(photo: OccurrencePhoto) -> PhotoOut:
    return PhotoOut(
        id=photo.id,
        kind=photo.kind,
        width=photo.width,
        height=photo.height,
        url=f"/api/photos/{photo.id}",
    )


def history_out(occurrence: Occurrence) -> list[HistoryOut]:
    return [
        HistoryOut(from_status=h.from_status, to_status=h.to_status, created_at=h.created_at)
        for h in occurrence.history
    ]


def risk_out(row) -> RiskOut:
    """Build the risk breakdown from a row of the occurrence_risk view."""
    nearby = None
    if row.nearest_sensitive_name is not None:
        nearby = SensitiveNearby(
            name=row.nearest_sensitive_name,
            kind=row.nearest_sensitive_kind,
            distance_m=float(row.nearest_sensitive_distance_m),
        )
    return RiskOut(
        risk=float(row.risk),
        raw_risk=float(row.raw_risk),
        capped=row.capped,
        type_weight=float(row.type_weight),
        days_open=int(row.days_open),
        recurrence_count=row.recurrence_count,
        recurrence_factor=float(row.recurrence_factor),
        proximity_factor=float(row.proximity_factor),
        nearest_sensitive=nearby,
        confirmations=row.confirmations,
        recommendation=row.recommendation,
    )


def occurrence_detail(
    occurrence: Occurrence, viewer: User | None, risk: RiskOut | None = None
) -> OccurrenceDetail:
    """Private view (staff or author). Anonymous reports hide the reporter from staff."""
    reporter = None
    if not occurrence.is_anonymous:
        if occurrence.author is not None:
            reporter = ReporterOut(name=occurrence.author.name, contact=occurrence.author.email)
        elif occurrence.reporter_name or occurrence.reporter_contact:
            reporter = ReporterOut(
                name=occurrence.reporter_name, contact=occurrence.reporter_contact
            )
    return OccurrenceDetail(
        id=occurrence.id,
        protocol=occurrence.protocol,
        type=OccurrenceTypeOut.model_validate(occurrence.type),
        custom_type_label=occurrence.custom_type_label,
        status=occurrence.status,
        latitude=occurrence.latitude,
        longitude=occurrence.longitude,
        location_is_exact=True,
        description=occurrence.description,
        is_anonymous=occurrence.is_anonymous,
        reporter=reporter,
        is_chronic=occurrence.is_chronic,
        notified_at=occurrence.notified_at,
        first_response_at=occurrence.first_response_at,
        created_at=occurrence.created_at,
        updated_at=occurrence.updated_at,
        photos=[photo_out(p) for p in occurrence.photos],
        history=history_out(occurrence),
        confirmations=occurrence.confirmation_count or 0,
        risk=risk,
    )

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.deps import CurrentUser, DbSession, OptionalUser, StaffUser, is_staff
from app.domain.status import TransitionError
from app.models import (
    Notification,
    NotificationStatus,
    Occurrence,
    OccurrencePhoto,
    OccurrenceStatus,
    OccurrenceType,
)
from app.ratelimit import rate_limit
from app.schemas import (
    MapItemsOut,
    OccurrenceCreatedOut,
    OccurrenceDetail,
    ReclassifyIn,
    StartIn,
)
from app.security import hash_tracking_token, new_tracking_token
from app.services import messaging, notifications
from app.services.alerts import check_area_alert, queue_alert_notifications
from app.services.occurrences import (
    NewOccurrence,
    can_view_private,
    clean_custom_label,
    create_occurrence,
    in_bbox,
    map_item,
    occurrence_detail,
    parse_bbox,
    risk_out,
)
from app.services.photos import (
    InvalidPhotoError,
    ProcessedPhoto,
    resolve_photo_path,
    sanitize_image,
)
from app.services.privacy import grid_steps
from app.services.risk import deadline_days, load_settings, risk_row
from app.services.scope import apply_scope
from app.services.workflow import WorkflowError, holds_token, resolve, start_service

router = APIRouter(tags=["ocorrências"])

PUBLIC_LIMIT = 5000
TrackingTokenHeader = Annotated[str | None, Header(alias="X-Tracking-Token")]


def _bbox_or_422(raw: str | None):
    try:
        return parse_bbox(raw)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


def _envelope(bbox, pad_lon: float = 0.0, pad_lat: float = 0.0):
    min_lon, min_lat, max_lon, max_lat = bbox
    return cast(
        func.ST_MakeEnvelope(
            max(min_lon - pad_lon, -180),
            max(min_lat - pad_lat, -90),
            min(max_lon + pad_lon, 180),
            min(max_lat + pad_lat, 90),
            4326,
        ),
        Geography,
    )


def read_photos(photos: list[UploadFile], settings) -> list[ProcessedPhoto]:
    """Validate count and sanitize every photo in memory, so a bad one leaves no files."""
    photos = [p for p in photos if p.filename]
    if not photos:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Envie pelo menos uma foto.")
    if len(photos) > settings.max_photos_per_occurrence:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Envie no máximo {settings.max_photos_per_occurrence} fotos.",
        )
    processed = []
    for upload in photos:
        raw = upload.file.read(settings.max_photo_bytes + 1)
        try:
            processed.append(
                sanitize_image(
                    raw, max_side=settings.photo_max_side_px, max_bytes=settings.max_photo_bytes
                )
            )
        except InvalidPhotoError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return processed


def _replay(db, submission_hash: str) -> OccurrenceCreatedOut | None:
    """Same offline report sent again: return the original protocol with a fresh token.

    The first response was lost (that is why the phone re-sent), so its token is unknown to
    the reporter; rotating it keeps exactly one valid tracking link.
    """
    occurrence = db.scalar(
        select(Occurrence).where(Occurrence.client_submission_hash == submission_hash)
    )
    if occurrence is None:
        return None
    token, token_hash = new_tracking_token()
    occurrence.tracking_token_hash = token_hash
    db.commit()
    return OccurrenceCreatedOut(
        id=occurrence.id,
        protocol=occurrence.protocol,
        status=occurrence.status,
        department=occurrence.type.department,
        tracking_token=token,
        replayed=True,
    )


def _check_observed_at(observed_at: datetime | None, settings) -> datetime | None:
    if observed_at is None:
        return None
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    if observed_at > now + timedelta(minutes=10):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "A data do registro está no futuro."
        )
    if observed_at < now - timedelta(days=settings.offline_max_age_days):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Registro guardado há mais de {settings.offline_max_age_days} dias. Se o problema "
            "continua, faça um novo registro com uma foto atual.",
        )
    return observed_at


def _filtered(stmt, types: list[str] | None, statuses: list[OccurrenceStatus] | None):
    if types:
        stmt = stmt.join(Occurrence.type).where(OccurrenceType.code.in_(types))
    if statuses:
        stmt = stmt.where(Occurrence.status.in_(statuses))
    return stmt


@router.post(
    "/occurrences",
    response_model=OccurrenceCreatedOut,
    status_code=status.HTTP_201_CREATED,
    # Generous for a family or a school campaign on one connection, tight for a flood.
    dependencies=[Depends(rate_limit("report", 20, 3600))],
)
def create(
    db: DbSession,
    user: OptionalUser,
    background: BackgroundTasks,
    type_id: Annotated[int, Form()],
    latitude: Annotated[float, Form(ge=-90, le=90)],
    longitude: Annotated[float, Form(ge=-180, le=180)],
    photos: Annotated[list[UploadFile], File(description="De 1 a 3 fotos")],
    description: Annotated[str, Form(max_length=500)] = "",
    is_anonymous: Annotated[bool, Form()] = False,
    reporter_name: Annotated[str | None, Form(max_length=120)] = None,
    reporter_contact: Annotated[str | None, Form(max_length=254)] = None,
    client_submission_id: Annotated[str | None, Form(min_length=16, max_length=100)] = None,
    observed_at: Annotated[datetime | None, Form()] = None,
    custom_type_label: Annotated[str | None, Form(max_length=200)] = None,
) -> OccurrenceCreatedOut:
    """Register a report. Offline-queued reports send `client_submission_id` (a random id
    generated on the phone) so that re-sending after a lost response never duplicates it,
    and `observed_at`, when the resident actually saw it."""
    settings = get_settings()
    submission_hash = hash_tracking_token(client_submission_id) if client_submission_id else None
    if submission_hash and (replay := _replay(db, submission_hash)) is not None:
        return replay
    observed_at = _check_observed_at(observed_at, settings)

    occurrence_type = db.get(OccurrenceType, type_id)
    if occurrence_type is None or not occurrence_type.is_active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Tipo de ocorrência inválido.")
    label = None
    if occurrence_type.is_other:
        try:
            label = clean_custom_label(custom_type_label)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    area = settings.service_area()
    if area and not in_bbox(latitude, longitude, area):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"O ponto informado está fora de {settings.service_area_name}, "
            "área atendida pelo Sentinela Urbano.",
        )

    processed = read_photos(photos, settings)

    data = NewOccurrence(
        type=occurrence_type,
        latitude=latitude,
        longitude=longitude,
        description=description,
        is_anonymous=is_anonymous,
        reporter_name=reporter_name,
        reporter_contact=reporter_contact,
        observed_at=observed_at,
        client_submission_hash=submission_hash,
        custom_type_label=label,
    )
    stored: list[str] = []
    try:
        occurrence, token, stored = create_occurrence(db, settings, data, processed, user)
        queued = [notifications.queue_new_occurrence_email(db, occurrence)]
        values = load_settings(db)
        queued.append(
            messaging.queue_urgent_if_critical(
                db,
                settings,
                occurrence,
                risk_row(db, occurrence.id),
                float(values["messaging_immediate_risk"]),
            )
        )
        if (alert := check_area_alert(db, occurrence)) is not None:
            queued += queue_alert_notifications(db, settings, alert)
        db.flush()
        notification_ids = [n.id for n in queued if n is not None]
        db.commit()
    except IntegrityError:
        # The same offline report arrived twice at the same time: answer like a replay.
        db.rollback()
        for key in stored:
            resolve_photo_path(settings.upload_dir, key).unlink(missing_ok=True)
        if submission_hash and (replay := _replay(db, submission_hash)) is not None:
            return replay
        raise
    except Exception:
        db.rollback()
        for key in stored:
            resolve_photo_path(settings.upload_dir, key).unlink(missing_ok=True)
        raise

    for notification_id in notification_ids:
        background.add_task(notifications.deliver_by_id, notification_id)

    return OccurrenceCreatedOut(
        id=occurrence.id,
        protocol=occurrence.protocol,
        status=occurrence.status,
        department=occurrence_type.department,
        tracking_token=token,
    )


@router.get("/occurrences/public", response_model=MapItemsOut)
def public_map(
    db: DbSession,
    bbox: Annotated[str | None, Query(description="min_lon,min_lat,max_lon,max_lat")] = None,
    type: Annotated[list[str] | None, Query()] = None,
    status_: Annotated[list[OccurrenceStatus] | None, Query(alias="status")] = None,
) -> MapItemsOut:
    """Public map: approximate coordinates only, no photo, description or reporter."""
    settings = get_settings()
    box = _bbox_or_422(bbox)
    stmt = _filtered(select(Occurrence), type, status_)
    if box:
        # Query a box padded by one grid cell, then filter on the *snapped* coordinate.
        # Filtering on the exact point would let tiny bboxes reveal where it really is.
        lat_step, lon_step = grid_steps(settings.privacy_grid_meters, settings.privacy_grid_ref_lat)
        stmt = stmt.where(
            func.ST_Intersects(Occurrence.location, _envelope(box, lon_step, lat_step))
        )
    rows = (
        db.scalars(stmt.order_by(Occurrence.created_at.desc()).limit(PUBLIC_LIMIT + 1))
        .unique()
        .all()
    )
    truncated = len(rows) > PUBLIC_LIMIT
    deadline = deadline_days(db)
    items = [
        map_item(o, settings, exact=False, deadline_days=deadline) for o in rows[:PUBLIC_LIMIT]
    ]
    if box:
        items = [i for i in items if in_bbox(i.latitude, i.longitude, box)]
    return MapItemsOut(items=items, truncated=truncated)


@router.get("/occurrences", response_model=MapItemsOut)
def staff_list(
    db: DbSession,
    staff: StaffUser,
    bbox: Annotated[str | None, Query()] = None,
    type: Annotated[list[str] | None, Query()] = None,
    status_: Annotated[list[OccurrenceStatus] | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=PUBLIC_LIMIT)] = PUBLIC_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MapItemsOut:
    """Agents and managers: exact coordinates (the risk-ordered queue is /queue)."""
    settings = get_settings()
    deadline = deadline_days(db)
    box = _bbox_or_422(bbox)
    stmt = apply_scope(_filtered(select(Occurrence), type, status_), db, staff)
    if box:
        stmt = stmt.where(func.ST_Intersects(Occurrence.location, _envelope(box)))
    rows = (
        db.scalars(stmt.order_by(Occurrence.created_at.desc()).offset(offset).limit(limit + 1))
        .unique()
        .all()
    )
    return MapItemsOut(
        items=[map_item(o, settings, exact=True, deadline_days=deadline) for o in rows[:limit]],
        truncated=len(rows) > limit,
    )


@router.get("/occurrences/mine", response_model=MapItemsOut)
def my_occurrences(db: DbSession, user: CurrentUser) -> MapItemsOut:
    settings = get_settings()
    rows = (
        db.scalars(
            select(Occurrence)
            .where(Occurrence.author_id == user.id)
            .order_by(Occurrence.created_at.desc())
        )
        .unique()
        .all()
    )
    deadline = deadline_days(db)
    return MapItemsOut(
        items=[map_item(o, settings, exact=True, deadline_days=deadline) for o in rows]
    )


@router.get("/occurrences/{occurrence_id}", response_model=OccurrenceDetail)
def detail(occurrence_id: int, db: DbSession, user: OptionalUser) -> OccurrenceDetail:
    occurrence = db.get(Occurrence, occurrence_id)
    # 404 (not 403) for both cases, so ids cannot be probed.
    if occurrence is None or not can_view_private(user, occurrence):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ocorrência não encontrada.")
    # The risk breakdown is a work tool for the health team, not shown to residents.
    risk = None
    if is_staff(user) and (row := risk_row(db, occurrence.id)) is not None:
        risk = risk_out(row)
    return occurrence_detail(occurrence, user, risk)


def _staff_occurrence(db, occurrence_id: int) -> Occurrence:
    occurrence = db.get(Occurrence, occurrence_id)
    if occurrence is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ocorrência não encontrada.")
    return occurrence


@router.put("/occurrences/{occurrence_id}/type", response_model=OccurrenceDetail)
def reclassify(
    occurrence_id: int, data: ReclassifyIn, db: DbSession, staff: StaffUser
) -> OccurrenceDetail:
    """Agent or manager moves a report to the right type (mostly "Outro" ones).

    The risk follows the new type's weight at once, since it is computed at query time.
    The resident's description is dropped when the new type is not "Outro" any more.
    """
    occurrence = _staff_occurrence(db, occurrence_id)
    new_type = db.get(OccurrenceType, data.type_id)
    if new_type is None or not new_type.is_active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Tipo de ocorrência inválido.")
    if new_type.is_other and not occurrence.custom_type_label:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            'Escolha um tipo específico: só o morador descreve um risco como "Outro".',
        )
    occurrence.type = new_type
    if not new_type.is_other:
        occurrence.custom_type_label = None
    db.commit()
    db.refresh(occurrence)
    risk = risk_out(row) if (row := risk_row(db, occurrence.id)) is not None else None
    return occurrence_detail(occurrence, staff, risk)


@router.post("/occurrences/{occurrence_id}/start", response_model=OccurrenceDetail)
def start(occurrence_id: int, data: StartIn, db: DbSession, staff: StaffUser) -> OccurrenceDetail:
    """Agent takes the occurrence (aberta or contestada → em_atendimento)."""
    occurrence = _staff_occurrence(db, occurrence_id)
    try:
        start_service(occurrence, staff, data.note)
    except TransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    db.commit()
    return detail(occurrence_id, db, staff)


@router.post("/occurrences/{occurrence_id}/resolve", response_model=OccurrenceDetail)
def resolve_occurrence(
    occurrence_id: int,
    db: DbSession,
    staff: StaffUser,
    background: BackgroundTasks,
    photos: Annotated[list[UploadFile], File(description="Foto(s) do local após a ação")],
    note: Annotated[str, Form(max_length=500)] = "",
) -> OccurrenceDetail:
    """Close the occurrence. A photo of the spot after the action is mandatory."""
    settings = get_settings()
    occurrence = _staff_occurrence(db, occurrence_id)
    processed = read_photos(photos, settings)
    stored: list[str] = []
    try:
        stored = resolve(db, settings, occurrence, staff, note, processed)
        db.flush()
        pending = list(
            db.scalars(
                select(Notification.id).where(
                    Notification.occurrence_id == occurrence.id,
                    Notification.status == NotificationStatus.PENDING,
                    Notification.kind == "pedido_confirmacao",
                )
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        for key in stored:
            resolve_photo_path(settings.upload_dir, key).unlink(missing_ok=True)
        if isinstance(exc, TransitionError | WorkflowError):
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
        raise
    for notification_id in pending:
        background.add_task(notifications.deliver_by_id, notification_id)
    return detail(occurrence_id, db, staff)


@router.get("/photos/{photo_id}", response_class=FileResponse)
def photo(
    photo_id: int,
    db: DbSession,
    user: OptionalUser,
    tracking_token: TrackingTokenHeader = None,
) -> FileResponse:
    """Photos are never public: staff, the author, or whoever holds the tracking token."""
    settings = get_settings()
    item = db.get(OccurrencePhoto, photo_id)
    allowed = item is not None and (
        is_staff(user)
        or can_view_private(user, item.occurrence)
        or holds_token(tracking_token, item.occurrence)
    )
    if not allowed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foto não encontrada.")
    path = resolve_photo_path(settings.upload_dir, item.storage_key)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foto não encontrada.")
    return FileResponse(
        path, media_type=item.content_type, headers={"Cache-Control": "private, max-age=3600"}
    )

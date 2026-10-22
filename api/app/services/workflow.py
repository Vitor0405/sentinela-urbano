from datetime import UTC, datetime

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.status import QUEUE_STATUSES, Actor, check_transition
from app.models import (
    Notification,
    NotificationStatus,
    Occurrence,
    OccurrenceConfirmation,
    OccurrencePhoto,
    OccurrenceStatus,
    OccurrenceStatusHistory,
    PhotoKind,
    User,
    UserRole,
)
from app.security import new_tracking_token, tracking_token_matches
from app.services.photos import ProcessedPhoto, store_photo


class WorkflowError(ValueError):
    """Business rule violation, with a pt-BR message for the API response."""


def holds_token(token: str | None, occurrence: Occurrence) -> bool:
    """The original tracking link or the one e-mailed at closure both identify the reporter."""
    return tracking_token_matches(token, occurrence.tracking_token_hash) or (
        occurrence.feedback_token_hash is not None
        and tracking_token_matches(token, occurrence.feedback_token_hash)
    )


def _move(
    occurrence: Occurrence,
    target: OccurrenceStatus,
    actor: Actor,
    user: User | None,
    note: str,
) -> None:
    check_transition(occurrence.status, target, actor)
    occurrence.history.append(
        OccurrenceStatusHistory(
            from_status=occurrence.status,
            to_status=target,
            changed_by_id=user.id if user else None,
            note=note,
        )
    )
    occurrence.status = target
    # Any staff action counts as the prefecture's response (stops "dias sem resposta").
    if actor == Actor.STAFF and occurrence.first_response_at is None:
        occurrence.first_response_at = datetime.now(UTC)


def start_service(occurrence: Occurrence, staff: User, note: str = "") -> None:
    _move(
        occurrence,
        OccurrenceStatus.IN_PROGRESS,
        Actor.STAFF,
        staff,
        note.strip() or "Atendimento iniciado.",
    )


def resolve(
    db: Session,
    settings: Settings,
    occurrence: Occurrence,
    staff: User,
    note: str,
    photos: list[ProcessedPhoto],
) -> list[str]:
    """Close with mandatory photo(s); asks the reporter to confirm. Returns stored keys."""
    if not photos:
        raise WorkflowError("Para encerrar, anexe pelo menos uma foto do local após a ação.")
    _move(
        occurrence,
        OccurrenceStatus.RESOLVED_BY_AGENT,
        Actor.STAFF,
        staff,
        note.strip() or "Ocorrência resolvida pelo agente.",
    )
    stored = []
    for photo in photos:
        key = store_photo(settings.upload_dir, photo)
        stored.append(key)
        occurrence.photos.append(
            OccurrencePhoto(
                kind=PhotoKind.RESOLUTION,
                storage_key=key,
                content_type=photo.content_type,
                width=photo.width,
                height=photo.height,
                size_bytes=len(photo.data),
                uploaded_by_id=staff.id,
            )
        )
    queue_feedback_request(db, settings, occurrence)
    return stored


def _as_email(contact: str | None, settings: Settings) -> str | None:
    if not contact or "@" not in contact:
        return None
    try:
        return validate_email(
            contact,
            check_deliverability=False,
            test_environment=settings.allow_test_email_domains,
        ).normalized
    except EmailNotValidError:
        return None


def queue_feedback_request(
    db: Session, settings: Settings, occurrence: Occurrence
) -> Notification | None:
    """E-mail the single question to whoever reported, when we have an address for them."""
    if not settings.notifications_enabled:
        return None
    base = f"{settings.public_web_url.rstrip('/')}/acompanhar/{occurrence.protocol}"
    if occurrence.author is not None:
        recipient, link = occurrence.author.email, base  # logged-in authors open it signed in
    elif email := _as_email(occurrence.reporter_contact, settings):
        token, token_hash = new_tracking_token()
        occurrence.feedback_token_hash = token_hash
        recipient, link = email, f"{base}#t={token}"
    else:
        return None  # anonymous visitor: the question waits on their tracking page
    notification = Notification(
        occurrence=occurrence,
        kind="pedido_confirmacao",
        recipient=recipient,
        link=link,
        status=NotificationStatus.PENDING,
    )
    db.add(notification)
    return notification


def answer_feedback(occurrence: Occurrence, resolved: bool, user: User | None) -> None:
    """The reporter's single answer: yes → confirmada; no → contestada (back to the queue)."""
    if occurrence.status != OccurrenceStatus.RESOLVED_BY_AGENT:
        raise WorkflowError("Esta ocorrência não está aguardando a sua confirmação.")
    target = OccurrenceStatus.CONFIRMED if resolved else OccurrenceStatus.CONTESTED
    note = (
        "Morador confirmou que o problema foi resolvido."
        if resolved
        else "Morador informou que o problema NÃO foi resolvido. Voltou para a fila."
    )
    _move(occurrence, target, Actor.REPORTER, user, note)


def confirm_sighting(db: Session, occurrence: Occurrence, user: User) -> int:
    """'Eu também vi': one per resident, never on their own report. Returns the new count."""
    if user.role != UserRole.RESIDENT:
        raise WorkflowError("Somente moradores podem confirmar ocorrências.")
    if occurrence.author_id == user.id:
        raise WorkflowError("Você não pode confirmar uma ocorrência que você mesmo registrou.")
    if occurrence.status not in QUEUE_STATUSES:
        raise WorkflowError("Esta ocorrência já foi resolvida.")
    already = db.scalar(
        select(OccurrenceConfirmation.id).where(
            OccurrenceConfirmation.occurrence_id == occurrence.id,
            OccurrenceConfirmation.user_id == user.id,
        )
    )
    if already:
        raise WorkflowError("Você já confirmou esta ocorrência.")
    db.add(OccurrenceConfirmation(occurrence_id=occurrence.id, user_id=user.id))
    db.flush()
    db.expire(occurrence, ["confirmation_count"])  # the cached count is stale now
    return db.scalar(
        select(func.count(OccurrenceConfirmation.id)).where(
            OccurrenceConfirmation.occurrence_id == occurrence.id
        )
    )

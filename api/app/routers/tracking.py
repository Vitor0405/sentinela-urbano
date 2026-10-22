from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select

from app.config import get_settings
from app.deps import CurrentUser, DbSession, OptionalUser
from app.domain.status import TransitionError
from app.models import Notification, NotificationStatus, Occurrence, OccurrenceStatus, User
from app.ratelimit import rate_limit
from app.schemas import ConfirmationOut, FeedbackIn, TrackingOut
from app.services.occurrences import (
    can_view_private,
    clock_for,
    history_out,
    map_item,
    photo_out,
)
from app.services.ouvidoria_pdf import build_ouvidoria_pdf
from app.services.risk import deadline_days
from app.services.workflow import WorkflowError, answer_feedback, confirm_sighting, holds_token

router = APIRouter(prefix="/tracking", tags=["acompanhamento"])

TrackingTokenHeader = Annotated[str | None, Header(alias="X-Tracking-Token")]


def _by_protocol(db, protocol: str) -> Occurrence:
    occurrence = db.scalar(select(Occurrence).where(Occurrence.protocol == protocol.upper()))
    if occurrence is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Protocolo não encontrado.")
    return occurrence


def _is_owner(occurrence: Occurrence, user: User | None, token: str | None) -> bool:
    return holds_token(token, occurrence) or (user is not None and occurrence.author_id == user.id)


@router.get("/{protocol}", response_model=TrackingOut)
def track(
    protocol: str,
    db: DbSession,
    user: OptionalUser,
    tracking_token: TrackingTokenHeader = None,
) -> TrackingOut:
    """Anyone with the protocol sees the status timeline (backlog story 4).

    The private tracking token (or being the logged-in author) also unlocks the exact
    point, the description, the photos and the "foi resolvido?" question.
    """
    settings = get_settings()
    occurrence = _by_protocol(db, protocol)
    is_owner = _is_owner(occurrence, user, tracking_token)
    point = map_item(occurrence, settings, exact=is_owner or can_view_private(user, occurrence))
    clock = clock_for(occurrence, deadline_days(db))
    return TrackingOut(
        deadline_days=clock.deadline_days,
        days_without_response=clock.days_without_response,
        response_overdue=clock.overdue,
        days_left=clock.days_left,
        responded_after_days=clock.responded_after_days,
        can_request_ouvidoria=is_owner and clock.overdue,
        protocol=occurrence.protocol,
        type_name=point.type_name,
        department=occurrence.type.department,
        status=occurrence.status,
        created_at=occurrence.created_at,
        latitude=point.latitude,
        longitude=point.longitude,
        location_is_exact=point.location_is_exact,
        history=history_out(occurrence),
        is_owner=is_owner,
        can_answer=is_owner and occurrence.status == OccurrenceStatus.RESOLVED_BY_AGENT,
        confirmations=point.confirmations,
        description=occurrence.description if is_owner else None,
        photos=[photo_out(p) for p in occurrence.photos] if is_owner else [],
    )


@router.get("/{protocol}/ouvidoria.pdf", response_class=Response)
def ouvidoria_pdf(
    protocol: str,
    db: DbSession,
    user: OptionalUser,
    tracking_token: TrackingTokenHeader = None,
) -> Response:
    """Document for the municipal ombudsman, for the reporter, once the deadline is missed."""
    settings = get_settings()
    occurrence = _by_protocol(db, protocol)
    if not _is_owner(occurrence, user, tracking_token):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Protocolo não encontrado.")
    clock = clock_for(occurrence, deadline_days(db))
    if not clock.overdue:
        reason = (
            "A prefeitura já respondeu a esta ocorrência."
            if clock.days_without_response is None
            else f"O prazo de {clock.deadline_days} dias ainda não venceu "
            f"(faltam {clock.days_left} dia(s))."
        )
        raise HTTPException(status.HTTP_409_CONFLICT, reason)
    recipient = db.scalar(
        select(Notification.recipient)
        .where(
            Notification.occurrence_id == occurrence.id,
            Notification.kind == "nova_ocorrencia",
            Notification.status == NotificationStatus.SENT,
        )
        .order_by(Notification.sent_at)
        .limit(1)
    )
    pdf = build_ouvidoria_pdf(occurrence, clock, settings, recipient)
    filename = f"ouvidoria-{occurrence.protocol}.pdf"
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/{protocol}/feedback", response_model=TrackingOut)
def feedback(
    protocol: str,
    data: FeedbackIn,
    db: DbSession,
    user: OptionalUser,
    tracking_token: TrackingTokenHeader = None,
) -> TrackingOut:
    """The reporter's single answer to "o problema foi realmente resolvido?"."""
    occurrence = _by_protocol(db, protocol)
    if not _is_owner(occurrence, user, tracking_token):
        # Same 404 as an unknown protocol: nothing to learn by probing.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Protocolo não encontrado.")
    try:
        answer_feedback(occurrence, data.resolved, user)
    except (TransitionError, WorkflowError) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    db.commit()
    return track(protocol, db, user, tracking_token)


@router.post(
    "/{protocol}/confirmations",
    response_model=ConfirmationOut,
    dependencies=[Depends(rate_limit("confirm", 30, 3600))],
)
def confirm(protocol: str, db: DbSession, user: CurrentUser) -> ConfirmationOut:
    """'Eu também vi': requires an account so it counts once per person."""
    occurrence = _by_protocol(db, protocol)
    try:
        count = confirm_sighting(db, occurrence, user)
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    db.commit()
    return ConfirmationOut(confirmations=count)

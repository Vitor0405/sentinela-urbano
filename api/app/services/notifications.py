"""Outbox of notifications: e-mail (new occurrence to the prefecture, "foi resolvido?" to
the reporter, accumulation alerts to managers) and the messaging group (app.services.messaging).

The Notification row is created in the same transaction as the occurrence, so a crash or
an SMTP failure never loses it: `python -m app.cli retry-notifications` resends anything
pending or failed.
"""

import logging
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Notification, NotificationStatus, Occurrence
from app.services import messaging
from app.services.mailer import send_email
from app.services.photos import resolve_photo_path

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 10


def queue_new_occurrence_email(db: Session, occurrence: Occurrence) -> Notification | None:
    settings = get_settings()
    if not settings.notifications_enabled:
        return None
    recipient = occurrence.type.notification_email or settings.prefecture_email
    notification = Notification(
        occurrence=occurrence,
        channel="email",
        kind="nova_ocorrencia",
        recipient=recipient,
        status=NotificationStatus.PENDING,
    )
    db.add(notification)
    return notification


def build_new_occurrence_email(occurrence: Occurrence, recipient: str, settings: Settings):
    lat, lon = occurrence.latitude, occurrence.longitude
    msg = EmailMessage()
    msg["From"] = settings.mail_from
    msg["To"] = recipient
    msg["Subject"] = (
        f"[Sentinela Urbano] Nova ocorrência {occurrence.protocol}: {occurrence.type_label}"
    )
    osm_link = (
        f"https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f}#map=19/{lat:.6f}/{lon:.6f}"
    )
    panel_link = f"{settings.public_web_url.rstrip('/')}/ocorrencias/{occurrence.id}"
    body = f"""Uma nova ocorrência foi registrada no Sentinela Urbano.

Protocolo: {occurrence.protocol}
Tipo: {occurrence.type_label}
Setor responsável: {occurrence.type.department}
Data do registro: {occurrence.created_at.astimezone(ZoneInfo(settings.timezone)):%d/%m/%Y %H:%M}
Coordenadas: {lat:.6f}, {lon:.6f}
Descrição: {occurrence.description or "(sem descrição)"}

Ver no painel (requer login de agente ou gestor): {panel_link}
Ver no OpenStreetMap: {osm_link}

O registro está público no mapa com localização aproximada. A contagem de dias sem
resposta começa a partir deste aviso e para quando um agente ou gestor atuar na ocorrência.

Esta mensagem foi enviada automaticamente. Não responda a este e-mail.
"""
    msg.set_content(body)

    report_photos = [p for p in occurrence.photos if p.kind == "registro"]
    if report_photos:
        photo = report_photos[0]
        try:
            data = resolve_photo_path(settings.upload_dir, photo.storage_key).read_bytes()
            msg.add_attachment(
                data, maintype="image", subtype="jpeg", filename=f"{occurrence.protocol}.jpg"
            )
        except OSError:
            log.warning("photo %s missing for occurrence %s", photo.id, occurrence.id)
    return msg


def build_feedback_request_email(
    occurrence: Occurrence, notification: Notification, settings: Settings
) -> EmailMessage:
    """The single question to the reporter after the agent closes the occurrence."""
    msg = EmailMessage()
    msg["From"] = settings.mail_from
    msg["To"] = notification.recipient
    msg["Subject"] = f"[Sentinela Urbano] {occurrence.protocol}: o problema foi resolvido?"
    msg.set_content(
        f"""Olá!

O agente de saúde informou que resolveu a ocorrência que você registrou:

Protocolo: {occurrence.protocol}
Tipo: {occurrence.type.name}

O problema foi realmente resolvido? Responda com um toque (sim ou não):
{notification.link}

Se você disser que não, a ocorrência volta para a fila de atendimento.

Esta mensagem foi enviada automaticamente. Não responda a este e-mail.
"""
    )
    return msg


def build_area_alert_email(notification: Notification, settings: Settings) -> EmailMessage:
    alert = notification.area_alert
    msg = EmailMessage()
    msg["From"] = settings.mail_from
    msg["To"] = notification.recipient
    msg["Subject"] = (
        f"[Sentinela Urbano] Alerta de acúmulo: {alert.occurrence_count} registros de "
        f"{alert.type.name}"
    )
    msg.set_content(
        messaging.text_area_alert(alert, settings)
        + "\n\nVeja os alertas no painel: "
        + f"{settings.public_web_url.rstrip('/')}/painel"
        + "\n\nEsta mensagem foi enviada automaticamente. Não responda a este e-mail.\n"
    )
    return msg


def build_message(notification: Notification, settings: Settings) -> EmailMessage:
    occurrence = notification.occurrence
    if notification.kind == "pedido_confirmacao":
        return build_feedback_request_email(occurrence, notification, settings)
    if notification.kind == "alerta_acumulo":
        return build_area_alert_email(notification, settings)
    return build_new_occurrence_email(occurrence, notification.recipient, settings)


def _send(msg: EmailMessage, settings: Settings) -> None:
    send_email(msg, settings)


def _dispatch(notification: Notification, settings: Settings) -> None:
    if notification.channel == messaging.CHANNEL:
        messaging.send_message(notification.body or "", notification.recipient, settings)
    else:
        _send(build_message(notification, settings), settings)


def deliver(db: Session, notification: Notification) -> bool:
    settings = get_settings()
    occurrence = notification.occurrence
    notification.attempts += 1
    try:
        _dispatch(notification, settings)
    except (OSError, smtplib.SMTPException) as exc:
        notification.status = NotificationStatus.FAILED
        notification.last_error = f"{type(exc).__name__}: {exc}"[:2000]
        db.commit()
        log.warning("notification %s failed: %s", notification.id, exc)
        return False

    now = datetime.now(UTC)
    notification.status = NotificationStatus.SENT
    notification.sent_at = now
    notification.last_error = None
    # The link may carry a private token; it is only kept until the e-mail goes out.
    notification.link = None
    if (
        notification.kind == "nova_ocorrencia"
        and notification.channel == "email"
        and occurrence is not None
        and occurrence.notified_at is None
    ):
        occurrence.notified_at = now
    db.commit()
    return True


def deliver_by_id(notification_id: int) -> None:
    """Entry point for FastAPI background tasks: uses its own session."""
    from app.db import SessionLocal

    with SessionLocal() as db:
        notification = db.get(Notification, notification_id)
        if notification and notification.status != NotificationStatus.SENT:
            deliver(db, notification)


def retry_pending(db: Session) -> tuple[int, int]:
    """Resend pending/failed notifications. Returns (sent, failed)."""
    pending = db.scalars(
        select(Notification)
        .where(
            Notification.status.in_([NotificationStatus.PENDING, NotificationStatus.FAILED]),
            Notification.attempts < MAX_ATTEMPTS,
        )
        .order_by(Notification.id)
    ).all()
    sent = failed = 0
    for notification in pending:
        if deliver(db, notification):
            sent += 1
        else:
            failed += 1
    return sent, failed

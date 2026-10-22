"""Messaging group of the municipal department (Telegram), besides e-mail.

Rule from the original project, to keep the channel from turning into spam and being
ignored: an immediate message only for critical reports (initial risk at or above
`messaging_immediate_risk`); everything else goes into one daily digest
(`python -m app.cli send-digest`, schedulable).

Providers (MESSAGING_PROVIDER):
- `telegram`: Bot API sendMessage (TELEGRAM_BOT_TOKEN, MESSAGING_CHAT_ID);
- `email`: development stand-in that e-mails the text to MESSAGING_DEV_EMAIL (Mailpit);
- `none`: messaging off (default).

Messages are Notification rows (channel "mensagem") with the final text in `body`, so the
outbox retry resends exactly the same message.
"""

import json
import logging
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.status import QUEUE_STATUSES
from app.models import AreaAlert, Notification, NotificationStatus, Occurrence
from app.services.mailer import send_email

log = logging.getLogger(__name__)

CHANNEL = "mensagem"
DIGEST_MAX_LINES = 25
TELEGRAM_MAX_CHARS = 4000  # API limit is 4096


class MessagingError(OSError):
    """Delivery failure; an OSError so the outbox treats it like an SMTP failure."""


def enabled(settings: Settings) -> bool:
    return settings.notifications_enabled and settings.messaging_provider in ("telegram", "email")


def chat_for(settings: Settings, occurrence: Occurrence | None = None) -> str:
    if occurrence is not None and occurrence.type.messaging_chat_id:
        return occurrence.type.messaging_chat_id
    return settings.messaging_chat_id or "grupo-padrao"


# --- texts (plain text: no markup to escape, readable in any client) --------------------


def _local(dt: datetime, settings: Settings) -> str:
    return dt.astimezone(ZoneInfo(settings.timezone)).strftime("%d/%m/%Y %H:%M")


def _panel(settings: Settings, path: str) -> str:
    return f"{settings.public_web_url.rstrip('/')}{path}"


def text_urgent_occurrence(
    occurrence: Occurrence, raw_risk: float, reasons: list[str], settings: Settings
) -> str:
    lat, lon = occurrence.latitude, occurrence.longitude
    lines = [
        f"🔴 Ocorrência prioritária {occurrence.protocol}",
        f"{occurrence.type_label} · {occurrence.type.department}",
        f"Risco inicial: {raw_risk:.1f}" + (f" ({'; '.join(reasons)})" if reasons else ""),
        f"Registrada em {_local(occurrence.created_at, settings)}",
        f"Local: {lat:.6f}, {lon:.6f}",
        f"Painel: {_panel(settings, f'/ocorrencias/{occurrence.id}')}",
    ]
    return "\n".join(lines)[:TELEGRAM_MAX_CHARS]


def text_digest(occurrences: list[Occurrence], settings: Settings) -> str:
    counts = Counter(o.type.name for o in occurrences)
    summary = ", ".join(f"{name}: {n}" for name, n in counts.most_common())
    lines = [
        f"📋 Resumo do Sentinela Urbano: {len(occurrences)} nova(s) ocorrência(s)",
        summary,
        "",
    ]
    for o in occurrences[:DIGEST_MAX_LINES]:
        lines.append(
            f"• {o.protocol} · {o.type_label} · {_panel(settings, f'/ocorrencias/{o.id}')}"
        )
    if len(occurrences) > DIGEST_MAX_LINES:
        lines.append(f"… e mais {len(occurrences) - DIGEST_MAX_LINES}. Veja a fila no painel.")
    lines.append(f"Fila completa: {_panel(settings, '/fila')}")
    return "\n".join(lines)[:TELEGRAM_MAX_CHARS]


def text_area_alert(alert: AreaAlert, settings: Settings) -> str:
    lat, lon = alert.center_latitude, alert.center_longitude
    return "\n".join(
        [
            f"⚠️ Alerta de acúmulo: {alert.occurrence_count} registros de {alert.type.name}",
            f"Num raio de {alert.radius_m} m, entre {_local(alert.window_start, settings)} "
            f"e {_local(alert.window_end, settings)}.",
            f"Centro: {lat:.6f}, {lon:.6f}",
            f"Mapa: {_panel(settings, f'/?lat={lat:.5f}&lon={lon:.5f}&z=17')}",
        ]
    )


# --- queueing (outbox) ------------------------------------------------------------------


def queue_message(
    db: Session,
    settings: Settings,
    body: str,
    kind: str,
    chat_id: str,
    occurrence: Occurrence | None = None,
    alert: AreaAlert | None = None,
) -> Notification | None:
    if not enabled(settings):
        return None
    notification = Notification(
        occurrence=occurrence,
        area_alert=alert,
        channel=CHANNEL,
        kind=kind,
        recipient=chat_id,
        body=body,
        status=NotificationStatus.PENDING,
    )
    db.add(notification)
    return notification


def queue_urgent_if_critical(
    db: Session, settings: Settings, occurrence: Occurrence, risk_row, threshold: float
) -> Notification | None:
    """Immediate message for a critical report; otherwise it waits for the daily digest."""
    if not enabled(settings) or risk_row is None or float(risk_row.raw_risk) < threshold:
        return None
    reasons = []
    if risk_row.nearest_sensitive_name:
        reasons.append(
            f"a {float(risk_row.nearest_sensitive_distance_m):.0f} m de "
            f"{risk_row.nearest_sensitive_name}"
        )
    if risk_row.recurrence_count:
        reasons.append(f"{risk_row.recurrence_count} resolução(ões) anterior(es) no ponto")
    occurrence.messaged_at = datetime.now(UTC)
    return queue_message(
        db,
        settings,
        text_urgent_occurrence(occurrence, float(risk_row.raw_risk), reasons, settings),
        "nova_ocorrencia_urgente",
        chat_for(settings, occurrence),
        occurrence=occurrence,
    )


def queue_daily_digest(db: Session, settings: Settings) -> Notification | None:
    """One message with every active occurrence not yet sent to the group. Caller commits."""
    if not enabled(settings):
        return None
    pending = list(
        db.scalars(
            select(Occurrence)
            .where(Occurrence.messaged_at.is_(None), Occurrence.status.in_(QUEUE_STATUSES))
            .order_by(Occurrence.created_at)
        ).unique()
    )
    if not pending:
        return None
    now = datetime.now(UTC)
    for occurrence in pending:
        occurrence.messaged_at = now
    return queue_message(
        db, settings, text_digest(pending, settings), "resumo_diario", chat_for(settings)
    )


# --- delivery ---------------------------------------------------------------------------


def send_message(body: str, chat_id: str, settings: Settings) -> None:
    if settings.messaging_provider == "telegram":
        _send_telegram(body, chat_id, settings)
    elif settings.messaging_provider == "email":
        msg = EmailMessage()
        msg["From"] = settings.mail_from
        msg["To"] = settings.messaging_dev_email
        msg["Subject"] = f"[Grupo {chat_id}] {body.splitlines()[0]}"
        msg.set_content(body)
        send_email(msg, settings)
    else:
        raise MessagingError("Canal de mensagens desativado (MESSAGING_PROVIDER=none).")


def _send_telegram(body: str, chat_id: str, settings: Settings) -> None:
    if not settings.telegram_bot_token:
        raise MessagingError("TELEGRAM_BOT_TOKEN não configurado.")
    url = f"{settings.telegram_api_base.rstrip('/')}/bot{settings.telegram_bot_token}/sendMessage"
    payload = json.dumps(
        {"chat_id": chat_id, "text": body, "disable_web_page_preview": True}
    ).encode()
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            answer = json.load(response)
    except urllib.error.HTTPError as exc:
        # The token is part of the URL: never let it reach logs or the database.
        raise MessagingError(f"Telegram respondeu HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise MessagingError(f"Telegram inacessível: {type(exc).__name__}") from None
    if not answer.get("ok"):
        raise MessagingError(f"Telegram recusou: {answer.get('description', 'sem detalhe')}")

"""Accumulation alerts (backlog story 10).

When a new report brings the number of *active* reports of the same type within
`cluster_radius_m` over the last `cluster_window_days` to `cluster_min_count` or more, the
managers get one alert. While an alert for that type covers the spot within the window,
new reports there do not trigger another one.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.status import QUEUE_STATUSES
from app.models import AreaAlert, Notification, NotificationStatus, Occurrence, User, UserRole
from app.services import messaging
from app.services.risk import load_settings

ACTIVE = [s.value for s in QUEUE_STATUSES]

CLUSTER_SQL = text(
    """
    SELECT o.id, o.created_at
    FROM occurrences o, occurrences n
    WHERE n.id = :new_id
      AND o.type_id = n.type_id
      AND o.status::text = ANY(:active)
      AND o.created_at >= :since
      AND ST_DWithin(o.location, n.location, :radius)
    ORDER BY o.created_at
    """
)

ALREADY_ALERTED_SQL = text(
    """
    SELECT 1
    FROM area_alerts a, occurrences n
    WHERE n.id = :new_id
      AND a.type_id = n.type_id
      AND a.created_at >= :since
      AND ST_DWithin(a.center, n.location, :radius)
    LIMIT 1
    """
)

CENTER_SQL = text(
    """
    SELECT ST_AsText(ST_Centroid(ST_Collect(location::geometry)))
    FROM occurrences WHERE id = ANY(:ids)
    """
)


def check_area_alert(db: Session, occurrence: Occurrence) -> AreaAlert | None:
    """Create (not commit) an alert if `occurrence` completes a cluster. Needs a flush first."""
    # "Outro" groups unrelated things; three of them nearby are not the same risk.
    if occurrence.type.is_other:
        return None
    values = load_settings(db)
    radius = int(values["cluster_radius_m"])
    minimum = int(values["cluster_min_count"])
    window = timedelta(days=int(values["cluster_window_days"]))
    now = datetime.now(UTC)
    params = {"new_id": occurrence.id, "since": now - window, "radius": radius}

    rows = db.execute(CLUSTER_SQL, {**params, "active": ACTIVE}).all()
    if len(rows) < minimum:
        return None
    if db.execute(ALREADY_ALERTED_SQL, params).first():
        return None

    ids = [r.id for r in rows]
    center = db.scalar(CENTER_SQL, {"ids": ids})
    alert = AreaAlert(
        type_id=occurrence.type_id,
        center=f"SRID=4326;{center}",
        radius_m=radius,
        occurrence_count=len(ids),
        occurrence_ids=ids,
        window_start=min(r.created_at for r in rows),
        window_end=max(r.created_at for r in rows),
    )
    db.add(alert)
    db.flush()
    db.refresh(alert)
    return alert


def queue_alert_notifications(
    db: Session, settings: Settings, alert: AreaAlert
) -> list[Notification]:
    """E-mail every active manager and post to the messaging group."""
    if not settings.notifications_enabled:
        return []
    managers = db.scalars(
        select(User).where(User.role == UserRole.MANAGER, User.is_active.is_(True))
    ).all()
    queued = []
    for manager in managers:
        notification = Notification(
            area_alert=alert,
            channel="email",
            kind="alerta_acumulo",
            recipient=manager.email,
            status=NotificationStatus.PENDING,
        )
        db.add(notification)
        queued.append(notification)
    message = messaging.queue_message(
        db,
        settings,
        messaging.text_area_alert(alert, settings),
        "alerta_acumulo",
        messaging.chat_for(settings),
        alert=alert,
    )
    if message is not None:
        queued.append(message)
    return queued

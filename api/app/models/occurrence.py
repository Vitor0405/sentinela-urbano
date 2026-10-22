from datetime import datetime
from typing import Any

from geoalchemy2 import Geography, Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    cast,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from app.db import Base
from app.models.catalog import OccurrenceType
from app.models.enums import (
    NotificationStatus,
    OccurrenceStatus,
    PhotoKind,
    notification_status_enum,
    occurrence_status_enum,
    photo_kind_enum,
)
from app.models.user import User


class Occurrence(Base):
    __tablename__ = "occurrences"
    __table_args__ = (
        Index("ix_occurrences_location", "location", postgresql_using="gist"),
        Index("ix_occurrences_status", "status"),
        Index("ix_occurrences_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Human-facing number, e.g. SU-2026-000123. Filled right after the first flush.
    protocol: Mapped[str | None] = mapped_column(String(20), unique=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("occurrence_types.id"))
    # Exact point (SRID 4326). Only agents and managers ever see it; the public map
    # receives the grid-snapped coordinate from app.services.privacy.
    location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    latitude: Mapped[float] = column_property(func.ST_Y(cast(location, Geometry)))
    longitude: Mapped[float] = column_property(func.ST_X(cast(location, Geometry)))
    description: Mapped[str] = mapped_column(Text, default="")
    # Only for the "Outro" type: what the resident says the risk is (cleaned, ≤ 60 chars).
    # Never shown on the public map, which keeps the generic type name.
    custom_type_label: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[OccurrenceStatus] = mapped_column(
        occurrence_status_enum, default=OccurrenceStatus.OPEN
    )

    # Hybrid identity: a logged-in author, an identified visitor (name + contact only)
    # or nobody. `is_anonymous` hides the identity from agents and managers.
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reporter_name: Mapped[str | None] = mapped_column(String(120))
    reporter_contact: Mapped[str | None] = mapped_column(String(254))
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    # SHA-256 of the private tracking token handed to the reporter (never stored in clear).
    tracking_token_hash: Mapped[str] = mapped_column(String(64))
    # Second token, e-mailed to an identified visitor when the agent closes the occurrence,
    # so they can answer "foi resolvido?" without the original link. Same powers, hash only.
    feedback_token_hash: Mapped[str | None] = mapped_column(String(64))

    # True when, at creation, a resolved occurrence existed within chronic_radius_m.
    is_chronic: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # When the prefecture was e-mailed, and when an agent or manager first acted on it.
    # Together they drive the public "dias sem resposta" counter (phase 3).
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When it went out to the messaging group (immediately if critical, else in the digest).
    messaged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Offline reports (phase 4): when the resident saw it on the phone, and a hash of the
    # client-generated submission id that makes re-sending the same report idempotent.
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_submission_hash: Mapped[str | None] = mapped_column(String(64), unique=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    type: Mapped[OccurrenceType] = relationship(lazy="joined")
    author: Mapped[User | None] = relationship()
    photos: Mapped[list["OccurrencePhoto"]] = relationship(
        back_populates="occurrence",
        cascade="all, delete-orphan",
        order_by="OccurrencePhoto.id",
    )
    history: Mapped[list["OccurrenceStatusHistory"]] = relationship(
        back_populates="occurrence",
        cascade="all, delete-orphan",
        order_by="OccurrenceStatusHistory.id",
    )
    confirmations: Mapped[list["OccurrenceConfirmation"]] = relationship(
        back_populates="occurrence", cascade="all, delete-orphan"
    )

    @property
    def type_label(self) -> str:
        """Type name for the team and the author: "Outro risco: caixa de isopor"."""
        if self.custom_type_label:
            return f"{self.type.name}: {self.custom_type_label}"
        return self.type.name


class OccurrencePhoto(Base):
    __tablename__ = "occurrence_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurrence_id: Mapped[int] = mapped_column(
        ForeignKey("occurrences.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[PhotoKind] = mapped_column(photo_kind_enum, default=PhotoKind.REPORT)
    # Path relative to UPLOAD_DIR. The file is always a re-encoded JPEG without EXIF.
    storage_key: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(40), default="image/jpeg")
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    occurrence: Mapped[Occurrence] = relationship(back_populates="photos")


class OccurrenceStatusHistory(Base):
    __tablename__ = "occurrence_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurrence_id: Mapped[int] = mapped_column(
        ForeignKey("occurrences.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[OccurrenceStatus | None] = mapped_column(occurrence_status_enum)
    to_status: Mapped[OccurrenceStatus] = mapped_column(occurrence_status_enum)
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    occurrence: Mapped[Occurrence] = relationship(back_populates="history")


class OccurrenceConfirmation(Base):
    """'Eu também vi': another resident with an account vouches for the report.

    One per user and occurrence; the author cannot confirm their own report. Until there is
    at least one, the risk is capped at unconfirmed_risk_cap (false-report mitigation).
    """

    __tablename__ = "occurrence_confirmations"
    __table_args__ = (UniqueConstraint("occurrence_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    occurrence_id: Mapped[int] = mapped_column(
        ForeignKey("occurrences.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    occurrence: Mapped[Occurrence] = relationship(back_populates="confirmations")


# Count of "eu também vi", loaded with every occurrence (cheap, indexed subquery).
Occurrence.confirmation_count = column_property(
    select(func.count(OccurrenceConfirmation.id))
    .where(OccurrenceConfirmation.occurrence_id == Occurrence.id)
    .correlate_except(OccurrenceConfirmation)
    .scalar_subquery()
)


class Notification(Base):
    """Outbox of e-mails (prefecture and residents); failures stay here to be retried."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Null for messages not tied to one occurrence (daily digest, area alerts).
    occurrence_id: Mapped[int | None] = mapped_column(
        ForeignKey("occurrences.id", ondelete="CASCADE"), index=True
    )
    area_alert_id: Mapped[int | None] = mapped_column(
        ForeignKey("area_alerts.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[str] = mapped_column(String(20), default="email")  # email | mensagem
    kind: Mapped[str] = mapped_column(String(40), default="nova_ocorrencia")
    recipient: Mapped[str] = mapped_column(String(254))
    # Private link for the resident (may carry a token); cleared once the e-mail is sent.
    link: Mapped[str | None] = mapped_column(Text)
    # Prebuilt text for messaging-group notifications, so a retry resends exactly the same.
    body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[NotificationStatus] = mapped_column(
        notification_status_enum, default=NotificationStatus.PENDING
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    occurrence: Mapped[Occurrence | None] = relationship()
    area_alert: Mapped["AreaAlert | None"] = relationship()


class AreaAlert(Base):
    """Several reports of the same type piling up in one area (backlog story 10)."""

    __tablename__ = "area_alerts"
    __table_args__ = (Index("ix_area_alerts_center", "center", postgresql_using="gist"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("occurrence_types.id"))
    center: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    center_latitude: Mapped[float] = column_property(func.ST_Y(cast(center, Geometry)))
    center_longitude: Mapped[float] = column_property(func.ST_X(cast(center, Geometry)))
    radius_m: Mapped[int] = mapped_column(Integer)
    occurrence_count: Mapped[int] = mapped_column(Integer)
    occurrence_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    type: Mapped[OccurrenceType] = relationship(lazy="joined")

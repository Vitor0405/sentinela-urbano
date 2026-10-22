from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OccurrenceType(Base):
    """Risk type with its configurable weight in the risk index."""

    __tablename__ = "occurrence_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    weight: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    # Municipal department that handles this type (backlog story 3). Not to be confused
    # with `sectors`, the geographic polygons used for the LIRAa comparison.
    department: Mapped[str] = mapped_column(String(120))
    # Overrides PREFECTURE_EMAIL for this type when set.
    notification_email: Mapped[str | None] = mapped_column(String(254))
    # Direct Aedes breeding site vs. associated environmental risk factor (improvement 6).
    is_breeding_site: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Short pt-BR prevention advice shown to the resident after reporting (backlog story 14).
    prevention_tips: Mapped[str] = mapped_column(Text, default="", server_default="")
    # Optional messaging group for this type; falls back to MESSAGING_CHAT_ID.
    messaging_chat_id: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # The catch-all "Outro" type: the resident describes the risk in a few words
    # (`Occurrence.custom_type_label`) and the team reclassifies it later.
    is_other: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class RiskSetting(Base):
    """Configurable coefficients (risk formula, chronic radius, deadlines)."""

    __tablename__ = "risk_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    description: Mapped[str] = mapped_column(Text, default="")

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Sector(Base):
    """Area used to aggregate the index (and to compare it with the LIRAa of the same area).

    Indices per sector are always normalised by `population` (reporting bias: areas with
    more smartphones report more, which must not pull public resources towards them).
    Occurrences are assigned to sectors spatially at query time, never stored.
    """

    __tablename__ = "sectors"
    __table_args__ = (
        CheckConstraint("population > 0", name="population_positive"),
        Index("ix_sectors_geom", "geom", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    population: Mapped[int] = mapped_column(Integer)
    # Planar containment on lat/lon is exact enough for point-in-polygon.
    geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False)
    )
    # Where the polygon came from: a file name, or "ficticio (seed)" for demo data.
    source: Mapped[str] = mapped_column(String(200))
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    surveys: Mapped[list["LiraaSurvey"]] = relationship(
        back_populates="sector", cascade="all, delete-orphan"
    )


class LiraaSurvey(Base):
    """One LIRAa result (Levantamento Rápido de Índices para Aedes aegypti) for a sector."""

    __tablename__ = "liraa_surveys"
    __table_args__ = (UniqueConstraint("sector_id", "period"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sector_id: Mapped[int] = mapped_column(ForeignKey("sectors.id", ondelete="CASCADE"))
    # Label of the survey cycle as the municipality names it, e.g. "2026-1" or "out/2026".
    period: Mapped[str] = mapped_column(String(40))
    survey_date: Mapped[date] = mapped_column(Date)
    # Índice de Infestação Predial (%), and optionally the Breteau index.
    iip: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    ib: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sector: Mapped[Sector] = relationship(back_populates="surveys")

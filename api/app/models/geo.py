from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import BigInteger, DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SensitivePoint(Base):
    """Schools, day-care centres and health units imported from OpenStreetMap (Overpass).

    Filled only by `python -m app.cli import-sensitive-points`; never queried live.
    """

    __tablename__ = "sensitive_points"
    __table_args__ = (
        UniqueConstraint("osm_type", "osm_id"),
        Index("ix_sensitive_points_location", "location", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osm_type: Mapped[str] = mapped_column(String(10))  # node | way | relation
    osm_id: Mapped[int] = mapped_column(BigInteger)
    # amenity value (school, kindergarten, hospital, clinic, doctors) or "healthcare:<value>"
    kind: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(200))
    location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

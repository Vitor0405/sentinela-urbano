"""Read-only mapping of the `occurrence_risk` SQL view (created in migration 0002).

The risk is computed by PostgreSQL on every query and never stored, because it grows
with the days the occurrence stays open:

    risk = type_weight × days_open × recurrence_factor × proximity_factor

capped at `unconfirmed_risk_cap` while no other resident has confirmed ("eu também vi").
All coefficients come from `risk_settings`.

The view lives on its own MetaData so Alembic autogenerate never tries to create it as a
table.
"""

from sqlalchemy import Boolean, Column, Integer, MetaData, Numeric, String, Table

view_metadata = MetaData()

occurrence_risk = Table(
    "occurrence_risk",
    view_metadata,
    Column("occurrence_id", Integer, primary_key=True),
    Column("type_weight", Numeric),
    Column("days_open", Numeric),
    Column("recurrence_count", Integer),
    Column("recurrence_factor", Numeric),
    Column("nearest_sensitive_name", String),
    Column("nearest_sensitive_kind", String),
    Column("nearest_sensitive_distance_m", Numeric),
    Column("proximity_factor", Numeric),
    Column("confirmations", Integer),
    Column("raw_risk", Numeric),
    Column("risk", Numeric),
    Column("capped", Boolean),
    # 'nova_visita' | 'notificar_proprietario'
    Column("recommendation", String),
)

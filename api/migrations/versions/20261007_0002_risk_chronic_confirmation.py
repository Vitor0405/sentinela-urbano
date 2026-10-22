"""Phase 2: sensitive points, 'eu também vi', feedback token and the risk view.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMP = sa.DateTime(timezone=True)

# "Resolved" for recurrence and chronic purposes: closed by the agent (awaiting the
# resident) or confirmed by the resident. A contested closure does not count.
RESOLVED = "('resolvida_pelo_agente', 'confirmada')"

RISK_VIEW = f"""
CREATE VIEW occurrence_risk AS
WITH s AS (
    SELECT
        COALESCE(MAX(value) FILTER (WHERE key = 'min_days_open'), 1) AS min_days_open,
        COALESCE(MAX(value) FILTER (WHERE key = 'recurrence_increment'), 0.5)
            AS recurrence_increment,
        COALESCE(MAX(value) FILTER (WHERE key = 'recurrence_radius_m'), 30)
            AS recurrence_radius_m,
        COALESCE(MAX(value) FILTER (WHERE key = 'chronic_owner_notice_threshold'), 3)
            AS owner_notice_threshold,
        COALESCE(MAX(value) FILTER (WHERE key = 'sensitive_proximity_factor'), 1.5)
            AS sensitive_factor,
        COALESCE(MAX(value) FILTER (WHERE key = 'sensitive_radius_m'), 200)
            AS sensitive_radius_m,
        COALESCE(MAX(value) FILTER (WHERE key = 'unconfirmed_risk_cap'), 15) AS unconfirmed_cap
    FROM risk_settings
),
base AS (
    SELECT
        o.id AS occurrence_id,
        t.weight AS type_weight,
        GREATEST(
            s.min_days_open,
            FLOOR(EXTRACT(EPOCH FROM (now() - o.created_at)) / 86400)
        )::numeric AS days_open,
        (
            SELECT COUNT(*)
            FROM occurrences p
            WHERE p.id <> o.id
              AND p.status IN {RESOLVED}
              AND ST_DWithin(p.location, o.location, s.recurrence_radius_m)
        )::int AS recurrence_count,
        sp.name AS nearest_sensitive_name,
        sp.kind AS nearest_sensitive_kind,
        sp.distance_m AS nearest_sensitive_distance_m,
        (
            SELECT COUNT(*) FROM occurrence_confirmations c WHERE c.occurrence_id = o.id
        )::int AS confirmations,
        s.recurrence_increment,
        s.owner_notice_threshold,
        s.sensitive_factor,
        s.unconfirmed_cap
    FROM occurrences o
    JOIN occurrence_types t ON t.id = o.type_id
    CROSS JOIN s
    LEFT JOIN LATERAL (
        SELECT p.name, p.kind, ROUND(ST_Distance(p.location, o.location)::numeric, 1) AS distance_m
        FROM sensitive_points p
        WHERE ST_DWithin(p.location, o.location, s.sensitive_radius_m)
        ORDER BY ST_Distance(p.location, o.location)
        LIMIT 1
    ) sp ON true
),
factors AS (
    SELECT
        b.*,
        1 + b.recurrence_increment * b.recurrence_count AS recurrence_factor,
        CASE WHEN b.nearest_sensitive_distance_m IS NOT NULL THEN b.sensitive_factor ELSE 1 END
            AS proximity_factor
    FROM base b
),
raw AS (
    SELECT
        f.*,
        f.type_weight * f.days_open * f.recurrence_factor * f.proximity_factor AS raw_risk
    FROM factors f
)
SELECT
    occurrence_id,
    type_weight,
    days_open,
    recurrence_count,
    recurrence_factor,
    nearest_sensitive_name,
    nearest_sensitive_kind,
    nearest_sensitive_distance_m,
    proximity_factor,
    confirmations,
    ROUND(raw_risk, 2) AS raw_risk,
    ROUND(
        CASE WHEN confirmations = 0 THEN LEAST(raw_risk, unconfirmed_cap) ELSE raw_risk END, 2
    ) AS risk,
    (confirmations = 0 AND raw_risk > unconfirmed_cap) AS capped,
    CASE WHEN recurrence_count >= owner_notice_threshold
        THEN 'notificar_proprietario' ELSE 'nova_visita' END AS recommendation
FROM raw
"""


def upgrade() -> None:
    op.create_table(
        "sensitive_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("osm_type", sa.String(10), nullable=False),
        sa.Column("osm_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(60), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("imported_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sensitive_points"),
        sa.UniqueConstraint("osm_type", "osm_id", name="uq_sensitive_points_osm_type"),
    )
    op.create_index(
        "ix_sensitive_points_location", "sensitive_points", ["location"], postgresql_using="gist"
    )

    op.create_table(
        "occurrence_confirmations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("occurrence_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_occurrence_confirmations"),
        sa.UniqueConstraint(
            "occurrence_id", "user_id", name="uq_occurrence_confirmations_occurrence_id"
        ),
        sa.ForeignKeyConstraint(
            ["occurrence_id"],
            ["occurrences.id"],
            name="fk_occurrence_confirmations_occurrence_id_occurrences",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_occurrence_confirmations_user_id_users",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_occurrence_confirmations_occurrence_id",
        "occurrence_confirmations",
        ["occurrence_id"],
    )

    op.add_column("occurrences", sa.Column("feedback_token_hash", sa.String(64), nullable=True))
    op.add_column("notifications", sa.Column("link", sa.Text(), nullable=True))

    op.execute(RISK_VIEW)

    # Backfill: mark occurrences that already sit within the chronic radius of a resolved one.
    op.execute(
        f"""
        UPDATE occurrences o SET is_chronic = true
        WHERE EXISTS (
            SELECT 1 FROM occurrences p
            WHERE p.id <> o.id
              AND p.status IN {RESOLVED}
              AND p.created_at < o.created_at
              AND ST_DWithin(
                  p.location, o.location,
                  COALESCE(
                      (SELECT value FROM risk_settings WHERE key = 'chronic_radius_m'), 30
                  )
              )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS occurrence_risk")
    op.drop_column("notifications", "link")
    op.drop_column("occurrences", "feedback_token_hash")
    op.drop_table("occurrence_confirmations")
    op.drop_table("sensitive_points")

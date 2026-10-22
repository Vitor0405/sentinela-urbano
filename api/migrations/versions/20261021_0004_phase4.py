"""Phase 4: offline idempotency, messaging, area alerts, prevention tips and agent scope.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMP = sa.DateTime(timezone=True)

NEW_SETTINGS = [
    ("cluster_radius_m", 150, "Raio, em metros, do alerta de acúmulo de registros do mesmo tipo."),
    (
        "cluster_min_count",
        3,
        "Quantidade de ocorrências ativas do mesmo tipo que dispara o alerta.",
    ),
    ("cluster_window_days", 7, "Período, em dias, considerado no alerta de acúmulo."),
    (
        "messaging_immediate_risk",
        7.5,
        "Risco inicial a partir do qual o grupo de mensagens é avisado na hora (o resto vai no resumo diário).",
    ),
    ("route_max_stops", 12, "Número máximo de paradas na rota sugerida ao agente."),
]


def upgrade() -> None:
    # --- occurrences: offline submissions and messaging -----------------------------------
    op.add_column("occurrences", sa.Column("observed_at", TIMESTAMP, nullable=True))
    op.add_column("occurrences", sa.Column("messaged_at", TIMESTAMP, nullable=True))
    op.add_column("occurrences", sa.Column("client_submission_hash", sa.String(64), nullable=True))
    op.create_unique_constraint(
        "uq_occurrences_client_submission_hash", "occurrences", ["client_submission_hash"]
    )
    # Occurrences that existed before the messaging channel must not flood the first digest.
    op.execute("UPDATE occurrences SET messaged_at = created_at")

    # --- occurrence types: prevention text and messaging group ----------------------------
    op.add_column(
        "occurrence_types",
        sa.Column("prevention_tips", sa.Text(), server_default="", nullable=False),
    )
    op.add_column("occurrence_types", sa.Column("messaging_chat_id", sa.String(64), nullable=True))

    # --- area alerts ----------------------------------------------------------------------
    op.create_table(
        "area_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column(
            "center",
            geoalchemy2.Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("radius_m", sa.Integer(), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("occurrence_ids", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("window_start", TIMESTAMP, nullable=False),
        sa.Column("window_end", TIMESTAMP, nullable=False),
        sa.Column("created_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_area_alerts"),
        sa.ForeignKeyConstraint(
            ["type_id"], ["occurrence_types.id"], name="fk_area_alerts_type_id_occurrence_types"
        ),
    )
    op.create_index("ix_area_alerts_center", "area_alerts", ["center"], postgresql_using="gist")

    # --- notifications: not always tied to one occurrence ---------------------------------
    op.alter_column("notifications", "occurrence_id", nullable=True)
    op.add_column("notifications", sa.Column("area_alert_id", sa.Integer(), nullable=True))
    op.add_column("notifications", sa.Column("body", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_notifications_area_alert_id_area_alerts",
        "notifications",
        "area_alerts",
        ["area_alert_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_notifications_area_alert_id", "notifications", ["area_alert_id"])

    # --- agent scope ----------------------------------------------------------------------
    op.create_table(
        "agent_sectors",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sector_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "sector_id", name="pk_agent_sectors"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_agent_sectors_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["sector_id"],
            ["sectors.id"],
            name="fk_agent_sectors_sector_id_sectors",
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "agent_types",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "type_id", name="pk_agent_types"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_agent_types_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["type_id"],
            ["occurrence_types.id"],
            name="fk_agent_types_type_id_occurrence_types",
            ondelete="CASCADE",
        ),
    )

    # --- coefficients ---------------------------------------------------------------------
    for key, value, description in NEW_SETTINGS:
        op.execute(
            sa.text(
                "INSERT INTO risk_settings (key, value, description) VALUES (:k, :v, :d) "
                "ON CONFLICT (key) DO NOTHING"
            ).bindparams(k=key, v=value, d=description)
        )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM risk_settings WHERE key = ANY(:keys)").bindparams(
            keys=[k for k, _, _ in NEW_SETTINGS]
        )
    )
    op.drop_table("agent_types")
    op.drop_table("agent_sectors")
    op.drop_index("ix_notifications_area_alert_id", table_name="notifications")
    op.drop_constraint(
        "fk_notifications_area_alert_id_area_alerts", "notifications", type_="foreignkey"
    )
    op.drop_column("notifications", "body")
    op.drop_column("notifications", "area_alert_id")
    op.execute("DELETE FROM notifications WHERE occurrence_id IS NULL")
    op.alter_column("notifications", "occurrence_id", nullable=False)
    op.drop_table("area_alerts")
    op.drop_column("occurrence_types", "messaging_chat_id")
    op.drop_column("occurrence_types", "prevention_tips")
    op.drop_constraint("uq_occurrences_client_submission_hash", "occurrences", type_="unique")
    op.drop_column("occurrences", "client_submission_hash")
    op.drop_column("occurrences", "messaged_at")
    op.drop_column("occurrences", "observed_at")

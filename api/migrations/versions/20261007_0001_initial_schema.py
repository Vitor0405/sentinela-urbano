"""Initial schema: users, types, risk settings, occurrences, photos, history, notifications.

Revision ID: 0001
Revises:
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = postgresql.ENUM("morador", "agente", "gestor", name="user_role", create_type=False)
occurrence_status = postgresql.ENUM(
    "aberta",
    "em_atendimento",
    "resolvida_pelo_agente",
    "confirmada",
    "contestada",
    name="occurrence_status",
    create_type=False,
)
photo_kind = postgresql.ENUM("registro", "resolucao", name="photo_kind", create_type=False)
notification_status = postgresql.ENUM(
    "pendente", "enviada", "falhou", name="notification_status", create_type=False
)

TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    bind = op.get_bind()
    for enum in (user_role, occurrence_status, photo_kind, notification_status):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("terms_version", sa.String(20), nullable=False),
        sa.Column("terms_accepted_at", TIMESTAMP, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "occurrence_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("weight", sa.Numeric(6, 2), nullable=False),
        sa.Column("department", sa.String(120), nullable=False),
        sa.Column("notification_email", sa.String(254), nullable=True),
        sa.Column("is_breeding_site", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_occurrence_types"),
        sa.UniqueConstraint("code", name="uq_occurrence_types_code"),
        sa.CheckConstraint("weight > 0", name="weight_positive"),
    )

    op.create_table(
        "risk_settings",
        sa.Column("key", sa.String(60), nullable=False),
        sa.Column("value", sa.Numeric(12, 3), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_risk_settings"),
    )

    op.create_table(
        "occurrences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("protocol", sa.String(20), nullable=True),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", occurrence_status, nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("reporter_name", sa.String(120), nullable=True),
        sa.Column("reporter_contact", sa.String(254), nullable=True),
        sa.Column("is_anonymous", sa.Boolean(), nullable=False),
        sa.Column("tracking_token_hash", sa.String(64), nullable=False),
        sa.Column("is_chronic", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("notified_at", TIMESTAMP, nullable=True),
        sa.Column("first_response_at", TIMESTAMP, nullable=True),
        sa.Column("created_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_occurrences"),
        sa.UniqueConstraint("protocol", name="uq_occurrences_protocol"),
        sa.ForeignKeyConstraint(
            ["type_id"], ["occurrence_types.id"], name="fk_occurrences_type_id_occurrence_types"
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name="fk_occurrences_author_id_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_occurrences_location", "occurrences", ["location"], postgresql_using="gist")
    op.create_index("ix_occurrences_status", "occurrences", ["status"])
    op.create_index("ix_occurrences_created_at", "occurrences", ["created_at"])

    op.create_table(
        "occurrence_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("occurrence_id", sa.Integer(), nullable=False),
        sa.Column("kind", photo_kind, nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(40), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_occurrence_photos"),
        sa.ForeignKeyConstraint(
            ["occurrence_id"],
            ["occurrences.id"],
            name="fk_occurrence_photos_occurrence_id_occurrences",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"],
            ["users.id"],
            name="fk_occurrence_photos_uploaded_by_id_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_occurrence_photos_occurrence_id", "occurrence_photos", ["occurrence_id"])

    op.create_table(
        "occurrence_status_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("occurrence_id", sa.Integer(), nullable=False),
        sa.Column("from_status", occurrence_status, nullable=True),
        sa.Column("to_status", occurrence_status, nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_occurrence_status_history"),
        sa.ForeignKeyConstraint(
            ["occurrence_id"],
            ["occurrences.id"],
            name="fk_occurrence_status_history_occurrence_id_occurrences",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"],
            ["users.id"],
            name="fk_occurrence_status_history_changed_by_id_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_occurrence_status_history_occurrence_id",
        "occurrence_status_history",
        ["occurrence_id"],
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("occurrence_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("recipient", sa.String(254), nullable=False),
        sa.Column("status", notification_status, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", TIMESTAMP, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
        sa.ForeignKeyConstraint(
            ["occurrence_id"],
            ["occurrences.id"],
            name="fk_notifications_occurrence_id_occurrences",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_notifications_occurrence_id", "notifications", ["occurrence_id"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("occurrence_status_history")
    op.drop_table("occurrence_photos")
    op.drop_table("occurrences")
    op.drop_table("risk_settings")
    op.drop_table("occurrence_types")
    op.drop_table("users")
    bind = op.get_bind()
    for enum in (notification_status, photo_kind, occurrence_status, user_role):
        enum.drop(bind, checkfirst=True)

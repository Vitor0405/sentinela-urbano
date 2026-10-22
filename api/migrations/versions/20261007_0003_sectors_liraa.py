"""Phase 3: sectors (with population) and LIRAa surveys.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "sectors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("population", sa.Integer(), nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("imported_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sectors"),
        sa.UniqueConstraint("code", name="uq_sectors_code"),
        sa.CheckConstraint("population > 0", name="ck_sectors_population_positive"),
    )
    op.create_index("ix_sectors_geom", "sectors", ["geom"], postgresql_using="gist")

    op.create_table(
        "liraa_surveys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sector_id", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(40), nullable=False),
        sa.Column("survey_date", sa.Date(), nullable=False),
        sa.Column("iip", sa.Numeric(6, 2), nullable=False),
        sa.Column("ib", sa.Numeric(6, 2), nullable=True),
        sa.Column("imported_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_liraa_surveys"),
        sa.UniqueConstraint("sector_id", "period", name="uq_liraa_surveys_sector_id"),
        sa.ForeignKeyConstraint(
            ["sector_id"],
            ["sectors.id"],
            name="fk_liraa_surveys_sector_id_sectors",
            ondelete="CASCADE",
        ),
    )

    # New coefficient; the seed also inserts it, this keeps non-dev databases complete.
    op.execute(
        """
        INSERT INTO risk_settings (key, value, description) VALUES (
            'liraa_window_days', 60,
            'Janela, em dias antes da data do LIRAa, das ocorrências comparadas com o levantamento.'
        ) ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM risk_settings WHERE key = 'liraa_window_days'")
    op.drop_table("liraa_surveys")
    op.drop_table("sectors")

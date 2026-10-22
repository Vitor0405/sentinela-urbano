"""Risk type "Outro": the resident describes a risk that is not on the list.

`occurrence_types.is_other` marks the catch-all type (inserted by the seed);
`occurrences.custom_type_label` keeps the resident's short description of it.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "occurrence_types",
        sa.Column("is_other", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("occurrences", sa.Column("custom_type_label", sa.String(60), nullable=True))


def downgrade() -> None:
    op.drop_column("occurrences", "custom_type_label")
    op.drop_column("occurrence_types", "is_other")

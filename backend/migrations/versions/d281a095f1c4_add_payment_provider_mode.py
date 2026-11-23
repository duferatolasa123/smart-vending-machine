"""add payment provider mode

Revision ID: d281a095f1c4
Revises: 8115dff6813d
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d281a095f1c4"
down_revision: Union[str, Sequence[str], None] = "8115dff6813d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(
            sa.Column(
                "provider_mode",
                sa.String(length=10),
                nullable=False,
                server_default="test",
            )
        )
        batch_op.create_check_constraint(
            "ck_payments_provider_mode",
            "provider_mode IN ('test', 'live')",
        )
        batch_op.alter_column("provider_mode", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_constraint(
            "ck_payments_provider_mode",
            type_="check",
        )
        batch_op.drop_column("provider_mode")

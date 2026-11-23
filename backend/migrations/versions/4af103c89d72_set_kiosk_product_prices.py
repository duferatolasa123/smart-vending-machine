"""set the six kiosk product prices

Revision ID: 4af103c89d72
Revises: d281a095f1c4
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "4af103c89d72"
down_revision: Union[str, Sequence[str], None] = "d281a095f1c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    price_rules = (
        ("60.00", "lower(name) LIKE '%water%' AND (lower(name) LIKE '%1 l%' OR lower(name) LIKE '%1l%' OR lower(trim(name)) IN ('water', 'bottled water'))"),
        ("80.00", "lower(name) LIKE '%mirinda%'"),
        ("80.00", "lower(name) LIKE '%coca%cola%' OR lower(trim(name)) = 'coke'"),
        ("40.00", "lower(name) LIKE '%chip%'"),
        ("60.00", "lower(name) LIKE '%chocolate%'"),
        ("20.00", "lower(name) LIKE '%cappuccino%' OR lower(name) LIKE '%cappucino%'"),
    )
    for price, predicate in price_rules:
        op.execute(
            sa.text(f"UPDATE products SET price = :price WHERE {predicate}").bindparams(
                price=price
            )
        )


def downgrade() -> None:
    # Original prices are not stored, so restoring them would be guesswork.
    pass

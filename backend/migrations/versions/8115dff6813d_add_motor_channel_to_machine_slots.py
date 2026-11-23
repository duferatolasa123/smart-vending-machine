
"""add motor channel to machine slots

Revision ID: 8115dff6813d
Revises: bb67571cb73a
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Alembic revision identifiers
revision: str = "8115dff6813d"

down_revision: Union[str, Sequence[str], None] = "bb67571cb73a"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add nullable motor channel.
    # Existing machine slots will receive NULL.
    op.add_column(
        "machine_slots",
        sa.Column(
            "motor_channel",
            sa.Integer(),
            nullable=True,
        ),
    )

    # Prevent duplicate motor assignments
    # within the same vending machine.
    op.create_index(
        "uq_machine_slots_machine_motor_channel",
        "machine_slots",
        ["machine_id", "motor_channel"],
        unique=True,
    )

    # Enforce motor channel range during INSERT.
    op.execute("""
        CREATE TRIGGER trg_machine_slots_motor_channel_insert
        BEFORE INSERT ON machine_slots
        FOR EACH ROW
        WHEN NEW.motor_channel IS NOT NULL
             AND (
                 NEW.motor_channel < 1
                 OR NEW.motor_channel > 6
             )
        BEGIN
            SELECT RAISE(
                ABORT,
                'motor_channel must be between 1 and 6'
            );
        END;
    """)

    # Enforce motor channel range during UPDATE.
    op.execute("""
        CREATE TRIGGER trg_machine_slots_motor_channel_update
        BEFORE UPDATE OF motor_channel ON machine_slots
        FOR EACH ROW
        WHEN NEW.motor_channel IS NOT NULL
             AND (
                 NEW.motor_channel < 1
                 OR NEW.motor_channel > 6
             )
        BEGIN
            SELECT RAISE(
                ABORT,
                'motor_channel must be between 1 and 6'
            );
        END;
    """)


def downgrade() -> None:
    # Remove validation triggers.
    op.execute("""
        DROP TRIGGER IF EXISTS
        trg_machine_slots_motor_channel_insert;
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS
        trg_machine_slots_motor_channel_update;
    """)

    # Remove unique index.
    op.drop_index(
        "uq_machine_slots_machine_motor_channel",
        table_name="machine_slots",
    )

    # Remove motor channel column.
    op.drop_column(
        "machine_slots",
        "motor_channel",
    )

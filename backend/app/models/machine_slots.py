
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.machines import Machine
    from app.models.products import Product


class MachineSlot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "machine_slots"

    __table_args__ = (
        # Preserve original uniqueness rules.
        UniqueConstraint(
            "machine_id",
            "slot_code",
            name="uq_machine_slot_code",
        ),
        UniqueConstraint(
            "machine_id",
            "slot_number",
            name="uq_machine_slot_number",
        ),

        # Each motor channel can be assigned to one slot
        # per vending machine.
        Index(
            "uq_machine_slots_machine_motor_channel",
            "machine_id",
            "motor_channel",
            unique=True,
        ),

        CheckConstraint(
            "slot_number > 0",
            name="ck_machine_slot_number_positive",
        ),
        CheckConstraint(
            "capacity > 0",
            name="ck_machine_slot_capacity_positive",
        ),
        CheckConstraint(
            "motor_channel IS NULL OR "
            "(motor_channel >= 1 AND motor_channel <= 6)",
            name="ck_machine_slots_motor_channel",
        ),
    )

    machine_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    slot_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    slot_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    motor_channel: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    machine: Mapped["Machine"] = relationship(
        "Machine",
        back_populates="slots",
    )

    product: Mapped["Product | None"] = relationship(
        "Product",
    )

    def __repr__(self) -> str:
        return (
            f"<MachineSlot("
            f"slot_code={self.slot_code!r}, "
            f"slot_number={self.slot_number}, "
            f"motor_channel={self.motor_channel})>"
        )

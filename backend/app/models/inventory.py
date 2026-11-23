
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.machine_slots import MachineSlot


class Inventory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "inventory"

    __table_args__ = (
        UniqueConstraint(
            "machine_slot_id",
            name="uq_inventory_machine_slot",
        ),
        CheckConstraint(
            "quantity >= 0",
            name="ck_inventory_quantity_nonnegative",
        ),
        CheckConstraint(
            "reserved_quantity >= 0",
            name="ck_inventory_reserved_nonnegative",
        ),
        CheckConstraint(
            "reserved_quantity <= quantity",
            name="ck_inventory_reserved_lte_quantity",
        ),
    )

    machine_slot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("machine_slots.id", ondelete="CASCADE"),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    reserved_quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    slot: Mapped["MachineSlot"] = relationship(
        "MachineSlot",
    )

    @property
    def available_quantity(self) -> int:
        return self.quantity - self.reserved_quantity

    def __repr__(self) -> str:
        return (
            f"<Inventory("
            f"machine_slot_id={self.machine_slot_id}, "
            f"quantity={self.quantity}, "
            f"reserved_quantity={self.reserved_quantity})>"
        )

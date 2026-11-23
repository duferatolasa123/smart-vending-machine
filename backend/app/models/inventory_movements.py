
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.admins import Admin
    from app.models.inventory import Inventory


class InventoryMovement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "inventory_movements"

    __table_args__ = (
        CheckConstraint(
            "quantity_changed != 0",
            name="ck_inventory_movement_quantity_nonzero",
        ),
        CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name="ck_inventory_movement_unit_cost_nonnegative",
        ),
    )

    inventory_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inventory.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    movement_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    quantity_changed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    performed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admins.id", ondelete="SET NULL"),
        nullable=True,
    )

    inventory: Mapped["Inventory"] = relationship(
        "Inventory",
    )

    performed_by_admin: Mapped["Admin | None"] = relationship(
        "Admin",
    )

    def __repr__(self) -> str:
        return (
            f"<InventoryMovement("
            f"type={self.movement_type!r}, "
            f"quantity_changed={self.quantity_changed})>"
        )

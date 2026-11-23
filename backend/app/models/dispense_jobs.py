
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.machines import Machine
    from app.models.machine_slots import MachineSlot
    from app.models.order_items import OrderItem
    from app.models.orders import Order


class DispenseJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dispense_jobs"

    __table_args__ = (
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_dispense_jobs_attempt_count_nonnegative",
        ),
        UniqueConstraint(
            "order_item_id",
            name="uq_dispense_jobs_order_item",
        ),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    order_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("order_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    machine_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("machines.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    machine_slot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("machine_slots.id", ondelete="RESTRICT"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="QUEUED",
        nullable=False,
        index=True,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    command_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    order: Mapped["Order"] = relationship("Order")

    order_item: Mapped["OrderItem"] = relationship("OrderItem")

    machine: Mapped["Machine"] = relationship("Machine")

    machine_slot: Mapped["MachineSlot"] = relationship(
        "MachineSlot",
    )

    def __repr__(self) -> str:
        return (
            f"<DispenseJob("
            f"command_id={self.command_id!r}, "
            f"status={self.status!r})>"
        )

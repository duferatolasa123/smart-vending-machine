
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.machine_slots import MachineSlot

class Machine(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "machines"

    __table_args__ = (
        CheckConstraint(
            "status IN ('offline', 'online', 'maintenance', 'error')",
            name="ck_machines_status_valid",
        ),
    )

    machine_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    location_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    serial_number: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="offline",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    firmware_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    slots: Mapped[list["MachineSlot"]] = relationship(
        "MachineSlot",
        back_populates="machine",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return (
            f"<Machine("
            f"machine_code={self.machine_code!r}, "
            f"name={self.name!r}, "
            f"status={self.status!r})>"
        )

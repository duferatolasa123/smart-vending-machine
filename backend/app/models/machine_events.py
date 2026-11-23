
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.machines import Machine


class MachineEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "machine_events"

    __table_args__ = (
        CheckConstraint(
            "severity IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')",
            name="ck_machine_events_severity_valid",
        ),
    )

    machine_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("machines.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        default="INFO",
        nullable=False,
        index=True,
    )

    event_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    event_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    machine: Mapped["Machine"] = relationship("Machine")

    def __repr__(self) -> str:
        return (
            f"<MachineEvent("
            f"event_type={self.event_type!r}, "
            f"severity={self.severity!r}, "
            f"message={self.message!r})>"
        )

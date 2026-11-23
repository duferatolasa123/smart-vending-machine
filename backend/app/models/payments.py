
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.orders import Order


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_payments_amount_positive",
        ),
        CheckConstraint(
            "provider_mode IN ('test', 'live')",
            name="ck_payments_provider_mode",
        ),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(30),
        default="TELEBIRR",
        nullable=False,
    )

    payment_method: Mapped[str] = mapped_column(
        String(50),
        default="H5_C2B",
        nullable=False,
    )

    provider_mode: Mapped[str] = mapped_column(
        String(10),
        default="test",
        nullable=False,
    )

    merchant_order_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    transaction_id: Mapped[str | None] = mapped_column(
        String(150),
        unique=True,
        nullable=True,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="ETB",
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="PENDING",
        nullable=False,
        index=True,
    )

    prepay_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    payment_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    provider_response: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    order: Mapped["Order"] = relationship("Order")

    def __repr__(self) -> str:
        return (
            f"<Payment("
            f"merchant_order_id={self.merchant_order_id!r}, "
            f"status={self.status!r}, "
            f"amount={self.amount})>"
        )


from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.categories import Category

class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "products"

    __table_args__ = (
        Index(
            "ix_products_category_active",
            "category_id",
            "is_active",
        ),
        CheckConstraint(
            "price >= 0",
            name="ck_products_price_nonnegative",
        ),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    sku: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    image_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    category: Mapped["Category"] = relationship(
        "Category",
        back_populates="products",
    )

    def __repr__(self) -> str:
        return f"<Product(name={self.name!r}, sku={self.sku!r})>"

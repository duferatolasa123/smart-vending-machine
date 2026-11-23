
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    String,
    Table,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.admins import Admin


admin_roles = Table(
    "admin_roles",
    Base.metadata,
    Column(
        "admin_id",
        Uuid(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        Uuid(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    admins: Mapped[list["Admin"]] = relationship(
        "Admin",
        secondary=admin_roles,
        back_populates="roles",
    )

    def __repr__(self) -> str:
        return f"<Role(code={self.code!r}, name={self.name!r})>"

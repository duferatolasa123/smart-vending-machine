
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import UUIDPrimaryKeyMixin, TimestampMixin
from app.models.roles import admin_roles

if TYPE_CHECKING:
    from app.models.roles import Role


class Admin(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "admins"

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary=admin_roles,
        back_populates="admins",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Admin(id={self.id}, email={self.email!r})>"


from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field, SecretStr, field_validator

from app.schemas.common import BaseSchema, TimestampSchema


class AdminBase(BaseSchema):
    """Shared administrator fields."""

    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Full name cannot be empty.")

        return value


class AdminCreate(AdminBase):
    """Data required to create an administrator."""

    password: SecretStr = Field(min_length=12, max_length=128)


class AdminProvision(AdminCreate):
    """Administrator creation data, including assigned roles."""

    role_codes: list[str] = Field(min_length=1)

    @field_validator("role_codes")
    @classmethod
    def normalize_role_codes(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(
            value.strip().upper() for value in values
        ))

        if any(not value for value in normalized):
            raise ValueError("Role codes cannot be empty.")

        return normalized


class AdminUpdate(BaseSchema):
    """Fields that can be updated on an administrator."""

    full_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
    )
    email: EmailStr | None = None
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None):
        if value is None:
            return None

        return str(value).strip().lower()

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str | None):
        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError("Full name cannot be empty.")

        return value


class AdminRoleAssignment(BaseSchema):
    """Role codes assigned to an administrator."""

    role_codes: list[str] = Field(min_length=1)

    @field_validator("role_codes")
    @classmethod
    def normalize_role_codes(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(
            value.strip().upper() for value in values
        ))

        if any(not value for value in normalized):
            raise ValueError("Role codes cannot be empty.")

        return normalized


class AdminPasswordChange(BaseSchema):
    """Data required to change an administrator password."""

    current_password: SecretStr
    new_password: SecretStr = Field(min_length=12, max_length=128)


class AdminLogin(BaseSchema):
    """Administrator login credentials."""

    email: EmailStr
    password: SecretStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class AdminResponse(AdminBase, TimestampSchema):
    """Safe administrator information returned by the API."""

    id: UUID
    is_active: bool
    last_login_at: datetime | None = None
    roles: list[str] = Field(default_factory=list)

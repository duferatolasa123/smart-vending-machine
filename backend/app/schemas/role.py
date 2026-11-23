
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema, TimestampSchema

class RoleBase(BaseSchema):
    """Shared role fields."""

    code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=255)

class RoleCreate(RoleBase):
    """Data required to create an administrator role."""

    is_system: bool = False

class RoleUpdate(BaseSchema):
    """Fields that can be updated on a role."""

    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=255)

class RoleResponse(RoleBase, TimestampSchema):
    """Role information returned by the API."""

    id: UUID
    is_system: bool
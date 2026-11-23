
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema, TimestampSchema


class CategoryCreate(BaseSchema):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = None
    image_path: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class CategoryUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = None
    image_path: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class CategoryResponse(TimestampSchema):
    id: UUID
    name: str
    description: str | None
    image_path: str | None
    is_active: bool

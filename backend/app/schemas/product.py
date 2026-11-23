
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema, TimestampSchema


class ProductCreate(BaseSchema):
    category_id: UUID
    name: str = Field(min_length=2, max_length=150)
    sku: str = Field(min_length=1, max_length=80)
    description: str | None = None
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    image_path: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class ProductUpdate(BaseSchema):
    category_id: UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    price: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    image_path: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class ProductResponse(TimestampSchema):
    id: UUID
    category_id: UUID
    name: str
    sku: str
    description: str | None
    price: Decimal
    image_path: str | None
    is_active: bool

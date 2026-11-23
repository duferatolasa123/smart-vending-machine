
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema, TimestampSchema

class OrderItemCreate(BaseSchema):
    product_id: UUID
    machine_slot_id: UUID
    quantity: int = Field(gt=0)

class OrderCreate(BaseSchema):
    machine_id: UUID
    items: list[OrderItemCreate] = Field(min_length=1)

class OrderItemResponse(TimestampSchema):
    id: UUID
    order_id: UUID
    product_id: UUID
    machine_slot_id: UUID
    quantity: int
    unit_price: Decimal
    line_total: Decimal

class OrderResponse(TimestampSchema):
    id: UUID
    order_number: str
    machine_id: UUID
    status: str
    subtotal: Decimal
    total_amount: Decimal
    currency: str
    expires_at: datetime
    paid_at: datetime | None
    completed_at: datetime | None
    items: list[OrderItemResponse] = Field(default_factory=list)

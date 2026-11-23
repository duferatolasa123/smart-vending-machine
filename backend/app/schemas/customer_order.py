from decimal import Decimal
from uuid import UUID

from app.schemas.common import BaseSchema


class CustomerOrderItemStatus(BaseSchema):
    product_name: str
    quantity: int
    dispense_status: str | None


class CustomerOrderStatusResponse(BaseSchema):
    order_id: UUID
    order_number: str
    order_status: str
    payment_status: str | None
    total_amount: Decimal
    currency: str
    items: list[CustomerOrderItemStatus]

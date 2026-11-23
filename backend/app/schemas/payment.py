
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.schemas.common import BaseSchema, TimestampSchema


class TelebirrPaymentCreate(BaseSchema):
    order_id: UUID


class ChapaPaymentCreate(BaseSchema):
    order_id: UUID


class ChapaPaymentStatusRequest(BaseSchema):
    order_id: UUID


class PaymentResponse(TimestampSchema):
    id: UUID
    order_id: UUID
    provider: str
    payment_method: str
    provider_mode: str
    merchant_order_id: str
    transaction_id: str | None
    amount: Decimal
    currency: str
    status: str
    payment_url: str | None
    paid_at: datetime | None


class PaymentStatusResponse(BaseSchema):
    order_id: UUID
    payment_status: str
    order_status: str
    paid: bool

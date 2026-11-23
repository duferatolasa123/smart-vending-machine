
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema

class InventoryMovementCreate(BaseSchema):
    inventory_id: UUID
    movement_type: str = Field(min_length=1, max_length=30)
    quantity_changed: int
    unit_cost: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )
    reference: str | None = Field(default=None, max_length=100)
    notes: str | None = None

class InventoryMovementResponse(BaseSchema):
    id: UUID
    inventory_id: UUID
    movement_type: str
    quantity_changed: int
    unit_cost: Decimal | None
    reference: str | None
    notes: str | None
    performed_by_admin_id: UUID | None
    created_at: datetime
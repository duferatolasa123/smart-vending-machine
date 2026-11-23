
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema, TimestampSchema


class InventoryResponse(TimestampSchema):
    id: UUID
    machine_slot_id: UUID
    quantity: int = Field(ge=0)
    reserved_quantity: int = Field(ge=0)
    available_quantity: int = Field(ge=0)


class InventoryAdjustment(BaseSchema):
    """Internal inventory adjustment request."""

    quantity_changed: int
    movement_type: str = Field(min_length=1, max_length=30)
    unit_cost: float | None = Field(default=None, ge=0)
    reference: str | None = Field(default=None, max_length=100)
    notes: str | None = None

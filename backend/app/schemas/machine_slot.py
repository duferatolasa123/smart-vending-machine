
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema, TimestampSchema


class MachineSlotCreate(BaseSchema):
    machine_id: UUID
    slot_code: str = Field(min_length=1, max_length=50)
    slot_number: int = Field(gt=0)
    product_id: UUID | None = None
    motor_channel: int | None = Field(default=None, ge=1, le=6)
    capacity: int = Field(gt=0)
    is_active: bool = True


class MachineSlotUpdate(BaseSchema):
    product_id: UUID | None = None
    motor_channel: int | None = Field(default=None, ge=1, le=6)
    capacity: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class MachineSlotResponse(TimestampSchema):
    id: UUID
    machine_id: UUID
    slot_code: str
    slot_number: int
    product_id: UUID | None
    motor_channel: int | None
    capacity: int
    is_active: bool

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class McuDispenseCommand(BaseSchema):
    job_id: UUID
    command_id: str
    machine_slot_id: UUID
    slot_code: str
    motor_channel: int = Field(ge=1, le=6)
    quantity: int = Field(gt=0)
    sensor_timeout_seconds: int = Field(default=12, ge=1, le=60)


class McuDispenseResult(BaseSchema):
    command_id: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=30)
    sensor_confirmed: bool = False
    sensor_event_id: str | None = Field(default=None, max_length=100)
    error_code: str | None = Field(default=None, max_length=100)
    error_message: str | None = None
    completed_at: datetime | None = None

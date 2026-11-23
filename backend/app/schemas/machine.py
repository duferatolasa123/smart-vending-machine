
from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema, TimestampSchema


class MachineCreate(BaseSchema):
    machine_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=2, max_length=150)
    location_description: str | None = None
    serial_number: str | None = Field(default=None, max_length=100)
    firmware_version: str | None = Field(default=None, max_length=50)
    is_active: bool = True


class MachineUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    location_description: str | None = None
    firmware_version: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class MachineHeartbeat(BaseSchema):
    firmware_version: str | None = Field(default=None, max_length=50)


class MachineResponse(TimestampSchema):
    id: UUID
    machine_code: str
    name: str
    location_description: str | None
    serial_number: str | None
    status: str
    is_active: bool
    firmware_version: str | None
    last_seen_at: datetime | None


from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema

class MachineEventCreate(BaseSchema):
    event_type: str = Field(min_length=1, max_length=50)
    severity: str = Field(min_length=1, max_length=20)
    event_code: str | None = Field(default=None, max_length=100)
    message: str
    event_data: dict[str, Any] | None = None
    occurred_at: datetime

class MachineEventResponse(BaseSchema):
    id: UUID
    machine_id: UUID
    event_type: str
    severity: str
    event_code: str | None
    message: str
    event_data: dict[str, Any] | None
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime
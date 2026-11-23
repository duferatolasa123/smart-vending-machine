
from datetime import datetime
from uuid import UUID

from app.schemas.common import BaseSchema, TimestampSchema

class DispenseJobResponse(TimestampSchema):
    id: UUID
    order_id: UUID
    order_item_id: UUID
    machine_id: UUID
    machine_slot_id: UUID
    status: str
    attempt_count: int
    command_id: str
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None

class DispenseJobResult(BaseSchema):
    command_id: str
    status: str
    error_code: str | None = None
    error_message: str | None = None
    completed_at: datetime | None = None
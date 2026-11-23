
from datetime import datetime
from typing import Any
from uuid import UUID

from app.schemas.common import BaseSchema

class AuditLogResponse(BaseSchema):
    id: UUID
    admin_id: UUID | None
    action: str
    entity_type: str
    entity_id: str | None
    description: str
    old_values: dict[str, Any] | None
    new_values: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime
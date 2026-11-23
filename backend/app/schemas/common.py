from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

class BaseSchema(BaseModel):
    """Base schema for API request and response models."""

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
    )

class TimestampSchema(BaseSchema):
    """Common timestamp fields."""

    created_at: datetime
    updated_at: datetime

class UUIDSchema(BaseSchema):
    """Common UUID identifier."""

    id: UUID
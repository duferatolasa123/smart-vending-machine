
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class DispenseCommand(BaseModel):
    """
    Authorized command sent from the backend
    through the Raspberry Pi to the motor controller.

    The motor channel must come from the machine-slot
    configuration, never from customer input.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    protocol_version: Literal["1.0"] = "1.0"

    command_id: str = Field(
        min_length=1,
        max_length=100,
    )

    dispense_job_id: UUID

    machine_id: UUID

    order_item_id: UUID

    machine_slot_id: UUID

    slot_code: str = Field(
        min_length=1,
        max_length=50,
    )

    motor_channel: int = Field(
        ge=1,
        le=6,
    )

    quantity: int = Field(
        gt=0,
    )

    issued_at: datetime

    expires_at: datetime

    @model_validator(mode="after")
    def validate_command_timestamps(self):
        if (
            self.issued_at.tzinfo is None
            or self.issued_at.utcoffset() is None
        ):
            raise ValueError(
                "issued_at must include a timezone."
            )

        if (
            self.expires_at.tzinfo is None
            or self.expires_at.utcoffset() is None
        ):
            raise ValueError(
                "expires_at must include a timezone."
            )

        if self.expires_at <= self.issued_at:
            raise ValueError(
                "expires_at must be later than issued_at."
            )

        return self

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.dispense_jobs import DispenseJob
from app.models.inventory import Inventory
from app.models.machine_events import MachineEvent
from app.models.machine_slots import MachineSlot
from app.models.machines import Machine
from app.models.order_items import OrderItem
from app.models.orders import Order
from app.schemas.dispense_job import DispenseJobResponse
from app.schemas.mcu import McuDispenseCommand, McuDispenseResult

router = APIRouter(prefix="/api/mcu", tags=["MCU"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _authenticate(token: str | None) -> None:
    configured = settings.mcu_api_token.strip()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCU API is not configured.",
        )
    if not token or not hmac.compare_digest(
        hashlib.sha256(token.encode()).digest(),
        hashlib.sha256(configured.encode()).digest(),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MCU token.",
        )


def _machine_or_404(db: Session, machine_id: UUID) -> Machine:
    machine = db.scalar(select(Machine).where(Machine.id == machine_id))
    if machine is None:
        raise HTTPException(status_code=404, detail="Machine not found.")
    if not machine.is_active or machine.status != "online":
        raise HTTPException(status_code=409, detail="Machine is not online.")
    return machine


@router.get(
    "/{machine_id}/dispense/next",
    response_model=McuDispenseCommand | None,
)
def claim_next_dispense_job(
    machine_id: UUID,
    x_machine_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> McuDispenseCommand | None:
    """Atomically claim the next paid dispense job for an MCU."""
    _authenticate(x_machine_token)
    _machine_or_404(db, machine_id)
    job = db.scalar(
        select(DispenseJob)
        .where(
            DispenseJob.machine_id == machine_id,
            DispenseJob.status == "QUEUED",
        )
        .order_by(DispenseJob.created_at)
        .limit(1)
    )
    if job is None:
        return None
    slot = db.get(MachineSlot, job.machine_slot_id)
    item = db.get(OrderItem, job.order_item_id)
    if slot is None or item is None or slot.motor_channel is None:
        job.status = "FAILED"
        job.error_code = "MACHINE_CONFIGURATION"
        job.error_message = "Dispense slot has no valid motor channel."
        job.completed_at = _utc_now()
        db.commit()
        raise HTTPException(status_code=409, detail=job.error_message)
    job.status = "IN_PROGRESS"
    job.attempt_count += 1
    job.started_at = _utc_now()
    db.commit()
    return McuDispenseCommand(
        job_id=job.id,
        command_id=job.command_id,
        machine_slot_id=slot.id,
        slot_code=slot.slot_code,
        motor_channel=slot.motor_channel,
        quantity=item.quantity,
    )


@router.post(
    "/{machine_id}/dispense/{job_id}/result",
    response_model=DispenseJobResponse,
)
def report_dispense_result(
    machine_id: UUID,
    job_id: UUID,
    result: McuDispenseResult,
    x_machine_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> DispenseJobResponse:
    """Accept a motor result only when the physical sensor confirms delivery."""
    _authenticate(x_machine_token)
    _machine_or_404(db, machine_id)
    job = db.scalar(
        select(DispenseJob).where(
            DispenseJob.id == job_id,
            DispenseJob.machine_id == machine_id,
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Dispense job not found.")
    if job.command_id != result.command_id:
        raise HTTPException(status_code=409, detail="Command ID does not match the job.")
    if job.status in {"COMPLETED", "FAILED"}:
        return DispenseJobResponse.model_validate(job)
    if job.status != "IN_PROGRESS":
        raise HTTPException(status_code=409, detail="Dispense job is not in progress.")

    now = result.completed_at or _utc_now()
    delivered = result.status.strip().upper() == "COMPLETED" and result.sensor_confirmed
    job.completed_at = now
    if delivered:
        inventory = db.scalar(
            select(Inventory).where(Inventory.machine_slot_id == job.machine_slot_id)
        )
        item = db.get(OrderItem, job.order_item_id)
        if inventory is None or item is None or inventory.quantity < item.quantity:
            delivered = False
            job.error_code = "INVENTORY_MISMATCH"
            job.error_message = "Sensor result received but inventory was insufficient."
        else:
            inventory.quantity -= item.quantity
            inventory.reserved_quantity = max(
                0, inventory.reserved_quantity - item.quantity
            )
    if delivered:
        job.status = "COMPLETED"
        job.error_code = None
        job.error_message = None
        event_severity = "INFO"
        event_code = "DISPENSE_CONFIRMED"
        event_message = "Product delivery confirmed by sensor."
    else:
        job.status = "FAILED"
        job.error_code = job.error_code or result.error_code or "SENSOR_NOT_CONFIRMED"
        job.error_message = job.error_message or result.error_message or (
            "The delivery sensor did not confirm the product."
        )
        inventory = db.scalar(
            select(Inventory).where(Inventory.machine_slot_id == job.machine_slot_id)
        )
        item = db.get(OrderItem, job.order_item_id)
        if inventory is not None and item is not None:
            inventory.reserved_quantity = max(
                0, inventory.reserved_quantity - item.quantity
            )
        event_severity = "WARNING"
        event_code = job.error_code
        event_message = job.error_message

    db.add(
        MachineEvent(
            machine_id=machine_id,
            event_type="DISPENSE_RESULT",
            severity=event_severity,
            event_code=event_code,
            message=event_message,
            event_data={
                "job_id": str(job.id),
                "command_id": job.command_id,
                "sensor_confirmed": result.sensor_confirmed,
                "sensor_event_id": result.sensor_event_id,
            },
            occurred_at=now,
        )
    )
    order = db.get(Order, job.order_id)
    if order is not None:
        jobs = db.scalars(
            select(DispenseJob).where(DispenseJob.order_id == order.id)
        ).all()
        if jobs and all(other.status == "COMPLETED" for other in jobs):
            order.status = "COMPLETED"
            order.completed_at = now
    db.commit()
    db.refresh(job)
    return DispenseJobResponse.model_validate(job)

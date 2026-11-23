
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.dispense_jobs import DispenseJob
from app.models.machines import Machine
from app.models.machine_slots import MachineSlot
from app.models.order_items import OrderItem
from app.models.orders import Order
from app.models.payments import Payment
from app.schemas.dispense_command import DispenseCommand


class DispenseAuthorizationError(Exception):
    """Raised when a dispense job is not authorized for execution."""


DEFAULT_COMMAND_TTL_SECONDS = 60

ELIGIBLE_JOB_STATUS = "QUEUED"
PAID_ORDER_STATUS = "PAID"
SUCCESSFUL_PAYMENT_STATUS = "SUCCESS"
ONLINE_MACHINE_STATUS = "online"


def build_dispense_command(
    db: Session,
    dispense_job_id: UUID,
    command_ttl_seconds: int = DEFAULT_COMMAND_TTL_SECONDS,
) -> DispenseCommand:
    """
    Build an authorized motor command from an existing dispense job.

    This function does not:
    - Create dispense jobs.
    - Change inventory.
    - Change payment status.
    - Mark jobs as started or completed.
    - Send commands to the Raspberry Pi.

    It only validates authorization and constructs the command.
    """

    if command_ttl_seconds <= 0:
        raise ValueError(
            "Command TTL must be greater than zero."
        )

    # 1. Retrieve the dispense job.
    job = (
        db.query(DispenseJob)
        .filter(DispenseJob.id == dispense_job_id)
        .first()
    )

    if job is None:
        raise DispenseAuthorizationError(
            "Dispense job was not found."
        )

    # 2. Only queued jobs are eligible for a new command.
    if (job.status or "").upper() != ELIGIBLE_JOB_STATUS:
        raise DispenseAuthorizationError(
            f"Job status '{job.status}' is not eligible for execution."
        )

    if not job.command_id:
        raise DispenseAuthorizationError(
            "Dispense job has no command ID."
        )

    # 3. Retrieve the order.
    order = (
        db.query(Order)
        .filter(Order.id == job.order_id)
        .first()
    )

    if order is None:
        raise DispenseAuthorizationError(
            "Associated order was not found."
        )

    # 4. Require an explicitly paid order.
    if (order.status or "").upper() != PAID_ORDER_STATUS:
        raise DispenseAuthorizationError(
            "Order is not marked as PAID."
        )

    if order.paid_at is None:
        raise DispenseAuthorizationError(
            "Order has no confirmed payment timestamp."
        )

    # 5. Require a successful, identifiable payment.
    payment = (
        db.query(Payment)
        .filter(
            Payment.order_id == order.id,
            Payment.status == SUCCESSFUL_PAYMENT_STATUS,
        )
        .first()
    )

    if payment is None:
        raise DispenseAuthorizationError(
            "No successful payment exists for this order."
        )

    if not payment.transaction_id:
        raise DispenseAuthorizationError(
            "Successful payment has no provider transaction ID."
        )

    # 6. Verify the payment amount and currency.
    if payment.amount != order.total_amount:
        raise DispenseAuthorizationError(
            "Payment amount does not match the order total."
        )

    if payment.currency != order.currency:
        raise DispenseAuthorizationError(
            "Payment currency does not match the order currency."
        )

    # 7. Retrieve the order item.
    order_item = (
        db.query(OrderItem)
        .filter(
            OrderItem.id == job.order_item_id,
            OrderItem.order_id == order.id,
        )
        .first()
    )

    if order_item is None:
        raise DispenseAuthorizationError(
            "Order item does not belong to the associated order."
        )

    if order_item.quantity <= 0:
        raise DispenseAuthorizationError(
            "Order item quantity must be positive."
        )

    # 8. Retrieve the machine.
    machine = (
        db.query(Machine)
        .filter(Machine.id == job.machine_id)
        .first()
    )

    if machine is None:
        raise DispenseAuthorizationError(
            "Associated machine was not found."
        )

    if not machine.is_active:
        raise DispenseAuthorizationError(
            "Machine is inactive."
        )

    if (machine.status or "").lower() != ONLINE_MACHINE_STATUS:
        raise DispenseAuthorizationError(
            "Machine is not online."
        )

    # 9. Confirm the order, job and machine agree.
    if order.machine_id != machine.id:
        raise DispenseAuthorizationError(
            "Order and dispense job reference different machines."
        )

    # 10. Retrieve the physical machine slot.
    slot = (
        db.query(MachineSlot)
        .filter(MachineSlot.id == job.machine_slot_id)
        .first()
    )

    if slot is None:
        raise DispenseAuthorizationError(
            "Machine slot was not found."
        )

    if slot.machine_id != machine.id:
        raise DispenseAuthorizationError(
            "Machine slot does not belong to the assigned machine."
        )

    if not slot.is_active:
        raise DispenseAuthorizationError(
            "Machine slot is inactive."
        )

    if order_item.machine_slot_id != slot.id:
        raise DispenseAuthorizationError(
            "Order item and dispense job reference different slots."
        )

    if order_item.product_id != slot.product_id:
        raise DispenseAuthorizationError(
            "Order item product does not match the slot product."
        )

    # 11. Validate the physical motor assignment.
    if slot.motor_channel is None:
        raise DispenseAuthorizationError(
            "Machine slot has no assigned motor channel."
        )

    if not 1 <= slot.motor_channel <= 6:
        raise DispenseAuthorizationError(
            "Machine slot has an invalid motor channel."
        )

    # 12. Construct a short-lived command.
    issued_at = datetime.now(timezone.utc)

    expires_at = issued_at + timedelta(
        seconds=command_ttl_seconds
    )

    return DispenseCommand(
        protocol_version="1.0",
        command_id=job.command_id,
        dispense_job_id=job.id,
        machine_id=machine.id,
        order_item_id=order_item.id,
        machine_slot_id=slot.id,
        slot_code=slot.slot_code,
        motor_channel=slot.motor_channel,
        quantity=order_item.quantity,
        issued_at=issued_at,
        expires_at=expires_at,
    )

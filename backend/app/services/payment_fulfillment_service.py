
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.dispense_jobs import DispenseJob
from app.models.inventory import Inventory
from app.models.machine_slots import MachineSlot
from app.models.order_items import OrderItem
from app.models.orders import Order
from app.models.payments import Payment
from app.services.chapa_verification_service import (
    ChapaVerificationResult,
)


class PaymentFulfillmentError(Exception):
    """Base exception for payment fulfillment errors."""


class PaymentFulfillmentNotFoundError(PaymentFulfillmentError):
    """The local payment or associated order does not exist."""


class PaymentFulfillmentMismatchError(PaymentFulfillmentError):
    """Verified payment data does not match the local records."""


class PaymentFulfillmentStateError(PaymentFulfillmentError):
    """The payment or order is in an invalid state for fulfillment."""


class PaymentFulfillmentInventoryError(PaymentFulfillmentError):
    """The order's inventory reservation is missing or insufficient."""


class PaymentFulfillmentConfigurationError(PaymentFulfillmentError):
    """The machine or product-slot configuration is invalid."""


@dataclass(frozen=True)
class PaymentFulfillmentResult:
    merchant_order_id: str
    transaction_id: str
    payment_status: str
    order_status: str
    dispense_jobs_created: int
    requires_manual_review: bool


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""

    return datetime.now(timezone.utc)


def _is_expired(expires_at: datetime, now: datetime) -> bool:
    """
    Compare an order expiration time with UTC now.

    SQLite may return a naive datetime even when the column
    was declared with timezone=True. Treat such values as UTC.
    """

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return expires_at <= now


def fulfill_verified_chapa_payment(
    db: Session,
    verification: ChapaVerificationResult,
) -> PaymentFulfillmentResult:
    """
    Record a verified Chapa payment and authorize dispense jobs.

    Safety rules:
    - Accept only a successful Chapa test-mode verification result.
    - Match the provider reference, amount, and currency locally.
    - Record payment success and order authorization atomically.
    - Create one queued job per order item.
    - Never create jobs for expired orders.
    - Never reduce physical inventory here.
    - Never send commands to a machine from this service.

    The caller must first call verify_chapa_payment().
    """

    if verification.provider_status.lower() != "success":
        raise PaymentFulfillmentMismatchError(
            "Only a successful provider verification can be fulfilled."
        )

    if verification.mode.lower() not in {"test", "live"}:
        raise PaymentFulfillmentMismatchError(
            "The verified Chapa mode is invalid."
        )
    if (
        settings.environment.lower() == "production"
        and verification.mode.lower() != "live"
    ):
        raise PaymentFulfillmentMismatchError(
            "Production fulfillment requires a live-mode payment."
        )

    if not verification.merchant_order_id.strip():
        raise PaymentFulfillmentMismatchError(
            "The verified merchant transaction reference is empty."
        )

    if not verification.transaction_id.strip():
        raise PaymentFulfillmentMismatchError(
            "The provider transaction ID is empty."
        )

    if verification.amount <= 0:
        raise PaymentFulfillmentMismatchError(
            "The verified payment amount must be positive."
        )

    if verification.currency.upper() != "ETB":
        raise PaymentFulfillmentMismatchError(
            "Only ETB payments are accepted."
        )

    try:
        payment = db.scalar(
            select(Payment)
            .where(
                Payment.merchant_order_id
                == verification.merchant_order_id
            )
            .with_for_update()
        )

        if payment is None:
            raise PaymentFulfillmentNotFoundError(
                "The local payment record was not found."
            )

        if payment.provider != "CHAPA":
            raise PaymentFulfillmentMismatchError(
                "The local payment provider is not Chapa."
            )

        payment_mode = getattr(payment, "provider_mode", "test")
        if payment_mode != verification.mode.lower():
            raise PaymentFulfillmentMismatchError(
                "Verified mode does not match the local payment attempt."
            )

        order = db.scalar(
            select(Order).where(Order.id == payment.order_id)
        )

        if order is None:
            raise PaymentFulfillmentNotFoundError(
                "The payment's associated order was not found."
            )

        # Match the verification result against local records.
        if payment.amount != verification.amount:
            raise PaymentFulfillmentMismatchError(
                "Verified amount does not match the local payment."
            )

        if order.total_amount != verification.amount:
            raise PaymentFulfillmentMismatchError(
                "Verified amount does not match the order total."
            )

        if (
            payment.currency.upper() != verification.currency.upper()
            or order.currency.upper() != verification.currency.upper()
        ):
            raise PaymentFulfillmentMismatchError(
                "Verified currency does not match local records."
            )

        now = _utc_now()

        # Idempotency: a repeated request must not create duplicate jobs.
        if payment.status == "SUCCESS":
            if payment.transaction_id != verification.transaction_id:
                raise PaymentFulfillmentMismatchError(
                    "The successful payment has a different "
                    "provider transaction ID."
                )

            if order.status == "PAYMENT_REVIEW":
                return PaymentFulfillmentResult(
                    merchant_order_id=payment.merchant_order_id,
                    transaction_id=payment.transaction_id,
                    payment_status="SUCCESS",
                    order_status="PAYMENT_REVIEW",
                    dispense_jobs_created=0,
                    requires_manual_review=True,
                )

            if order.status != "PAID":
                raise PaymentFulfillmentStateError(
                    "The payment is successful, but the order is "
                    f"in unexpected state {order.status!r}."
                )

            existing_jobs = db.scalars(
                select(DispenseJob).where(
                    DispenseJob.order_id == order.id
                )
            ).all()

            order_items = db.scalars(
                select(OrderItem).where(
                    OrderItem.order_id == order.id
                )
            ).all()

            if len(existing_jobs) != len(order_items):
                raise PaymentFulfillmentStateError(
                    "The paid order does not have exactly one "
                    "dispense job per order item."
                )

            return PaymentFulfillmentResult(
                merchant_order_id=payment.merchant_order_id,
                transaction_id=payment.transaction_id,
                payment_status="SUCCESS",
                order_status="PAID",
                dispense_jobs_created=0,
                requires_manual_review=False,
            )

        if payment.status != "PENDING":
            raise PaymentFulfillmentStateError(
                f"Payment status {payment.status!r} cannot be fulfilled."
            )

        if order.status != "PENDING_PAYMENT":
            raise PaymentFulfillmentStateError(
                f"Order status {order.status!r} cannot be fulfilled."
            )

        # Load all order items before changing payment/order state.
        order_items = db.scalars(
            select(OrderItem)
            .where(OrderItem.order_id == order.id)
            .order_by(OrderItem.id)
        ).all()

        if not order_items:
            raise PaymentFulfillmentStateError(
                "The order has no items."
            )

        calculated_total = sum(
            (item.line_total for item in order_items),
            start=order.total_amount.__class__("0.00"),
        )

        if calculated_total != order.total_amount:
            raise PaymentFulfillmentMismatchError(
                "Order item totals do not match the order total."
            )

        # A late payment is recorded, but must not authorize dispensing.
        if _is_expired(order.expires_at, now):
            # Record confirmed funds, then route the expired order to review.
            payment.status = "SUCCESS"
            payment.transaction_id = verification.transaction_id
            payment.paid_at = now
            order.status = "PAYMENT_REVIEW"
            order.paid_at = now

            db.commit()

            return PaymentFulfillmentResult(
                merchant_order_id=payment.merchant_order_id,
                transaction_id=payment.transaction_id,
                payment_status="SUCCESS",
                order_status="PAYMENT_REVIEW",
                dispense_jobs_created=0,
                requires_manual_review=True,
            )

        # Validate every item and its reservation before creating jobs.
        for item in order_items:
            machine_slot = db.scalar(
                select(MachineSlot).where(
                    MachineSlot.id == item.machine_slot_id
                )
            )

            if machine_slot is None:
                raise PaymentFulfillmentConfigurationError(
                    "An order item references a missing machine slot."
                )

            if machine_slot.machine_id != order.machine_id:
                raise PaymentFulfillmentConfigurationError(
                    "An order item references a slot on another machine."
                )

            if not machine_slot.is_active:
                raise PaymentFulfillmentConfigurationError(
                    "An order item references an inactive machine slot."
                )

            if machine_slot.product_id != item.product_id:
                raise PaymentFulfillmentConfigurationError(
                    "The product assigned to a machine slot has changed."
                )

            if (
                machine_slot.motor_channel is None
                or not 1 <= machine_slot.motor_channel <= 6
            ):
                raise PaymentFulfillmentConfigurationError(
                    "A machine slot has no valid motor channel assignment."
                )

            inventory = db.scalar(
                select(Inventory).where(
                    Inventory.machine_slot_id == item.machine_slot_id
                )
            )

            if inventory is None:
                raise PaymentFulfillmentInventoryError(
                    "Inventory record for an order item was not found."
                )

            if inventory.reserved_quantity < item.quantity:
                raise PaymentFulfillmentInventoryError(
                    "The reserved inventory is insufficient "
                    "for an order item."
                )

        # All checks passed. Record payment and authorize the order in the
        # same transaction that creates its dispense jobs.
        payment.status = "SUCCESS"
        payment.transaction_id = verification.transaction_id
        payment.paid_at = now
        order.status = "PAID"
        order.paid_at = now

        for item in order_items:
            job = DispenseJob(
                order_id=order.id,
                order_item_id=item.id,
                machine_id=order.machine_id,
                machine_slot_id=item.machine_slot_id,
                status="QUEUED",
                attempt_count=0,
                command_id=f"DISP-{uuid.uuid4().hex.upper()}",
            )

            db.add(job)

        db.flush()
        db.commit()

        return PaymentFulfillmentResult(
            merchant_order_id=payment.merchant_order_id,
            transaction_id=payment.transaction_id,
            payment_status="SUCCESS",
            order_status="PAID",
            dispense_jobs_created=len(order_items),
            requires_manual_review=False,
        )

    except (
        PaymentFulfillmentInventoryError,
        PaymentFulfillmentConfigurationError,
    ):
        # Chapa has already confirmed the funds. Keep that fact durable but
        # never authorize dispensing when stock or machine setup is unsafe.
        db.rollback()
        payment.status = "SUCCESS"
        payment.transaction_id = verification.transaction_id
        payment.paid_at = _utc_now()
        order.status = "PAYMENT_REVIEW"
        order.paid_at = payment.paid_at
        db.commit()
        return PaymentFulfillmentResult(
            merchant_order_id=payment.merchant_order_id,
            transaction_id=verification.transaction_id,
            payment_status="SUCCESS",
            order_status="PAYMENT_REVIEW",
            dispense_jobs_created=0,
            requires_manual_review=True,
        )

    except IntegrityError as exc:
        db.rollback()
        raise PaymentFulfillmentStateError(
            "A database uniqueness or integrity constraint prevented "
            "payment fulfillment. No partial fulfillment was committed."
        ) from exc

    except Exception:
        db.rollback()
        raise

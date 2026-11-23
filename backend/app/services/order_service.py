
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import TypedDict

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import (
    Inventory,
    Machine,
    MachineSlot,
    Order,
    OrderItem,
    Product,
)
from app.schemas.order import OrderCreate


ORDER_EXPIRATION_MINUTES = 10


class ValidatedOrderItem(TypedDict):
    product_id: uuid.UUID
    machine_slot_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    line_total: Decimal


def create_order(db: Session, order_data: OrderCreate) -> Order:
    """
    Create a customer order and reserve its inventory.

    Prices are always read from the database.
    All inventory reservations and order records are committed
    in one database transaction.
    """

    try:
        # Reject duplicate slot entries so quantities cannot be
        # accidentally split across duplicate lines.
        slot_ids = [
            item.machine_slot_id for item in order_data.items
        ]

        if len(slot_ids) != len(set(slot_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each machine slot can appear only once in an order.",
            )

        # Validate the machine.
        machine = db.scalar(
            select(Machine).where(
                Machine.id == order_data.machine_id
            )
        )

        if machine is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Machine not found.",
            )

        if not machine.is_active or machine.status != "online":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This vending machine is currently unavailable.",
            )

        # Validate all requested items before reserving stock.
        validated_items: list[ValidatedOrderItem] = []

        for item in order_data.items:
            slot = db.scalar(
                select(MachineSlot).where(
                    MachineSlot.id == item.machine_slot_id,
                    MachineSlot.machine_id == machine.id,
                )
            )

            if slot is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        f"Machine slot {item.machine_slot_id} "
                        "was not found on this machine."
                    ),
                )

            if not slot.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Machine slot {slot.slot_code} is unavailable.",
                )

            if slot.product_id != item.product_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"The selected product does not match "
                        f"machine slot {slot.slot_code}."
                    ),
                )

            product = db.scalar(
                select(Product).where(
                    Product.id == item.product_id
                )
            )

            if product is None or not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="The selected product is unavailable.",
                )

            inventory = db.scalar(
                select(Inventory).where(
                    Inventory.machine_slot_id == slot.id
                )
            )

            if inventory is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Inventory has not been configured "
                        f"for slot {slot.slot_code}."
                    ),
                )

            if inventory.available_quantity < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Insufficient stock in slot {slot.slot_code}. "
                        f"Available: {inventory.available_quantity}."
                    ),
                )

            unit_price = Decimal(product.price)
            line_total = unit_price * item.quantity

            validated_items.append(
                {
                    "product_id": product.id,
                    "machine_slot_id": slot.id,
                    "quantity": item.quantity,
                    "unit_price": unit_price,
                    "line_total": line_total,
                }
            )

        # Calculate the authoritative order total.
        subtotal = sum(
            (item["line_total"] for item in validated_items),
            Decimal("0.00"),
        )

        # Reserve stock using a conditional database update.
        # This prevents an order from reserving stock that has
        # already been reserved by another transaction.
        for item in sorted(
            validated_items,
            key=lambda value: str(value["machine_slot_id"]),
        ):
            reservation = db.execute(
                update(Inventory)
                .where(
                    Inventory.machine_slot_id
                    == item["machine_slot_id"],
                    (
                        Inventory.quantity
                        - Inventory.reserved_quantity
                    ) >= item["quantity"],
                )
                .values(
                    reserved_quantity=(
                        Inventory.reserved_quantity
                        + item["quantity"]
                    )
                )
            )

            if reservation.rowcount != 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Stock availability changed while creating "
                        "your order. Please try again."
                    ),
                )

        # Create the order.
        order = Order(
            order_number=f"ORD-{uuid.uuid4().hex[:20].upper()}",
            machine_id=machine.id,
            status="PENDING_PAYMENT",
            subtotal=subtotal,
            total_amount=subtotal,
            currency="ETB",
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(minutes=ORDER_EXPIRATION_MINUTES)
            ),
        )

        db.add(order)
        db.flush()

        # Create the order item records.
        for item in validated_items:
            db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=item["product_id"],
                    machine_slot_id=item["machine_slot_id"],
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                    line_total=item["line_total"],
                )
            )

        # Commit the order and reservations together.
        db.commit()
        db.refresh(order)

        return order

    except Exception:
        db.rollback()
        raise


from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.order import OrderCreate, OrderResponse
from app.schemas.customer_order import (
    CustomerOrderItemStatus,
    CustomerOrderStatusResponse,
)
from app.models.dispense_jobs import DispenseJob
from app.models.order_items import OrderItem
from app.models.orders import Order
from app.models.payments import Payment
from app.models.products import Product
from app.services.order_service import create_order

router = APIRouter(
    prefix="/api/orders",
    tags=["Orders"],
)


@router.post(
    "/",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_customer_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
) -> OrderResponse:
    """Create an order and reserve its inventory."""

    order = create_order(db, order_data)

    return OrderResponse.model_validate(order)


@router.get(
    "/{order_id}/status",
    response_model=CustomerOrderStatusResponse,
)
def get_customer_order_status(
    order_id: UUID,
    db: Session = Depends(get_db),
) -> CustomerOrderStatusResponse:
    """Return only the customer-visible order/payment/dispense state."""

    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )

    payment_status = db.scalar(
        select(Payment.status)
        .where(Payment.order_id == order.id)
        .order_by(Payment.created_at.desc())
        .limit(1)
    )
    rows = db.execute(
        select(OrderItem, Product.name, DispenseJob.status)
        .join(Product, Product.id == OrderItem.product_id)
        .outerjoin(DispenseJob, DispenseJob.order_item_id == OrderItem.id)
        .where(OrderItem.order_id == order.id)
        .order_by(OrderItem.created_at)
    ).all()

    return CustomerOrderStatusResponse(
        order_id=order.id,
        order_number=order.order_number,
        order_status=order.status,
        payment_status=payment_status,
        total_amount=order.total_amount,
        currency=order.currency,
        items=[
            CustomerOrderItemStatus(
                product_name=product_name,
                quantity=item.quantity,
                dispense_status=job_status,
            )
            for item, product_name, job_status in rows
        ],
    )

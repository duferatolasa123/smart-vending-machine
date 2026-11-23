from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.payments import Payment
from app.schemas.payment import (
    ChapaPaymentCreate,
    ChapaPaymentStatusRequest,
    PaymentResponse,
    PaymentStatusResponse,
)
from app.services.chapa_payment_service import (
    ChapaConfigurationError,
    ChapaInitializationError,
    PaymentAlreadyExistsError,
    initialize_chapa_payment,
)
from app.services.chapa_verification_service import (
    ChapaVerificationConfigurationError,
    ChapaVerificationError,
    ChapaVerificationFailedError,
    ChapaVerificationNotFoundError,
    ChapaVerificationPendingError,
    ChapaVerificationResponseError,
    verify_chapa_payment,
)
from app.services.payment_fulfillment_service import (
    PaymentFulfillmentError,
    fulfill_verified_chapa_payment,
)

router = APIRouter(prefix="/api/payments", tags=["Payments"])


def _payment_for_order(db: Session, order_id: UUID) -> Payment:
    payment = db.scalar(
        select(Payment)
        .where(Payment.order_id == order_id)
        .order_by(Payment.created_at.desc())
        .limit(1)
    )
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No payment attempt was found for this order.",
        )
    return payment


def _reconcile_payment(
    db: Session,
    merchant_order_id: str,
) -> PaymentStatusResponse:
    try:
        verification = verify_chapa_payment(db, merchant_order_id)
    except ChapaVerificationPendingError:
        payment = db.scalar(
            select(Payment).where(
                Payment.merchant_order_id == merchant_order_id
            )
        )
        if payment is None:
            raise HTTPException(status_code=404, detail="Payment not found.")
        return PaymentStatusResponse(
            order_id=payment.order_id,
            payment_status=payment.status,
            order_status=payment.order.status,
            paid=False,
        )
    except ChapaVerificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ChapaVerificationConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ChapaVerificationFailedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ChapaVerificationResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ChapaVerificationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        result = fulfill_verified_chapa_payment(db, verification)
    except PaymentFulfillmentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return PaymentStatusResponse(
        order_id=payment_order_id(db, merchant_order_id),
        payment_status=result.payment_status,
        order_status=result.order_status,
        paid=result.payment_status == "SUCCESS",
    )


def payment_order_id(db: Session, merchant_order_id: str) -> UUID:
    order_id = db.scalar(
        select(Payment.order_id).where(
            Payment.merchant_order_id == merchant_order_id
        )
    )
    if order_id is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    return order_id


@router.post(
    "/chapa/initialize",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
)
def initialize_customer_chapa_payment(
    payment_data: ChapaPaymentCreate,
    db: Session = Depends(get_db),
) -> PaymentResponse:
    """Create or reuse the hosted checkout for a server-priced order."""

    try:
        payment = initialize_chapa_payment(
            db=db,
            order_id=payment_data.order_id,
        )
        return PaymentResponse.model_validate(payment)
    except ChapaConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PaymentAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ChapaInitializationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/chapa/verify",
    response_model=PaymentStatusResponse,
)
def verify_customer_chapa_payment(
    payment_data: ChapaPaymentStatusRequest,
    db: Session = Depends(get_db),
) -> PaymentStatusResponse:
    """Verify an order's latest Chapa attempt directly with Chapa."""

    payment = _payment_for_order(db, payment_data.order_id)
    return _reconcile_payment(db, payment.merchant_order_id)


@router.get("/chapa/callback", response_model=PaymentStatusResponse)
def chapa_callback(
    db: Session = Depends(get_db),
    tx_ref: str | None = None,
    trx_ref: str | None = None,
) -> PaymentStatusResponse:
    """Treat Chapa callback parameters as hints and verify server-side."""

    merchant_reference = tx_ref or trx_ref
    if not merchant_reference:
        raise HTTPException(status_code=400, detail="Missing transaction reference.")
    return _reconcile_payment(db, merchant_reference)


@router.post("/chapa/webhook")
async def chapa_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Authenticate Chapa signatures; independently verify successful events."""

    secret = settings.chapa_webhook_secret.strip()
    if not secret:
        raise HTTPException(status_code=503, detail="Chapa webhook is not configured.")

    raw_body = await request.body()
    if len(raw_body) > 65536:
        raise HTTPException(status_code=413, detail="Webhook payload is too large.")
    try:
        event = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook JSON.") from exc
    if not isinstance(event, dict):
        raise HTTPException(status_code=400, detail="Invalid webhook payload.")

    # Chapa's examples sign JSON.stringify(req.body); accept that compact
    # representation as well as the exact received bytes.
    canonical_body = json.dumps(
        event,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    payload_signature = hmac.new(
        secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    canonical_signature = hmac.new(
        secret.encode(), canonical_body, hashlib.sha256
    ).hexdigest()
    secret_signature = hmac.new(
        secret.encode(), secret.encode(), hashlib.sha256
    ).hexdigest()
    candidates = (
        request.headers.get("x-chapa-signature", ""),
        request.headers.get("chapa-signature", ""),
    )
    if not any(
        supplied and hmac.compare_digest(supplied, expected)
        for supplied in candidates
        for expected in (
            payload_signature,
            canonical_signature,
            secret_signature,
        )
    ):
        raise HTTPException(status_code=401, detail="Invalid Chapa signature.")

    if event.get("event") != "charge.success":
        return {"received": True, "processed": False}

    merchant_reference = event.get("tx_ref")
    if not isinstance(merchant_reference, str) or not merchant_reference:
        raise HTTPException(status_code=400, detail="Missing transaction reference.")

    result = _reconcile_payment(db, merchant_reference)
    return {
        "received": True,
        "processed": True,
        "payment_status": result.payment_status,
        "order_status": result.order_status,
    }


from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, cast
from urllib.parse import urlencode, urlparse, urlunparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.orders import Order
from app.models.payments import Payment


class ChapaPaymentError(Exception):
    """Base exception for Chapa payment initialization errors."""

class ChapaConfigurationError(ChapaPaymentError):
    """Raised when Chapa configuration is missing or unsafe."""

class ChapaInitializationError(ChapaPaymentError):
    """Raised when Chapa cannot initialize a payment."""

class PaymentAlreadyExistsError(ChapaPaymentError):
    """Raised when an order already has an active payment attempt."""

def _validate_chapa_configuration() -> tuple[str, str]:
    """
    Validate that the application is configured for Chapa test mode.
    Live payments are deliberately disabled at this stage.
    """

    secret_key = settings.chapa_secret_key.strip()
    base_url = settings.chapa_base_url.rstrip("/")
    mode = settings.chapa_mode.strip().lower()

    if not secret_key:
        raise ChapaConfigurationError(
            "Chapa secret key is not configured."
        )

    if mode not in {"test", "live"}:
        raise ChapaConfigurationError("Chapa mode must be test or live.")

    if mode == "test" and not secret_key.startswith("CHASECK_TEST"):
        raise ChapaConfigurationError(
            "The configured Chapa key does not appear to be a test secret key."
        )
    if mode == "live" and secret_key.startswith("CHASECK_TEST"):
        raise ChapaConfigurationError(
            "A test secret key cannot be used in live mode."
        )

    parsed_base_url = urlparse(base_url)

    if (
        parsed_base_url.scheme != "https"
        or parsed_base_url.hostname != "api.chapa.co"
        or parsed_base_url.path.rstrip("/") != "/v1"
        or parsed_base_url.query
        or parsed_base_url.fragment
    ):
        raise ChapaConfigurationError(
            "Chapa base URL must be https://api.chapa.co/v1."
        )

    return secret_key, base_url


def _append_query(url: str, **values: str) -> str:
    parsed = urlparse(url)
    query = parsed.query
    additions = urlencode(values)
    return urlunparse(parsed._replace(query=f"{query}&{additions}" if query else additions))

def _validate_checkout_url(checkout_url: str) -> None:
    """
    Accept only HTTPS checkout URLs from Chapa's hosted checkout domain.
    """

    parsed_url = urlparse(checkout_url)

    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "checkout.chapa.co"
        or parsed_url.username is not None
        or parsed_url.password is not None
    ):
        raise ChapaInitializationError(
            "Chapa returned an unexpected checkout URL."
        )

def initialize_chapa_payment(
    db: Session,
    order_id: uuid.UUID,
) -> Payment:
    """
    Initialize a Chapa hosted checkout for an existing order.

    Important:
    - The order amount and currency come from the database.
    - A payment attempt is persisted before contacting Chapa.
    - Existing pending attempts are reused only when their checkout URL
      has already been saved.
    - An uncertain initialization is not automatically retried.
    - This function never marks an order as paid.
    - This function never creates dispense jobs or activates motors.
    """

    secret_key, base_url = _validate_chapa_configuration()

    # Retrieve the authoritative order.
    order = db.scalar(
        select(Order).where(Order.id == order_id)
    )

    if order is None:
        raise ChapaInitializationError(
            "Order was not found."
        )

    if order.status != "PENDING_PAYMENT":
        raise ChapaInitializationError(
            "This order is not awaiting payment."
        )

    if order.total_amount <= Decimal("0.00"):
        raise ChapaInitializationError(
            "Order total must be greater than zero."
        )

    if order.currency != "ETB":
        raise ChapaInitializationError(
            "Only ETB orders are supported by this payment integration."
        )

    now = datetime.now(timezone.utc)

    # SQLite may return a timezone-naive datetime. Treat stored UTC values
    # as UTC so that expiry comparison is consistent.
    expires_at = order.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= now:
        raise ChapaInitializationError(
            "This order has expired. Please create a new order."
        )

    # Find any previous payment attempt for this order.
    existing_payment = db.scalar(
        select(Payment)
        .where(Payment.order_id == order.id)
        .order_by(Payment.created_at.desc())
        .limit(1)
    )

    if existing_payment is not None:
        if existing_payment.status == "SUCCESS":
            raise PaymentAlreadyExistsError(
                "This order already has a successful payment."
            )

        if existing_payment.status == "PENDING":
            if existing_payment.payment_url:
                return existing_payment

            # We cannot know whether Chapa created the transaction if
            # the previous request timed out or the server stopped.
            # Do not create another transaction automatically.
            raise PaymentAlreadyExistsError(
                "A previous payment initialization is unresolved. "
                "Verify its transaction reference before retrying."
            )

        if existing_payment.status not in {"FAILED", "EXPIRED"}:
            raise PaymentAlreadyExistsError(
                "The previous payment attempt must be reconciled first."
            )

    # Generate a new merchant transaction reference.
    tx_ref = f"VEND-{uuid.uuid4().hex.upper()}"

    payment = Payment(
        order_id=order.id,
        provider="CHAPA",
        payment_method="HOSTED_CHECKOUT",
        provider_mode=settings.chapa_mode.strip().lower(),
        merchant_order_id=tx_ref,
        amount=order.total_amount,
        currency=order.currency,
        status="PENDING",
    )

    # Persist the payment attempt before making the external request.
    # This allows later reconciliation if the network outcome is unknown.
    db.add(payment)

    try:
        db.commit()
        db.refresh(payment)
    except Exception:
        db.rollback()
        raise

    payload: dict[str, Any] = {
        "amount": format(order.total_amount, ".2f"),
        "currency": order.currency,
        "tx_ref": tx_ref,
        "customization": {
            "title": "Vending Machine",
            "description": f"Payment for order {order.order_number}",
        },
    }

    if settings.chapa_callback_url:
        payload["callback_url"] = _append_query(
            settings.chapa_callback_url,
            order_id=str(order.id),
        )

    if settings.chapa_return_url:
        payload["return_url"] = _append_query(
            settings.chapa_return_url,
            order_id=str(order.id),
        )

    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }

    endpoint = f"{base_url}/transaction/initialize"

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                endpoint,
                json=payload,
                headers=headers,
            )

    except httpx.RequestError as exc:
        # The request may have reached Chapa even if our connection
        # timed out. Keep the payment PENDING for later reconciliation.
        raise ChapaInitializationError(
            "Chapa initialization outcome is unknown. "
            f"Do not create another attempt. Transaction reference: {tx_ref}"
        ) from exc

    try:
        response_data_value = response.json()
    except ValueError as exc:
        raise ChapaInitializationError(
            "Chapa returned an invalid response. "
            f"Transaction reference: {tx_ref}"
        ) from exc

    # A non-2xx response may still contain useful provider error details, but
    # it can also be valid JSON with a non-object shape. Normalize that case
    # before reading fields so an upstream error cannot cause UnboundLocalError.
    response_data = (
        cast(dict[str, Any], response_data_value)
        if isinstance(response_data_value, dict)
        else {}
    )

    if not response.is_success:
        # Do not automatically retry. The persisted reference can be
        # reconciled against Chapa before another attempt is created.
        provider_message = str(response_data.get("message", "")).strip()
        message_suffix = f" Message: {provider_message}" if provider_message else ""
        payment.status = "FAILED"
        payment.provider_response = json.dumps(
            {
                "status": response_data.get("status"),
                "message": response_data.get("message"),
                "http_status": response.status_code,
            }
        )
        db.commit()
        raise ChapaInitializationError(
            "Chapa rejected or could not complete initialization. "
            f"HTTP status: {response.status_code}.{message_suffix} "
            f"Transaction reference: {tx_ref}"
        )

    if not isinstance(response_data_value, dict):
        raise ChapaInitializationError(
            "Chapa returned an unexpected response format."
        )

    provider_status = str(
        response_data.get("status", "")
    ).lower()

    if provider_status != "success":
        payment.status = "FAILED"
        payment.provider_response = json.dumps(
            {
                "status": response_data.get("status"),
                "message": response_data.get("message"),
            }
        )
        db.commit()

        raise ChapaInitializationError(
            "Chapa did not create the hosted checkout session."
        )

    data_value = response_data.get("data")

    if not isinstance(data_value, dict):
        raise ChapaInitializationError(
            "Chapa response did not contain checkout data."
        )

    data = cast(dict[str, Any], data_value)

    checkout_url = data.get("checkout_url")

    if not isinstance(checkout_url, str) or not checkout_url.strip():
        raise ChapaInitializationError(
            "Chapa response did not contain a checkout URL."
        )

    _validate_checkout_url(checkout_url)

    # Store the URL and a minimal provider response.
    payment.payment_url = checkout_url
    payment.provider_response = json.dumps(
        {
            "status": response_data.get("status"),
            "message": response_data.get("message"),
        }
    )

    try:
        db.commit()
        db.refresh(payment)
    except Exception:
        db.rollback()
        raise

    return payment

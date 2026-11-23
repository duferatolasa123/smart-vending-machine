
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.orders import Order
from app.models.payments import Payment


class ChapaVerificationError(Exception):
    """Base exception for Chapa transaction verification."""

class ChapaVerificationConfigurationError(ChapaVerificationError):
    """Raised when Chapa configuration is missing or unsafe."""

class ChapaVerificationNotFoundError(ChapaVerificationError):
    """Raised when the local payment reference does not exist."""

class ChapaVerificationPendingError(ChapaVerificationError):
    """Raised when Chapa has not confirmed payment yet."""

class ChapaVerificationFailedError(ChapaVerificationError):
    """Raised when Chapa explicitly reports a failed payment."""

class ChapaVerificationResponseError(ChapaVerificationError):
    """Raised when Chapa returns an invalid or inconsistent response."""

@dataclass(frozen=True)
class ChapaVerificationResult:
    merchant_order_id: str
    transaction_id: str
    amount: Decimal
    currency: str
    provider_status: str
    mode: str

def _validate_configuration() -> tuple[str, str]:
    """
    Allow only Chapa test credentials and the official API endpoint.
    Live payment verification is disabled during development.
    """

    secret_key = settings.chapa_secret_key.strip()
    base_url = settings.chapa_base_url.rstrip("/")
    mode = settings.chapa_mode.strip().lower()

    if not secret_key:
        raise ChapaVerificationConfigurationError(
            "Chapa secret key is not configured."
        )

    if mode not in {"test", "live"}:
        raise ChapaVerificationConfigurationError(
            "Chapa mode must be test or live."
        )

    if mode == "test" and not secret_key.startswith("CHASECK_TEST"):
        raise ChapaVerificationConfigurationError(
            "A Chapa test secret key is required."
        )
    if mode == "live" and secret_key.startswith("CHASECK_TEST"):
        raise ChapaVerificationConfigurationError(
            "A test secret key cannot be used in live mode."
        )

    parsed = urlparse(base_url)

    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.chapa.co"
        or parsed.path.rstrip("/") != "/v1"
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ChapaVerificationConfigurationError(
            "Chapa base URL must be https://api.chapa.co/v1."
        )

    return secret_key, base_url

def _parse_amount(value: Any) -> Decimal:
    """Convert a provider amount safely into Decimal."""

    if isinstance(value, bool) or value is None:
        raise ChapaVerificationResponseError(
            "Chapa returned an invalid transaction amount."
        )

    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ChapaVerificationResponseError(
            "Chapa returned an invalid transaction amount."
        ) from None

    if not amount.is_finite() or amount <= Decimal("0"):
        raise ChapaVerificationResponseError(
            "Chapa returned a non-positive or invalid amount."
        )

    return amount

def verify_chapa_payment(
    db: Session,
    merchant_order_id: str,
) -> ChapaVerificationResult:
    """
    Independently verify a locally stored payment with Chapa.

    This function:
    - Uses the locally stored merchant transaction reference.
    - Calls Chapa's server-side verification endpoint.
    - Validates transaction reference, amount, currency and mode.
    - Does not trust frontend or callback payment status.
    - Does not update Payment or Order records.
    - Does not create dispense jobs.
    - Does not send motor commands.

    Database fulfillment is deliberately handled by a separate service.
    """

    if not merchant_order_id or not merchant_order_id.strip():
        raise ChapaVerificationNotFoundError(
            "A transaction reference is required."
        )

    secret_key, base_url = _validate_configuration()

    payment = db.scalar(
        select(Payment).where(
            Payment.merchant_order_id == merchant_order_id
        )
    )

    if payment is None:
        raise ChapaVerificationNotFoundError(
            "The payment transaction was not found."
        )

    if payment.provider != "CHAPA":
        raise ChapaVerificationResponseError(
            "The payment provider does not match Chapa."
        )

    payment_mode = getattr(
        payment,
        "provider_mode",
        settings.chapa_mode.strip().lower(),
    )
    configured_mode = settings.chapa_mode.strip().lower()
    if payment_mode != configured_mode:
        raise ChapaVerificationConfigurationError(
            "Payment mode does not match the configured Chapa credentials."
        )

    order = db.scalar(
        select(Order).where(Order.id == payment.order_id)
    )

    if order is None:
        raise ChapaVerificationResponseError(
            "The payment's associated order was not found."
        )

    # An already verified payment can be returned without another
    # provider request, provided its transaction ID was saved.
    if payment.status == "SUCCESS":
        if not payment.transaction_id:
            raise ChapaVerificationResponseError(
                "A successful payment has no provider transaction ID."
            )

        return ChapaVerificationResult(
            merchant_order_id=payment.merchant_order_id,
            transaction_id=payment.transaction_id,
            amount=payment.amount,
            currency=payment.currency,
            provider_status="success",
            mode=payment_mode,
        )

    if payment.status != "PENDING":
        raise ChapaVerificationResponseError(
            f"Payment status {payment.status!r} is not eligible "
            "for verification."
        )

    endpoint = (
        f"{base_url}/transaction/verify/"
        f"{payment.merchant_order_id}"
    )

    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                endpoint,
                headers=headers,
            )
    except httpx.RequestError as exc:
        raise ChapaVerificationError(
            "Could not reach Chapa. The payment remains unresolved; "
            "do not create another payment attempt."
        ) from exc

    # Parse the response body before classifying HTTP 404.
    # Chapa can use HTTP 404 for both unpaid and invalid transactions.
    try:
        response_data_value = response.json()
    except ValueError as exc:
        if response.status_code == 404:
            raise ChapaVerificationResponseError(
                "Chapa returned HTTP 404 with invalid JSON. "
                "The payment remains unresolved."
            ) from exc

        if response.is_success:
            raise ChapaVerificationResponseError(
                "Chapa returned invalid JSON."
            ) from exc

        raise ChapaVerificationError(
            f"Chapa verification returned HTTP "
            f"{response.status_code}. The payment remains unresolved."
        ) from exc

    if not isinstance(response_data_value, dict):
        raise ChapaVerificationResponseError(
            "Chapa returned an unexpected response format."
        )

    response_data = cast(dict[str, Any], response_data_value)

    # Classify HTTP 404 using the actual response body.
    if response.status_code == 404:
        response_message = str(
            response_data.get("message", "")
        ).strip().lower()

        response_status = response_data.get("status")

        # Only an explicit unpaid-transaction response is considered pending.
        if (
            response_status is None
            and "payment not paid yet" in response_message
        ):
            raise ChapaVerificationPendingError(
                "Chapa has not confirmed payment yet."
            )

        # Invalid references and ambiguous 404 responses are not pending.
        # They remain unresolved and cannot authorize dispensing.
        raise ChapaVerificationResponseError(
            "Chapa returned HTTP 404 for this transaction. "
            "The reference may be invalid or the response is "
            "ambiguous. The payment remains unresolved."
        )

    if not response.is_success:
        raise ChapaVerificationError(
            f"Chapa verification returned HTTP "
            f"{response.status_code}. The payment remains unresolved."
        )

    provider_status = str(
        response_data.get("status", "")
    ).strip().lower()

    data_value = response_data.get("data")

    if not isinstance(data_value, dict):
        raise ChapaVerificationResponseError(
            "Chapa response did not contain transaction data."
        )

    data = cast(dict[str, Any], data_value)

    transaction_status = str(
        data.get("status", "")
    ).strip().lower()

    if transaction_status == "pending":
        raise ChapaVerificationPendingError(
            "Chapa reports that payment is still pending."
        )

    if transaction_status == "failed":
        raise ChapaVerificationFailedError(
            "Chapa explicitly reports that this payment failed."
        )

    if provider_status != "success" or transaction_status != "success":
        raise ChapaVerificationResponseError(
            "Chapa did not provide a confirmed successful transaction."
        )

    returned_tx_ref = data.get("tx_ref")

    if not isinstance(returned_tx_ref, str):
        raise ChapaVerificationResponseError(
            "Chapa response is missing the transaction reference."
        )

    if returned_tx_ref != payment.merchant_order_id:
        raise ChapaVerificationResponseError(
            "Chapa transaction reference does not match the local payment."
        )

    transaction_id = data.get("reference")

    if (
        not isinstance(transaction_id, str)
        or not transaction_id.strip()
    ):
        raise ChapaVerificationResponseError(
            "Chapa response is missing its provider transaction ID."
        )

    verified_amount = _parse_amount(data.get("amount"))

    if verified_amount != payment.amount:
        raise ChapaVerificationResponseError(
            "Verified payment amount does not match the local payment."
        )

    if verified_amount != order.total_amount:
        raise ChapaVerificationResponseError(
            "Verified payment amount does not match the order total."
        )

    returned_currency = str(
        data.get("currency", "")
    ).strip().upper()

    if (
        returned_currency != payment.currency.upper()
        or returned_currency != order.currency.upper()
    ):
        raise ChapaVerificationResponseError(
            "Verified payment currency does not match the order."
        )

    returned_mode = str(
        data.get("mode", "")
    ).strip().lower()

    if returned_mode != payment_mode:
        raise ChapaVerificationResponseError(
            "The verified transaction mode does not match the payment attempt."
        )

    return ChapaVerificationResult(
        merchant_order_id=payment.merchant_order_id,
        transaction_id=transaction_id.strip(),
        amount=verified_amount,
        currency=returned_currency,
        provider_status=transaction_status,
        mode=returned_mode,
    )


from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services import payment_fulfillment_service as service
from app.services.chapa_verification_service import ChapaVerificationResult


@pytest.fixture
def verification() -> ChapaVerificationResult:
    return ChapaVerificationResult(
        merchant_order_id="VEND-TEST-123",
        transaction_id="CHAPA-REFERENCE-456",
        amount=Decimal("100.00"),
        currency="ETB",
        provider_status="success",
        mode="test",
    )

@pytest.fixture
def payment() -> SimpleNamespace:
    return SimpleNamespace(
        id="payment-test-id",
        order_id="order-test-id",
        provider="CHAPA",
        merchant_order_id="VEND-TEST-123",
        transaction_id=None,
        amount=Decimal("100.00"),
        currency="ETB",
        status="PENDING",
        paid_at=None,
    )

@pytest.fixture
def order() -> SimpleNamespace:
    return SimpleNamespace(
        id="order-test-id",
        machine_id="machine-test-id",
        total_amount=Decimal("100.00"),
        currency="ETB",
        status="PENDING_PAYMENT",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        paid_at=None,
    )

@pytest.fixture
def order_item() -> SimpleNamespace:
    return SimpleNamespace(
        id="item-test-id",
        order_id="order-test-id",
        product_id="product-test-id",
        machine_slot_id="slot-test-id",
        quantity=1,
        line_total=Decimal("100.00"),
    )

@pytest.fixture
def machine_slot() -> SimpleNamespace:
    return SimpleNamespace(
        id="slot-test-id",
        machine_id="machine-test-id",
        product_id="product-test-id",
        is_active=True,
        motor_channel=1,
    )

@pytest.fixture
def inventory() -> SimpleNamespace:
    return SimpleNamespace(
        machine_slot_id="slot-test-id",
        quantity=10,
        reserved_quantity=1,
    )

@pytest.fixture
def mock_database() -> MagicMock:
    return MagicMock()

def configure_database(
    db: MagicMock,
    payment: SimpleNamespace,
    order: SimpleNamespace,
    items: list[SimpleNamespace],
    slots: list[SimpleNamespace] | None = None,
    inventories: list[SimpleNamespace] | None = None,
    existing_jobs: list[object] | None = None,
) -> None:
    """
    Configure the mocked SQLAlchemy Session.

    scalar() returns payment, order, then each slot and inventory.
    scalars() returns order items, or existing jobs and items
    for the idempotency test.
    """

    scalar_results: list[object] = [payment, order]

    for index, slot in enumerate(slots or []):
        scalar_results.append(slot)

        if inventories is not None:
            scalar_results.append(inventories[index])

    db.scalar.side_effect = scalar_results

    result_objects = [
        SimpleNamespace(all=MagicMock(return_value=items))
    ]

    if existing_jobs is not None:
        result_objects = [
            SimpleNamespace(all=MagicMock(return_value=existing_jobs)),
            SimpleNamespace(all=MagicMock(return_value=items)),
        ]

    db.scalars.side_effect = result_objects

def test_successful_payment_creates_one_job_per_item(
    monkeypatch: pytest.MonkeyPatch,
    mock_database: MagicMock,
    payment: SimpleNamespace,
    order: SimpleNamespace,
    order_item: SimpleNamespace,
    machine_slot: SimpleNamespace,
    inventory: SimpleNamespace,
    verification: ChapaVerificationResult,
) -> None:
    configure_database(
        mock_database,
        payment,
        order,
        [order_item],
        [machine_slot],
        [inventory],
    )

    fixed_now = datetime.now(timezone.utc)
    monkeypatch.setattr(service, "_utc_now", lambda: fixed_now)

    result = service.fulfill_verified_chapa_payment(
        mock_database,
        verification,
    )

    assert result.payment_status == "SUCCESS"
    assert result.order_status == "PAID"
    assert result.dispense_jobs_created == 1
    assert result.requires_manual_review is False

    assert payment.status == "SUCCESS"
    assert payment.transaction_id == "CHAPA-REFERENCE-456"
    assert payment.paid_at == fixed_now

    assert order.status == "PAID"
    assert order.paid_at == fixed_now

    assert mock_database.add.call_count == 1
    mock_database.flush.assert_called_once()
    mock_database.commit.assert_called_once()

    # Physical inventory must not be reduced here.
    assert inventory.quantity == 10
    assert inventory.reserved_quantity == 1

def test_repeated_fulfillment_does_not_create_duplicate_jobs(
    mock_database: MagicMock,
    payment: SimpleNamespace,
    order: SimpleNamespace,
    order_item: SimpleNamespace,
    verification: ChapaVerificationResult,
) -> None:
    payment.status = "SUCCESS"
    payment.transaction_id = "CHAPA-REFERENCE-456"
    order.status = "PAID"

    existing_job = SimpleNamespace(id="existing-job-id")

    configure_database(
        mock_database,
        payment,
        order,
        [order_item],
        existing_jobs=[existing_job],
    )

    result = service.fulfill_verified_chapa_payment(
        mock_database,
        verification,
    )

    assert result.payment_status == "SUCCESS"
    assert result.order_status == "PAID"
    assert result.dispense_jobs_created == 0
    assert result.requires_manual_review is False

    mock_database.add.assert_not_called()
    mock_database.commit.assert_not_called()

def test_expired_order_requires_manual_review(
    monkeypatch: pytest.MonkeyPatch,
    mock_database: MagicMock,
    payment: SimpleNamespace,
    order: SimpleNamespace,
    order_item: SimpleNamespace,
    verification: ChapaVerificationResult,
) -> None:
    fixed_now = datetime.now(timezone.utc)

    order.expires_at = fixed_now - timedelta(minutes=1)

    configure_database(
        mock_database,
        payment,
        order,
        [order_item],
    )

    monkeypatch.setattr(service, "_utc_now", lambda: fixed_now)

    result = service.fulfill_verified_chapa_payment(
        mock_database,
        verification,
    )

    assert result.payment_status == "SUCCESS"
    assert result.order_status == "PAYMENT_REVIEW"
    assert result.dispense_jobs_created == 0
    assert result.requires_manual_review is True

    assert payment.status == "SUCCESS"
    assert order.status == "PAYMENT_REVIEW"

    mock_database.add.assert_not_called()
    mock_database.commit.assert_called_once()

def test_amount_mismatch_is_rejected(
    mock_database: MagicMock,
    payment: SimpleNamespace,
    order: SimpleNamespace,
    verification: ChapaVerificationResult,
) -> None:
    verification = ChapaVerificationResult(
        merchant_order_id="VEND-TEST-123",
        transaction_id="CHAPA-REFERENCE-456",
        amount=Decimal("200.00"),
        currency="ETB",
        provider_status="success",
        mode="test",
    )

    configure_database(
        mock_database,
        payment,
        order,
        [],
    )

    with pytest.raises(service.PaymentFulfillmentMismatchError):
        service.fulfill_verified_chapa_payment(
            mock_database,
            verification,
        )

    assert payment.status == "PENDING"
    assert order.status == "PENDING_PAYMENT"

    mock_database.add.assert_not_called()
    mock_database.commit.assert_not_called()
    mock_database.rollback.assert_called_once()

def test_wrong_provider_is_rejected(
    mock_database: MagicMock,
    payment: SimpleNamespace,
    order: SimpleNamespace,
    verification: ChapaVerificationResult,
) -> None:
    payment.provider = "OTHER_PROVIDER"

    configure_database(
        mock_database,
        payment,
        order,
        [],
    )

    with pytest.raises(service.PaymentFulfillmentMismatchError):
        service.fulfill_verified_chapa_payment(
            mock_database,
            verification,
        )

    mock_database.add.assert_not_called()
    mock_database.commit.assert_not_called()
    mock_database.rollback.assert_called_once()

def test_insufficient_reserved_inventory_requires_manual_review(
    mock_database: MagicMock,
    payment: SimpleNamespace,
    order: SimpleNamespace,
    order_item: SimpleNamespace,
    machine_slot: SimpleNamespace,
    inventory: SimpleNamespace,
    verification: ChapaVerificationResult,
) -> None:
    inventory.reserved_quantity = 0

    configure_database(
        mock_database,
        payment,
        order,
        [order_item],
        [machine_slot],
        [inventory],
    )

    result = service.fulfill_verified_chapa_payment(
        mock_database,
        verification,
    )

    assert result.payment_status == "SUCCESS"
    assert result.order_status == "PAYMENT_REVIEW"
    assert result.dispense_jobs_created == 0
    assert result.requires_manual_review is True
    assert payment.status == "SUCCESS"
    assert order.status == "PAYMENT_REVIEW"

    mock_database.add.assert_not_called()
    mock_database.commit.assert_called_once()
    mock_database.rollback.assert_called_once()

def test_invalid_motor_channel_requires_manual_review(
    mock_database: MagicMock,
    payment: SimpleNamespace,
    order: SimpleNamespace,
    order_item: SimpleNamespace,
    machine_slot: SimpleNamespace,
    inventory: SimpleNamespace,
    verification: ChapaVerificationResult,
) -> None:
    machine_slot.motor_channel = 7

    configure_database(
        mock_database,
        payment,
        order,
        [order_item],
        [machine_slot],
        [inventory],
    )

    result = service.fulfill_verified_chapa_payment(
        mock_database,
        verification,
    )

    assert result.payment_status == "SUCCESS"
    assert result.order_status == "PAYMENT_REVIEW"
    assert result.dispense_jobs_created == 0
    assert result.requires_manual_review is True
    assert payment.status == "SUCCESS"
    assert order.status == "PAYMENT_REVIEW"

    mock_database.add.assert_not_called()
    mock_database.commit.assert_called_once()
    mock_database.rollback.assert_called_once()

def test_non_successful_verification_is_rejected(
    mock_database: MagicMock,
    verification: ChapaVerificationResult,
) -> None:
    verification = ChapaVerificationResult(
        merchant_order_id="VEND-TEST-123",
        transaction_id="CHAPA-REFERENCE-456",
        amount=Decimal("100.00"),
        currency="ETB",
        provider_status="pending",
        mode="test",
    )

    with pytest.raises(service.PaymentFulfillmentMismatchError):
        service.fulfill_verified_chapa_payment(
            mock_database,
            verification,
        )

    mock_database.scalar.assert_not_called()
    mock_database.add.assert_not_called()
    mock_database.commit.assert_not_called()

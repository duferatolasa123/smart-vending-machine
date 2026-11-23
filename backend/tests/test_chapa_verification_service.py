
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any, Self, cast
from unittest.mock import MagicMock

import pytest
from app.services import chapa_verification_service as service


@pytest.fixture
def payment_and_order() -> tuple[SimpleNamespace, SimpleNamespace]:
    payment = SimpleNamespace(
        id="payment-test-id",
        order_id="order-test-id",
        provider="CHAPA",
        merchant_order_id="VEND-TEST-123",
        transaction_id=None,
        amount=Decimal("100.00"),
        currency="ETB",
        status="PENDING",
    )

    order = SimpleNamespace(
        id="order-test-id",
        total_amount=Decimal("100.00"),
        currency="ETB",
    )

    return payment, order

@pytest.fixture
def mock_database(
    payment_and_order: tuple[SimpleNamespace, SimpleNamespace],
) -> MagicMock:
    payment, order = payment_and_order

    db = MagicMock()
    db.scalar.side_effect = [payment, order]

    return db

class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self.is_success = 200 <= status_code < 300
        self.payload = payload

    def json(self) -> dict[str, Any]:
        return self.payload

class FakeHttpClient:
    def __init__(
        self,
        response: FakeResponse,
        captured_request: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.response = response
        self.captured_request = captured_request

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> bool:
        return False

    def get(self, url: str, headers: dict[str, str]) -> FakeResponse:
        if self.captured_request is not None:
            self.captured_request["url"] = url
            self.captured_request["headers"] = headers

        return self.response

def install_fake_chapa(
    monkeypatch: pytest.MonkeyPatch,
    response: FakeResponse,
    captured_request: dict[str, Any] | None = None,
) -> None:
    monkeypatch.setattr(
        service,
        "_validate_configuration",
        lambda: (
            "CHASECK_TEST_FAKE_KEY",
            "https://api.chapa.co/v1",
        ),
    )

    def fake_client_factory(**kwargs: Any) -> FakeHttpClient:
        return FakeHttpClient(response, captured_request, **kwargs)

    monkeypatch.setattr(
        service.httpx,
        "Client",
        cast(Any, fake_client_factory),
    )

def successful_response() -> FakeResponse:
    return FakeResponse(
        200,
        {
            "status": "success",
            "message": "Verified",
            "data": {
                "status": "success",
                "tx_ref": "VEND-TEST-123",
                "reference": "CHAPA-REFERENCE-456",
                "amount": "100.00",
                "currency": "ETB",
                "mode": "test",
            },
        },
    )

def test_successful_payment_verification(
    monkeypatch: pytest.MonkeyPatch,
    mock_database: MagicMock,
) -> None:
    install_fake_chapa(monkeypatch, successful_response())

    result = service.verify_chapa_payment(
        mock_database,
        "VEND-TEST-123",
    )

    assert result.merchant_order_id == "VEND-TEST-123"
    assert result.transaction_id == "CHAPA-REFERENCE-456"
    assert result.amount == Decimal("100.00")
    assert result.currency == "ETB"
    assert result.provider_status == "success"
    assert result.mode == "test"

    # Verification must not modify database records.
    mock_database.commit.assert_not_called()
    mock_database.flush.assert_not_called()

def test_pending_payment_is_not_marked_failed(
    monkeypatch: pytest.MonkeyPatch,
    mock_database: MagicMock,
) -> None:
    response = FakeResponse(
        200,
        {
            "status": "success",
            "data": {
                "status": "pending",
                "tx_ref": "VEND-TEST-123",
            },
        },
    )

    install_fake_chapa(monkeypatch, response)

    with pytest.raises(service.ChapaVerificationPendingError):
        service.verify_chapa_payment(
            mock_database,
            "VEND-TEST-123",
        )

    mock_database.commit.assert_not_called()
    mock_database.flush.assert_not_called()

def test_http_404_payment_not_paid_yet_is_pending(
    monkeypatch: pytest.MonkeyPatch,
    mock_database: MagicMock,
) -> None:
    response = FakeResponse(
        404,
        {
            "status": None,
            "message": "Payment not paid yet",
        },
    )

    install_fake_chapa(monkeypatch, response)

    with pytest.raises(service.ChapaVerificationPendingError):
        service.verify_chapa_payment(
            mock_database,
            "VEND-TEST-123",
        )

    mock_database.commit.assert_not_called()
    mock_database.flush.assert_not_called()

def test_http_404_invalid_transaction_is_not_pending(
    monkeypatch: pytest.MonkeyPatch,
    mock_database: MagicMock,
) -> None:
    response = FakeResponse(
        404,
        {
            "status": "failed",
            "message": "Transaction not found",
        },
    )

    install_fake_chapa(monkeypatch, response)

    with pytest.raises(service.ChapaVerificationResponseError):
        service.verify_chapa_payment(
            mock_database,
            "VEND-TEST-123",
        )

    mock_database.commit.assert_not_called()
    mock_database.flush.assert_not_called()

def test_http_404_ambiguous_response_is_not_pending(
    monkeypatch: pytest.MonkeyPatch,
    mock_database: MagicMock,
) -> None:
    response = FakeResponse(
        404,
        {
            "status": "failed",
        },
    )

    install_fake_chapa(monkeypatch, response)

    with pytest.raises(service.ChapaVerificationResponseError):
        service.verify_chapa_payment(
            mock_database,
            "VEND-TEST-123",
        )

    mock_database.commit.assert_not_called()
    mock_database.flush.assert_not_called()

def test_explicit_failed_payment(
    monkeypatch: pytest.MonkeyPatch,
    mock_database: MagicMock,
) -> None:
    response = FakeResponse(
        200,
        {
            "status": "success",
            "data": {
                "status": "failed",
                "tx_ref": "VEND-TEST-123",
            },
        },
    )

    install_fake_chapa(monkeypatch, response)

    with pytest.raises(service.ChapaVerificationFailedError):
        service.verify_chapa_payment(
            mock_database,
            "VEND-TEST-123",
        )

    mock_database.commit.assert_not_called()
    mock_database.flush.assert_not_called()

def test_amount_mismatch_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    mock_database: MagicMock,
) -> None:
    response = FakeResponse(
        200,
        {
            "status": "success",
            "data": {
                "status": "success",
                "tx_ref": "VEND-TEST-123",
                "reference": "CHAPA-REFERENCE-456",
                "amount": "50.00",
                "currency": "ETB",
                "mode": "test",
            },
        },
    )

    install_fake_chapa(monkeypatch, response)

    with pytest.raises(service.ChapaVerificationResponseError):
        service.verify_chapa_payment(
            mock_database,
            "VEND-TEST-123",
        )

    mock_database.commit.assert_not_called()
    mock_database.flush.assert_not_called()

def test_currency_mismatch_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    mock_database: MagicMock,
) -> None:
    response = FakeResponse(
        200,
        {
            "status": "success",
            "data": {
                "status": "success",
                "tx_ref": "VEND-TEST-123",
                "reference": "CHAPA-REFERENCE-456",
                "amount": "100.00",
                "currency": "USD",
                "mode": "test",
            },
        },
    )

    install_fake_chapa(monkeypatch, response)

    with pytest.raises(service.ChapaVerificationResponseError):
        service.verify_chapa_payment(
            mock_database,
            "VEND-TEST-123",
        )

    mock_database.commit.assert_not_called()
    mock_database.flush.assert_not_called()

def test_transaction_reference_mismatch_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    mock_database: MagicMock,
) -> None:
    response = FakeResponse(
        200,
        {
            "status": "success",
            "data": {
                "status": "success",
                "tx_ref": "ANOTHER-TRANSACTION",
                "reference": "CHAPA-REFERENCE-456",
                "amount": "100.00",
                "currency": "ETB",
                "mode": "test",
            },
        },
    )

    install_fake_chapa(monkeypatch, response)

    with pytest.raises(service.ChapaVerificationResponseError):
        service.verify_chapa_payment(
            mock_database,
            "VEND-TEST-123",
        )

    mock_database.commit.assert_not_called()
    mock_database.flush.assert_not_called()

def test_live_mode_transaction_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    mock_database: MagicMock,
) -> None:
    response = FakeResponse(
        200,
        {
            "status": "success",
            "data": {
                "status": "success",
                "tx_ref": "VEND-TEST-123",
                "reference": "CHAPA-REFERENCE-456",
                "amount": "100.00",
                "currency": "ETB",
                "mode": "live",
            },
        },
    )

    install_fake_chapa(monkeypatch, response)

    with pytest.raises(service.ChapaVerificationResponseError):
        service.verify_chapa_payment(
            mock_database,
            "VEND-TEST-123",
        )

    mock_database.commit.assert_not_called()
    mock_database.flush.assert_not_called()

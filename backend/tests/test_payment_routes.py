import hashlib
import hmac
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.routers import payments
from app.schemas.payment import PaymentStatusResponse


def test_chapa_webhook_rejects_invalid_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "chapa_webhook_secret", "test-webhook-secret")
    body = json.dumps({"event": "charge.success", "tx_ref": "VEND-123"})

    response = TestClient(app).post(
        "/api/payments/chapa/webhook",
        content=body,
        headers={"x-chapa-signature": "invalid"},
    )

    assert response.status_code == 401


def test_chapa_webhook_reconciles_valid_success_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "test-webhook-secret"
    order_id = uuid4()
    event = {"event": "charge.success", "tx_ref": "VEND-123"}
    body = json.dumps(event, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    monkeypatch.setattr(settings, "chapa_webhook_secret", secret)
    monkeypatch.setattr(
        payments,
        "_reconcile_payment",
        lambda _db, _reference: PaymentStatusResponse(
            order_id=order_id,
            payment_status="SUCCESS",
            order_status="PAID",
            paid=True,
        ),
    )

    response = TestClient(app).post(
        "/api/payments/chapa/webhook",
        content=body,
        headers={"x-chapa-signature": signature},
    )

    assert response.status_code == 200
    assert response.json() == {
        "received": True,
        "processed": True,
        "payment_status": "SUCCESS",
        "order_status": "PAID",
    }

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class FakeYooKassaClient:
    def __init__(self) -> None:
        self.payments: dict[str, dict] = {}

    async def create_payment(self, **kwargs):
        provider_id = f"pay_{len(self.payments) + 1}"
        status = "waiting_for_capture" if not kwargs["capture"] else "pending"
        payment_method = None
        if kwargs.get("save_payment_method"):
            payment_method = {
                "type": "bank_card",
                "id": "pm_saved_123",
                "saved": True,
                "card": {"last4": "1111", "card_type": "Visa"},
            }
        payload = {
            "id": provider_id,
            "status": status,
            "confirmation": {"confirmation_url": f"https://pay.example/{provider_id}"},
            "payment_method": payment_method,
        }
        self.payments[provider_id] = payload
        return payload

    async def get_payment(self, provider_payment_id: str):
        payment = dict(self.payments[provider_payment_id])
        payment["status"] = "succeeded"
        payment["payment_method"] = {
            "type": "bank_card",
            "id": "pm_saved_123",
            "saved": True,
            "card": {"last4": "1111", "card_type": "Visa"},
        }
        self.payments[provider_payment_id] = payment
        return payment

    async def capture_payment(self, provider_payment_id: str, idempotence_key: str):
        self.payments[provider_payment_id]["status"] = "succeeded"
        return self.payments[provider_payment_id]

    async def cancel_payment(self, provider_payment_id: str, idempotence_key: str):
        self.payments[provider_payment_id]["status"] = "canceled"
        return self.payments[provider_payment_id]

    async def create_refund(self, **kwargs):
        return {"id": "refund_1", "status": "succeeded"}


def make_client(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'test.sqlite3'}")
    app = create_app(settings, yookassa_client=FakeYooKassaClient())
    return TestClient(app)


def test_create_payment_with_idempotence_and_saved_method(tmp_path):
    client = make_client(tmp_path)
    response = client.post(
        "/api/payments",
        json={
            "order_id": "order-100",
            "user_id": "user-1",
            "amount": {"value": "990.00", "currency": "RUB"},
            "capture": False,
            "save_payment_method": True,
            "description": "Test order",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["order_id"] == "order-100"
    assert body["provider_payment_id"] == "pay_1"
    assert body["status"] == "waiting_for_capture"
    assert body["payment_method_id"] == "pm_saved_123"
    assert "pay_1" in body["confirmation_url"]


def test_webhook_is_idempotent_and_verifies_actual_status(tmp_path):
    client = make_client(tmp_path)
    created = client.post(
        "/api/payments",
        json={
            "order_id": "order-101",
            "user_id": "user-1",
            "amount": {"value": "100.00", "currency": "RUB"},
        },
    ).json()

    payload = {"event": "payment.succeeded", "object": {"id": created["provider_payment_id"]}}
    first = client.post("/api/webhooks/yookassa", json=payload)
    second = client.post("/api/webhooks/yookassa", json=payload)

    assert first.status_code == 200
    assert first.json()["processed"] is True
    assert first.json()["status"] == "succeeded"
    assert second.status_code == 200
    assert second.json()["duplicate"] is True


def test_refund_uses_separate_refund_entity(tmp_path):
    client = make_client(tmp_path)
    created = client.post(
        "/api/payments",
        json={
            "order_id": "order-102",
            "user_id": "user-2",
            "amount": {"value": "500.00", "currency": "RUB"},
        },
    ).json()

    response = client.post(
        f"/api/payments/{created['id']}/refunds",
        json={"amount": {"value": str(Decimal("100.00")), "currency": "RUB"}, "reason": "partial refund"},
    )

    assert response.status_code == 201
    assert response.json()["provider_refund_id"] == "refund_1"
    assert response.json()["status"] == "succeeded"


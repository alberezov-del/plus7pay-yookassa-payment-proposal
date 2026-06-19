from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, Payment, PaymentMethod, PaymentStatus, Refund, RefundStatus, WebhookEvent
from app.schemas import PaymentCreate, RecurringPaymentCreate, RefundCreate
from app.security import mask_sensitive, new_idempotence_key, stable_payload_hash
from app.yookassa_client import YooKassaClient


def _confirmation_url(provider_payment: dict[str, Any]) -> str | None:
    confirmation = provider_payment.get("confirmation") or {}
    return confirmation.get("confirmation_url")


def _save_payment_method_if_available(db: Session, payment: Payment, provider_payment: dict[str, Any]) -> None:
    method = provider_payment.get("payment_method") or {}
    if not method.get("id") or not method.get("saved"):
        return

    card = method.get("card") or {}
    existing = db.scalar(
        select(PaymentMethod).where(
            PaymentMethod.user_id == payment.user_id,
            PaymentMethod.provider_payment_method_id == method["id"],
        )
    )
    if existing:
        existing.active = True
        existing.saved = bool(method.get("saved"))
    else:
        db.add(
            PaymentMethod(
                user_id=payment.user_id,
                provider_payment_method_id=method["id"],
                payment_type=method.get("type"),
                card_last4=card.get("last4"),
                card_brand=card.get("card_type") or card.get("issuer_name"),
                saved=bool(method.get("saved")),
            )
        )
    payment.payment_method_id = method["id"]


def _write_audit(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | int,
    actor_id: str | None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditEvent(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            actor_id=actor_id,
            details_json=json.dumps(mask_sensitive(details or {}), ensure_ascii=False, sort_keys=True),
        )
    )


def _ensure_status(payment: Payment, allowed: set[str], action: str) -> None:
    if payment.status not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(
            f"Нельзя выполнить действие '{action}' для платежа в статусе "
            f"'{payment.status}'. Разрешенные статусы: {allowed_text}"
        )


class PaymentService:
    def __init__(self, db: Session, yookassa: YooKassaClient):
        self.db = db
        self.yookassa = yookassa

    async def create_payment(self, data: PaymentCreate, idempotence_key: str | None = None) -> Payment:
        idempotence_key = idempotence_key or new_idempotence_key(f"payment:{data.order_id}")
        existing = self.db.scalar(select(Payment).where(Payment.idempotence_key == idempotence_key))
        if existing:
            return existing

        payment = Payment(
            order_id=data.order_id,
            user_id=data.user_id,
            amount_value=data.amount.value,
            currency=data.amount.currency,
            capture=data.capture,
            save_payment_method=data.save_payment_method,
            idempotence_key=idempotence_key,
        )
        self.db.add(payment)
        self.db.flush()
        _write_audit(
            self.db,
            action="payment.local_created",
            entity_type="payment",
            entity_id=payment.id,
            actor_id=data.user_id,
            details={"order_id": data.order_id, "amount": str(data.amount.value), "capture": data.capture},
        )

        provider_payment = await self.yookassa.create_payment(
            amount_value=data.amount.value,
            currency=data.amount.currency,
            capture=data.capture,
            description=data.description,
            save_payment_method=data.save_payment_method,
            idempotence_key=idempotence_key,
            metadata={"order_id": data.order_id, "user_id": data.user_id},
        )
        self._apply_provider_payment(payment, provider_payment)
        _write_audit(
            self.db,
            action="payment.provider_created",
            entity_type="payment",
            entity_id=payment.id,
            actor_id=data.user_id,
            details={"provider_payment_id": payment.provider_payment_id, "status": payment.status},
        )
        return payment

    async def create_recurring_payment(
        self,
        data: RecurringPaymentCreate,
        idempotence_key: str | None = None,
    ) -> Payment:
        idempotence_key = idempotence_key or new_idempotence_key(f"recurring:{data.order_id}")
        existing = self.db.scalar(select(Payment).where(Payment.idempotence_key == idempotence_key))
        if existing:
            return existing

        payment = Payment(
            order_id=data.order_id,
            user_id=data.user_id,
            amount_value=data.amount.value,
            currency=data.amount.currency,
            capture=True,
            save_payment_method=False,
            payment_method_id=data.payment_method_id,
            idempotence_key=idempotence_key,
        )
        self.db.add(payment)
        self.db.flush()
        _write_audit(
            self.db,
            action="recurring.local_created",
            entity_type="payment",
            entity_id=payment.id,
            actor_id=data.user_id,
            details={"order_id": data.order_id, "payment_method_id": data.payment_method_id},
        )

        provider_payment = await self.yookassa.create_payment(
            amount_value=data.amount.value,
            currency=data.amount.currency,
            capture=True,
            description=data.description,
            payment_method_id=data.payment_method_id,
            idempotence_key=idempotence_key,
            metadata={"order_id": data.order_id, "user_id": data.user_id, "recurring": True},
        )
        self._apply_provider_payment(payment, provider_payment)
        _write_audit(
            self.db,
            action="recurring.provider_created",
            entity_type="payment",
            entity_id=payment.id,
            actor_id=data.user_id,
            details={"provider_payment_id": payment.provider_payment_id, "status": payment.status},
        )
        return payment

    async def capture(self, payment: Payment, idempotence_key: str | None = None) -> Payment:
        if not payment.provider_payment_id:
            raise ValueError("У платежа нет provider_payment_id")
        _ensure_status(payment, {PaymentStatus.waiting_for_capture.value}, "capture")
        provider_payment = await self.yookassa.capture_payment(
            payment.provider_payment_id,
            idempotence_key or new_idempotence_key(f"capture:{payment.order_id}"),
        )
        self._apply_provider_payment(payment, provider_payment)
        _write_audit(
            self.db,
            action="payment.captured",
            entity_type="payment",
            entity_id=payment.id,
            actor_id=payment.user_id,
            details={"provider_payment_id": payment.provider_payment_id, "status": payment.status},
        )
        return payment

    async def cancel(self, payment: Payment, idempotence_key: str | None = None) -> Payment:
        if not payment.provider_payment_id:
            raise ValueError("У платежа нет provider_payment_id")
        _ensure_status(
            payment,
            {PaymentStatus.pending.value, PaymentStatus.waiting_for_capture.value},
            "cancel",
        )
        provider_payment = await self.yookassa.cancel_payment(
            payment.provider_payment_id,
            idempotence_key or new_idempotence_key(f"cancel:{payment.order_id}"),
        )
        self._apply_provider_payment(payment, provider_payment)
        _write_audit(
            self.db,
            action="payment.canceled",
            entity_type="payment",
            entity_id=payment.id,
            actor_id=payment.user_id,
            details={"provider_payment_id": payment.provider_payment_id, "status": payment.status},
        )
        return payment

    async def refund(
        self,
        payment: Payment,
        data: RefundCreate,
        idempotence_key: str | None = None,
    ) -> Refund:
        if not payment.provider_payment_id:
            raise ValueError("У платежа нет provider_payment_id")
        _ensure_status(payment, {PaymentStatus.succeeded.value, PaymentStatus.refunded.value}, "refund")
        idempotence_key = idempotence_key or new_idempotence_key(f"refund:{payment.order_id}")
        existing = self.db.scalar(select(Refund).where(Refund.idempotence_key == idempotence_key))
        if existing:
            return existing

        refund = Refund(
            payment_id=payment.id,
            amount_value=data.amount.value,
            currency=data.amount.currency,
            idempotence_key=idempotence_key,
        )
        self.db.add(refund)
        self.db.flush()
        _write_audit(
            self.db,
            action="refund.local_created",
            entity_type="refund",
            entity_id=refund.id,
            actor_id=payment.user_id,
            details={"payment_id": payment.id, "amount": str(data.amount.value)},
        )

        provider_refund = await self.yookassa.create_refund(
            provider_payment_id=payment.provider_payment_id,
            amount_value=data.amount.value,
            currency=data.amount.currency,
            idempotence_key=idempotence_key,
            description=data.reason,
        )
        refund.provider_refund_id = provider_refund.get("id")
        refund.status = provider_refund.get("status", RefundStatus.pending.value)
        _write_audit(
            self.db,
            action="refund.provider_created",
            entity_type="refund",
            entity_id=refund.id,
            actor_id=payment.user_id,
            details={"provider_refund_id": refund.provider_refund_id, "status": refund.status},
        )
        return refund

    async def handle_webhook(self, payload: dict[str, Any]) -> tuple[bool, bool, Payment | None]:
        event_type = payload.get("event", "unknown")
        provider_object = payload.get("object") or {}
        provider_payment_id = provider_object.get("id")
        if not provider_payment_id:
            raise ValueError("В webhook нет object.id")

        payload_hash = stable_payload_hash(payload)
        existing_event = self.db.scalar(select(WebhookEvent).where(WebhookEvent.payload_hash == payload_hash))
        if existing_event:
            return False, True, None

        event = WebhookEvent(
            event_type=event_type,
            provider_object_id=provider_payment_id,
            payload_hash=payload_hash,
        )
        self.db.add(event)
        self.db.flush()

        payment = self.db.scalar(select(Payment).where(Payment.provider_payment_id == provider_payment_id))
        if payment:
            actual_payment = await self.yookassa.get_payment(provider_payment_id)
            old_status = payment.status
            self._apply_provider_payment(payment, actual_payment)
            event.processed = True
            _write_audit(
                self.db,
                action="webhook.payment_updated",
                entity_type="payment",
                entity_id=payment.id,
                actor_id=None,
                details={
                    "event_type": event_type,
                    "provider_payment_id": provider_payment_id,
                    "old_status": old_status,
                    "new_status": payment.status,
                },
            )
        return True, False, payment

    def _apply_provider_payment(self, payment: Payment, provider_payment: dict[str, Any]) -> None:
        payment.provider_payment_id = provider_payment.get("id", payment.provider_payment_id)
        payment.raw_provider_status = provider_payment.get("status")
        payment.status = provider_payment.get("status", PaymentStatus.pending.value)
        payment.confirmation_url = _confirmation_url(provider_payment)

        if payment.status in {PaymentStatus.succeeded.value, PaymentStatus.waiting_for_capture.value}:
            _save_payment_method_if_available(self.db, payment, provider_payment)

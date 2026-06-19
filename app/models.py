from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class PaymentStatus(str, Enum):
    pending = "pending"
    waiting_for_capture = "waiting_for_capture"
    succeeded = "succeeded"
    canceled = "canceled"
    refunded = "refunded"
    failed = "failed"


class RefundStatus(str, Enum):
    pending = "pending"
    succeeded = "succeeded"
    canceled = "canceled"
    failed = "failed"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(96), unique=True, index=True)
    amount_value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    status: Mapped[str] = mapped_column(String(32), default=PaymentStatus.pending.value, index=True)
    capture: Mapped[bool] = mapped_column(Boolean, default=True)
    save_payment_method: Mapped[bool] = mapped_column(Boolean, default=False)
    idempotence_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    confirmation_url: Mapped[str | None] = mapped_column(Text)
    payment_method_id: Mapped[str | None] = mapped_column(String(96), index=True)
    raw_provider_status: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    refunds: Mapped[list["Refund"]] = relationship(back_populates="payment")


class PaymentMethod(Base):
    __tablename__ = "payment_methods"
    __table_args__ = (UniqueConstraint("user_id", "provider_payment_method_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    provider_payment_method_id: Mapped[str] = mapped_column(String(96), index=True)
    payment_type: Mapped[str | None] = mapped_column(String(32))
    card_last4: Mapped[str | None] = mapped_column(String(4))
    card_brand: Mapped[str | None] = mapped_column(String(32))
    saved: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"))
    provider_refund_id: Mapped[str | None] = mapped_column(String(96), unique=True, index=True)
    amount_value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    status: Mapped[str] = mapped_column(String(32), default=RefundStatus.pending.value, index=True)
    idempotence_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    payment: Mapped[Payment] = relationship(back_populates="refunds")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    provider_object_id: Mapped[str] = mapped_column(String(96), index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(96), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(64), index=True)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

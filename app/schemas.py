from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class Money(BaseModel):
    value: Decimal = Field(gt=0, examples=["990.00"])
    currency: str = Field(default="RUB", min_length=3, max_length=3)


class PaymentCreate(BaseModel):
    order_id: str = Field(min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=64)
    amount: Money
    description: str = Field(default="Оплата заказа", max_length=128)
    capture: bool = True
    save_payment_method: bool = False


class RecurringPaymentCreate(BaseModel):
    order_id: str = Field(min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=64)
    payment_method_id: str = Field(min_length=1, max_length=96)
    amount: Money
    description: str = Field(default="Автосписание по сохраненному платежному методу", max_length=128)


class RefundCreate(BaseModel):
    amount: Money
    reason: str = Field(default="Возврат клиенту", max_length=128)


class PaymentOut(BaseModel):
    id: int
    order_id: str
    user_id: str
    provider_payment_id: str | None
    amount_value: Decimal
    currency: str
    status: str
    capture: bool
    save_payment_method: bool
    payment_method_id: str | None
    confirmation_url: str | None

    model_config = {"from_attributes": True}


class PaymentMethodOut(BaseModel):
    id: int
    user_id: str
    provider_payment_method_id: str
    payment_type: str | None
    card_last4: str | None
    card_brand: str | None
    saved: bool
    active: bool

    model_config = {"from_attributes": True}


class RefundOut(BaseModel):
    id: int
    payment_id: int
    provider_refund_id: str | None
    amount_value: Decimal
    currency: str
    status: str

    model_config = {"from_attributes": True}


class WebhookResult(BaseModel):
    processed: bool
    duplicate: bool = False
    provider_payment_id: str | None = None
    status: str | None = None


class ProviderPayment(BaseModel):
    id: str
    status: str
    paid: bool | None = None
    confirmation: dict[str, Any] | None = None
    payment_method: dict[str, Any] | None = None

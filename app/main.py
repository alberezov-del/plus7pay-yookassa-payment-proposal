from __future__ import annotations

from collections.abc import Generator
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.database import Base, make_engine, make_session_factory, session_scope
from app.models import Payment, PaymentMethod
from app.schemas import (
    PaymentCreate,
    PaymentMethodOut,
    PaymentOut,
    RecurringPaymentCreate,
    RefundCreate,
    RefundOut,
    WebhookResult,
)
from app.services import PaymentService
from app.yookassa_client import YooKassaClient


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: sessionmaker[Session] | None = None,
    yookassa_client: YooKassaClient | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    engine = make_engine(settings.database_url)
    session_factory = session_factory or make_session_factory(settings.database_url)
    yookassa_client = yookassa_client or YooKassaClient(settings)

    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        description=(
            "Демо и техническое предложение платежного бэкенда для интеграции с YooKassa: "
            "платежи, автосписания, холдирование, возвраты, вебхуки и безопасное хранение."
        ),
    )

    Base.metadata.create_all(bind=engine)

    def get_db() -> Generator[Session, None, None]:
        yield from session_scope(session_factory)

    def get_service(db: Session = Depends(get_db)) -> PaymentService:
        return PaymentService(db, yookassa_client)

    def get_payment_or_404(payment_id: int, db: Session = Depends(get_db)) -> Payment:
        payment = db.get(Payment, payment_id)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Платеж не найден")
        return payment

    @app.get("/health", summary="Проверить состояние сервиса")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/api/payments",
        response_model=PaymentOut,
        status_code=status.HTTP_201_CREATED,
        summary="Создать платеж",
    )
    async def create_payment(
        data: PaymentCreate,
        idempotence_key: str | None = Header(default=None, alias="Idempotence-Key"),
        service: PaymentService = Depends(get_service),
    ):
        return await service.create_payment(data, idempotence_key=idempotence_key)

    @app.post(
        "/api/payments/recurring",
        response_model=PaymentOut,
        status_code=status.HTTP_201_CREATED,
        summary="Создать автосписание",
    )
    async def create_recurring_payment(
        data: RecurringPaymentCreate,
        idempotence_key: str | None = Header(default=None, alias="Idempotence-Key"),
        service: PaymentService = Depends(get_service),
    ):
        return await service.create_recurring_payment(data, idempotence_key=idempotence_key)

    @app.get("/api/payments/{payment_id}", response_model=PaymentOut, summary="Получить платеж")
    def get_payment(payment_id: int, db: Session = Depends(get_db)):
        payment = db.get(Payment, payment_id)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Платеж не найден")
        return payment

    @app.get(
        "/api/payments/by-order/{order_id}",
        response_model=list[PaymentOut],
        summary="Получить платежи по заказу",
    )
    def get_payments_by_order(order_id: str, db: Session = Depends(get_db)):
        return list(db.scalars(select(Payment).where(Payment.order_id == order_id)))

    @app.post(
        "/api/payments/{payment_id}/capture",
        response_model=PaymentOut,
        summary="Подтвердить холдированный платеж",
    )
    async def capture_payment(
        idempotence_key: str | None = Header(default=None, alias="Idempotence-Key"),
        payment: Payment = Depends(get_payment_or_404),
        service: PaymentService = Depends(get_service),
    ):
        try:
            return await service.capture(payment, idempotence_key=idempotence_key)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    @app.post(
        "/api/payments/{payment_id}/cancel",
        response_model=PaymentOut,
        summary="Отменить платеж",
    )
    async def cancel_payment(
        idempotence_key: str | None = Header(default=None, alias="Idempotence-Key"),
        payment: Payment = Depends(get_payment_or_404),
        service: PaymentService = Depends(get_service),
    ):
        try:
            return await service.cancel(payment, idempotence_key=idempotence_key)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    @app.post(
        "/api/payments/{payment_id}/refunds",
        response_model=RefundOut,
        status_code=status.HTTP_201_CREATED,
        summary="Создать возврат",
    )
    async def create_refund(
        data: RefundCreate,
        idempotence_key: str | None = Header(default=None, alias="Idempotence-Key"),
        payment: Payment = Depends(get_payment_or_404),
        service: PaymentService = Depends(get_service),
    ):
        try:
            return await service.refund(payment, data, idempotence_key=idempotence_key)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    @app.get(
        "/api/users/{user_id}/payment-methods",
        response_model=list[PaymentMethodOut],
        summary="Получить сохраненные платежные методы пользователя",
    )
    def list_payment_methods(user_id: str, db: Session = Depends(get_db)):
        return list(
            db.scalars(
                select(PaymentMethod).where(
                    PaymentMethod.user_id == user_id,
                    PaymentMethod.active.is_(True),
                )
            )
        )

    @app.post(
        "/api/webhooks/yookassa",
        response_model=WebhookResult,
        summary="Обработать webhook от YooKassa",
    )
    async def yookassa_webhook(payload: dict[str, Any], service: PaymentService = Depends(get_service)):
        processed, duplicate, payment = await service.handle_webhook(payload)
        return WebhookResult(
            processed=processed,
            duplicate=duplicate,
            provider_payment_id=payment.provider_payment_id if payment else None,
            status=payment.status if payment else None,
        )

    return app


app = create_app()

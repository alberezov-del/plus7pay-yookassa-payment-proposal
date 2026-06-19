# Примеры API

Примеры рассчитаны на локальный запуск. Клиент провайдера написан в форме, близкой
к реальной интеграции, а тесты используют тестовый клиент YooKassa, поэтому реальные
ключи для проверки проекта не нужны.

## Создание двухстадийного платежа

```bash
curl -X POST http://127.0.0.1:8000/api/payments \
  -H "Content-Type: application/json" \
  -H "Idempotence-Key: payment:order-100:attempt-1" \
  -d '{
    "order_id": "order-100",
    "user_id": "user-42",
    "amount": {"value": "990.00", "currency": "RUB"},
    "capture": false,
    "save_payment_method": true,
    "description": "Двухстадийный тестовый платеж"
  }'
```

## Подтверждение холдированного платежа

```bash
curl -X POST http://127.0.0.1:8000/api/payments/1/capture \
  -H "Idempotence-Key: capture:order-100:attempt-1"
```

## Отмена холдированного платежа

```bash
curl -X POST http://127.0.0.1:8000/api/payments/1/cancel \
  -H "Idempotence-Key: cancel:order-100:attempt-1"
```

## Создание автосписания

```bash
curl -X POST http://127.0.0.1:8000/api/payments/recurring \
  -H "Content-Type: application/json" \
  -H "Idempotence-Key: recurring:order-101:attempt-1" \
  -d '{
    "order_id": "order-101",
    "user_id": "user-42",
    "payment_method_id": "pm_saved_123",
    "amount": {"value": "490.00", "currency": "RUB"},
    "description": "Ежемесячная подписка"
  }'
```

## Список сохраненных платежных методов

```bash
curl http://127.0.0.1:8000/api/users/user-42/payment-methods
```

## Обработка webhook от YooKassa

```bash
curl -X POST http://127.0.0.1:8000/api/webhooks/yookassa \
  -H "Content-Type: application/json" \
  -d '{
    "event": "payment.succeeded",
    "object": {"id": "2a217a2d-000f-5000-9000-1bd6f124af9c"}
  }'
```

## Возврат платежа

```bash
curl -X POST http://127.0.0.1:8000/api/payments/1/refunds \
  -H "Content-Type: application/json" \
  -H "Idempotence-Key: refund:order-100:attempt-1" \
  -d '{
    "amount": {"value": "100.00", "currency": "RUB"},
    "reason": "Частичный возврат клиенту"
  }'
```

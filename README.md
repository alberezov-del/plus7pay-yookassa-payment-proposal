# +7 Pay YooKassa Payment Backend Proposal

FastAPI demo/proposal for a payment backend that shows how I would structure a YooKassa
integration before refactoring a fintech MVP.

This repository is a technical proposal and portfolio demo. It does not claim affiliation with
+7 Pay and does not contain production secrets.

## What This Demonstrates

- Payment creation through YooKassa-style `/v3/payments`.
- Provider idempotency via `Idempotence-Key`.
- Two-stage payments: `capture=false`, then `capture` or `cancel`.
- Saved payment methods via `save_payment_method` and later recurring charges by `payment_method_id`.
- Webhook endpoint with duplicate protection and provider status verification.
- Refunds as separate entities through `/v3/refunds`.
- Safe persistence: no card numbers, no CVV, no raw provider secrets in the database.
- A database layout that separates payments, saved payment methods, webhooks, and refunds.

## Why This Fits A +7 Pay-Style Task

For a fintech MVP with app logic, bank/provider API integration, and database refactoring, I would
start by isolating the payment module from the rest of the product:

- `app/yookassa_client.py` contains provider HTTP calls.
- `app/services.py` contains payment business logic and transactional state changes.
- `app/models.py` contains the proposed payment tables.
- `app/main.py` exposes a small API surface for payments, recurring payments, holds, refunds, and webhooks.
- `docs/security-checklist.md` lists security assumptions for sensitive data.

The goal is to keep provider-specific logic replaceable. If the project later moves from YooKassa
to a bank API, most changes should stay inside the provider client and mapping layer.

## API Surface

```text
POST /api/payments
POST /api/payments/recurring
GET  /api/payments/{payment_id}
GET  /api/payments/by-order/{order_id}
POST /api/payments/{payment_id}/capture
POST /api/payments/{payment_id}/cancel
POST /api/payments/{payment_id}/refunds
POST /api/webhooks/yookassa
GET  /health
```

## Local Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Tests

Tests use a fake YooKassa client, so no real YooKassa credentials are required.

```bash
python -m pytest -q
```

## Example Request

```bash
curl -X POST http://127.0.0.1:8000/api/payments \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "order-100",
    "user_id": "user-42",
    "amount": {"value": "990.00", "currency": "RUB"},
    "capture": false,
    "save_payment_method": true,
    "description": "Demo two-stage payment"
  }'
```

## Proposed Tables

- `payments`: order id, user id, amount, status, provider payment id, idempotency key.
- `payment_methods`: user id, provider payment method id, safe card metadata such as last4/brand.
- `webhook_events`: event type, provider object id, stable payload hash, processed flag.
- `refunds`: linked payment id, provider refund id, amount, status, idempotency key.

## Production Notes

Before production use, I would add:

- Alembic migrations.
- Structured audit logs for refunds/cancellations.
- Strong webhook source verification according to the provider contract.
- Full observability: metrics for failed payments, duplicate webhooks, capture/cancel/refund errors.
- Role-based admin access for refund and payment-method operations.
- More explicit state machine validation for allowed payment transitions.

## References

- YooKassa API reference: https://yookassa.ru/developers/api
- Saving payment method during payment: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment
- Recurring payments with saved payment method: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments


# Payment Backend Architecture

This is a compact backend proposal for a YooKassa-based payment layer that could be adapted for
+7 Pay or a similar fintech MVP.

## Components

- `PaymentService` owns business transactions and database writes.
- `YooKassaClient` isolates provider HTTP calls and idempotency headers.
- `payments` stores order/payment state, provider ids, amounts, and confirmation URLs.
- `payment_methods` stores only provider tokens and safe card metadata, not card numbers or CVV.
- `webhook_events` stores a stable payload hash to ignore duplicate provider notifications.
- `refunds` tracks every refund as a separate operation with its own idempotency key.

## Main Flow

1. Client requests `POST /api/payments`.
2. Backend creates a local pending payment and generates an idempotency key.
3. Backend calls YooKassa `/v3/payments`.
4. Backend saves `provider_payment_id`, status, and confirmation URL.
5. YooKassa sends webhook events.
6. Backend deduplicates the webhook, fetches actual payment state from YooKassa, and updates the order.
7. If `payment_method.saved=true`, backend stores only `payment_method.id` and safe card metadata.

## Data Safety

The project intentionally avoids storing PAN, CVV/CVC, raw authorization headers, or provider secret
keys in the database. Secrets are expected in environment variables or a proper secret manager.


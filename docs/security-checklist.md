# Security Checklist

- Do not store card number, CVV/CVC, or full payment form payloads.
- Store only provider identifiers: `provider_payment_id`, `payment_method.id`, refund ids.
- Use a unique `Idempotence-Key` for every payment, capture, cancel, recurring charge, and refund.
- Treat webhooks as at-least-once delivery: deduplicate and verify current status via provider API.
- Keep all order updates inside database transactions.
- Put provider keys in environment variables or a secret manager, never in source control.
- Mask authorization headers, secrets, card fields, and CVV-like keys in logs.
- Split operational tables: `payments`, `payment_methods`, `webhook_events`, `refunds`.
- Add audit logging for admin/user-triggered refunds and payment method deletion in production.
- Add provider webhook source verification according to the production gateway contract.


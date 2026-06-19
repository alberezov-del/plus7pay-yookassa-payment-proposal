# Техническое предложение: платежный бэкенд на YooKassa

[![CI](https://github.com/alberezov-del/plus7pay-yookassa-payment-proposal/actions/workflows/ci.yml/badge.svg)](https://github.com/alberezov-del/plus7pay-yookassa-payment-proposal/actions/workflows/ci.yml)

Это небольшой FastAPI-проект, который показывает, как я бы выделил платежный модуль
перед рефакторингом fintech-MVP: платежи, привязка карты, автосписания, холдирование,
возвраты, вебхуки и безопасное хранение данных.

Репозиторий сделан как техническое предложение и портфолио-демо. Он не заявляет
о связи с +7 Pay и не содержит продакшен-секретов.

## Что показывает проект

- Создание платежа в стиле YooKassa через `/v3/payments`.
- Идемпотентность на стороне провайдера и приложения через заголовок `Idempotence-Key`.
- Двухстадийные платежи: `capture=false`, затем `capture` или `cancel`.
- Сохранение платежного метода через `save_payment_method` и последующие автосписания по `payment_method_id`.
- Webhook-эндпоинт с защитой от дублей и сверкой актуального статуса через API провайдера.
- Возвраты как отдельные операции через `/v3/refunds`.
- Проверки платежной машины состояний для `capture`, `cancel` и `refund`.
- Маскированный журнал аудита для чувствительных платежных операций.
- Безопасное хранение: без номеров карт, CVV и сырых секретов провайдера в базе.
- Разделение таблиц для платежей, сохраненных платежных методов, вебхуков, возвратов и аудита.

## Почему это подходит под задачу в стиле +7 Pay

Если в fintech-MVP нужно привести в порядок логику приложения, API банка/провайдера
и структуру БД, я бы начал с изоляции платежного модуля от остального продукта:

- `app/yookassa_client.py` отвечает за HTTP-вызовы к провайдеру.
- `app/services.py` содержит бизнес-логику платежей и транзакционные изменения состояния.
- `app/models.py` описывает предлагаемые таблицы платежного контура.
- `app/main.py` открывает API для платежей, автосписаний, холдов, возвратов и вебхуков.
- `docs/security-checklist.md` фиксирует базовые правила работы с чувствительными данными.
- `.github/workflows/ci.yml` запускает линтер и тесты в GitHub Actions.

Главная идея: провайдерская логика должна быть заменяемой. Если позже проект уйдет
с YooKassa на API банка, основная часть изменений должна остаться внутри клиента
провайдера и слоя сопоставления статусов/ответов.

## API

```text
POST /api/payments
POST /api/payments/recurring
GET  /api/payments/{payment_id}
GET  /api/payments/by-order/{order_id}
GET  /api/users/{user_id}/payment-methods
POST /api/payments/{payment_id}/capture
POST /api/payments/{payment_id}/cancel
POST /api/payments/{payment_id}/refunds
POST /api/webhooks/yookassa
GET  /health
```

## Локальный запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

После запуска Swagger будет доступен здесь:

```text
http://127.0.0.1:8000/docs
```

## Проверки

Тесты используют тестовый клиент YooKassa, поэтому реальные ключи YooKassa для проверки не нужны.

```bash
python -m pytest -q
python -m ruff check .
```

## Пример запроса

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

## Предлагаемые таблицы

- `payments`: заказ, пользователь, сумма, статус, идентификатор платежа у провайдера, ключ идемпотентности.
- `payment_methods`: пользователь, идентификатор платежного метода у провайдера, безопасные карточные метаданные вроде `last4` и `brand`.
- `webhook_events`: тип события, идентификатор объекта у провайдера, стабильный хеш полезной нагрузки, флаг обработки.
- `refunds`: связанный платеж, идентификатор возврата у провайдера, сумма, статус, ключ идемпотентности.
- `audit_events`: действие, сущность, инициатор, маскированные JSON-детали.

## Документация

- [Архитектура](docs/architecture.md)
- [Чеклист безопасности](docs/security-checklist.md)
- [Примеры API](docs/api-examples.md)

## Что я бы добавил перед продакшеном

- Alembic-миграции.
- Проверку источника вебхуков по правилам конкретного провайдера.
- Наблюдаемость: метрики по неуспешным платежам, дублям вебхуков, ошибкам `capture/cancel/refund`.
- Ролевой доступ к админским операциям: возвраты, удаление платежных методов, ручные сверки.
- Более строгую машину состояний для разрешенных переходов платежа.
- Отдельную обработку частичных списаний, частичных возвратов и спорных платежных операций.

## Источники

- API YooKassa: https://yookassa.ru/developers/api
- Сохранение платежного метода во время платежа: https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/save-payment-method/save-during-payment
- Рекуррентные платежи с сохраненным платежным методом: https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/additional-settings/recurring-payments

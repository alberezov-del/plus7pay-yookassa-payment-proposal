.PHONY: install test lint run docker-build docker-run

install:
	python3 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -e ".[dev]"

test:
	.venv/bin/python -m pytest -q

lint:
	.venv/bin/python -m ruff check .

run:
	.venv/bin/uvicorn app.main:app --reload

docker-build:
	docker build -t plus7pay-yookassa-payment-proposal .

docker-run:
	docker run --rm -p 8000:8000 --env-file .env plus7pay-yookassa-payment-proposal


from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx

from app.config import Settings


def money_payload(value: Decimal, currency: str) -> dict[str, str]:
    return {"value": f"{value:.2f}", "currency": currency}


class YooKassaClient:
    def __init__(self, settings: Settings):
        self._base_url = settings.yookassa_api_url.rstrip("/")
        self._auth = (settings.yookassa_shop_id, settings.yookassa_secret_key)
        self._return_url = settings.public_return_url

    async def create_payment(
        self,
        *,
        amount_value: Decimal,
        currency: str,
        capture: bool,
        description: str,
        idempotence_key: str,
        save_payment_method: bool = False,
        payment_method_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "amount": money_payload(amount_value, currency),
            "capture": capture,
            "description": description,
            "metadata": metadata or {},
        }
        if payment_method_id:
            payload["payment_method_id"] = payment_method_id
        else:
            payload["confirmation"] = {"type": "redirect", "return_url": self._return_url}
            payload["save_payment_method"] = save_payment_method

        return await self._request("POST", "/payments", payload, idempotence_key=idempotence_key)

    async def get_payment(self, provider_payment_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/payments/{provider_payment_id}")

    async def capture_payment(self, provider_payment_id: str, idempotence_key: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/payments/{provider_payment_id}/capture",
            {},
            idempotence_key=idempotence_key,
        )

    async def cancel_payment(self, provider_payment_id: str, idempotence_key: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/payments/{provider_payment_id}/cancel",
            {},
            idempotence_key=idempotence_key,
        )

    async def create_refund(
        self,
        *,
        provider_payment_id: str,
        amount_value: Decimal,
        currency: str,
        idempotence_key: str,
        description: str,
    ) -> dict[str, Any]:
        payload = {
            "payment_id": provider_payment_id,
            "amount": money_payload(amount_value, currency),
            "description": description,
        }
        return await self._request("POST", "/refunds", payload, idempotence_key=idempotence_key)

    async def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        idempotence_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if idempotence_key:
            headers["Idempotence-Key"] = idempotence_key

        async with httpx.AsyncClient(base_url=self._base_url, auth=self._auth, timeout=15) as client:
            response = await client.request(method, path, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()


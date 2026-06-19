from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4


SENSITIVE_KEYS = {"authorization", "secret", "password", "cvv", "cvc", "card_number"}


def new_idempotence_key(prefix: str) -> str:
    return f"{prefix}:{uuid4()}"


def stable_payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def mask_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***" if key.lower() in SENSITIVE_KEYS else mask_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [mask_sensitive(item) for item in value]
    return value


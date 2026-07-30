from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


REDACTED = "[REDACTED]"
REDACTED_EMAIL = "[REDACTED_EMAIL]"

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
BEARER_RE = re.compile(
    r"(?P<prefix>\bAuthorization\s*[:=]\s*Bearer\s+)(?P<secret>[^\s'\",}]+)",
    re.IGNORECASE,
)
STANDALONE_BEARER_RE = re.compile(r"(?<!Authorization[:=]\s)\bBearer\s+[^\s'\",}]+", re.IGNORECASE)
ENV_SECRET_RE = re.compile(
    r"(?P<key>\b(?:GIFT_API|GIFT_PASSWORD|GIFT_EMAIL|OPENROUTER_API_KEY)\b\s*=\s*)(?P<secret>[^\s'\",}]+)",
    re.IGNORECASE,
)
JSON_SECRET_RE = re.compile(
    r"(?P<prefix>[\"'](?:GIFT_API|GIFT_PASSWORD|GIFT_EMAIL|OPENROUTER_API_KEY|authorization|api_key|password|token)[\"']\s*:\s*[\"'])(?P<secret>.*?)(?P<suffix>[\"'])",
    re.IGNORECASE,
)
API_KEY_RE = re.compile(r"\b(?:sk-or-v1-|sk-)[A-Za-z0-9._-]{6,}\b")

SECRET_KEY_PARTS = (
    "authorization",
    "password",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "bearer",
    "openrouter_api_key",
    "gift_api",
    "gift_password",
)


def redact_secrets(value: Any) -> Any:
    if isinstance(value, str):
        return redact_string(value)
    if isinstance(value, Mapping):
        return {
            redact_string(key) if isinstance(key, str) else key: (
                REDACTED if isinstance(key, str) and _is_secret_key(key) else redact_secrets(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    if isinstance(value, set):
        return {redact_secrets(item) for item in value}
    return value


def redact_string(value: str) -> str:
    redacted = BEARER_RE.sub(lambda match: f"{match.group('prefix')}{REDACTED}", value)
    redacted = STANDALONE_BEARER_RE.sub(f"Bearer {REDACTED}", redacted)
    redacted = ENV_SECRET_RE.sub(lambda match: f"{match.group('key')}{REDACTED}", redacted)
    redacted = JSON_SECRET_RE.sub(lambda match: f"{match.group('prefix')}{REDACTED}{match.group('suffix')}", redacted)
    redacted = API_KEY_RE.sub(REDACTED, redacted)
    return EMAIL_RE.sub(REDACTED_EMAIL, redacted)


def _is_secret_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in SECRET_KEY_PARTS) or normalized in {"email", "gift_email"}

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from ..logging_utils import redact_string

SECRET_REQUEST_KEYS = {
    "authorization",
    "proxy-authorization",
    "headers",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "id_token",
    "api_key",
    "openrouter_api_key",
    "gift_password",
    "apikey",
    "api-key",
    "x-api-key",
    "client_secret",
    "client-secret",
    "secret",
    "email",
    "gift_email",
}

SECRET_KEY_PARTS = (
    "authorization",
    "password",
    "token",
    "api_key",
    "apikey",
    "api-key",
    "secret",
)


class ProviderStatus(str, Enum):
    OK = "ok"
    AUTH_ERROR = "auth_error"
    PAYMENT_REQUIRED = "payment_required"
    FORBIDDEN = "forbidden"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    TIMEOUT = "timeout"
    MALFORMED_JSON = "malformed_json"
    MISSING_CHOICES = "missing_choices"
    REQUEST_ERROR = "request_error"
    HTTP_ERROR = "http_error"


@dataclass(frozen=True)
class ProviderRequest:
    provider: str
    model: str
    messages: list[dict[str, Any]]
    temperature: float = 0
    top_p: float | None = None
    stream: bool = False
    response_schema: dict[str, Any] | None = None
    request_json: dict[str, Any] | None = None
    request_body: bytes | str | None = None
    # TailScale-specific controls. OpenRouter ignores these.
    # prompt_id maps to the backend's stored prompt template (`X-Prompt-ID` header).
    # top_k maps to retrieval depth (`X-Top-K` header). `metadata.top_k` in the body
    # is documented as unreliable on this route, so we never use it.
    prompt_id: int | None = None
    top_k: int | None = None


@dataclass
class ProviderResponse:
    provider: str
    model: str | None
    status: ProviderStatus
    status_code: int | None = None
    latency_ms: int | None = None
    request_json: dict[str, Any] | None = None
    request_headers: dict[str, str] | None = None
    prompt_id: int | None = None
    top_k: int | None = None
    request_body: bytes | str | None = None
    response_body: str | None = None
    response_json: Any = None
    error: str | None = None
    should_retry: bool = False
    retry_after_seconds: float | None = None
    attempts: int = 1
    attempt_responses: list["ProviderResponse"] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.request_json = sanitize_request_json(self.request_json)
        # Defense in depth: scrub any bearer tokens / api keys / emails that
        # could leak through an exception's str() into a stored error_message.
        if isinstance(self.error, str):
            self.error = redact_string(self.error)

    @property
    def error_type(self) -> str | None:
        return None if self.status == ProviderStatus.OK else self.status.value

    @property
    def error_message(self) -> str | None:
        return self.error

    @property
    def finish_reason(self) -> str | None:
        choice = self._first_choice()
        return choice.get("finish_reason") if isinstance(choice, dict) else None

    @property
    def prompt_tokens(self) -> int | None:
        return self._usage_int("prompt_tokens")

    @property
    def completion_tokens(self) -> int | None:
        return self._usage_int("completion_tokens")

    @property
    def total_tokens(self) -> int | None:
        return self._usage_int("total_tokens")

    @property
    def content_text(self) -> str | None:
        choice = self._first_choice()
        if not isinstance(choice, dict):
            return None
        message = choice.get("message")
        if not isinstance(message, dict):
            return None
        content = message.get("content")
        if isinstance(content, str):
            return content
        if content is None:
            return None
        return str(content)

    def _first_choice(self) -> Any:
        if not isinstance(self.response_json, dict):
            return None
        choices = self.response_json.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        return choices[0]

    def _usage_int(self, key: str) -> int | None:
        if not isinstance(self.response_json, dict):
            return None
        usage = self.response_json.get("usage")
        if not isinstance(usage, dict):
            return None
        value = usage.get(key)
        return int(value) if isinstance(value, int) else None


def sanitize_request_headers(headers: dict[str, str] | None) -> dict[str, str] | None:
    """Return a copy of `headers` with any secret-bearing key removed.

    Used when persisting which headers the harness sent on the wire so that
    Authorization / cookies / api keys never reach the DB or exports.
    """
    if not headers:
        return None
    safe: dict[str, str] = {}
    for key, value in headers.items():
        if not isinstance(key, str):
            continue
        key_normalized = key.lower().replace("-", "_")
        if (
            key_normalized in SECRET_REQUEST_KEYS
            or key_normalized.endswith("_token")
            or any(part in key_normalized for part in SECRET_KEY_PARTS)
        ):
            continue
        safe[key] = value
    return safe or None


def sanitize_request_json(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            key_lower = key_text.lower()
            key_normalized = key_lower.replace("-", "_")
            if (
                key_lower in SECRET_REQUEST_KEYS
                or key_normalized in SECRET_REQUEST_KEYS
                or key_lower.endswith("_token")
                or key_lower.endswith("-token")
                or any(part in key_normalized for part in SECRET_KEY_PARTS)
            ):
                continue
            sanitized[key] = sanitize_request_json(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_request_json(item) for item in value]
    return value


def parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value.strip())
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    return seconds


def status_from_code(status_code: int) -> ProviderStatus:
    if 200 <= status_code < 300:
        return ProviderStatus.OK
    if status_code == 401:
        return ProviderStatus.AUTH_ERROR
    if status_code == 402:
        return ProviderStatus.PAYMENT_REQUIRED
    if status_code == 403:
        return ProviderStatus.FORBIDDEN
    if status_code == 429:
        return ProviderStatus.RATE_LIMITED
    if status_code >= 500:
        return ProviderStatus.SERVER_ERROR
    return ProviderStatus.HTTP_ERROR


def response_from_timeout(
    *,
    provider: str,
    model: str | None,
    request_json: dict[str, Any] | None,
    error: Exception,
    attempts: int = 1,
    request_headers: dict[str, str] | None = None,
    prompt_id: int | None = None,
    top_k: int | None = None,
) -> ProviderResponse:
    return ProviderResponse(
        provider=provider,
        model=model,
        status=ProviderStatus.TIMEOUT,
        request_json=request_json,
        request_headers=sanitize_request_headers(request_headers),
        prompt_id=prompt_id,
        top_k=top_k,
        error=str(error),
        should_retry=True,
        attempts=attempts,
    )


def response_from_request_error(
    *,
    provider: str,
    model: str | None,
    request_json: dict[str, Any] | None,
    error: Exception,
    attempts: int = 1,
    request_headers: dict[str, str] | None = None,
    prompt_id: int | None = None,
    top_k: int | None = None,
) -> ProviderResponse:
    return ProviderResponse(
        provider=provider,
        model=model,
        status=ProviderStatus.REQUEST_ERROR,
        request_json=request_json,
        request_headers=sanitize_request_headers(request_headers),
        prompt_id=prompt_id,
        top_k=top_k,
        error=str(error),
        should_retry=True,
        attempts=attempts,
    )


def response_from_httpx_response(
    *,
    provider: str,
    model: str | None,
    request_json: dict[str, Any] | None,
    response: httpx.Response,
    attempts: int = 1,
    request_headers: dict[str, str] | None = None,
    prompt_id: int | None = None,
    top_k: int | None = None,
) -> ProviderResponse:
    body = response.text
    status = status_from_code(response.status_code)
    retry_after = parse_retry_after(response.headers.get("Retry-After"))
    parsed_json: Any = None

    try:
        parsed_json = response.json()
    except ValueError:
        if status == ProviderStatus.OK:
            status = ProviderStatus.MALFORMED_JSON

    if status == ProviderStatus.OK:
        choices = parsed_json.get("choices") if isinstance(parsed_json, dict) else None
        if not choices:
            status = ProviderStatus.MISSING_CHOICES

    return ProviderResponse(
        provider=provider,
        model=model,
        status=status,
        status_code=response.status_code,
        request_json=request_json,
        request_headers=sanitize_request_headers(request_headers),
        prompt_id=prompt_id,
        top_k=top_k,
        response_body=body,
        response_json=parsed_json,
        should_retry=status in {ProviderStatus.RATE_LIMITED, ProviderStatus.SERVER_ERROR},
        retry_after_seconds=retry_after,
        attempts=attempts,
    )

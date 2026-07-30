from __future__ import annotations

import threading
from dataclasses import replace
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx

from .base import (
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    response_from_httpx_response,
    response_from_request_error,
    response_from_timeout,
    sanitize_request_json,
    status_from_code,
)


GIFT_MCQ_PROMPT_ID = 13


class TailScaleMedicalRAGProvider:
    provider_name = "tailscale_medical_rag"
    supports_response_schema = False

    def __init__(
        self,
        *,
        base_url: str | None = None,
        email: str | None = None,
        password: str | None = None,
        client: httpx.Client | None = None,
        env: Mapping[str, str] | None = None,
        # Per the API characterization, TailScale tiny-prompt latency was
        # observed at 35–91 seconds. A 60s default would silently time out
        # roughly half of calls. 180s gives ~2x safety margin over the
        # observed P95 without making infinite hangs invisible.
        timeout: float = 180,
    ) -> None:
        # Credentials must be supplied explicitly. The canonical CLI path uses
        # get_provider(..., settings=Settings.from_env()) which forwards each
        # field via base_url=/email=/password=. Tests and ad-hoc callers can
        # still pass env={...}. os.environ is no longer read implicitly.
        if env is not None:
            if base_url is None:
                base_url = env.get("GIFT_API")
            if email is None:
                email = env.get("GIFT_EMAIL")
            if password is None:
                password = env.get("GIFT_PASSWORD")
        self._base_url = (base_url or "").rstrip("/")
        self._email = email or ""
        self._password = password or ""
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None
        self._token: str | None = None
        self._token_lock = threading.Lock()

    def check_auth(self) -> ProviderResponse:
        config_error = self._config_error()
        if config_error is not None:
            return config_error
        request_json = {
            "health": {"method": "GET", "path": "/v1/health"},
            "login": {"method": "POST", "path": "/api/v1/auth/login", "email": self._email},
            "models": {"method": "GET", "path": "/v1/models"},
        }

        health = self._request("GET", "/v1/health")
        if isinstance(health, ProviderResponse):
            health.request_json = sanitize_request_json(request_json)
            return health
        if status_from_code(health.status_code) != ProviderStatus.OK:
            return self._simple_http_response(model=None, request_json=request_json, response=health)

        login_response = self._login()
        if login_response.status != ProviderStatus.OK:
            login_response.request_json = sanitize_request_json(request_json)
            return login_response

        models = self._request("GET", "/v1/models", headers=self._auth_headers())
        if isinstance(models, ProviderResponse):
            models.request_json = sanitize_request_json(request_json)
            return models

        return self._simple_http_response(model=None, request_json=request_json, response=models)

    def healthcheck(self) -> None:
        response = self.check_auth()
        if response.status != ProviderStatus.OK:
            raise RuntimeError(response.error or f"TailScale auth check failed: {response.status.value}")

    def chat(self, request: ProviderRequest, retry: bool = True) -> ProviderResponse:
        request = self._with_mandatory_mcq_prompt(request)
        payload = self._chat_payload(request)
        extra_headers = self._extra_headers(request)
        config_error = self._config_error(model=request.model, request_json=payload)
        if config_error is not None:
            config_error.request_headers = self._safe_headers(extra_headers)
            config_error.prompt_id = request.prompt_id
            config_error.top_k = request.top_k
            return config_error
        auth_response = self._ensure_token()
        if auth_response is not None:
            auth_response.request_json = sanitize_request_json(payload)
            auth_response.request_headers = self._safe_headers(extra_headers)
            auth_response.prompt_id = request.prompt_id
            auth_response.top_k = request.top_k
            return auth_response

        attempts = 1
        token = self._token_snapshot()
        response = self._post_chat(
            payload,
            attempts=attempts,
            model=request.model,
            auth_token=token,
            extra_headers=extra_headers,
            prompt_id=request.prompt_id,
            top_k=request.top_k,
        )
        if response.status != ProviderStatus.AUTH_ERROR or not retry:
            return response

        login_response = self._refresh_token_after_auth_error(token)
        if login_response is not None:
            login_response.request_json = sanitize_request_json(payload)
            login_response.request_headers = self._safe_headers(extra_headers)
            login_response.prompt_id = request.prompt_id
            login_response.top_k = request.top_k
            login_response.attempts = attempts
            login_response.attempt_responses = [response]
            return login_response

        attempts = 2
        retry_response = self._post_chat(
            payload,
            attempts=attempts,
            model=request.model,
            auth_token=self._token_snapshot(),
            extra_headers=extra_headers,
            prompt_id=request.prompt_id,
            top_k=request.top_k,
        )
        retry_response.attempt_responses = [response]
        return retry_response

    def chat_completion(self, request: ProviderRequest, retry: bool = True) -> ProviderResponse:
        return self.chat(request, retry=retry)

    def answer_schema(self) -> dict[str, Any] | None:
        return None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _ensure_token(self) -> ProviderResponse | None:
        if self._token_snapshot():
            return None
        with self._token_lock:
            if self._token:
                return None
            response = self._login_locked()
            return None if response.status == ProviderStatus.OK else response

    def _refresh_token_after_auth_error(self, token_used: str | None) -> ProviderResponse | None:
        with self._token_lock:
            if self._token and self._token != token_used:
                return None
            response = self._login_locked()
            return None if response.status == ProviderStatus.OK else response

    def _login(self) -> ProviderResponse:
        with self._token_lock:
            return self._login_locked()

    def _login_locked(self) -> ProviderResponse:
        login_payload = {"email": self._email, "password": self._password}
        safe_request = {"email": self._email}
        try:
            response = self._client.post(self._url("/api/v1/auth/login"), json=login_payload)
        except httpx.TimeoutException as exc:
            return response_from_timeout(
                provider=self.provider_name,
                model=None,
                request_json=safe_request,
                error=exc,
            )
        except httpx.HTTPError as exc:
            return response_from_request_error(
                provider=self.provider_name,
                model=None,
                request_json=safe_request,
                error=exc,
            )

        parsed_json: Any = None
        status = status_from_code(response.status_code)
        try:
            parsed_json = response.json()
        except ValueError:
            if status == ProviderStatus.OK:
                status = ProviderStatus.MALFORMED_JSON

        if status == ProviderStatus.OK:
            token = parsed_json.get("access_token") if isinstance(parsed_json, dict) else None
            if not token:
                status = ProviderStatus.MALFORMED_JSON
            else:
                self._token = token

        # Login response body is intentionally dropped: a successful body contains the
        # raw JWT (access_token), which must never reach logs, the DB, or exports.
        # status + status_code + error remain available for diagnostics.
        return ProviderResponse(
            provider=self.provider_name,
            model=None,
            status=status,
            status_code=response.status_code,
            request_json=safe_request,
            response_body=None,
            response_json=None,
            should_retry=status in {ProviderStatus.RATE_LIMITED, ProviderStatus.SERVER_ERROR},
        )

    def _post_chat(
        self,
        payload: dict[str, Any],
        *,
        attempts: int,
        model: str,
        auth_token: str | None,
        extra_headers: dict[str, str] | None = None,
        prompt_id: int | None = None,
        top_k: int | None = None,
    ) -> ProviderResponse:
        wire_headers = {**self._auth_headers_for_token(auth_token), **(extra_headers or {})}
        safe_headers = self._safe_headers(extra_headers)
        try:
            response = self._client.post(
                self._url("/v1/chat/completions"),
                headers=wire_headers,
                json=payload,
            )
        except httpx.TimeoutException as exc:
            return response_from_timeout(
                provider=self.provider_name,
                model=model,
                request_json=payload,
                error=exc,
                attempts=attempts,
                request_headers=safe_headers,
                prompt_id=prompt_id,
                top_k=top_k,
            )
        except httpx.HTTPError as exc:
            return response_from_request_error(
                provider=self.provider_name,
                model=model,
                request_json=payload,
                error=exc,
                attempts=attempts,
                request_headers=safe_headers,
                prompt_id=prompt_id,
                top_k=top_k,
            )

        return response_from_httpx_response(
            provider=self.provider_name,
            model=model,
            request_json=payload,
            response=response,
            attempts=attempts,
            request_headers=safe_headers,
            prompt_id=prompt_id,
            top_k=top_k,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response | ProviderResponse:
        try:
            return self._client.request(method, self._url(path), headers=headers)
        except httpx.TimeoutException as exc:
            return response_from_timeout(provider=self.provider_name, model=None, request_json=None, error=exc)
        except httpx.HTTPError as exc:
            return response_from_request_error(provider=self.provider_name, model=None, request_json=None, error=exc)

    def _simple_http_response(
        self,
        *,
        model: str | None,
        request_json: dict[str, Any],
        response: httpx.Response,
    ) -> ProviderResponse:
        parsed_json: Any = None
        status = status_from_code(response.status_code)
        try:
            parsed_json = response.json()
        except ValueError:
            if status == ProviderStatus.OK:
                status = ProviderStatus.MALFORMED_JSON

        return ProviderResponse(
            provider=self.provider_name,
            model=model,
            status=status,
            status_code=response.status_code,
            request_json=request_json,
            response_body=response.text,
            response_json=parsed_json,
            should_retry=status in {ProviderStatus.RATE_LIMITED, ProviderStatus.SERVER_ERROR},
        )

    def _auth_headers(self) -> dict[str, str]:
        return self._auth_headers_for_token(self._token_snapshot())

    @staticmethod
    def _auth_headers_for_token(token: str | None) -> dict[str, str]:
        if token is None:
            return {}
        return {"Authorization": f"Bearer {token}"}

    def _token_snapshot(self) -> str | None:
        with self._token_lock:
            return self._token

    def _config_error(
        self, *, model: str | None = None, request_json: dict[str, Any] | None = None
    ) -> ProviderResponse | None:
        missing = []
        if not self._base_url.strip():
            missing.append("GIFT_API")
        if not self._email.strip():
            missing.append("GIFT_EMAIL")
        if not self._password.strip():
            missing.append("GIFT_PASSWORD")
        if missing:
            return ProviderResponse(
                provider=self.provider_name,
                model=model,
                status=ProviderStatus.AUTH_ERROR,
                request_json=request_json,
                error=(
                    f"Missing {', '.join(missing)}. Create .env from .env.example and set the TailScale "
                    "Medical RAG credentials."
                ),
            )

        parsed = urlparse(self._base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ProviderResponse(
                provider=self.provider_name,
                model=model,
                status=ProviderStatus.AUTH_ERROR,
                request_json=request_json,
                error="Invalid GIFT_API. It must be a full URL starting with http:// or https://.",
            )
        return None

    def _url(self, path: str) -> str:
        if not self._base_url:
            return path
        return f"{self._base_url}{path}"

    def _chat_payload(self, request: ProviderRequest) -> dict[str, Any]:
        # Per backend guidance the wire body stays minimal: model + messages +
        # temperature + top_p + stream. Prompt selection and retrieval depth
        # travel as headers (X-Prompt-ID, X-Top-K), NOT inside `metadata`.
        #
        # The optional `request.request_json` escape-hatch is applied FIRST so
        # the explicit named fields below always win. Reversing the order would
        # let a caller silently override (e.g.) `top_p` via the escape-hatch,
        # which is a footgun we don't want.
        payload: dict[str, Any] = dict(request.request_json) if request.request_json else {}
        payload.update(
            {
                "model": request.model,
                "messages": request.messages,
                "temperature": request.temperature,
                "stream": request.stream,
            }
        )
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.response_schema is not None:
            # response_format is not honored by TailScale (supports_response_schema=False
            # on this class), but we forward it for symmetry if a future caller flips
            # the flag. Today the runner never sets response_schema on TailScale calls.
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": request.response_schema,
            }
        return payload

    def _extra_headers(self, request: ProviderRequest) -> dict[str, str]:
        headers: dict[str, str] = {}
        if request.prompt_id is not None:
            headers["X-Prompt-ID"] = str(int(request.prompt_id))
        if request.top_k is not None:
            headers["X-Top-K"] = str(int(request.top_k))
        return headers

    @staticmethod
    def _safe_headers(extra_headers: dict[str, str] | None) -> dict[str, str] | None:
        # Authorization is intentionally excluded; only the prompt/top_k controls
        # we explicitly set are echoed back to the caller for persistence.
        if not extra_headers:
            return None
        return dict(extra_headers)

    @staticmethod
    def _with_mandatory_mcq_prompt(request: ProviderRequest) -> ProviderRequest:
        """Pin every GIFT benchmark request to the MCQ prompt."""
        if request.prompt_id is None:
            return replace(request, prompt_id=GIFT_MCQ_PROMPT_ID)
        if request.prompt_id != GIFT_MCQ_PROMPT_ID:
            raise ValueError(
                "GIFT benchmark requests must use "
                f"prompt_id={GIFT_MCQ_PROMPT_ID}, got {request.prompt_id}"
            )
        return request

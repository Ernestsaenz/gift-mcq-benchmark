from __future__ import annotations

from typing import Any, Mapping

import httpx

from .base import (
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    response_from_httpx_response,
    response_from_request_error,
    response_from_timeout,
    status_from_code,
)


OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_CREDITS_URL = "https://openrouter.ai/api/v1/credits"


class OpenRouterProvider:
    provider_name = "openrouter"
    supports_response_schema = True

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: httpx.Client | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float = 60,
    ) -> None:
        # Credentials must be supplied explicitly. The canonical CLI path uses
        # get_provider(..., settings=Settings.from_env()) which forwards the key
        # via api_key=. Tests and ad-hoc callers can still pass env={"OPENROUTER_API_KEY": ...}.
        # os.environ is no longer read implicitly.
        if api_key is None and env is not None:
            api_key = env.get("OPENROUTER_API_KEY")
        self._api_key = api_key or ""
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None

    def check_auth(self) -> ProviderResponse:
        config_error = self._config_error()
        if config_error is not None:
            return config_error
        request_json = {"endpoint": "credits"}
        try:
            response = self._client.get(OPENROUTER_CREDITS_URL, headers=self._auth_headers())
        except httpx.TimeoutException as exc:
            return response_from_timeout(
                provider=self.provider_name, model=None, request_json=request_json, error=exc
            )
        except httpx.HTTPError as exc:
            return response_from_request_error(
                provider=self.provider_name, model=None, request_json=request_json, error=exc
            )

        status = status_from_code(response.status_code)
        parsed_json: Any = None
        try:
            parsed_json = response.json()
        except ValueError:
            if status == ProviderStatus.OK:
                status = ProviderStatus.MALFORMED_JSON

        return ProviderResponse(
            provider=self.provider_name,
            model=None,
            status=status,
            status_code=response.status_code,
            request_json=request_json,
            response_body=response.text,
            response_json=parsed_json,
            should_retry=status in {ProviderStatus.RATE_LIMITED, ProviderStatus.SERVER_ERROR},
        )

    def healthcheck(self) -> None:
        response = self.check_auth()
        if response.status != ProviderStatus.OK:
            raise RuntimeError(response.error or f"OpenRouter auth check failed: {response.status.value}")

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def chat(self, request: ProviderRequest, retry: bool = True) -> ProviderResponse:
        config_error = self._config_error(model=request.model)
        if config_error is not None:
            return config_error
        payload = self._chat_payload(request)
        responses: list[ProviderResponse] = []
        max_attempts = 2 if retry else 1
        for attempt_number in range(1, max_attempts + 1):
            response = self._chat_once(request, payload, attempts=attempt_number)
            responses.append(response)
            if not response.should_retry:
                response.attempt_responses = responses[:-1]
                return response
        final = responses[-1]
        final.attempt_responses = responses[:-1]
        return final

    def _chat_once(self, request: ProviderRequest, payload: dict[str, Any], *, attempts: int) -> ProviderResponse:
        try:
            response = self._client.post(OPENROUTER_CHAT_URL, headers=self._auth_headers(), json=payload)
        except httpx.TimeoutException as exc:
            return response_from_timeout(
                provider=self.provider_name,
                model=request.model,
                request_json=payload,
                error=exc,
                attempts=attempts,
            )
        except httpx.HTTPError as exc:
            return response_from_request_error(
                provider=self.provider_name,
                model=request.model,
                request_json=payload,
                error=exc,
                attempts=attempts,
            )

        return response_from_httpx_response(
            provider=self.provider_name,
            model=request.model,
            request_json=payload,
            response=response,
            attempts=attempts,
        )

    def chat_completion(self, request: ProviderRequest, retry: bool = True) -> ProviderResponse:
        return self.chat(request, retry=retry)

    def answer_schema(self) -> dict[str, Any]:
        return {
            "name": "mcq_answer",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["question_id", "selected_letter", "selected_option_text"],
                "properties": {
                    "question_id": {"type": "string"},
                    "selected_letter": {"type": "string", "enum": ["a", "b", "c", "d"]},
                    "selected_option_text": {"type": "string"},
                },
            },
        }

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def _config_error(self, *, model: str | None = None) -> ProviderResponse | None:
        if not self._api_key.strip():
            return ProviderResponse(
                provider=self.provider_name,
                model=model,
                status=ProviderStatus.AUTH_ERROR,
                error="Missing OPENROUTER_API_KEY. Create .env from .env.example and set OPENROUTER_API_KEY.",
            )
        return None

    def _chat_payload(self, request: ProviderRequest) -> dict[str, Any]:
        # Optional `request.request_json` escape-hatch is applied FIRST so the
        # explicit named fields below cannot be silently overridden by a caller
        # passing the same key inside request_json.
        payload: dict[str, Any] = dict(request.request_json) if request.request_json else {}
        payload.update(
            {
                "model": request.model,
                "messages": request.messages,
                "temperature": request.temperature,
                "stream": request.stream,
                "provider": request.provider_routing or {"require_parameters": True},
            }
        )
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": request.response_schema,
            }
        return payload

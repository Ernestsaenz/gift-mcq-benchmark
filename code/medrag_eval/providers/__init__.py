from __future__ import annotations

from typing import Any

from .base import ProviderRequest, ProviderResponse, ProviderStatus
from .openrouter import OpenRouterProvider
from .tailscale_medical_rag import TailScaleMedicalRAGProvider


PROVIDER_ALIASES = {
    "tailscale": "tailscale_medical_rag",
    "tailscale_medical_rag": "tailscale_medical_rag",
    "openrouter": "openrouter",
}


def get_provider(name: str, **kwargs: Any) -> OpenRouterProvider | TailScaleMedicalRAGProvider:
    settings = kwargs.pop("settings", None)
    canonical = PROVIDER_ALIASES.get(name)
    if canonical is None:
        raise KeyError(f"Unknown provider: {name}")
    if settings is not None:
        if canonical == "openrouter":
            kwargs.setdefault("api_key", settings.openrouter_api_key)
        else:
            kwargs.setdefault("base_url", settings.gift_api)
            kwargs.setdefault("email", settings.gift_email)
            kwargs.setdefault("password", settings.gift_password)
    if canonical == "openrouter":
        return OpenRouterProvider(**kwargs)
    return TailScaleMedicalRAGProvider(**kwargs)


def normalize_provider_name(name: str) -> str:
    canonical = PROVIDER_ALIASES.get(name)
    if canonical is None:
        raise KeyError(f"Unknown provider: {name}")
    return canonical


__all__ = [
    "OpenRouterProvider",
    "PROVIDER_ALIASES",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderStatus",
    "TailScaleMedicalRAGProvider",
    "get_provider",
    "normalize_provider_name",
]

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from string import Formatter
from typing import Any

# Historical regime used by the committed evidence package.
SHARED_PROMPT_VERSION = "mcq_shared_v2"

# Live benchmark regime. OpenRouter receives the MCQ instructions in-message;
# GIFT receives only the question and options because the same instructions are
# already provided server-side by X-Prompt-ID: 13.
BENCHMARK_PROMPT_VERSION = "mcq_provider_v3"
GIFT_PROVIDERS = frozenset({"tailscale", "tailscale_medical_rag"})
OPENROUTER_PROVIDER = "openrouter"

GIFT_QUESTION_TEMPLATE = """{question_text}

a) {option_a}
b) {option_b}
c) {option_c}
d) {option_d}"""

# Empty-string sentinel for system_prompt_sha256 when no system role is sent.
# Stored verbatim in the DB so a query like `WHERE system_prompt_sha256 = ''`
# isolates user-only-regime calls without joining experiments.config_json.
NO_SYSTEM_PROMPT_SHA256 = ""


@dataclass(frozen=True)
class RenderedPrompt:
    version: str
    system_text: str
    user_text: str
    system_sha256: str
    user_sha256: str

    @property
    def system_prompt(self) -> str:
        return self.system_text

    @property
    def user_prompt(self) -> str:
        return self.user_text


def render_shared_prompt(
    question: Any,
    prompt_dir: str | Path | None = None,
    prompt_version: str = SHARED_PROMPT_VERSION,
) -> RenderedPrompt:
    """Render the canonical user-only MCQ prompt.

    The returned RenderedPrompt has empty `system_text` so callers building a
    messages array emit only the user role. The user message carries the
    English instructions, the JSON output contract, and the Spanish question
    content (question_text + options a–d).
    """
    user_template = _load_user_only_template(prompt_version, prompt_dir)
    values = _prompt_values(question)
    return _render(prompt_version, "", user_template, values)


def render_benchmark_prompt(
    question: Any,
    *,
    provider: str,
    prompt_dir: str | Path | None = None,
    prompt_version: str = BENCHMARK_PROMPT_VERSION,
) -> RenderedPrompt:
    """Render the provider-specific user message for a live benchmark call."""
    if provider in GIFT_PROVIDERS:
        return _render(
            prompt_version,
            "",
            GIFT_QUESTION_TEMPLATE,
            _prompt_values(question),
        )
    if provider == OPENROUTER_PROVIDER:
        return render_shared_prompt(
            question,
            prompt_dir=prompt_dir,
            prompt_version=prompt_version,
        )
    raise ValueError(f"Unsupported prompt provider: {provider}")


def _prompt_values(question: Any) -> dict[str, str]:
    options = _options(question)
    return {
        "question_id": str(_field(question, "question_id")),
        "question_text": str(_field(question, "question_text")),
        "option_a": options["a"],
        "option_b": options["b"],
        "option_c": options["c"],
        "option_d": options["d"],
    }


def _render(
    version: str,
    system_template: str,
    user_template: str,
    values: Mapping[str, str],
) -> RenderedPrompt:
    _validate_template_fields(system_template, values.keys())
    _validate_template_fields(user_template, values.keys())
    system_text = system_template.format(**values).strip() if system_template else ""
    user_text = user_template.format(**values).strip()
    # When no system prompt is sent, record the empty-string sentinel SHA so the
    # DB distinguishes "no system" from a hypothetical "some system prompt" path.
    system_sha = _hash_text(system_text) if system_text else NO_SYSTEM_PROMPT_SHA256
    return RenderedPrompt(
        version=version,
        system_text=system_text,
        user_text=user_text,
        system_sha256=system_sha,
        user_sha256=_hash_text(user_text),
    )


def _options(question: Any) -> dict[str, str]:
    raw_options = _maybe_field(question, "options")
    if isinstance(raw_options, Mapping):
        return {letter: str(raw_options[letter]) for letter in ("a", "b", "c", "d")}
    return {
        "a": str(_field(question, "option_a")),
        "b": str(_field(question, "option_b")),
        "c": str(_field(question, "option_c")),
        "d": str(_field(question, "option_d")),
    }


def _field(question: Any, name: str) -> Any:
    value = _maybe_field(question, name)
    if value is None:
        raise KeyError(f"Question is missing required prompt field: {name}")
    return value


def _maybe_field(question: Any, name: str) -> Any:
    if isinstance(question, Mapping):
        return question.get(name)
    if hasattr(question, name):
        return getattr(question, name)
    try:
        return question[name]
    except (KeyError, TypeError, IndexError):
        return None


def _load_user_only_template(version: str, prompt_dir: str | Path | None) -> str:
    root = str(Path(prompt_dir)) if prompt_dir is not None else str(_default_prompt_dir())
    return _load_user_only_template_cached(version, root)


@lru_cache(maxsize=16)
def _load_user_only_template_cached(version: str, prompt_dir: str) -> str:
    root = Path(prompt_dir)
    user_path = root / f"{version}_user_template.txt"
    return user_path.read_text(encoding="utf-8")


def _default_prompt_dir() -> Path:
    return Path(__file__).resolve().parent / "prompts"


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _validate_template_fields(template: str, allowed_fields) -> None:
    allowed = set(allowed_fields)
    formatter = Formatter()
    for _, field_name, _, _ in formatter.parse(template):
        if not field_name:
            continue
        base_field = field_name.split(".", 1)[0].split("[", 1)[0]
        if base_field not in allowed:
            raise ValueError(f"Prompt template references disallowed field: {base_field}")

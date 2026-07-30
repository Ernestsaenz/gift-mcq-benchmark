from __future__ import annotations

from medrag_eval.prompting import (
    BENCHMARK_PROMPT_VERSION,
    NO_SYSTEM_PROMPT_SHA256,
    render_benchmark_prompt,
)

QUESTION = {
    "question_id": "g001",
    "question_text": "¿Cuál es la respuesta correcta?",
    "option_a": "Opción A",
    "option_b": "Opción B",
    "option_c": "Opción C",
    "option_d": "Opción D",
}


def test_gift_receives_only_question_and_options() -> None:
    prompt = render_benchmark_prompt(
        QUESTION,
        provider="tailscale_medical_rag",
    )

    assert prompt.version == BENCHMARK_PROMPT_VERSION
    assert prompt.system_prompt == ""
    assert prompt.system_sha256 == NO_SYSTEM_PROMPT_SHA256
    assert prompt.user_prompt == (
        "¿Cuál es la respuesta correcta?\n\n"
        "a) Opción A\n"
        "b) Opción B\n"
        "c) Opción C\n"
        "d) Opción D"
    )
    assert "You are" not in prompt.user_prompt
    assert "Output exactly" not in prompt.user_prompt
    assert "question_id" not in prompt.user_prompt


def test_openrouter_receives_mcq_instructions_and_same_question() -> None:
    prompt = render_benchmark_prompt(QUESTION, provider="openrouter")

    assert prompt.version == BENCHMARK_PROMPT_VERSION
    assert prompt.system_prompt == ""
    assert "select the single best answer" in prompt.user_prompt
    assert "Output exactly one JSON object" in prompt.user_prompt
    assert '"question_id": "g001"' in prompt.user_prompt
    assert "¿Cuál es la respuesta correcta?" in prompt.user_prompt
    assert "a. Opción A" in prompt.user_prompt
    assert "d. Opción D" in prompt.user_prompt


def test_provider_payloads_have_distinct_auditable_hashes() -> None:
    gift = render_benchmark_prompt(
        QUESTION,
        provider="tailscale_medical_rag",
    )
    openrouter = render_benchmark_prompt(QUESTION, provider="openrouter")

    assert gift.user_sha256 != openrouter.user_sha256

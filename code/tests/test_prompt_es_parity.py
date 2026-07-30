"""Asserts the two arms carry the SAME Spanish instructions.

Background. `mcq_shared_v2` (the published run) sent a byte-identical user
message to both arms, so instruction equivalence was a provable fact — 315
shared SHA-256 hashes in the results database. `mcq_provider_v3` gave that up:
GIFT's instructions moved server-side into stored prompt 13, which is not in
this repository, so equivalence became an unverifiable assertion.

`mcq_es_v4` restores the guarantee a different way. The same Spanish instruction
block lives in two files:

* `prompts/mcq_es_v4_user_template.txt` — sent in-message to OpenRouter.
* `prompts/gift_stored_prompt_13_es.txt` — the canonical text of GIFT stored
  prompt 13, kept here so the server-side half is versioned and reviewable.

These tests fail if the two drift. That converts "both arms got the same
instructions" back into something a reviewer can check, without requiring access
to the GIFT backend.

NOTE: this repository cannot verify that the deployed prompt 13 actually matches
`gift_stored_prompt_13_es.txt` — that is a deployment step. What it can and does
guarantee is that the text we *claim* is prompt 13 matches what OpenRouter gets.
"""
from __future__ import annotations

import re
from pathlib import Path

PROMPTS = Path(__file__).resolve().parents[1] / "medrag_eval" / "prompts"
OPENROUTER_TEMPLATE = PROMPTS / "mcq_es_v4_user_template.txt"
GIFT_PROMPT_13 = PROMPTS / "gift_stored_prompt_13_es.txt"

# The single line that legitimately differs: OpenRouter interpolates the real id,
# the server-side prompt can only describe where to find it.
QUESTION_ID_LINE = re.compile(r'^\s*"question_id":\s*".*?",\s*$', re.MULTILINE)
CANONICAL = '  "question_id": "<ID>",'


def _instructions(path: Path) -> str:
    """Instruction block only, normalised for comparison."""
    text = path.read_text(encoding="utf-8")
    # The OpenRouter template appends the question section after a '---' rule.
    text = text.split("\n---\n", 1)[0]
    # It also escapes braces for str.format; the stored prompt does not.
    text = text.replace("{{", "{").replace("}}", "}")
    text = QUESTION_ID_LINE.sub(CANONICAL, text)
    return text.strip()


def test_both_prompt_files_exist():
    assert OPENROUTER_TEMPLATE.is_file()
    assert GIFT_PROMPT_13.is_file()


def test_instruction_blocks_are_identical():
    """The core guarantee: both arms are instructed identically."""
    assert _instructions(OPENROUTER_TEMPLATE) == _instructions(GIFT_PROMPT_13), (
        "The Spanish instruction block has drifted between the OpenRouter template "
        "and the stored-prompt-13 reference. The two arms would no longer be "
        "instructed identically, which is the premise of the arm comparison."
    )


def test_openrouter_template_adds_only_the_question_section():
    text = OPENROUTER_TEMPLATE.read_text(encoding="utf-8")
    assert "\n---\n" in text, "expected a '---' rule separating instructions from the question"
    question_part = text.split("\n---\n", 1)[1]
    for placeholder in ("{question_id}", "{question_text}",
                        "{option_a}", "{option_b}", "{option_c}", "{option_d}"):
        assert placeholder in question_part


def test_stored_prompt_has_no_format_placeholders():
    """Prompt 13 is pasted into GIFT verbatim — a stray {placeholder} would ship literally."""
    text = GIFT_PROMPT_13.read_text(encoding="utf-8")
    for placeholder in ("{question_text}", "{option_a}", "{option_b}",
                        "{option_c}", "{option_d}"):
        assert placeholder not in text


def test_both_mandate_the_json_contract():
    """The output contract must survive in both halves.

    If GIFT stops demanding JSON, every GIFT response falls to the parser's prose
    heuristics — the fragile path that produced the g134/g261 false negatives.
    """
    for path in (OPENROUTER_TEMPLATE, GIFT_PROMPT_13):
        text = path.read_text(encoding="utf-8")
        for key in ("question_id", "selected_letter", "selected_option_text"):
            assert key in text, f"{path.name} lost the {key} key"
        assert "sin markdown" in text, f"{path.name} lost the no-markdown instruction"


def test_negative_stem_rule_is_present():
    """42.5% of the benchmark has a negative stem (see data/README.md)."""
    for path in (OPENROUTER_TEMPLATE, GIFT_PROMPT_13):
        text = path.read_text(encoding="utf-8")
        assert "falsa o incorrecta" in text, f"{path.name} lost the negative-stem rule"


def test_gift_user_message_carries_question_id():
    """Regression: mcq_provider_v3 omitted it, so prompt 13's required key was unanswerable."""
    from medrag_eval.prompting import render_benchmark_prompt

    prompt = render_benchmark_prompt(
        {"question_id": "g134", "question_text": "¿Cuál?", "option_a": "A",
         "option_b": "B", "option_c": "C", "option_d": "D"},
        provider="tailscale_medical_rag",
    )
    assert "question_id: g134" in prompt.user_prompt

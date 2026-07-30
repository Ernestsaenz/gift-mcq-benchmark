"""Guards the two copies of the historical `mcq_shared_v2` template.

After PR #1 the template exists in two places, deliberately:

* `code/mcq_shared_v2_user_template.txt` — the **evidence artifact**. Cited by
  file:line from `EVIDENCE.md` (sections 5 and 9) as the provenance of the prompt
  actually used to produce the committed `bench_315_v2` results. Its path must
  stay stable or those citations break.
* `code/medrag_eval/prompts/mcq_shared_v2_user_template.txt` — the **runtime
  copy**, inside the installed package, which `_default_prompt_dir()` resolves
  and which ships in the wheel.

Two copies can drift, and drift here would be silent and serious: the evidence
document would cite one prompt while the harness rendered another. This test
makes drift impossible to merge.

If you intend to change the historical template, don't — it is the record of
what was sent in May 2026. Add a new versioned template instead.
"""
from __future__ import annotations

from pathlib import Path

import pytest

CODE_DIR = Path(__file__).resolve().parents[1]
EVIDENCE_COPY = CODE_DIR / "mcq_shared_v2_user_template.txt"
RUNTIME_COPY = CODE_DIR / "medrag_eval" / "prompts" / "mcq_shared_v2_user_template.txt"


def test_both_copies_exist():
    assert EVIDENCE_COPY.is_file(), f"missing evidence artifact: {EVIDENCE_COPY}"
    assert RUNTIME_COPY.is_file(), f"missing packaged runtime copy: {RUNTIME_COPY}"


def test_copies_are_byte_identical():
    """The evidence artifact and the runtime copy must never diverge."""
    assert EVIDENCE_COPY.read_bytes() == RUNTIME_COPY.read_bytes(), (
        "mcq_shared_v2 template has drifted between its evidence copy and its "
        "packaged runtime copy. EVIDENCE.md cites the evidence copy as the prompt "
        "used for bench_315_v2; if the harness renders a different one, the "
        "provenance chain is broken."
    )


def test_runtime_copy_is_what_the_package_resolves():
    """`_default_prompt_dir()` must point at the packaged copy, not a stale path."""
    from medrag_eval.prompting import _default_prompt_dir

    resolved = _default_prompt_dir() / "mcq_shared_v2_user_template.txt"
    assert resolved.is_file(), (
        f"_default_prompt_dir() resolves to {_default_prompt_dir()}, which does not "
        "contain the shared template. Before PR #1 this pointed at a nonexistent "
        "<repo-root>/prompts directory."
    )
    assert resolved.read_bytes() == EVIDENCE_COPY.read_bytes()


@pytest.mark.parametrize(
    "marker",
    [
        "board-certified specialist in gastroenterology and hepatology",
        '"selected_letter": "<one of: a, b, c, d>"',
        "If the question asks for the false/incorrect option",
    ],
)
def test_historical_template_content_is_unchanged(marker):
    """Spot-checks the load-bearing parts of the May-2026 prompt.

    The persona line and the JSON contract are quoted in EVIDENCE.md section 5;
    the false/incorrect instruction matters because 134 of 315 items (42.5%)
    have a negative stem (see data/README.md).
    """
    assert marker in EVIDENCE_COPY.read_text(encoding="utf-8")

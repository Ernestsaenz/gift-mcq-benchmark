from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping


VALID_LETTERS = frozenset({"a", "b", "c", "d"})
OPTION_KEYS = {
    "a": "option_a",
    "b": "option_b",
    "c": "option_c",
    "d": "option_d",
}
SUCCESS_STATUSES = frozenset({"ok", "ok_conflict"})


@dataclass(frozen=True)
class ParseResult:
    parse_status: str
    parse_method: str | None = None
    question_id: str | None = None
    selected_letter_raw: str | None = None
    selected_option_text_raw: str | None = None
    selected_letter: str | None = None
    selected_option_text: str | None = None
    exact_text_match: bool = False
    letter_text_conflict: bool = False
    repair_needed: bool = False
    notes: str | None = None

    @property
    def is_successful_for_resume(self) -> bool:
        return self.parse_status in SUCCESS_STATUSES


@dataclass(frozen=True)
class _QuestionOptions:
    question_id: str
    options_by_letter: dict[str, str]
    letters_by_option: dict[str, str]


def parse_openai_response(response: Any, question: Any) -> ParseResult:
    """Parse and validate an OpenAI-style chat completion response."""
    content_result = _extract_content(response)
    if isinstance(content_result, ParseResult):
        return content_result

    content = content_result
    if isinstance(content, Mapping):
        return _parse_answer_object(content, question, parse_method="json_object")

    if not isinstance(content, str):
        return _failed(
            "failed_content_type",
            repair_needed=True,
            notes=f"choices[0].message.content was {type(content).__name__}",
        )

    try:
        parsed_content = json.loads(content)
    except json.JSONDecodeError as exc:
        # Some served models (notably gemma via the medical-RAG backend) wrap an
        # otherwise-valid answer object in a ```json fence. Retry once on the
        # unfenced body. This is deliberately attempted ONLY after a plain
        # json.loads has already failed, so it can never change the outcome of a
        # response that already parsed.
        unfenced = _strip_code_fence(content)
        if unfenced is None:
            return _failed(
                "failed_content_json_invalid",
                repair_needed=True,
                notes=str(exc),
            )
        try:
            parsed_content = json.loads(unfenced)
        except json.JSONDecodeError:
            return _failed(
                "failed_content_json_invalid",
                repair_needed=True,
                notes=str(exc),
            )

    if not isinstance(parsed_content, Mapping):
        return _failed(
            "failed_content_json_not_object",
            repair_needed=True,
            notes=f"content JSON decoded to {type(parsed_content).__name__}",
        )

    return _parse_answer_object(parsed_content, question, parse_method="json_string")


def parse_with_fallback(
    primary_response: Any,
    question: Any,
    repair_response: Any | None = None,
) -> ParseResult:
    """Parse primary output, optionally retry via JSON-repair, then regex repair, then regex primary.

    When `repair_response is None` (used on TailScale, which ignores `role: "system"`
    so a model-side repair call cannot improve behavior), the JSON-repair and
    regex_repair steps are skipped, but the regex_primary fallback still runs on
    the primary response text. This is the difference between "no answer found"
    and "model said 'la respuesta es C' in prose we can still extract."
    """
    primary_result = parse_openai_response(primary_response, question)
    if primary_result.is_successful_for_resume:
        return primary_result

    repair_result: ParseResult | None = None
    if repair_response is not None:
        repair_result = parse_openai_response(repair_response, question)
        if repair_result.is_successful_for_resume:
            return _with_method(repair_result, _repair_json_method(repair_result.parse_method))

        repair_text = _content_as_text(repair_response)
        if repair_text:
            fallback = parse_deterministic_fallback(
                repair_text,
                question,
                parse_method="regex_repair",
            )
            if fallback.is_successful_for_resume:
                return fallback

    primary_text = _content_as_text(primary_response)
    if primary_text:
        fallback = parse_deterministic_fallback(
            primary_text,
            question,
            parse_method="regex_primary",
        )
        if fallback.is_successful_for_resume:
            return fallback

    return _failed(
        "failed_no_answer_found",
        repair_needed=False,
        notes=(repair_result.notes if repair_result is not None else None) or primary_result.notes,
    )


def parse_deterministic_fallback(
    text: str,
    question: Any,
    parse_method: str = "regex",
) -> ParseResult:
    """Extract a selected answer from unstructured text without model calls."""
    options = _question_options(question)
    selected_letter_raw = _find_letter(text)
    selected_option_text_raw = _find_exact_option_text(text, options)

    return _normalize_answer(
        question_id=options.question_id,
        selected_letter_raw=selected_letter_raw,
        selected_option_text_raw=selected_option_text_raw,
        question=question,
        parse_method=parse_method,
        require_question_id=False,
        repair_needed=False,
    )


def _parse_answer_object(
    answer: Mapping[str, Any],
    question: Any,
    parse_method: str,
) -> ParseResult:
    options = _question_options(question)
    missing_keys = [
        key
        for key in ("question_id", "selected_letter", "selected_option_text")
        if key not in answer
    ]
    if missing_keys:
        return _failed(
            "failed_missing_keys",
            parse_method=parse_method,
            repair_needed=True,
            notes=f"missing keys: {', '.join(missing_keys)}",
        )

    question_id = _string_or_none(answer.get("question_id"))
    if question_id != options.question_id:
        return _failed(
            "failed_question_id_mismatch",
            parse_method=parse_method,
            question_id=question_id,
            repair_needed=True,
            notes=f"expected {options.question_id!r}",
        )

    return _normalize_answer(
        question_id=question_id,
        selected_letter_raw=_string_or_none(answer.get("selected_letter")),
        selected_option_text_raw=_string_or_none(answer.get("selected_option_text")),
        question=question,
        parse_method=parse_method,
        require_question_id=True,
        repair_needed=True,
    )


def _normalize_answer(
    *,
    question_id: str | None,
    selected_letter_raw: str | None,
    selected_option_text_raw: str | None,
    question: Any,
    parse_method: str,
    require_question_id: bool,
    repair_needed: bool,
) -> ParseResult:
    options = _question_options(question)
    selected_letter = _normalize_letter(selected_letter_raw)
    selected_option_text = selected_option_text_raw

    if selected_letter_raw is not None and selected_letter is None:
        return _failed(
            "failed_invalid_letter",
            parse_method=parse_method,
            question_id=question_id,
            selected_letter_raw=selected_letter_raw,
            selected_option_text_raw=selected_option_text_raw,
            repair_needed=repair_needed,
        )

    text_letter = None
    exact_text_match = False
    if selected_option_text is not None:
        text_letter = options.letters_by_option.get(selected_option_text)
        exact_text_match = text_letter is not None
        if text_letter is None:
            return _failed(
                "failed_invalid_option_text",
                parse_method=parse_method,
                question_id=question_id,
                selected_letter_raw=selected_letter_raw,
                selected_option_text_raw=selected_option_text_raw,
                selected_letter=selected_letter,
                selected_option_text=selected_option_text,
                repair_needed=repair_needed,
            )

    if selected_letter is None and text_letter is not None:
        selected_letter = text_letter

    if selected_option_text is None and selected_letter is not None:
        selected_option_text = options.options_by_letter[selected_letter]
        exact_text_match = True

    if selected_letter is None and selected_option_text is None:
        return _failed(
            "failed_no_answer_found",
            parse_method=parse_method,
            question_id=question_id if not require_question_id else options.question_id,
            repair_needed=repair_needed,
        )

    letter_text_conflict = (
        selected_letter is not None
        and text_letter is not None
        and selected_letter != text_letter
    )

    return ParseResult(
        parse_status="ok_conflict" if letter_text_conflict else "ok",
        parse_method=parse_method,
        question_id=question_id,
        selected_letter_raw=selected_letter_raw,
        selected_option_text_raw=selected_option_text_raw,
        selected_letter=selected_letter,
        selected_option_text=selected_option_text,
        exact_text_match=exact_text_match,
        letter_text_conflict=letter_text_conflict,
        repair_needed=False,
    )


def _extract_content(response: Any) -> str | Mapping[str, Any] | ParseResult:
    response_json = response
    if isinstance(response, str):
        try:
            response_json = json.loads(response)
        except json.JSONDecodeError as exc:
            return _failed(
                "failed_response_json_invalid",
                repair_needed=True,
                notes=str(exc),
            )

    if not isinstance(response_json, Mapping):
        return _failed(
            "failed_response_not_object",
            repair_needed=True,
            notes=f"response was {type(response_json).__name__}",
        )

    try:
        choices = response_json["choices"]
        first_choice = choices[0]
        message = first_choice["message"]
        return message["content"]
    except (KeyError, IndexError, TypeError) as exc:
        return _failed(
            "failed_missing_content",
            repair_needed=True,
            notes=str(exc),
        )


_FENCE_RE = re.compile(
    r"^\s*```[ \t]*[A-Za-z0-9_+-]*[ \t]*\r?\n(?P<body>.*?)\r?\n?[ \t]*```\s*$",
    re.DOTALL,
)


def _strip_code_fence(content: str) -> str | None:
    """Return the body of a single fenced code block, or None if not fenced."""
    match = _FENCE_RE.match(content)
    if match is None:
        return None
    body = match.group("body").strip()
    return body or None


def _content_as_text(response: Any) -> str:
    content = _extract_content(response)
    if isinstance(content, ParseResult):
        if isinstance(response, str):
            return response
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, Mapping):
        return json.dumps(content, ensure_ascii=False, sort_keys=True)
    return str(content)


# Optional markdown emphasis / quoting noise that models put between the
# declaration phrase and the letter itself: `**d`, `: **(c)`, `la **b**`.
_GAP = r"(?:\s*[:\-–]?\s*\**\s*)"
# The letter must end at a boundary a human would read as "end of the label":
# whitespace, punctuation, a closing paren, or markdown emphasis.
_LETTER_END = r'(?=[\s.,:;)\]\*"\'“”]|$)'

# Tier 0 — the designated machine-readable output channel. If the model emitted
# the JSON key anywhere, that is its answer regardless of surrounding prose.
_AUTHORITATIVE = (r'"selected_letter"\s*:\s*"([a-dA-D])"',)

# The English indefinite article "a" is itself a valid option letter, so
# "the correct answer is a combination of ..." must NOT yield 'a'. Reject a
# capture immediately followed by a genuinely lower-case word. The `(?-i:...)`
# scope matters: the outer search runs case-insensitively, and without it this
# would also reject "answer is b Gastroscopia", where the following word is a
# capitalised option text rather than running prose.
#
# English-only. Spanish has no single-letter article, and applying this there
# would wrongly reject the legitimate "... es la b porque ...".
_NOT_ARTICLE = r"(?!\s+(?-i:[a-z]{2,}))"

_LETTER_EN = r"\(?([a-dA-D])\)?" + _NOT_ARTICLE + _LETTER_END
_LETTER_ES = r"\(?([a-dA-D])\)?" + _LETTER_END

# Tier 1 — the model explicitly DECLARES its answer. These carry intent, so the
# EARLIEST such declaration wins (models state their answer first, then justify).
#
# Both the qualifier and the copula are REQUIRED in the English forms. An
# earlier revision accepted a bare `(?:answer|option|choice)` with an optional
# `is`, which made the enumeration label "Option a" parse as a declaration —
# so "Option a is wrong. The correct answer is d." returned 'a'. That is an
# enumeration label, not a declaration, and belongs in tier 2.
_DECLARATIONS = (
    # English, qualified: "the correct answer is X", "best option is (X)".
    r"\b(?:the\s+)?(?:correct|right|best)\s+(?:answer|option|choice)\s+is"
    + _GAP + _LETTER_EN,
    # English, answer-keyed: "answer is X", "Answer: X", "answer = X".
    r"\b(?:the\s+)?answer\s*(?:is\b|[:=])" + _GAP + _LETTER_EN,
    # Spanish: "La opción correcta es la **d.", "La respuesta **INCORRECTA** es la **c**",
    # "La opción más probable es la **a." — the qualifier may be markdown-wrapped.
    r"\b(?:la\s+)?(?:respuesta|opci[oó]n)\s+\**\s*(?:m[aá]s\s+)?"
    r"(?:correcta|incorrecta|correcto|incorrecto|adecuada|probable|apropiada|verdadera|falsa)"
    r"\s*\**(?:\s+es)?(?:\s+la)?" + _GAP + _LETTER_ES,
)

# Tier 2 — incidental mentions. `(Opción a)` in a differential-diagnosis bullet
# is NOT a declaration, so these rank below tier 1 and are only consulted when no
# declaration exists. Earliest match still wins within the tier.
_INCIDENTAL = (
    r"\bopci[oó]n\s+\**\(?([a-dA-D])\)?" + _LETTER_END,
    r"\boption\s+\**\(?([a-dA-D])\)?" + _LETTER_END,
    r"(?<![\w])([a-dA-D])\)",
    r"(?<![\w])([a-dA-D])\.\s",
)


def _find_letter(text: str) -> str | None:
    """Extract the model's selected letter from unstructured text.

    Candidates are ranked by (tier, position) — NOT by pattern order alone.
    Ranking on pattern order alone is a bug: a model that opens with
    "La opción correcta es la **d.**" and then enumerates "(Opción a)" deep in
    its justification would be scored as `a`, because the incidental pattern
    sits earlier in the tuple than the one matching the declaration. Position
    must dominate within a tier so the model's own stated answer wins.
    """
    for pattern in _AUTHORITATIVE:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)

    for tier in (_DECLARATIONS, _INCIDENTAL):
        best: tuple[int, str] | None = None
        for pattern in tier:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match and (best is None or match.start() < best[0]):
                best = (match.start(), match.group(1))
        if best is not None:
            return best[1]
    return None


def _find_exact_option_text(text: str, options: _QuestionOptions) -> str | None:
    matches = [
        option_text
        for option_text in options.options_by_letter.values()
        if option_text and option_text in text
    ]
    if not matches:
        return None
    return max(matches, key=len)


def _question_options(question: Any) -> _QuestionOptions:
    question_id = _required_question_value(question, "question_id")
    options_by_letter = {
        letter: _required_question_value(question, option_key)
        for letter, option_key in OPTION_KEYS.items()
    }
    return _QuestionOptions(
        question_id=question_id,
        options_by_letter=options_by_letter,
        letters_by_option={option_text: letter for letter, option_text in options_by_letter.items()},
    )


def _required_question_value(question: Any, key: str) -> str:
    if isinstance(question, Mapping):
        value = question.get(key)
    else:
        try:
            value = question[key]
        except (KeyError, TypeError, IndexError):
            value = getattr(question, key)
    if value is None:
        raise ValueError(f"question is missing {key}")
    return str(value)


def _normalize_letter(value: str | None) -> str | None:
    if value is None:
        return None
    letter = value.strip().lower()
    return letter if letter in VALID_LETTERS else None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _failed(
    parse_status: str,
    *,
    parse_method: str | None = None,
    question_id: str | None = None,
    selected_letter_raw: str | None = None,
    selected_option_text_raw: str | None = None,
    selected_letter: str | None = None,
    selected_option_text: str | None = None,
    repair_needed: bool,
    notes: str | None = None,
) -> ParseResult:
    return ParseResult(
        parse_status=parse_status,
        parse_method=parse_method,
        question_id=question_id,
        selected_letter_raw=selected_letter_raw,
        selected_option_text_raw=selected_option_text_raw,
        selected_letter=selected_letter,
        selected_option_text=selected_option_text,
        repair_needed=repair_needed,
        notes=notes,
    )


def _with_method(result: ParseResult, parse_method: str | None) -> ParseResult:
    return ParseResult(
        parse_status=result.parse_status,
        parse_method=parse_method,
        question_id=result.question_id,
        selected_letter_raw=result.selected_letter_raw,
        selected_option_text_raw=result.selected_option_text_raw,
        selected_letter=result.selected_letter,
        selected_option_text=result.selected_option_text,
        exact_text_match=result.exact_text_match,
        letter_text_conflict=result.letter_text_conflict,
        repair_needed=result.repair_needed,
        notes=result.notes,
    )


def _repair_json_method(method: str | None) -> str | None:
    if method == "json_object":
        return "json_repair_object"
    if method == "json_string":
        return "json_repair_string"
    return method

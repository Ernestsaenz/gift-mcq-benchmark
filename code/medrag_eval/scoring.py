from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ScoreResult:
    letter_correct: bool
    text_correct: bool
    strict_correct: bool
    lenient_correct: bool
    answer_text_matches_provided: bool


def score_answer(parsed_answer: Any, question: Any) -> ScoreResult:
    """Score a parsed answer against local gold fields only."""
    selected_letter = _value(parsed_answer, "selected_letter")
    selected_option_text = _value(parsed_answer, "selected_option_text")
    correct_letter = str(_value(question, "correct_letter")).strip().lower()
    correct_option_text = str(_value(question, "correct_option_text"))

    letter_correct = selected_letter is not None and selected_letter.lower() == correct_letter
    text_correct = selected_option_text == correct_option_text
    strict_correct = letter_correct and text_correct
    lenient_correct = letter_correct or text_correct

    return ScoreResult(
        letter_correct=letter_correct,
        text_correct=text_correct,
        strict_correct=strict_correct,
        lenient_correct=lenient_correct,
        answer_text_matches_provided=text_correct,
    )


def _value(source: Any, key: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(key)
    try:
        return source[key]
    except (KeyError, TypeError, IndexError):
        return getattr(source, key)

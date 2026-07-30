"""Regression tests for the answer-extraction defects found in the Tier-1 audit.

Two defects, both in `medrag_eval.parser`:

1. `_find_letter` ranked candidates by PATTERN ORDER only, so an incidental
   "(Opción a)" deep in a justification outranked the model's own opening
   declaration "La opción correcta es la **d.**". Cost: 2 false negatives on
   the GIFT/TailScale gemini arm (questions g134, g261).
2. `parse_openai_response` ran `json.loads` on raw content, so a ```json fence
   forced an otherwise-valid answer object down the regex path. Cost: 313 of
   403 regex-fallback rows were merely fenced JSON.

The `G134_RESPONSE` / `G261_RESPONSE` fixtures are verbatim contiguous PREFIXES of
the stored responses in `data/medrag_eval.sqlite` (experiment `bench_315_v2`,
provider `tailscale_medical_rag`, model `google/gemini-3.5-flash`), truncated at
the end of the line carrying the offending `(Opción a)` mention. Character offsets
asserted below therefore match the real responses exactly. `_question_g134` /
`_question_g261` carry the real option texts and gold letters from the `questions`
table.

Run from `tier1_mcq/code/`:
    uv run --no-project --with pytest python -m pytest tests/ -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from medrag_eval.parser import (  # noqa: E402
    _find_letter,
    _strip_code_fence,
    parse_openai_response,
    parse_with_fallback,
)
from medrag_eval.scoring import score_answer  # noqa: E402


def _question(**overrides):
    """Generic 4-option question; option texts are the real g134 ones."""
    q = {
        "question_id": "q1",
        "option_a": "Determinación de niveles plasmáticos de polipéptido intestinal vasoactivo.",
        "option_b": "Determinación de elastasa fecal.",
        "option_c": "Determinación de niveles de ácido 5-hidroxiindolacético en orina.",
        "option_d": "Determinación de niveles plasmáticos de gastrina y test de secretina.",
        "correct_letter": "d",
        "correct_option_text": "Determinación de niveles plasmáticos de gastrina y test de secretina.",
    }
    q.update(overrides)
    return q


def _question_g134():
    return _question(question_id="g134")


def _question_g261():
    return {
        "question_id": "g261",
        "option_a": ("Los pacientes con diabetes mellitus asociada a pancreatitis crónica "
                     "tienen más facilidad para presentar hipoglucemias respecto a otros "
                     "pacientes diabéticos."),
        "option_b": "La esteatorrea se produce cuando se pierde más del 90% de la función pancreática.",
        "option_c": ("Los pacientes a tratamiento sustitutivo con enzimas pancreáticos se "
                     "monitorizan con test de elastasa fecal semestrales."),
        "option_d": ("El tratamiento sustitutivo con enzimas pancreáticos no mejora el dolor "
                     "asociado a pancreatitis crónica."),
        "correct_letter": "c",
        "correct_option_text": ("Los pacientes a tratamiento sustitutivo con enzimas pancreáticos "
                                "se monitorizan con test de elastasa fecal semestrales."),
    }


def _chat(content: str) -> dict:
    return {"choices": [{"index": 0, "message": {"role": "assistant", "content": content}}]}


# --------------------------------------------------------------------------
# Defect 1 — declaration must beat incidental mention, regardless of pattern order
# --------------------------------------------------------------------------

G134_RESPONSE = (
    "## Respuesta Directa\n"
    "La opción correcta es la **d. Determinación de niveles plasmáticos de gastrina y test "
    "de secretina** (sin respaldo documental).\n"
    "\n"
    "## Justificación Clínica\n"
    "* **Sospecha de Gastrinoma (Síndrome de Zollinger-Ellison):** La presentación de una "
    "úlcera postbulbar refractaria (especialmente tras la erradicación de *H. pylori*), "
    "esofagitis por reflujo grave (grado C) y diarrea es altamente característica de un "
    "gastrinoma (sin respaldo documental). La hipersecreción masiva de ácido gástrico lesiona "
    "la mucosa duodenal y esofágica, y la diarrea se produce por la inactivación de las "
    "enzimas pancreáticas debido al pH extremadamente bajo en el duodeno (sin respaldo "
    "documental).\n"
    "* **Confirmación Diagnóstica:** El paso inicial es la determinación de los niveles de "
    "gastrina sérica en ayunas (sin respaldo documental). Ante niveles elevados que no son "
    "completamente concluyentes (menores de 10 veces el límite superior de la normalidad) "
    "pero con pH gástrico < 2, el **test de estimulación con secretina** es la prueba de "
    "elección (sin respaldo documental). La secretina provoca un aumento paradójico y "
    "significativo de la gastrina plasmática en pacientes con gastrinoma (sin respaldo "
    "documental).\n"
    "\n"
    "## Diagnóstico Diferencial\n"
    "* **Polipéptido Intestinal Vasoactivo (VIP) (Opción a):** Se emplea para el diagnóstico "
    "de VIPoma (síndrome de WDHA: diarrea acuosa, hipopotasemia y aclorhidria), el cual cursa "
    "con hipoclorhidria o aclorhidria, por lo que no produce úlceras pépticas ni esofagitis "
    "grave (sin respaldo documental)."
)

G261_RESPONSE = (
    "### Respuesta directa\n"
    'La respuesta **INCORRECTA** es la **c** ("Los pacientes a tratamiento sustitutivo con '
    'enzimas pancreáticos se monitorizan con test de elastasa fecal semestrales") [1].\n'
    "\n"
    "### Datos clave\n"
    "* **Monitoreo de la insuficiencia pancreática exocrina (IPE):** El test de elastasa "
    "fecal-1 (EF-1) mide específicamente la elastasa de origen humano y no presenta reacción "
    "cruzada con las enzimas pancreáticas de origen porcino utilizadas en el tratamiento "
    "sustitutivo (PERT) [1]. Por lo tanto, los niveles de EF-1 no se normalizan ni varían con "
    "el tratamiento, lo que hace que este test sea inútil para monitorizar la eficacia "
    "terapéutica [1]. La monitorización de la PERT debe ser estrictamente clínica (ganancia "
    "de peso, mejoría de la esteatorrea y síntomas digestivos) y mediante el seguimiento de "
    "parámetros nutricionales (como vitaminas liposolubles, prealbúmina y zinc) [1]. No "
    "existe indicación para realizar determinaciones semestrales de elastasa fecal con este "
    "fin [1].\n"
    "* **Diabetes pancreatógena (Tipo 3c) (Opción a):** Se asocia a una destrucción difusa "
    "del parénquima que afecta tanto a las células beta como a las alfa (productoras de "
    "glucagón) (sin respaldo documental). La ausencia de glucagón compromete la respuesta "
    "contrarreguladora ante la hipoglucemia, lo que predispone a estos pacientes a sufrir "
    "hipoglucemias graves y de difícil control (\"diabetes lábil\") (sin respaldo documental)."
)


def test_fixture_offsets_match_the_real_responses():
    """Guards the fixtures against silent paraphrasing.

    These offsets are the ones quoted in CORRECTION_NOTE.md section 2. If someone
    edits the fixture text, this fails rather than letting the documented
    'declaration at char ~25 vs incidental at char 1283' story drift from what
    the tests actually exercise.
    """
    assert G134_RESPONSE.index("La opción correcta es la") == 21
    assert G134_RESPONSE.index("Opción a") == 1283
    assert G261_RESPONSE.index("La respuesta **INCORRECTA** es la") == 22
    assert G261_RESPONSE.index("Opción a") == 1025


def test_g134_declaration_beats_later_incidental_mention():
    """Declaration at char 21; the '(Opción a)' that used to win is at char 1283."""
    assert _find_letter(G134_RESPONSE) == "d"


def test_g261_incorrecta_declaration_is_recognised():
    """'La respuesta **INCORRECTA** es la **c**' — negative-stem phrasing."""
    assert _find_letter(G261_RESPONSE) == "c"


def test_g134_scores_correct_end_to_end():
    q = _question_g134()
    result = parse_with_fallback(_chat(G134_RESPONSE), q, repair_response=None)
    assert result.parse_status == "ok"
    assert result.selected_letter == "d"
    assert score_answer(
        {"selected_letter": result.selected_letter,
         "selected_option_text": result.selected_option_text}, q).strict_correct


def test_g261_scores_correct_end_to_end():
    q = _question_g261()
    result = parse_with_fallback(_chat(G261_RESPONSE), q, repair_response=None)
    assert result.parse_status == "ok"
    assert result.selected_letter == "c"
    assert score_answer(
        {"selected_letter": result.selected_letter,
         "selected_option_text": result.selected_option_text}, q).strict_correct


@pytest.mark.parametrize(
    "text,expected",
    [
        ("La opción correcta es la **d. Foo**", "d"),
        ("La opción correcta es la d.", "d"),
        ("La respuesta correcta es la **b**", "b"),
        ("La respuesta **INCORRECTA** es la **c**", "c"),
        ("La opción más probable es la **a. Hiperplasia nodular focal**", "a"),
        ("La opción más adecuada es la **b**", "b"),
        ("## Direct Answer\nThe correct option is **b**: ...", "b"),
        ("The answer is (c)", "c"),
        # `_find_letter` returns the raw matched character; `_normalize_letter`
        # lowercases it downstream. Asserting on the raw value on purpose.
        ("The correct answer is: A", "A"),
    ],
)
def test_declaration_phrasings(text, expected):
    assert _find_letter(text) == expected


def test_uppercase_letter_is_normalised_downstream():
    result = parse_with_fallback(
        _chat("The correct answer is: D"), _question(), repair_response=None
    )
    assert result.selected_letter == "d"


@pytest.mark.parametrize(
    "text,expected",
    [
        # Found by adversarial review of the first version of the tiering fix: an
        # English tier-1 pattern of the shape `(answer|option|choice)( is)?` with
        # BOTH the qualifier and the copula optional accepted the enumeration
        # label "Option a" as a declaration, so these all returned 'a'.
        ("Option a is wrong. The correct answer is d.", "d"),
        ("**Option a (Incorrect):** ...\n\n## Direct Answer\nThe correct option is **b**.", "b"),
        ("This option is a reasonable second-line agent. The correct answer is b.", "b"),
        # "a" here is the English indefinite article, not option (a).
        ("The correct answer is a combination of surgery and chemotherapy; formally, answer is c.", "c"),
        ("The best option is a wait-and-see approach, therefore the correct answer is c.", "c"),
    ],
)
def test_english_enumeration_label_is_not_a_declaration(text, expected):
    assert (_find_letter(text) or "").lower() == expected


def test_capitalised_option_text_after_letter_is_not_mistaken_for_an_article():
    """The article guard is scoped to genuinely lower-case words."""
    assert _find_letter("The correct answer is b Gastroscopia con toma de biopsias") == "b"


def test_incidental_mention_still_used_when_no_declaration():
    """Tier 2 is a real fallback, not dead code."""
    assert _find_letter("Se descarta el VIPoma (Opción a) por el contexto.") == "a"


def test_tier2_english_option_pattern_is_reachable():
    """Regression: the over-broad tier-1 pattern made this branch unreachable."""
    assert _find_letter("Option c is listed among the differentials.") == "c"


def test_earliest_declaration_wins_within_tier():
    text = "La opción correcta es la **b**. Aunque la respuesta correcta es la **d** para otros."
    assert _find_letter(text) == "b"


def test_position_beats_pattern_order_across_declaration_patterns():
    """Kills the 'iterate patterns in order, return first hit' implementation.

    The Spanish declaration comes FIRST in the text but its pattern sits LAST in
    `_DECLARATIONS`. A pattern-order implementation returns the English 'd'; only
    position-ranking-within-tier returns the correct 'b'. The preceding test does
    not discriminate, because both of its declarations match the same pattern and
    `re.search` already returns the leftmost match for a single pattern.
    """
    text = ("La opción correcta es la **b**. Se descarta el resto. "
            "In the English-language guideline, the correct answer is d.")
    assert _find_letter(text) == "b"


def test_position_beats_pattern_order_across_incidental_patterns():
    """Same discrimination one tier down: English incidental precedes Spanish."""
    text = "Option c is listed among the differentials, y también (Opción a) se menciona."
    assert _find_letter(text) == "c"


def test_authoritative_json_key_wins_regardless_of_position():
    """A JSON key anywhere outranks any prose, at any distance."""
    text = "La opción correcta es la **a**. " + ("relleno " * 200) + '{"selected_letter": "c"}'
    assert _find_letter(text) == "c"


def test_no_letter_found_returns_none():
    assert _find_letter("No hay informacion suficiente para responder.") is None


# --------------------------------------------------------------------------
# Defect 2 — fenced JSON must parse structurally, not via regex
# --------------------------------------------------------------------------

FENCED = (
    '```json\n{\n "question_id": "q1",\n "selected_letter": "d",\n'
    ' "selected_option_text": "Determinación de niveles plasmáticos de gastrina y test de secretina."\n}\n```'
)


def test_fenced_json_parses_structurally():
    result = parse_openai_response(_chat(FENCED), _question())
    assert result.parse_status == "ok"
    assert result.parse_method == "json_string"   # not regex_primary
    assert result.selected_letter == "d"


@pytest.mark.parametrize("fence", ["```json", "```JSON", "```", "```  json  "])
def test_fence_variants(fence):
    body = '{"question_id": "q1", "selected_letter": "b", "selected_option_text": "Determinación de elastasa fecal."}'
    result = parse_openai_response(_chat(f"{fence}\n{body}\n```"), _question())
    assert result.parse_status == "ok"
    assert result.selected_letter == "b"


def test_unfenced_json_still_parses_unchanged():
    body = '{"question_id": "q1", "selected_letter": "c", "selected_option_text": "Determinación de niveles de ácido 5-hidroxiindolacético en orina."}'
    result = parse_openai_response(_chat(body), _question())
    assert result.parse_status == "ok"
    assert result.parse_method == "json_string"
    assert result.selected_letter == "c"


def test_fence_stripper_ignores_non_fenced_content():
    assert _strip_code_fence('{"a": 1}') is None
    assert _strip_code_fence("plain prose") is None
    assert _strip_code_fence("```\n\n```") is None


def test_prose_with_fence_marker_is_not_mangled():
    """Prose that merely mentions a fence must not be treated as JSON."""
    text = "La opción correcta es la **d**. Ejemplo de formato: ```json ... ```"
    result = parse_with_fallback(_chat(text), _question(), repair_response=None)
    assert result.selected_letter == "d"


def test_fence_fix_cannot_rescue_genuinely_invalid_json():
    result = parse_openai_response(_chat("```json\nnot valid json at all\n```"), _question())
    assert result.parse_status == "failed_content_json_invalid"


# --------------------------------------------------------------------------
# Guardrails on behaviour the audit relied on
# --------------------------------------------------------------------------

def test_letter_text_conflict_is_flagged_not_silently_resolved():
    """Letter 'd' + verbatim option-a text must surface as ok_conflict."""
    q = _question()
    body = (
        '{"question_id": "q1", "selected_letter": "d", '
        f'"selected_option_text": "{q["option_a"]}"}}'
    )
    result = parse_openai_response(_chat(body), q)
    assert result.parse_status == "ok_conflict"
    assert result.letter_text_conflict is True
    assert not score_answer(
        {"selected_letter": result.selected_letter,
         "selected_option_text": result.selected_option_text}, q).strict_correct


def test_letter_only_answer_backfills_text_making_strict_equal_letter():
    """Documents the known degeneracy: strict == letter when text is absent.

    This is why the audit flagged README section 5's claim that strict scoring
    makes the headline 'a floor, not an inflated lenient score'. Locked in as a
    test so any future change to the backfill is a deliberate decision.
    """
    q = _question()
    result = parse_with_fallback(_chat("La opción correcta es la **d**"), q, repair_response=None)
    score = score_answer(
        {"selected_letter": result.selected_letter,
         "selected_option_text": result.selected_option_text}, q)
    assert score.strict_correct == score.letter_correct == score.lenient_correct is True

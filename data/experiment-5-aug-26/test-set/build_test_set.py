"""Deterministically select the 10 Condition-B hard questions for experiment-5.

Source (read-only): ../../experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/
    analysis/openrouter-b-hardest-200/hardest-200-questions.csv
The CSV rows are already in Condition-B form (the NOTA sentinel sits in the correct slot).

Selection (spans the difficulty gradient, weighted to the hardest signal, fully deterministic
by `deterministic_rank`):
  - 5 from the 4-models-wrong core (unanimously wrong)
  - 3 from the 3-models-wrong tier
  - 2 from the 2-models-wrong tier

Outputs (this folder):
  hard10-flat-B.xlsx / .csv   harness-import format (Condition B)
  hard10-ids.json             ids + provenance + difficulty
  hard10-selection.md         human-readable rationale + composition
"""
from __future__ import annotations
import csv, json
from pathlib import Path
from collections import Counter
from openpyxl import Workbook

HERE = Path(__file__).resolve().parent
SRC = (HERE.parent.parent / "experiment-4-aug-26" / "replacements"
       / "ab520-replacement-22-2026-08-04" / "analysis" / "openrouter-b-hardest-200"
       / "hardest-200-questions.csv")
NOTA = "Ninguna de las respuestas anteriores es correcta."

# harness-required columns (17) + traceability trailing columns (importer ignores extras)
COLS = ["question_id","region","year","specialty","exam_part","question_number",
    "question_text","option_a","option_b","option_c","option_d",
    "correct_letter","correct_option_text","flags","page_in_exam_pdf",
    "source_exam_pdf","source_answer_key_pdf","content_sha256","source_key",
    "selection_score","context_ids","origin","negated_stem",
    "deterministic_rank","difficulty_tier_wrong_models","wrong_models_B"]

def main() -> None:
    rows = list(csv.DictReader(SRC.open(encoding="utf-8")))
    for r in rows:
        r["deterministic_rank"] = int(r["deterministic_rank"])
        r["difficulty_tier_wrong_models"] = int(r["difficulty_tier_wrong_models"])
    rows.sort(key=lambda r: r["deterministic_rank"])

    def take(tier: int, n: int) -> list[dict]:
        return [r for r in rows if r["difficulty_tier_wrong_models"] == tier][:n]

    picked = take(4, 5) + take(3, 3) + take(2, 2)
    assert len(picked) == 10, len(picked)
    assert len({r["question_id"] for r in picked}) == 10, "dup ids"

    out_rows = []
    for r in picked:
        # Condition-B integrity: NOTA sits in the correct slot and equals correct_option_text.
        L = r["correct_letter"].strip().lower()
        assert r["correct_option_text"] == NOTA, f'{r["question_id"]}: correct_option_text != NOTA'
        assert r[f"option_{L}"] == NOTA, f'{r["question_id"]}: option_{L} != NOTA'
        out_rows.append({
            "question_id": r["question_id"], "region": r["region"], "year": r["year"],
            "specialty": r["specialty"], "exam_part": r["exam_part"], "question_number": r["question_number"],
            "question_text": r["question_text"], "option_a": r["option_a"], "option_b": r["option_b"],
            "option_c": r["option_c"], "option_d": r["option_d"], "correct_letter": L,
            "correct_option_text": r["correct_option_text"], "flags": "", "page_in_exam_pdf": "",
            "source_exam_pdf": "", "source_answer_key_pdf": "", "content_sha256": r["content_sha256"],
            "source_key": r["source_key"], "selection_score": "", "context_ids": "",
            "origin": r["origin"], "negated_stem": r["negated_stem"],
            "deterministic_rank": r["deterministic_rank"],
            "difficulty_tier_wrong_models": r["difficulty_tier_wrong_models"],
            "wrong_models_B": r["wrong_models_B"]})

    # xlsx (sheet name "questions" like the canonical flat files)
    wb = Workbook(); ws = wb.active; ws.title = "questions"; ws.append(COLS)
    for r in out_rows: ws.append([r[c] for c in COLS])
    wb.save(HERE / "hard10-flat-B.xlsx")
    with (HERE / "hard10-flat-B.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(out_rows)

    ids = [{"question_id": r["question_id"], "source_key": r["source_key"], "origin": r["origin"],
            "correct_letter": r["correct_letter"], "negated_stem": r["negated_stem"],
            "deterministic_rank": r["deterministic_rank"],
            "difficulty_tier_wrong_models": r["difficulty_tier_wrong_models"],
            "wrong_models_B": r["wrong_models_B"]} for r in out_rows]
    (HERE / "hard10-ids.json").write_text(json.dumps(ids, ensure_ascii=False, indent=1))

    tier = Counter(r["difficulty_tier_wrong_models"] for r in out_rows)
    letters = Counter(r["correct_letter"] for r in out_rows)
    neg = Counter(str(r["negated_stem"]) for r in out_rows)
    origin = Counter(r["origin"] for r in out_rows)
    md = [
        "# experiment-5 test set — 10 Condition-B hard questions", "",
        f"Source: `{SRC.relative_to(HERE.parent.parent.parent)}`  (rows already in Condition-B form).", "",
        "Deterministic selection by `deterministic_rank` within difficulty tier "
        "(difficulty = number of the 4 OpenRouter-B models that answered wrong):", "",
        "- 5 from the 4-wrong core (unanimously wrong)",
        "- 3 from the 3-wrong tier",
        "- 2 from the 2-wrong tier", "",
        f"**Composition** — tiers {dict(tier)} · correct-letter {dict(letters)} · "
        f"negated_stem {dict(neg)} · origin {dict(origin)}.", "",
        "| rank | tier(wrong) | id | source_key | key | negated | wrong models (B) |",
        "|---:|---:|---|---|:--:|:--:|---|",
    ]
    for r in out_rows:
        md.append(f"| {r['deterministic_rank']} | {r['difficulty_tier_wrong_models']} | {r['question_id']} | "
                  f"`{r['source_key']}` | {r['correct_letter']} | {r['negated_stem']} | {r['wrong_models_B']} |")
    (HERE / "hard10-selection.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print("WROTE hard10-flat-B.xlsx/.csv, hard10-ids.json, hard10-selection.md")
    print("tiers:", dict(tier), "| letters:", dict(letters), "| negated:", dict(neg), "| origin:", dict(origin))
    print("ids:", [r["question_id"] for r in out_rows])

if __name__ == "__main__":
    main()

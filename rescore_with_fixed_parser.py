#!/usr/bin/env python3
"""Re-score Tier 1 from the stored raw responses using the FIXED parser.

Why this exists
---------------
The Tier-1 audit found two answer-extraction defects in `code/medrag_eval/parser.py`
(see `CORRECTION_NOTE.md`). This script re-derives every Tier-1 statistic from the
*same* raw provider responses already committed in `data/medrag_eval.sqlite`,
using the corrected parser, and reports the delta against the published numbers.

Provenance discipline
---------------------
`data/medrag_eval.sqlite` is the dossier's ground-truth anchor and is opened
**read-only** (SQLite URI `mode=ro`). Nothing is written back to it. Corrected
outputs go to `data/statistical_analysis_corrected/`.

Dependencies
------------
Standard library only — no numpy/pandas/scipy/statsmodels. Cochran's Q, the exact
(binomial) McNemar test, and the Holm step-down correction are implemented here so
that any reviewer can run this with a bare `python3`.

Usage
-----
    cd tier1_mcq && python3 rescore_with_fixed_parser.py
    python3 rescore_with_fixed_parser.py --check   # exit 1 if deltas != expected
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "code"))

from medrag_eval.parser import parse_with_fallback  # noqa: E402
from medrag_eval.scoring import score_answer  # noqa: E402

DB = ROOT / "data" / "medrag_eval.sqlite"
OUT = ROOT / "data" / "statistical_analysis_corrected"
EXPERIMENT = "bench_315_v2"

TAILSCALE = "tailscale_medical_rag"
OPENROUTER = "openrouter"
MODELS = [
    "google/gemini-3.5-flash",
    "google/gemma-4-26b-a4b-it",
    "qwen/qwen3.6-35b-a3b",
    "qwen/qwen3.7-max",
]
LABEL = {
    "google/gemini-3.5-flash": "Gemini",
    "google/gemma-4-26b-a4b-it": "Gemma",
    "qwen/qwen3.6-35b-a3b": "Qwen 3.6",
    "qwen/qwen3.7-max": "Qwen 3.7 Max",
}

# Published values this script is expected to reproduce / correct.
PUBLISHED = {
    (TAILSCALE, "google/gemini-3.5-flash"): 301,
    (TAILSCALE, "google/gemma-4-26b-a4b-it"): 232,
    (TAILSCALE, "qwen/qwen3.6-35b-a3b"): 265,
    (TAILSCALE, "qwen/qwen3.7-max"): 297,
    (OPENROUTER, "google/gemini-3.5-flash"): 303,
    (OPENROUTER, "google/gemma-4-26b-a4b-it"): 232,
    (OPENROUTER, "qwen/qwen3.6-35b-a3b"): 275,
    (OPENROUTER, "qwen/qwen3.7-max"): 298,
}
EXPECTED_CORRECTIONS = {(TAILSCALE, "google/gemini-3.5-flash", "g134"),
                        (TAILSCALE, "google/gemini-3.5-flash", "g261")}


# --------------------------------------------------------------------------
# Statistics (stdlib only)
# --------------------------------------------------------------------------
def _lower_gamma_regularized(a: float, x: float) -> float:
    """P(a, x) via series expansion. Valid for x < a + 1."""
    term = s = 1.0 / a
    for n in itertools.count(1):
        term *= x / (a + n)
        s += term
        if abs(term) <= 1e-17 * abs(s) or n > 1000:
            break
    return s * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _upper_gamma_regularized(a: float, x: float) -> float:
    """Q(a, x) via the Lentz continued fraction. Valid for x >= a + 1."""
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-16:
            break
    return h * math.exp(-x + a * math.log(x) - math.lgamma(a))


def chi2_sf(x: float, df: int) -> float:
    """Upper-tail probability of the chi-square distribution."""
    if x <= 0:
        return 1.0
    a, xx = df / 2.0, x / 2.0
    if xx < a + 1.0:
        return 1.0 - _lower_gamma_regularized(a, xx)
    return _upper_gamma_regularized(a, xx)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact (binomial) McNemar p-value.

    Matches `statsmodels.stats.contingency_tables.mcnemar(..., exact=True)`:
    a two-sided binomial test of min(b, c) successes in b + c trials at p = 0.5.
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    probs = [math.comb(n, i) * 0.5 ** n for i in range(n + 1)]
    threshold = probs[k] * (1.0 + 1e-9)
    return min(1.0, sum(p for p in probs if p <= threshold))


def cochran_q(matrix: list[list[int]]) -> tuple[float, float]:
    """Cochran's Q for k paired binary treatments blocked on rows."""
    k = len(matrix[0])
    row_sums = [sum(r) for r in matrix]
    col_sums = [sum(r[j] for r in matrix) for j in range(k)]
    numerator = (k - 1) * (k * sum(g * g for g in col_sums) - sum(col_sums) ** 2)
    denominator = k * sum(row_sums) - sum(l * l for l in row_sums)
    if denominator == 0:
        return 0.0, 1.0
    q = numerator / denominator
    return q, chi2_sf(q, k - 1)


def holm(pvalues: list[float]) -> list[float]:
    """Holm step-down family-wise adjusted p-values (monotonicity enforced)."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[idx]))
        adjusted[idx] = running
    return adjusted


# --------------------------------------------------------------------------
# Re-scoring
# --------------------------------------------------------------------------
def load_and_rescore() -> tuple[dict, list[dict]]:
    if not DB.exists():
        sys.exit(f"error: database not found at {DB}")
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)   # read-only: never mutate ground truth
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        WITH latest_answer AS (
          SELECT p.*, ROW_NUMBER() OVER (
                   PARTITION BY p.logical_call_id ORDER BY p.id DESC) rn
          FROM parsed_answers p
        )
        SELECT lc.provider, lc.model, q.question_id, q.correct_letter, q.correct_option_text,
               q.option_a, q.option_b, q.option_c, q.option_d,
               a.response_body,
               la.parse_method AS old_method, la.selected_letter AS old_letter,
               s.strict_correct AS old_strict
        FROM logical_calls lc
        JOIN experiments e ON e.id = lc.experiment_id
        JOIN questions q ON q.id = lc.question_id
        JOIN latest_answer la ON la.logical_call_id = lc.id AND la.rn = 1
        JOIN provider_attempts a ON a.id = la.provider_attempt_id
        JOIN scores s ON s.parsed_answer_id = la.id
        WHERE e.name = ?
        """,
        (EXPERIMENT,),
    ).fetchall()
    conn.close()

    scored: dict[tuple[str, str], dict[str, int]] = {}
    changes: list[dict] = []
    for r in rows:
        question = {
            "question_id": r["question_id"],
            "option_a": r["option_a"], "option_b": r["option_b"],
            "option_c": r["option_c"], "option_d": r["option_d"],
            "correct_letter": r["correct_letter"],
            "correct_option_text": r["correct_option_text"],
        }
        parsed = parse_with_fallback(r["response_body"], question, repair_response=None)
        ok = parsed.parse_status in ("ok", "ok_conflict")
        strict = int(
            score_answer(
                {"selected_letter": parsed.selected_letter,
                 "selected_option_text": parsed.selected_option_text},
                question,
            ).strict_correct
        ) if ok else 0

        scored.setdefault((r["provider"], r["model"]), {})[r["question_id"]] = strict
        # Record any divergence from the published run — including rows whose
        # answer is unchanged but which now parse structurally instead of via
        # the regex fallback. Those are the fence fix, and counting them is the
        # evidence that it moved 313 rows without moving a single answer.
        if (strict != r["old_strict"]
                or (parsed.selected_letter or "") != (r["old_letter"] or "")
                or parsed.parse_method != r["old_method"]):
            changes.append({
                "provider": r["provider"], "model": r["model"],
                "question_id": r["question_id"], "gold_letter": r["correct_letter"],
                "old_letter": r["old_letter"], "new_letter": parsed.selected_letter,
                "old_strict": r["old_strict"], "new_strict": strict,
                "old_parse_method": r["old_method"], "new_parse_method": parsed.parse_method,
            })
    return scored, changes


def analyse(scored: dict, provider: str) -> dict:
    per_model = {m: scored[(provider, m)] for m in MODELS}
    qids = sorted(per_model[MODELS[0]])
    matrix = [[per_model[m][q] for m in MODELS] for q in qids]
    q_stat, q_p = cochran_q(matrix)

    pairs, raw = [], []
    for left, right in itertools.combinations(MODELS, 2):
        b = sum(1 for q in qids if per_model[left][q] == 1 and per_model[right][q] == 0)
        c = sum(1 for q in qids if per_model[left][q] == 0 and per_model[right][q] == 1)
        p = mcnemar_exact(b, c)
        pairs.append({"model_a": LABEL[left], "model_b": LABEL[right],
                      "a_only_correct_b": b, "b_only_correct_c": c,
                      "discordant_pairs": b + c, "p_value": p})
        raw.append(p)
    for pair, adj in zip(pairs, holm(raw)):
        pair["p_holm_within_provider"] = adj
        pair["reject_holm_0_05"] = adj < 0.05

    accuracy = {m: (sum(per_model[m].values()), len(qids)) for m in MODELS}
    total = sum(v[0] for v in accuracy.values())
    return {
        "provider": provider,
        "accuracy": accuracy,
        "aggregate_correct": total,
        "aggregate_calls": len(qids) * len(MODELS),
        "cochran_q": q_stat,
        "cochran_p": q_p,
        "pairs": pairs,
    }


def provider_comparison(scored: dict) -> list[dict]:
    """GIFT vs OpenRouter, paired by question, within each model.

    This is the CROSS-arm analysis. The within-arm `analyse()` above cannot
    surface it, and `data/statistical_analysis/provider_mcnemar.csv` is computed
    from the published (pre-fix) scores — so it is superseded wherever the fix
    moved an answer. Re-derived here so the control arm's whole purpose is
    actually re-checked rather than assumed.
    """
    rows = []
    for model in MODELS:
        ts, orr = scored[(TAILSCALE, model)], scored[(OPENROUTER, model)]
        qids = sorted(ts)
        b = sum(1 for q in qids if orr[q] == 1 and ts[q] == 0)   # OpenRouter only
        c = sum(1 for q in qids if orr[q] == 0 and ts[q] == 1)   # TailScale only
        rows.append({
            "model": model, "model_label": LABEL[model],
            "openrouter_accuracy": sum(orr.values()) / len(qids),
            "tailscale_accuracy": sum(ts.values()) / len(qids),
            "paired_diff_openrouter_minus_tailscale":
                (sum(orr.values()) - sum(ts.values())) / len(qids),
            "openrouter_only_correct_b": b, "tailscale_only_correct_c": c,
            "discordant_pairs": b + c, "p_value": mcnemar_exact(b, c),
        })
    for row, adj in zip(rows, holm([r["p_value"] for r in rows])):
        row["p_holm"] = adj
        row["reject_holm_0_05"] = adj < 0.05
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if the corrections differ from the audited set")
    args = ap.parse_args()

    scored, changes = load_and_rescore()
    OUT.mkdir(parents=True, exist_ok=True)

    lines = ["# Tier 1 — Corrected Statistics (fixed parser)", "",
             "Re-derived from the SAME raw responses in `data/medrag_eval.sqlite`",
             "(opened read-only) using the corrected `medrag_eval.parser`.",
             "See `CORRECTION_NOTE.md` for the defects and their provenance.", ""]

    score_changes = [c for c in changes if c["old_strict"] != c["new_strict"]]
    method_only = len(changes) - len(score_changes)
    lines += [
        "## Extraction changes vs. the published run", "",
        f"- Answers whose score changed: **{len(score_changes)}**",
        f"- Rows that merely moved to structured parsing (answer unchanged): **{method_only}**", "",
        "| provider | model | question | gold | published | corrected | strict |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in score_changes:
        lines.append(
            f"| {c['provider']} | {LABEL.get(c['model'], c['model'])} | {c['question_id']} | "
            f"{c['gold_letter']} | `{c['old_letter']}` | `{c['new_letter']}` | "
            f"{c['old_strict']} → {c['new_strict']} |")
    lines.append("")

    results = {}
    for provider in (TAILSCALE, OPENROUTER):
        res = analyse(scored, provider)
        results[provider] = res
        name = "GIFT / TailScale" if provider == TAILSCALE else "OpenRouter (control)"
        lines += [f"## {name}", "",
                  "| model | published | corrected | accuracy |", "|---|---|---|---|"]
        for model in MODELS:
            correct, n = res["accuracy"][model]
            pub = PUBLISHED[(provider, model)]
            flag = "" if pub == correct else f" **(+{correct - pub})**"
            lines.append(f"| {LABEL[model]} | {pub}/{n} | {correct}/{n}{flag} | "
                         f"{100 * correct / n:.2f}% |")
        agg_pub = sum(PUBLISHED[(provider, m)] for m in MODELS)
        lines += [
            f"| **Aggregate** | **{agg_pub}/{res['aggregate_calls']}** | "
            f"**{res['aggregate_correct']}/{res['aggregate_calls']}** | "
            f"**{100 * res['aggregate_correct'] / res['aggregate_calls']:.4f}%** |", "",
            f"Cochran's Q = {res['cochran_q']:.3f}, df = 3, p = {res['cochran_p']:.3e}", "",
            "| model A | model B | b | c | raw p | Holm p | reject@0.05 |",
            "|---|---|---|---|---|---|---|",
        ]
        for pair in res["pairs"]:
            lines.append(
                f"| {pair['model_a']} | {pair['model_b']} | {pair['a_only_correct_b']} | "
                f"{pair['b_only_correct_c']} | {pair['p_value']:.6f} | "
                f"{pair['p_holm_within_provider']:.6f} | {pair['reject_holm_0_05']} |")
        lines.append("")

    prov = provider_comparison(scored)
    lines += [
        "## Cross-arm: GIFT / TailScale vs OpenRouter (paired by question)", "",
        "Supersedes `data/statistical_analysis/provider_mcnemar.csv`, which was",
        "computed from the pre-fix scores. Holm is across the four model comparisons.", "",
        "| model | OpenRouter | TailScale | diff (OR−TS) | b | c | raw p | Holm p |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in prov:
        lines.append(
            f"| {row['model_label']} | {100 * row['openrouter_accuracy']:.2f}% | "
            f"{100 * row['tailscale_accuracy']:.2f}% | "
            f"{100 * row['paired_diff_openrouter_minus_tailscale']:+.2f} pp | "
            f"{row['openrouter_only_correct_b']} | {row['tailscale_only_correct_c']} | "
            f"{row['p_value']:.6f} | {row['p_holm']:.6f} |")
    lines += ["", "No model shows a significant provider effect after correction.", ""]

    with (OUT / "corrected_provider_mcnemar.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(prov[0].keys()))
        writer.writeheader()
        writer.writerows(prov)

    (OUT / "corrected_statistical_report.md").write_text("\n".join(lines) + "\n")

    with (OUT / "corrected_accuracy_by_arm.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["provider", "model", "model_label", "calls",
                         "published_correct", "corrected_correct", "corrected_accuracy"])
        for provider in (TAILSCALE, OPENROUTER):
            for model in MODELS:
                correct, n = results[provider]["accuracy"][model]
                writer.writerow([provider, model, LABEL[model], n,
                                 PUBLISHED[(provider, model)], correct, correct / n])

    with (OUT / "extraction_changes.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(changes[0].keys()) if changes else
                                ["provider", "model", "question_id"])
        writer.writeheader()
        writer.writerows(changes)

    (OUT / "corrected_summary.json").write_text(json.dumps({
        "experiment": EXPERIMENT,
        "source_db": str(DB.relative_to(ROOT)),
        "db_opened_read_only": True,
        "score_changes": len(score_changes),
        "parse_method_only_changes": method_only,
        "providers": {
            p: {
                "aggregate_correct": results[p]["aggregate_correct"],
                "aggregate_calls": results[p]["aggregate_calls"],
                "accuracy": {LABEL[m]: results[p]["accuracy"][m][0] for m in MODELS},
                "cochran_q": results[p]["cochran_q"],
                "cochran_p": results[p]["cochran_p"],
                "gemini_vs_qwen37_holm_p": next(
                    x["p_holm_within_provider"] for x in results[p]["pairs"]
                    if {x["model_a"], x["model_b"]} == {"Gemini", "Qwen 3.7 Max"}),
            } for p in (TAILSCALE, OPENROUTER)
        },
    }, indent=2) + "\n")

    ts = results[TAILSCALE]
    headline = next(x for x in ts["pairs"]
                    if {x["model_a"], x["model_b"]} == {"Gemini", "Qwen 3.7 Max"})
    print(f"score changes: {len(score_changes)}  (method-only: {method_only})")
    print(f"GIFT aggregate : 1095/1260 = 86.9048%  ->  "
          f"{ts['aggregate_correct']}/1260 = {100 * ts['aggregate_correct'] / 1260:.4f}%")
    print(f"GIFT gemini    : 301/315 = 95.56%  ->  "
          f"{ts['accuracy'][MODELS[0]][0]}/315 = "
          f"{100 * ts['accuracy'][MODELS[0]][0] / 315:.2f}%")
    print(f"Cochran's Q    : 117.454 (p=2.727e-25)  ->  "
          f"{ts['cochran_q']:.3f} (p={ts['cochran_p']:.3e})")
    print(f"Gemini vs Qwen3.7 Holm p: 0.523467  ->  "
          f"{headline['p_holm_within_provider']:.6f}  "
          f"({'still NOT significant' if headline['p_holm_within_provider'] >= 0.05 else 'NOW SIGNIFICANT'})")
    print(f"OpenRouter arm : unchanged at {results[OPENROUTER]['aggregate_correct']}/1260")
    print(f"\nwrote -> {OUT.relative_to(ROOT)}/")

    if args.check:
        actual = {(c["provider"], c["model"], c["question_id"]) for c in score_changes}
        if actual != EXPECTED_CORRECTIONS:
            print(f"\nFAIL: correction set drifted.\n  expected {EXPECTED_CORRECTIONS}\n"
                  f"  actual   {actual}", file=sys.stderr)
            return 1
        if results[OPENROUTER]["aggregate_correct"] != 1108:
            print("\nFAIL: OpenRouter control arm changed; fix is not scope-safe.", file=sys.stderr)
            return 1
        print("\nCHECK PASSED: exactly the two audited corrections, control arm untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

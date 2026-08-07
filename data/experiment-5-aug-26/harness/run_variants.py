"""experiment-5 prompt-variant harness (OpenRouter arm, Condition B by default).

Reuses the REAL medrag_eval path so results are apples-to-apples with the published run:
  render_benchmark_prompt(prompt_dir=variants/) -> OpenRouterProvider.chat_completion
  -> parse_openai_response / parse_with_fallback -> score_answer

It NEVER touches code/ (prompt_dir is pointed at experiment-5/variants/). Each variant declares an
output_mode that selects the schema sent to OpenRouter:
  strict_json -> canonical 3-key answer_schema (identical to the published regime)
  cot_json    -> relaxed schema with a LEADING "razonamiento" key (model reasons first; parser ignores it)
  free_cot    -> no schema (prose->JSON, recovered by the regex fallback)

Every call is logged (results/<variant>-<model>.jsonl) and the run appends a ledger row to
experiment-log.{md,jsonl}. Run with --dry-run first to inspect prompts and the call plan (no API spend).

Usage (from repo root, with the project venv):
  .venv/bin/python data/experiment-5-aug-26/harness/run_variants.py --dry-run
  .venv/bin/python data/experiment-5-aug-26/harness/run_variants.py --variants all --models qwen,gemma
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent                      # data/experiment-5-aug-26
VARIANTS_DIR = EXP / "variants"
RESULTS_DIR = EXP / "results"
DEFAULT_WORKBOOK = EXP / "test-set" / "hard10-flat-B.xlsx"
MANIFEST = VARIANTS_DIR / "variants-manifest.json"

from medrag_eval.config import Settings
from medrag_eval.excel_io import import_questions_from_workbook
from medrag_eval.parser import parse_openai_response, parse_with_fallback
from medrag_eval.prompting import render_benchmark_prompt
from medrag_eval.providers import get_provider
from medrag_eval.providers.base import ProviderRequest, ProviderStatus
from medrag_eval.scoring import score_answer

MODEL_ALIASES = {
    "qwen": "qwen/qwen3.6-35b-a3b",
    "gemma": "google/gemma-4-26b-a4b-it",
    "gemini": "google/gemini-3.6-flash",
    "glm": "z-ai/glm-5.2",
}
DEFAULT_MODELS = ["qwen", "gemma"]

# Relaxed schema for cot_json: a LEADING razonamiento key forces the model to reason
# before committing the letter (structured output fills properties in schema order).
COT_SCHEMA = {
    "name": "mcq_answer_cot",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["razonamiento", "question_id", "selected_letter", "selected_option_text"],
        "properties": {
            "razonamiento": {"type": "string"},
            "question_id": {"type": "string"},
            "selected_letter": {"type": "string", "enum": ["a", "b", "c", "d"]},
            "selected_option_text": {"type": "string"},
        },
    },
}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class Variant:
    id: str
    version: str          # template stem: loads {version}_user_template.txt
    output_mode: str      # strict_json | cot_json | free_cot
    technique: str = ""
    change_vs_baseline: str = ""
    hypothesis: str = ""


def load_variants(selected: str) -> list[Variant]:
    """Load variants from the manifest; fall back to scanning template files (dry-run friendly)."""
    variants: list[Variant] = []
    if MANIFEST.is_file():
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        b = data.get("baseline")
        if b:  # baseline is the control and must be scored first (delta reference)
            variants.append(Variant(id=b["id"], version=b["version"],
                output_mode=b.get("output_mode", "strict_json"), technique="baseline control (mcq_es_v4)"))
        for v in data["variants"]:
            variants.append(Variant(
                id=v["id"], version=v["version"], output_mode=v.get("output_mode", "strict_json"),
                technique=v.get("technique", ""), change_vs_baseline=v.get("change_vs_baseline", ""),
                hypothesis=v.get("hypothesis", "")))
    else:
        for path in sorted(VARIANTS_DIR.glob("*_user_template.txt")):
            version = path.name[: -len("_user_template.txt")]
            vid = "baseline" if "baseline" in version else version
            variants.append(Variant(id=vid, version=version, output_mode="strict_json"))
        print(f"[warn] {MANIFEST.name} not found — scanned {len(variants)} template(s), "
              f"assuming strict_json. Real runs should use the manifest.", file=sys.stderr)
    if selected != "all":
        want = {s.strip() for s in selected.split(",") if s.strip()}
        variants = [v for v in variants if v.id in want]
        missing = want - {v.id for v in variants}
        if missing:
            raise SystemExit(f"unknown variant id(s): {sorted(missing)}")
    return variants


def schema_for(mode: str, adapter) -> dict | None:
    if mode == "strict_json":
        return adapter.answer_schema()
    if mode == "cot_json":
        return COT_SCHEMA
    if mode == "free_cot":
        return None
    raise SystemExit(f"unknown output_mode: {mode}")


def _razonamiento_of(resp) -> str | None:
    try:
        content = resp.content_text
        obj = json.loads(content) if isinstance(content, str) else None
        if isinstance(obj, dict) and isinstance(obj.get("razonamiento"), str):
            return obj["razonamiento"]
    except Exception:
        return None
    return None


@dataclass
class Task:
    variant: Variant
    model_alias: str
    model_slug: str
    question: object


def run_one(task: Task, adapter, temperature: float) -> dict:
    q = task.question
    prompt = render_benchmark_prompt(
        q, provider="openrouter", prompt_dir=str(VARIANTS_DIR), prompt_version=task.variant.version)
    schema = schema_for(task.variant.output_mode, adapter)
    req = ProviderRequest(
        provider="openrouter", model=task.model_slug,
        messages=[{"role": "user", "content": prompt.user_prompt}],
        temperature=temperature, top_p=1.0, stream=False, response_schema=schema)
    resp = adapter.chat_completion(req, retry=True)

    row = {
        "ts": _now_iso(), "variant": task.variant.id, "version": task.variant.version,
        "output_mode": task.variant.output_mode, "model_alias": task.model_alias, "model": task.model_slug,
        "question_id": q["question_id"], "correct_letter": str(q["correct_letter"]),
        "user_prompt_sha256": prompt.user_sha256, "latency_ms": resp.latency_ms,
        "prompt_tokens": resp.prompt_tokens, "completion_tokens": resp.completion_tokens,
    }
    if resp.error_type is not None:
        row.update({"api_error": resp.error_type, "parse_status": None,
                    "selected_letter": None, "strict_correct": None})
        return row

    pr = parse_openai_response(resp.response_json, q)
    if pr.repair_needed:
        pr = parse_with_fallback(resp.response_json or resp.response_body or "", q, repair_response=None)
    score = score_answer(pr, q) if pr.selected_letter is not None else None
    row.update({
        "api_error": None, "parse_status": pr.parse_status, "parse_method": pr.parse_method,
        "selected_letter": pr.selected_letter, "exact_text_match": pr.exact_text_match,
        "strict_correct": (bool(score.strict_correct) if score is not None else None),
        "letter_correct": (bool(score.letter_correct) if score is not None else None),
        "razonamiento": _razonamiento_of(resp),
    })
    return row


def main() -> None:
    ap = argparse.ArgumentParser(description="experiment-5 prompt-variant harness (OpenRouter, Condition B)")
    ap.add_argument("--variants", default="all", help="comma-separated variant ids, or 'all'")
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS),
                    help="comma-separated model aliases (qwen,gemma,gemini,glm) or full slugs")
    ap.add_argument("--workbook", default=str(DEFAULT_WORKBOOK), help="flat workbook to score (Condition B by default)")
    ap.add_argument("--limit", type=int, default=None, help="limit number of questions")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true", help="render prompts + print plan; NO API calls")
    ap.add_argument("--outdir", default=str(RESULTS_DIR))
    args = ap.parse_args()

    variants = load_variants(args.variants)
    models = [(m.strip(), MODEL_ALIASES.get(m.strip(), m.strip())) for m in args.models.split(",") if m.strip()]
    imported = import_questions_from_workbook(args.workbook)
    questions = imported.questions[: args.limit] if args.limit else imported.questions
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    plan = [(v, ma, ms, q) for v in variants for (ma, ms) in models for q in questions]
    print(f"variants={len(variants)} models={len(models)} questions={len(questions)} "
          f"=> {len(plan)} calls | workbook={Path(args.workbook).name}")
    for v in variants:
        print(f"  - {v.id:10s} mode={v.output_mode:11s} version={v.version}")

    if args.dry_run:
        # Show one fully-rendered prompt per variant (first question) and stop.
        q0 = questions[0]
        for v in variants:
            p = render_benchmark_prompt(q0, provider="openrouter", prompt_dir=str(VARIANTS_DIR),
                                        prompt_version=v.version)
            print(f"\n===== DRY-RUN render: {v.id} ({v.output_mode}) — q={q0['question_id']} =====")
            print(p.user_prompt)
        print(f"\n[dry-run] {len(plan)} calls planned; no API calls made.")
        return

    settings = Settings.from_env()
    adapter = get_provider("openrouter", settings=settings)
    adapter.healthcheck()

    tasks = [Task(v, ma, ms, q) for v in variants for (ma, ms) in models for q in questions]
    rows: list[dict] = []
    lock = threading.Lock()
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futs = {pool.submit(run_one, t, adapter, args.temperature): t for t in tasks}
        for fut in as_completed(futs):
            r = fut.result()
            with lock:
                rows.append(r); done += 1
                mark = "✓" if r.get("strict_correct") else ("✗" if r.get("strict_correct") is False else "?")
                extra = r.get("api_error") or f"{r.get('selected_letter')}/{r.get('correct_letter')} {mark}"
                print(f"[{done}/{len(tasks)}] {r['variant']:10s} {r['model_alias']:6s} "
                      f"q={r['question_id']:5s} {extra}", flush=True)
    adapter.close()

    # per-variant jsonl logs
    by_variant: dict[str, list[dict]] = {}
    for r in rows:
        by_variant.setdefault(r["variant"], []).append(r)
    for vid, rs in by_variant.items():
        with (outdir / f"{vid}.jsonl").open("w", encoding="utf-8") as f:
            for r in sorted(rs, key=lambda x: (x["model_alias"], x["question_id"])):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    write_summary(rows, variants, models, questions, outdir, args)


def _acc(rs: list[dict]) -> tuple[int, int]:
    graded = [r for r in rs if r.get("api_error") is None and r.get("strict_correct") is not None]
    return sum(1 for r in graded if r["strict_correct"]), len(graded)


def write_summary(rows, variants, models, questions, outdir: Path, args) -> None:
    import csv as _csv
    n_q = len(questions)
    model_aliases = [ma for ma, _ in models]
    # comparison.csv : one row per variant, columns per model + overall + delta-vs-baseline
    base = {r["variant"]: r for r in []}  # placeholder
    per = {v.id: {ma: [r for r in rows if r["variant"] == v.id and r["model_alias"] == ma]
                  for ma in model_aliases} for v in variants}
    overall = {v.id: [r for r in rows if r["variant"] == v.id] for v in variants}

    def pct(rs):
        c, n = _acc(rs); return (100.0 * c / n) if n else float("nan"), c, n

    baseline_overall = pct(overall["baseline"])[0] if "baseline" in overall else float("nan")

    comp_path = outdir / "comparison.csv"
    with comp_path.open("w", newline="", encoding="utf-8") as f:
        cols = ["variant", "output_mode"] + [f"{ma}_acc%" for ma in model_aliases] + \
               [f"{ma}_correct" for ma in model_aliases] + ["overall_acc%", "overall_correct_of", "delta_vs_baseline_pp"]
        w = _csv.writer(f); w.writerow(cols)
        vmap = {v.id: v for v in variants}
        for vid in [v.id for v in variants]:
            row = [vid, vmap[vid].output_mode]
            for ma in model_aliases:
                p, c, n = pct(per[vid][ma]); row.append(f"{p:.1f}")
            for ma in model_aliases:
                p, c, n = pct(per[vid][ma]); row.append(f"{c}/{n}")
            po, co, no = pct(overall[vid])
            row.append(f"{po:.1f}"); row.append(f"{co}/{no}")
            row.append(f"{(po - baseline_overall):+.1f}" if baseline_overall == baseline_overall else "")
            w.writerow(row)

    # summary.json
    summary = {"generated": _now_iso(), "workbook": Path(args.workbook).name, "n_questions": n_q,
               "models": {ma: ms for ma, ms in models}, "temperature": args.temperature,
               "baseline_overall_acc%": round(baseline_overall, 1) if baseline_overall == baseline_overall else None,
               "variants": []}
    for v in variants:
        po, co, no = pct(overall[v.id])
        summary["variants"].append({
            "id": v.id, "output_mode": v.output_mode, "technique": v.technique,
            "overall_acc%": round(po, 1) if po == po else None, "overall_correct": f"{co}/{no}",
            "delta_vs_baseline_pp": (round(po - baseline_overall, 1)
                                     if (po == po and baseline_overall == baseline_overall) else None),
            "by_model": {ma: {"acc%": round(pct(per[v.id][ma])[0], 1), "correct": f"{pct(per[v.id][ma])[1]}/{pct(per[v.id][ma])[2]}"}
                         for ma in model_aliases}})
    (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    append_experiment_log(summary, args)

    # console table
    print("\n==================== RESULTS (strict accuracy) ====================")
    header = f"{'variant':11s} {'mode':11s} " + " ".join(f"{ma:>8s}" for ma in model_aliases) + f" {'overall':>9s} {'Δbase':>7s}"
    print(header); print("-" * len(header))
    for v in summary["variants"]:
        cells = " ".join(f"{v['by_model'][ma]['acc%']:>7.1f}%" for ma in model_aliases)
        d = v["delta_vs_baseline_pp"]
        dtxt = "" if d is None else f"{d:+.1f}"
        print(f"{v['id']:11s} {v['output_mode']:11s} {cells} {str(v['overall_acc%'])+'%':>9s} {dtxt:>7s}")
    print(f"\nwrote {comp_path.name}, summary.json, per-variant jsonl, and appended experiment-log.*")


def append_experiment_log(summary: dict, args) -> None:
    log_md = EXP / "experiment-log.md"
    log_jsonl = EXP / "experiment-log.jsonl"
    entry = {"run_ts": summary["generated"], "workbook": summary["workbook"],
             "n_questions": summary["n_questions"], "models": summary["models"],
             "temperature": summary["temperature"], "baseline_overall_acc%": summary["baseline_overall_acc%"],
             "results": [{"id": v["id"], "mode": v["output_mode"], "overall_acc%": v["overall_acc%"],
                          "delta_vs_baseline_pp": v["delta_vs_baseline_pp"], "by_model": v["by_model"]}
                         for v in summary["variants"]]}
    with log_jsonl.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    lines = [f"\n## Run {summary['generated']} — {summary['workbook']} ({summary['n_questions']}q, "
             f"{', '.join(summary['models'].keys())}, temp {summary['temperature']})", "",
             f"Baseline overall: **{summary['baseline_overall_acc%']}%**", "",
             "| variant | mode | " + " | ".join(summary["models"].keys()) + " | overall | Δ base |",
             "|---|---|" + "---|" * len(summary["models"]) + "---|---|"]
    for v in summary["variants"]:
        by = " | ".join(f"{v['by_model'][ma]['acc%']}%" for ma in summary["models"].keys())
        d = v["delta_vs_baseline_pp"]; dtxt = "" if d is None else f"{d:+.1f}"
        lines.append(f"| {v['id']} | {v['output_mode']} | {by} | {v['overall_acc%']}% | {dtxt} |")
    with log_md.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

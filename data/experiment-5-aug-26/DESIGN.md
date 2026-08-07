# experiment-5-aug-26 — NOTA-robustness prompt variants (design)

Approved 2026-08-05. This folder produces **10 modified prompt variants** (+ a baseline control)
intended to improve model accuracy under the **Condition-B "none-of-the-above" (NOTA)** transform,
plus a **ready-to-run-but-unexecuted** evaluation harness. **The user runs the evaluation and
decides which variants win.** Nothing here executes an evaluation or calls the GIFT/Tailscale API.

## 1. Problem

The A/B benchmark replaces the correct option with *"Ninguna de las respuestas anteriores es
correcta."* (Condition B). This depresses accuracy: models **anchor on the closest surviving
distractor** instead of recognizing that the true answer was removed. The live prompt
(`mcq_es_v4`, temperature 0) gives **no policy for the NOTA option** — it only says "pick the single
best answer." The goal is prompt changes that let the model recognize *answer-absence* and select
Ninguna when (and only when) it is correct.

## 2. Strategy: OpenRouter now, GIFT/RAG later

- **OpenRouter (no-RAG)** is the dev proxy we can test today (Condition B, models **Qwen 3.6 35B**
  `qwen/qwen3.6-35b-a3b` and **Gemma 4 26B** `google/gemma-4-26b-a4b-it` — the two weakest, largest
  headroom).
- **The endgame is GIFT/Tailscale Condition-B**, where retrieved `{chunks}` + a NOTA-aware technique
  should give the **biggest** lift. So every variant ships in **two forms**: an OpenRouter form
  (tested now) and a **GIFT prompt-13 form** that keeps the `{chunks}` / `{question}` placeholders and
  is written to *exploit* retrieval once it is wired in. Chunks are **not** provided at present; the
  placeholder is inert now and helpful later. RAG-amplified variants will therefore look weaker on the
  OpenRouter proxy than they should on GIFT — this is stated in every report.

## 3. Output modes (verified against `parser.py` / `answer_schema`)

The OpenRouter arm enforces a **strict** JSON schema (`additionalProperties:false`, `strict:true`,
3 keys, `selected_letter` enum). So each variant declares an output mode that the harness maps to a schema:

| Mode | Schema sent | Reasoning | Notes |
|---|---|---|---|
| `strict_json` | canonical 3-key `answer_schema` | none (internal) | identical regime to the published run |
| `cot_json` | relaxed schema with a **leading** `"razonamiento"` string key | visible, before the letter | structured output fills keys in order → reasons first; parser **ignores** the extra key |
| `free_cot` | none (`response_schema=None`) | free prose then JSON | recovered by the regex fallback; used only if a variant needs it |

## 4. The 10 variants (+ baseline)

| id | Technique | Mode | RAG-amp | Hypothesis |
|---|---|---|---|---|
| `exp5_baseline` | current `mcq_es_v4` (control) | strict_json | — | reference |
| `v01` | Recall-then-match (instruction-only) | strict_json | ✓ | force independent recall → surface answer-absence |
| `v02` | NOTA calibration (balanced) | strict_json | ✓ | give an explicit two-way rule for the Ninguna option |
| `v03` | Few-shot NOTA exemplars | strict_json | partial | demonstrate answer-absence reasoning in-context |
| `v04` | Chain-of-thought (clinical) | cot_json | ✓ | reasoning space alone lifts hard items |
| `v05` | Option elimination (per-option T/F) | cot_json | ✓✓ | falsify all four → "all false → Ninguna" |
| `v06` | Recall-then-match (visible CoT) | cot_json | ✓✓ | core lever with a visible recall step |
| `v07` | Self-check / verify-revise | cot_json | ✓ | catch premature distractor lock-in |
| `v08` | Confidence / abstention framing | cot_json | ✓ | calibrated doubt routes to Ninguna |
| `v09` | RAG-grounded verification ⭐ | cot_json | ✓✓✓ | **GIFT endgame**: use chunks to verify options; absent → Ninguna |
| `v10` | Stacked best-of | cot_json | ✓✓✓ | ceiling of combined levers |

Split = 3 strict-JSON + 7 CoT (a "mixed spread"). The research pass validates/cites each and may
refine wording; the direction is fixed.

## 5. Test set

10 Condition-B questions from `../experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/`
`analysis/openrouter-b-hardest-200/`, chosen deterministically across the difficulty gradient
(~5 unanimously-wrong core, ~3 three-wrong, ~2 two-wrong), mixing negated/non-negated stems and
correct-key letters. Written as a harness-format `hard10-flat-B.xlsx`. A-forms are kept for an
optional later regression check; **default is B-only** per the approved scope.

## 6. Harness (`harness/run_variants.py`)

Imports `medrag_eval` as a library and reuses the exact
`render_benchmark_prompt → provider.chat_completion → parse_with_fallback → score_answer` path, with
`prompt_dir` pointed at `variants/` so **`code/` is never modified**. Per-variant `output_mode`
selects the schema. Defaults: Qwen + Gemma, temp 0, Condition B. Flags: `--dry-run` (render + plan,
no API spend), `--variants`, `--models`, `--limit`. **Logs every experiment** to
`results/<variant>-<model>.jsonl` and appends to `experiment-log.{md,jsonl}`
(variant → exact change vs baseline → hypothesis → accuracy). The harness is **set up but not run**.

## 7. Execution (dynamic workflow)

1. **Research** — 5 Sonnet-5 agents (parallel), one per cluster (CoT in medical MCQA;
   elimination & none-of-the-above; recall-first/abstention/calibration; Medprompt/few-shot/
   self-consistency; RAG-grounded verification). Structured findings + real citations.
2. **QA checkpoint 1 (~50%)** — 1 Opus-4.8 agent (max reasoning) independently audits research +
   draft templates (render safety, mode↔schema, NOTA-appropriateness, Spanish, citation reality).
3. **Draft** — 5 Sonnet-5 agents author the final OpenRouter + GIFT-13 forms + per-variant hypotheses.
4. **Assembly** — main thread writes harness, workbooks, manifest, folder; render smoke-tests all
   templates (brace-escaping gate).
5. **QA checkpoint 2 (100%)** — 1 Opus-4.8 agent (max reasoning) independently verifies the whole
   deliverable end to end.

## 8. Non-goals

No evaluation executed · no GIFT/Tailscale calls · no changes under `code/` or to the committed
templates · no new benchmark scores. Deliverable = variants + harness + logs, ready for the user.

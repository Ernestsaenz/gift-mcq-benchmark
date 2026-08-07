# experiment-5-aug-26 — NOTA-robustness prompt variants

**Goal.** Find prompt changes that raise model accuracy under the Condition-B *"none-of-the-above"*
(NOTA) transform — where the correct option is replaced by *"Ninguna de las respuestas anteriores es
correcta."* This folder delivers **10 research-backed prompt variants** (+ a baseline control), each in
two forms (OpenRouter + GIFT prompt-13), a **runnable harness**, and a **small live evaluation** on the
OpenRouter arm so you can see which changes actually help. **The endgame is GIFT/RAG Condition-B**; the
OpenRouter run is the dev proxy you can test today.

See `DESIGN.md` for the approved design and `research/NOTA_prompting_research.md` for the evidence base.

## What was found (headline)

<!-- RESULTS-SUMMARY -->
Two runs, 440 live calls (Qwen + Gemma × 10 items × {A, B}), temp 0, **0 API errors**. Baseline: **B = 5%,
A = 70%**. A variant only genuinely helps if it raises B **without** dropping A (else it is just
over-picking the sentinel). The Condition-A regression **overturned the B-only ranking**:

| variant | technique | B (ΔB) | A (ΔA) | verdict |
|---|---|---:|---:|---|
| **v03** | few-shot NOTA exemplars | 20 (+15) | 70 (+0) | ✅ **GENUINE — recommended** |
| **v10** | stacked best-of (symmetric) | 15 (+10) | 70 (+0) | ✅ **GENUINE** |
| v05 | option elimination | 25 (+20) | 55 (−15) | ⚠ over-abstention (B-only "winner") |
| v08 | confidence/abstention | 20 (+15) | 55 (−15) | ⚠ over-abstention |
| v09 | RAG-grounded (`{chunks}` inert here) | 15 (+10) | 60 (−10) | ⚠ needs GIFT to judge |
| v04 / v06 | CoT-only / visible-recall CoT | 10 / 5 | 50 / 35 | ❌ harmful to A |
| v01 / v02 / v07 | instruction-only / self-check | 5 | 65–70 | no effect |

**Bottom line: adopt v03 (and consider v10); do NOT ship v05/v08 despite their B scores.** The B-only
"winner" v05 quietly costs 15 pp on normal questions. **Stacking the two winners (v03+v10 → v11) backfired**
— net −5, it broke the Condition-A balance both held (70%→55%), so NOTA prompting is *not* monotonic: ship
v03 **alone**. Full analysis + the n=20 caveat: **`RESULTS.md`**.

## The 10 variants (+ baseline)

Each is a **minimal, attributable edit** of the live `mcq_es_v4` prompt adding exactly one technique.
Output modes: `strict_json` = the published 3-key contract (no visible reasoning); `cot_json` = a
relaxed schema with a leading `razonamiento` key so the model reasons **before** committing (the parser
ignores the extra key). Full per-variant rationale + citations in `variants/variants-manifest.json`.

| id | technique | mode | RAG-amp | one-line change |
|---|---|---|:--:|---|
| `baseline` | current `mcq_es_v4` control | strict_json | — | unchanged |
| `v01` | recall-then-match (instruction-only) | strict_json | ✓ | silently recall the guideline answer first, then match; absent → Ninguna |
| `v02` | **NOTA calibration (balanced)** | strict_json | ✓ | explicit symmetric rule for the sentinel (pick only on absolute failure of a–d; don't avoid when correct) |
| `v03` | few-shot NOTA exemplars | strict_json | partial | two worked examples (one sentinel-correct, one not) |
| `v04` | chain-of-thought (clinical) | cot_json | ✓ | CoT-only control: reason step by step, then answer |
| `v05` | option elimination (support-framed) | cot_json | ✓✓ | per-option verdadera/falsa verdict; all false → Ninguna |
| `v06` | recall-then-match (visible CoT) | cot_json | ✓✓ | state the ideal answer before options, then match |
| `v07` | self-check / verify-revise | cot_json | ✓ | tentative answer → self-critique (absence? anchoring?) → final |
| `v08` | confidence / abstention framing | cot_json | ✓ | confidence assessment, routed to Ninguna **only on genuine answer-absence** (QA-corrected) |
| `v09` | RAG-grounded verification ⭐ | cot_json | ✓✓✓ | use `{chunks}` to fix the guideline fact, verify each option; absent → Ninguna |
| `v10` | **stacked best-of** | cot_json | ✓✓✓ | recall + per-option elimination + symmetric NOTA rule (+ chunk-grounding in GIFT) |

## Folder map

```
DESIGN.md                     approved design / spec
README.md                     this file
research/
  NOTA_prompting_research.md  synthesis + citations (34 sources)
  research-raw.json           full structured findings (5 clusters)
  qa1-verdict.json            independent Opus QA-1 (pre-run audit of the drafts)
variants/
  exp5_baseline_user_template.txt        control (OpenRouter)
  exp5_vNN_user_template.txt             the 10 OpenRouter forms (tested here)
  gift13/exp5_*_prompt13_es.txt          GIFT prompt-13 forms (for future deploy; keep {chunks}/{question})
  variants-manifest.json                 id → version, output_mode, technique, hypothesis, citations, files
test-set/
  build_test_set.py           deterministic selection script
  hard10-flat-B.xlsx / .csv   the 10 Condition-B hard questions (harness import format)
  hard10-ids.json, hard10-selection.md   ids + provenance + rationale
harness/
  run_variants.py             the runner (reuses medrag_eval; OpenRouter, Condition B)
  validate_templates.py       template QA gate (render-safety + {chunks}/{question} checks)
results/                      per-variant JSONL, comparison.csv, summary.json, run log
experiment-log.md / .jsonl    ledger: each run's variant → change → accuracy → Δ vs baseline
```

## How to run

From the repo root, with the project venv (`.venv/bin/python`; `OPENROUTER_API_KEY` in `.env`):

```bash
# 1. validate every template (render-safety + placeholder checks)
.venv/bin/python data/experiment-5-aug-26/harness/validate_templates.py

# 2. inspect the rendered prompts + call plan WITHOUT spending API credits
.venv/bin/python data/experiment-5-aug-26/harness/run_variants.py --dry-run

# 3. run the small test (11 variants × Qwen+Gemma × 10 Condition-B questions = 220 calls)
.venv/bin/python data/experiment-5-aug-26/harness/run_variants.py --variants all --models qwen,gemma

# options: --variants baseline,v02,v10   --models qwen   --limit 3   --concurrency 10

# 4. Condition-A regression (over-abstention check) + combined verdict
.venv/bin/python data/experiment-5-aug-26/test-set/build_test_set_A.py
.venv/bin/python data/experiment-5-aug-26/harness/run_variants.py --variants all --models qwen,gemma \
    --workbook data/experiment-5-aug-26/test-set/hard10-flat-A.xlsx --outdir data/experiment-5-aug-26/results/condition-A
.venv/bin/python data/experiment-5-aug-26/harness/analyze_ab.py   # -> results/condition-AB-summary.csv
```

Results land in `results/` and a ledger row is appended to `experiment-log.md` / `.jsonl`.

## Deploying a variant to GIFT/Tailscale (future)

The `gift13/` forms are stored-prompt-13 bodies that keep the `{chunks}` and `{question}` injection
points. To test one on the RAG arm, replace the server-side stored prompt-13 text with the variant's
GIFT form and run the GIFT arm. Note: **`cot_json` GIFT forms add a leading `razonamiento` key**, so the
backend's "solo el objeto JSON" / 3-key validation must be relaxed to accept a 4-key object, or the key
will be stripped/rejected. The `strict_json` GIFT forms (v01/v02/v03) need no server change.

## Caveats (read before interpreting)

1. **OpenRouter is a proxy without retrieval.** The RAG-amplified variants (v05/v06/v09/v10) have an
   inert `{chunks}` clause here; their true potential shows only on GIFT. The OpenRouter numbers
   **under-estimate** them.
2. **Over-abstention — now measured, not just flagged.** The **Condition-A regression was run** (same 10
   items, A forms; `test-set/hard10-flat-A.xlsx`, `results/condition-A/`, `results/condition-AB-summary.csv`)
   and it **overturned the B-only ranking**: v05/v08/v09 gain on B only by over-picking the sentinel and
   cost 10–15 pp on A, while **v03 and v10 raise B with zero A cost**. Always read B and A together.
3. **10 questions, 1 run, temp 0.** This is a directional probe, not a powered benchmark. Promising
   variants should be run on the full hard-200 (and then the full 500) before any conclusion.
4. **Citations:** most are real/verifiable; a few 2025–2026 preprints sit past the assistant's knowledge
   cutoff and one (`arXiv:2605.15000`) was QA-flagged as likely fabricated — see the research doc.

## Provenance

Built by a dynamic multi-agent workflow: **5 Sonnet research agents** (web-cited) → **5 Sonnet draft
agents** (variant authoring) → **Opus-4.8 QA-1** (pre-run audit; caught 3 blocking issues, all fixed) →
deterministic assembly + template validation → live OpenRouter **Condition-B run** → **Condition-A
regression** → combined analysis. QA-2: the independent Opus verifier stalled on a file read, so the
final verification was done **deterministically in-thread** (accuracy independently recomputed from the
440 raw per-call logs; 15/15 checks pass, numbers match `comparison.csv`). Workflow run `wf_027edb0d`.
Nothing under `code/` or the committed templates was modified.

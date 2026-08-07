# experiment-5 — OpenRouter Condition-B results (2026-08-05)

Run: 11 variants (baseline + v01–v10) × {Qwen 3.6 35B, Gemma 4 26B} × 10 hardest Condition-B questions
= **220 live OpenRouter calls, temperature 0, 0 API errors**. Harness: `harness/run_variants.py`
(reuses the real `medrag_eval` render/parse/score path). Raw per-call logs: `results/*.jsonl`; table:
`results/comparison.csv`; ledger: `experiment-log.md` / `.jsonl`.

## Integrity

- **220/220 scored, 0 API errors.** Parse: 211 clean structured JSON + 9 recovered by the regex
  fallback (all 220 resolved to a letter and were scored).
- **CoT worked:** all 7 `cot_json` variants emitted a populated `razonamiento` in **20/20** rows — the
  relaxed leading-key schema forced reasoning before the committed letter, and the parser ignored the
  extra key as designed.

## Accuracy (strict) and delta vs baseline

| rank | variant | technique | mode | qwen | gemma | **overall** | Δ vs base |
|---:|---|---|---|---:|---:|---:|---:|
| 1 | **v05** | option elimination (per-option verification) | cot_json | 20% | 30% | **25.0%** | **+20.0** |
| 2 | **v03** | few-shot NOTA exemplars | strict_json | 10% | 30% | **20.0%** | **+15.0** |
| 2 | **v08** | confidence / abstention (QA-corrected) | cot_json | 30% | 10% | **20.0%** | **+15.0** |
| 4 | v09 | RAG-grounded verification ⭐ | cot_json | 10% | 20% | 15.0% | +10.0 |
| 4 | v10 | stacked best-of | cot_json | 0% | 30% | 15.0% | +10.0 |
| 6 | v04 | chain-of-thought (control) | cot_json | 10% | 10% | 10.0% | +5.0 |
| 7 | baseline | current `mcq_es_v4` | strict_json | 0% | 10% | 5.0% | — |
| 7 | v01 | recall-then-match (instruction-only) | strict_json | 10% | 0% | 5.0% | +0.0 |
| 7 | v02 | NOTA calibration (instruction-only) | strict_json | 0% | 10% | 5.0% | +0.0 |
| 7 | v06 | recall-then-match (visible CoT) | cot_json | 0% | 10% | 5.0% | +0.0 |
| 7 | v07 | self-check / verify-revise | cot_json | 0% | 10% | 5.0% | +0.0 |

## Reading (directional — see the hard caveat)

1. **Per-option verification (v05) is the standout (+20pp).** Forcing an explicit verdadera/falsa verdict
   for every option before choosing — framed as *support*, not refutation (per Balepur 2024) — helped
   most on the hardest items. Consistent with the POE literature.
2. **Few-shot exemplars (v03, +15) and calibrated abstention (v08, +15) also helped.** v08's gain
   survived the QA fix that decoupled the sentinel from mere low confidence, which is reassuring.
3. **Generic CoT alone (v04) barely moved (+5).** This matches the research: reasoning space by itself
   does not close the NOTA gap — the *specific* mechanisms do.
4. **Instruction-only levers (v01, v02) and visible recall (v06) / self-check (v07) did nothing here.**
   Notably v02 (NOTA calibration) — the research's top pick — was flat as a pure instruction; the models
   may need the reasoning *scaffold* (v05/v08) to act on the rule, not just the rule.
5. **RAG variants (v09, v10) scored +10 with their `{chunks}` clause INERT** (no retrieval on
   OpenRouter). This is a **floor**, not their real value — the whole point is that retrieved evidence
   should lift them further on GIFT. Do not rank them against the others from this proxy.

## ⚠ The decisive caveat: this cannot yet tell you what "works"

On these 10 items the correct answer is **always** the NOTA sentinel, so **Condition-B accuracy is
identical to the sentinel-selection rate.** A variant scores higher here *either* by genuinely detecting
answer-absence *or* by simply picking "Ninguna" more often. **B-only data cannot distinguish the two.**
A prompt that over-picks the sentinel would look great here and *destroy* Condition-A accuracy.

**Therefore the winners (v05/v03/v08) are provisional.** The required confirmation is a **Condition-A
regression** on the same items (where picking Ninguna is *wrong*): a genuine technique keeps A high while
lifting B; an over-abstention artifact tanks A. This is one command away once an A-form workbook is built
(`run_variants.py --workbook <A>.xlsx`).

Also: **n = 20 per variant** (baseline 1/20). Each correct answer = 5pp, so these deltas are a few
questions — a directional probe, not a powered result.

## Condition-A regression — the decisive result (RESOLVED 2026-08-05)

Ran the same 220-call design on the **Condition-A** forms of the identical 10 questions (real answer in
the correct slot, not the sentinel). Source: `test-set/hard10-flat-A.xlsx` (built from the adjusted
catalog; each A form is the verified pair of its B form). Combined table: `results/condition-AB-summary.csv`.

**Baseline: B = 5%, A = 70%** (n = 20 per cell). A variant genuinely improves NOTA robustness only if it
raises B **without** dropping A; a variant that gains B while losing A is winning by **over-picking the
sentinel** (over-abstention), which is worthless in production.

| variant | technique | B% (ΔB) | A% (ΔA) | net | verdict |
|---|---|---:|---:|---:|---|
| **v03** | few-shot NOTA exemplars (strict_json) | 20 (+15) | 70 (+0) | **+15** | ✅ **GENUINE** |
| **v10** | stacked best-of (recall+elim+symmetric rule) | 15 (+10) | 70 (+0) | **+10** | ✅ **GENUINE** |
| v05 | option elimination | 25 (+20) | 55 (−15) | +5 | ⚠ over-abstention |
| v08 | confidence/abstention | 20 (+15) | 55 (−15) | 0 | ⚠ over-abstention |
| v09 | RAG-grounded (chunks INERT here) | 15 (+10) | 60 (−10) | 0 | ⚠ over-abstention* |
| v04 | chain-of-thought (control) | 10 (+5) | 50 (−20) | −15 | ❌ harmful |
| v06 | recall-then-match (visible CoT) | 5 (+0) | 35 (−35) | −35 | ❌ harmful |
| v01 | recall (instruction-only) | 5 (+0) | 65 (−5) | −5 | no effect |
| v02 | NOTA calibration (instruction-only) | 5 (+0) | 70 (+0) | 0 | neutral |
| v07 | self-check / verify-revise | 5 (+0) | 70 (+0) | 0 | neutral |

### What this changes

- **The B-only "winner" (v05, +20 B) is largely an over-abstention artifact** — it costs **−15 pp on A**.
  Same for v08 and v09. Judged on B alone you would have shipped a prompt that quietly breaks normal items.
- **Only two variants are genuine wins: v03 (few-shot, +15 net) and v10 (stacked, +10 net)** — both raise
  B with **zero** A cost. **v03 is the recommended change.**
- **The A cost tracks unbalanced reasoning, not CoT per se.** Every cot_json variant dropped A **except
  v10** — whose *symmetric* decision rule and recall+elimination structure protected A (70%) that bare
  elimination (v05, 55%) did not. Likewise v03's exemplars (one sentinel-correct, one not) model balance.
  The lesson: **the mechanism must be symmetric/balanced**, or it over-abstains.
- **CoT-only (v04) and visible-recall (v06) actively harm A** (−20, −35) — consistent with the research
  that unstructured reasoning degrades knowledge items.
- \*v09 is **RAG-amplified and its `{chunks}` clause is inert on OpenRouter**, so its A drop here is the
  ungrounded fallback behaving like the other elimination variants. Its real behavior needs the GIFT arm.

### n = 20 caveat still applies

Each cell is 20 calls; ±1 question = ±5 pp. Treat exact deltas as directional. The **pattern** —
few-shot / balanced-stacked hold A while bare elimination / CoT-only drop it — is consistent across many
variants, which is stronger than any single cell.

## Mix experiment — do v03 and v10 stack? (No.)

Tested whether combining the two genuine winners sums their benefits. Built **v11** as a *proper*
integration (not concatenation): v10's 3-step reasoning scaffold + 4-key `cot_json` output, **plus** v03's
two balanced exemplars rewritten to demonstrate that CoT output (one sentinel-correct, one normal-correct).
Ran on both conditions (`results/v11.jsonl`, `results/condition-A/v11.jsonl`; 40 calls, 0 errors, 20/20
reasoning present, clean structured parse).

| variant | B (ΔB) | A (ΔA) | net | verdict |
|---|---:|---:|---:|---|
| v03 (parent) | 20 (+15) | 70 (+0) | +15 | ✅ genuine |
| v10 (parent) | 15 (+10) | 70 (+0) | +10 | ✅ genuine |
| **v11 (mix)** | 15 (+10) | **55 (−15)** | **−5** | ⚠ **regressed (A↓)** |

**The benefits did not sum — they anti-synergized.** v11 (a) failed to beat even the better parent on B
(+10 vs v03's +15), and (b) **broke the Condition-A balance both parents individually held** (70% → 55%),
turning two genuine winners into a net-negative prompt.

**Mechanism (corrected after independent QA — this is *not* over-abstention).** Condition A contains **no
"Ninguna" option**, so sentinel over-picking is impossible by construction; a QA read of all 9 Condition-A
errors found **zero** abstentions — every one is a substantive *wrong-real-option* pick. The A-loss is
therefore **CoT-induced degradation**: v11's heavy stacked reasoning (strict per-option "mark imperfect as
*incorrecta*" + two long worked demonstrations) destabilizes the model on normal items, consistent with the
"CoT can hurt clinical knowledge" literature. **The entire −15 pp is Gemma (6/10 → 3/10); Qwen is unchanged
(8/10)** — the compounding reasoning load degrades the weaker model and spares the stronger one. (The
`analyze_ab` "over-abstention" tag is a heuristic name for the B↑/A↓ *pattern*, not a row-level diagnosis.)

**Lesson: NOTA-robustness prompting is not monotonic.** More reasoning + more NOTA-awareness is not better —
two individually-safe techniques can combine into a harmful one, and the damage lands on the weaker model.
Ship v03 (or v10) **alone**; do not stack them.

**n caveat (tightened by QA).** 10 questions × 2 models = 20 observations per cell; each observation = 5 pp,
each *question* = 10 pp. The −15 pp A drop is **3 items, all in Gemma** — genuinely fragile and directional;
confirm on the full hard-200 (both A and B) before treating "the mix regresses" as more than a signal.

## Recommended next steps

1. **Adopt v03 alone** (v10 as alternative); **do not** ship v05/v08 (fail the A regression) and **do not**
   stack v03+v10 (the mix regresses).
2. Re-run **v03, v10, v05, v11** on the **full hard-200**, then the **full 500 with both A and B**, for
   powered estimates (n=20 here is directional).
3. **Deploy the v03 (and v09/v10) GIFT forms** on Tailscale when available — the RAG arm is the endgame, and
   v09/v10 exploit `{chunks}` (their true value is invisible on the OpenRouter proxy).

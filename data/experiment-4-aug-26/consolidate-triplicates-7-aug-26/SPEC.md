# SPEC — shared ground truth for the consolidation task

Every agent working in this folder MUST use the figures below rather than
re-deriving them independently, and MUST verify any figure it depends on against
the primary sources before writing it into a deliverable. Where a check disagrees
with this file, report the disagreement rather than silently overwriting it.

Written 2026-08-07. Base directory:
`data/experiment-4-aug-26/consolidate-triplicates-7-aug-26/`

## Primary sources (read-only — never modify)

| Role | Path |
| --- | --- |
| Run 1 results, 6000 cells | `data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/exports/benchmark-6000-cell-results-adjusted.csv` |
| Runs 2-3 database | `data/experiment-4-aug-26/replications/ab520-incorrect-cells-triplicate-2026-08-05/runs/ab520-incorrect-cell-triplicates-2026-08-05.sqlite` |
| Frozen replicate ledger | `.../ab520-incorrect-cells-triplicate-2026-08-05/manifests/frozen-replicate-cell-ledger.csv` |
| Preparation summary + hashes | `.../manifests/preparation-summary.json` |
| Pre-execution DB snapshot | `.../manifests/ab520-incorrect-cell-triplicates.pre-execution.sqlite` |
| Invocation records (34 files) | `.../invocations/*.json` |
| Per-invocation logs (34 files) | `.../logs/*.jsonl` |
| Narrative status | `.../ab520-incorrect-cells-triplicate-2026-08-05/STATUS.md` |

Open the SQLite database READ-ONLY. `sqlite3 -readonly` has failed on this
machine; use `sqlite3 "file:<abs-path>?mode=ro"` instead. Do not write to it.

## Design

Run 1 evaluated 500 questions x 3 arms x 4 models = 6000 cells, all answered.
898 of those were strictly incorrect (`strict_correct == "0"`). Only those 898
cells were repeated, at run indices 2 and 3, giving 1796 frozen logical calls.
The 5102 correct cells were never repeated — that is by design, not a gap.

Arms: `openrouter_A`, `openrouter_B`, `tailscale_A`.
Models: `google/gemini-3.6-flash`, `google/gemma-4-26b-a4b-it`,
`qwen/qwen3.6-35b-a3b`, `z-ai/glm-5.2`.

## Authoritative figures

Total scored: **1788 / 1796 (99.6%)**.

| Arm | Scored | Total |
| --- | --- | --- |
| openrouter_A | 406 | 406 |
| openrouter_B | 1057 | 1064 |
| tailscale_A | 325 | 326 |

Per arm x model (scored/total): or_A gemini 18/18, gemma 210/210, qwen 116/116,
glm 62/62. or_B gemini 93/100, gemma 458/458, qwen 284/284, glm 222/222.
ts_A gemini 26/26, gemma 162/162, qwen 98/98, glm 39/40.

Replicate completeness across the 898 run-1-incorrect cells:
**893 have both runs 2 and 3; 2 have only one; 3 have neither.**

The 8 unscored logical calls are all exhausted at the five-attempt ceiling:
or_B gemini n012 r2+r3, n036 r2+r3, b326 r2+r3, b373 r2; ts_A glm b264 r2.

Integrity: 1787 parses `ok`, 1 `ok_conflict`; no score without a provider
attempt; no logical call exceeds 5 attempts.

## PROTOCOL DEVIATION — must appear in every deliverable that reports gemini_B

91 of the 93 scored `openrouter_B` / gemini cells were served by **Google Vertex**
with `provider.require_parameters` relaxed. Vertex does not support `temperature`
or `top_p`, so the declared `temperature=0` was **silently dropped** and the model
sampled at its default temperature. Measured before authorisation: three repeats
of one frozen request returned `['b','c','b']`.

The remaining 2 gemini_B cells were served by Google AI Studio at real
`temperature=0` on 2026-08-05, before the shared pool blocked.

Every other cell in the study ran at `temperature=0`.

Consequence: gemini_B run-to-run variance contains provider sampling noise that
no other slice carries. A gemini A-vs-B contrast compares two sampling regimes,
not two prompt conditions. **Do not pool without stratifying.**

Attribution rule — attribute by the upstream that served the SCORING attempt, not
by attempt history. Three of the 91 Vertex cells also carry earlier failed AI
Studio attempts; counting by history double-counts them.

Those three cells, verified against the database on 2026-08-07 (an earlier draft
of this file said "2"; that figure predated the final Vertex batch and was wrong):

| Arm | Model | Question | Run | Distinct request_sha256 | Attempts | Scored |
| --- | --- | --- | --- | --- | --- | --- |
| openrouter_B | gemini-3.6-flash | b101 | 2 | 2 | 5 | yes |
| openrouter_B | gemini-3.6-flash | b323 | 2 | 2 | 3 | yes |
| openrouter_B | gemini-3.6-flash | b373 | 3 | 2 | 5 | yes |

All three scored on their Vertex attempt; the earlier AI Studio attempts returned
429 and produced nothing, so each score still has one unambiguous provenance.

```sql
-- upstream that produced each score
SELECT COALESCE(json_extract(pa.request_json,'$.provider.order[0]'),'google-ai-studio')
FROM provider_attempts pa WHERE pa.status_code = 200
```

Affected attempts also record `"provider": "Google"` in `response_json` (Vertex)
rather than `"Google AI Studio"`, and hash to a different `request_sha256`.

Note: in the study's own data model the provider for ALL these cells is
`openrouter` and the arm is `openrouter_B` — Vertex is an upstream *inside*
OpenRouter, not an alternative to it. Grouping by provider is therefore correct;
the temperature difference is the thing that must be disclosed.

## File ownership — do NOT write outside your assigned paths

| Agent | Owns |
| --- | --- |
| 1 data-export | `exports/` |
| 2 ledger | `ledger/` |
| 3 provenance | `provenance/` |
| 4 analysis | `analysis/` |
| 5 docs | `README.md`, `METHODS.md`, `DEVIATIONS.md` |

Do not create `checksums.sha256`; the coordinator generates it last, after all
outputs exist.

## Standards

- Every CSV gets a header row; use `\n` line endings and UTF-8.
- Never invent a number. If you cannot verify something, write `UNVERIFIED` and
  say why.
- Prefer recording provenance (source path, query, timestamp) alongside results.
- Do not modify anything outside this folder.

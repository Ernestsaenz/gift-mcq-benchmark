# Methods

## Benchmark

500-question Spanish-language multiple-choice benchmark (the "adjusted" AB520
question set). Each question was evaluated in **3 arms x 4 models = 12
arm-model conditions**. Run 1 answered all 500 questions in every condition,
giving 6,000 cells total.

Arms:

- `openrouter_A`
- `openrouter_B`
- `tailscale_A`

Models:

- `google/gemini-3.6-flash`
- `google/gemma-4-26b-a4b-it`
- `qwen/qwen3.6-35b-a3b`
- `z-ai/glm-5.2`

## Why only the run-1-incorrect cells were repeated

Run 1 scored every cell `strict_correct` (1) or not (0). Of the 6,000 cells,
**898 were strictly incorrect**. This replication study repeats only those 898
cells, at two further independent run indices (2 and 3), producing **1,796
frozen logical calls**. The 5,102 cells that were correct in run 1 were never
repeated — that is a deliberate scope decision, not missing coverage.

**This is a conditional sample, and that has one consequence you must not lose
sight of:** every number this study produces — a flip rate, a stability rate,
an "N of 3 wrong" count — is conditioned on the model having failed that
question on its first attempt. It answers "given a model got this wrong once,
how often does it get it right (or wrong) again?" It does **not** answer "what
is this model's accuracy?", and it must never be pooled with, or presented
alongside, the 5,102 never-repeated correct cells as if it were a general
accuracy estimate. The two populations (repeated-because-wrong vs.
never-repeated-because-right) are not exchangeable, and the 898 is a biased
sample of the 500-question set by construction.

## Frozen targets

Before execution began, the 898 incorrect cells were fixed into a single
**frozen replicate cell ledger**
(`replications/ab520-incorrect-cells-triplicate-2026-08-05/manifests/frozen-replicate-cell-ledger.csv`),
listing the exact 1,796 (arm, model, question, run_index) targets to be
executed, run_index restricted to `{2, 3}`. A pre-execution SQLite snapshot and
a `preparation-summary.json` record the SHA-256 hashes of the source results
file, the input condition files, the ledger itself, and the database, so the
target set can be verified as unchanged from what was planned. The source run-1
results file is
`replacements/ab520-replacement-22-2026-08-04/exports/benchmark-6000-cell-results-adjusted.csv`,
recorded with `source_results_sha256` in `preparation-summary.json`.

Each logical call carries a `system_prompt_sha256` / `user_prompt_sha256` pair;
the executor refuses to record an attempt against a logical call whose prompt
hash does not match the frozen value, so the request that produced a score is
provably the request that was planned.

## Prompt and request parameters

Every call in this study — repeated cell or not — used:

- Prompt version **`mcq_es_v4`** (the same instruction set as run 1; both arms
  share it).
- **`temperature = 0`, `top_p = 1`** (declared on every request).
- OpenRouter's **JSON-schema-enforced** response format, for arms served
  through OpenRouter.
- **GIFT prompt ID 13** on the `tailscale_A` arm.

`require_parameters: true` on OpenRouter requests
(`code/medrag_eval/providers/openrouter.py`) makes the request fail loudly if a
provider can't honor `temperature`/`top_p`, rather than silently serving it
under different sampling — this is an integrity guarantee shared by every
experiment in this repository, not a routing preference specific to this
study. One exception to that guarantee was made under explicit authorization;
see DEVIATIONS.md.

## Technical retries vs. independent replicates — how they're distinguished

These are two different things and the data model keeps them separate:

- A **replicate** is one of the frozen (arm, model, question, run_index)
  targets in the ledger — run_index 2 or run_index 3. Two replicates for the
  same run-1-incorrect cell are independent draws and are the unit this study
  is about.
- A **provider attempt** is one HTTP call made in pursuit of scoring a single
  logical call (replicate). If a call fails for a technical reason — rate
  limiting, transport error, timeout — the executor may attempt the *same*
  logical call again. These retries are attempts inside one logical replicate;
  **they are never counted as additional independent runs**, and they never
  change what run_index a score is attributed to.

## The five-attempt ceiling

Each logical call may accumulate **up to 5 provider attempts** before the
executor gives up on it (`--max-provider-attempts`, default and used value 5,
enforced to be between 1 and 5). Once a logical call reaches 5 attempts without
producing a parseable score, it is recorded as exhausted and the executor will
not attempt it again under the current protocol. In this run, 8 logical calls
reached that ceiling without a score (see DEVIATIONS.md for the list and
cause) — that is the entire gap between 1,796 targets and 1,788 scored
results.

## What is and isn't preserved

This folder preserves `system_prompt_sha256` / `user_prompt_sha256` and each
call's parsed `selected_letter`, plus the question stems and options
themselves (in `run1-6000-with-replicate-status.csv`) — enough to verify
which frozen prompt produced which parsed answer. It does **not** preserve
the raw rendered prompt text or the raw model completion text; a reviewer
asking "what exactly did the model see and say, word for word" cannot answer
that from this folder alone. This is a deliberate scope decision for this
consolidation, not an oversight.

## Scope authorization

Arms and scope were fixed against a production gate before execution: a
required repository commit, a verified deployment, and authenticated
connectivity checks for both the OpenRouter and TailScale backends, all
recorded in `preparation-summary.json`.

## Execution windows

Execution ran in two windows: 2026-08-05T16:17Z-17:11Z and
2026-08-06T09:21Z-21:16Z.

## What to read next

If any of the above raises a question about whether a specific number is safe
to use as-is, read **DEVIATIONS.md** — it documents every place where actual
execution departed from the design above, including one protocol deviation
that changes what a subset of the data measures.

# STATS_SPEC — design constraints for the statistical analysis

Read this before writing any test. Several requested comparisons are constrained
or infeasible by design, and running the naive version of them would produce a
confident wrong answer. Where a constraint below blocks a requested analysis,
report the constraint — do not substitute a different analysis silently.

Written 2026-08-07. Base: `data/experiment-4-aug-26/statistical-analysis-7-aug-26/`

## Data

| Role | Path |
| --- | --- |
| Run 1, 6000 cells, CLEAN | `../consolidate-triplicates-7-aug-26/exports/run1-6000-with-replicate-status.csv` |
| Replicates, 898 cells | `../consolidate-triplicates-7-aug-26/exports/consolidated-triplicates-898.csv` |
| Per-logical-call, 1796 | `../consolidate-triplicates-7-aug-26/exports/replicate-cell-level-1796.csv` |
| Attempt-level, 1856 | `../consolidate-triplicates-7-aug-26/ledger/ATTEMPT_TIMELINE.csv` |
| Run DB (read-only) | `../replications/ab520-incorrect-cells-triplicate-2026-08-05/runs/ab520-incorrect-cell-triplicates-2026-08-05.sqlite` |

Available: numpy 2.5.1, scipy 1.18.0, statsmodels 0.14.6, pandas 3.0.5.
**matplotlib is NOT installed** — build figures as hand-written inline SVG.

## Design facts, verified 2026-08-07

**Structure.** 500 questions x 3 arms x 4 models = 6000 run-1 cells, all answered.
Arms: `openrouter_A`, `openrouter_B`, `tailscale_A`.

**A and B are PAIRED.** Both conditions use the identical 500 questions
(intersection = 500). A-vs-B is therefore a WITHIN-QUESTION paired comparison.
Use McNemar (exact binomial for discordant pairs) — NOT a two-sample test of
proportions, which would ignore the pairing and inflate the standard error.

**`provider x condition` is NOT crossed.** OpenRouter has both A and B;
TailScale has only A. There is no `tailscale_B`. **The provider x condition
interaction is inestimable** — not underpowered, absent. Any provider-vs-condition
interaction claim must be refused with this reason. Provider comparisons must
hold condition fixed at A (`openrouter_A` vs `tailscale_A`); that is the only
clean provider contrast available.

**Run 1 is uncontaminated.** The Vertex protocol deviation affects ONLY runs 2-3
of `openrouter_B` / gemini. All 6000 run-1 cells were collected earlier, before
any Vertex routing existed. The primary accuracy analysis is therefore clean;
only stability analyses touching gemini_B replicates carry the deviation.

## WHAT CONDITIONS A AND B ACTUALLY ARE — verified 2026-08-07

Established by diffing `inputs/adjusted-500-condition-A.csv` against
`inputs/adjusted-500-condition-B.csv`. This is NOT a prompt variation, and any
write-up calling it a generic "condition" contrast is uninformative.

The two files share all 500 questions, all question text, and all `correct_letter`
values. Column-by-column, the ONLY differences are:

| Column | Rows differing |
| --- | --- |
| `option_a` | 0 / 500 |
| `option_b` | 178 — exactly the questions whose correct letter is `b` |
| `option_c` | 198 — exactly the questions whose correct letter is `c` |
| `option_d` | 124 — exactly the questions whose correct letter is `d` |
| `correct_option_text` | 500 / 500 |

So only the CORRECT option changes; every distractor is byte-identical across
conditions. And in condition B that correct option takes exactly one value, in
all 500 questions:

> "Ninguna de las respuestas anteriores es correcta."

**Condition B is a none-of-the-above (NOTA) manipulation.** The substantive
correct answer is removed and replaced with a NOTA statement sitting in the same
letter position. The three remaining options are genuine distractors, all wrong.
To score correct in B, a model must recognise that no listed substantive option
is right — it cannot succeed by selecting the most plausible-sounding content.

Therefore the A-vs-B contrast measures **susceptibility to NOTA items**: how much
accuracy a model loses when the correct answer stops being a plausible assertion
and becomes a negation. Frame every A-vs-B result this way. "Condition A scored
higher than condition B" is true but says almost nothing; "models lose X points
when the correct answer is replaced by none-of-the-above" is the finding.

Two related facts to state where relevant:
- Option `a` is NEVER the correct answer in any of the 500 questions
  (178 + 198 + 124 = 500). It is always a distractor, in both conditions. Models
  selected `a` on 2.6% of OpenRouter condition-A cells and 7.5% of condition-B
  cells — always wrong, and the rise under B is itself a NOTA-failure signature.
- The correct option averages 68.7 characters in A but 49.0 in B (the fixed NOTA
  string), against 65.1 for distractors. In A the correct answer is slightly
  LONGER than the distractors; in B it is conspicuously shorter and identical
  across all items. Note this as a possible surface cue in both directions when
  interpreting results.

Because condition B is harder, the 898 run-1-incorrect cells are not balanced
across conditions — `openrouter_B` contributes 532 of them versus 203 for
`openrouter_A`. Any pooled statement about the replicate set is weighted toward
NOTA items. State the composition wherever it matters.

## Outcome definitions

`strict_correct = letter_correct AND text_correct`, where `text_correct` is exact
string equality against the gold option text (`code/medrag_eval/scoring.py:23-26`).
Among the 898 run-1-incorrect cells, 896 are wrong on both criteria, 1 is
letter-correct/text-wrong and 1 letter-wrong/text-correct — so `strict_correct`
is effectively "picked the wrong option", not a formatting artefact.

Primary outcome: **run-1 `strict_correct`** (binary, 6000 cells) — for comparing
models, conditions and providers.
Secondary outcome: **flip rate** (binary per scored replicate, 1788) — stability,
CONDITIONED on having failed run 1. It is not a general accuracy measure and
regression to the mean applies. The 5102 run-1-correct cells were never
replicated, so the correct-to-wrong transition is unmeasured.

## The requested groupings, and what each can support

**Open vs closed weights.**
- closed: `google/gemini-3.6-flash`
- open: `google/gemma-4-26b-a4b-it`, `qwen/qwen3.6-35b-a3b`, `z-ai/glm-5.2`

The closed group contains exactly ONE model, so "open vs closed" is completely
confounded with "gemini vs the other three". A significant difference is
evidence about gemini, NOT about weight licensing. Report it, but label it
descriptive; do not phrase any conclusion as being about open-source models as a
class. State n_models per group everywhere.

**Big vs small.** Problematic — resolve before testing:
- `gemma-4-26b-a4b-it`: 26B total / ~4B active (MoE)
- `qwen3.6-35b-a3b`: 35B total / ~3B active (MoE)
- `z-ai/glm-5.2`: parameter count not established from the repo
- `gemini-3.6-flash`: proprietary, size undisclosed

Two of four models have no defensible size. Do NOT invent parameter counts. Pick
one of: (a) restrict to the two models with published sizes and state the test is
underpowered at n_models=2; (b) use total-vs-active parameters as an explicit
operationalisation for the two MoE models only; (c) declare the comparison
infeasible. Whichever you choose, state it and its limits explicitly. Inventing a
size for gemini or glm is a fabrication and is not acceptable.

**Provider.** `openrouter_A` vs `tailscale_A` only (condition held at A).
Note these differ in more than transport: the TailScale arm uses GIFT prompt ID
13 with server-side MCQ instructions and does not honour the JSON-schema
enforcement that OpenRouter applies. It is a provider+prompt-delivery contrast,
not a pure transport contrast. Say so.

**Condition A vs B.** Paired, OpenRouter only. This is the cleanest contrast in
the study.

## Statistical requirements

**Normality.** The primary outcomes are BINARY; normality of a Bernoulli variable
is not a meaningful question and Shapiro-Wilk on 0/1 data is not a valid gate.
Honour the request properly:
1. Run genuine normality diagnostics on the quantities that ARE continuous:
   per-question accuracy (proportion correct over the 12 cells per question) and
   attempt `latency_ms`. Use Shapiro-Wilk and Anderson-Darling, report statistic,
   p, and a QQ-plot as SVG.
2. State plainly that for the binary outcomes the choice of test is driven by the
   data type and the pairing/clustering structure, not by a normality result, and
   name the tests that follow from that.
Do not run a normality test on binary data and then justify a test choice with it.

**Non-independence is the main threat.** Each question contributes up to 12 cells.
Treat question as a cluster: use McNemar for paired binary contrasts, and for
model-level and grouped contrasts use either cluster-robust logistic regression
(GEE, exchangeable, clusters = question) or a permutation test permuting whole
questions. State the clustering approach used and why.

**Effect sizes are mandatory.** Report risk difference and odds ratio with CIs
alongside every p-value. A p-value alone is not an acceptable result here.

**Multiplicity.** Many contrasts. Apply Holm-Bonferroni within each family of
tests, report raw and adjusted p, and define the families explicitly.

**Sensitivity.** Any analysis touching gemini_B replicates must be repeated
excluding the 91 Vertex-served cells, with both results reported.

## Standards

- Never invent a number, a parameter count, or a citation. `UNVERIFIED` is an
  acceptable answer; a plausible-looking fabrication is not.
- Every figure stated in prose must be reproducible from a committed script.
- Report assumptions and their violations, not just results.
- Scripts go in `scripts/`, machine-readable output in `results/`, SVG in
  `figures/`.

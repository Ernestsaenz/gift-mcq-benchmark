# PRIMARY_TESTS -- Condition, provider, model, and flip-rate contrasts

Owner: agent 2 of 4. Reproduced by `scripts/02_primary.py`. Sources are read-only; outputs live in this `results/` directory as CSV + `primary_summary.json`.

## Constraints honoured (see STATS_SPEC.md)

- **provider x condition interaction: INESTIMABLE.** OpenRouter has both A and B; TailScale has only A (`tailscale_B` does not exist). This design is not underpowered for the interaction -- the interaction term has no data to estimate it from. No interaction test is attempted anywhere in this script or report.
- **A vs B is paired** on the identical 500 questions (verified: 500/500 matched pairs per model in both arms). Every A-vs-B test below is McNemar (exact, binomial on discordant pairs) or a paired/clustered generalisation of it -- never a two-sample proportion test.
- **Run 1 is uncontaminated.** Verified from ledger/ATTEMPT_TIMELINE.csv: all logged attempts are run_index in {2,3}; run 1 has zero rows in the deviation-era attempt log and predates any Vertex routing (deviation began 2026-08-06; run-1 collection finished before that window per DEVIATIONS.md).

## Clustering diagnostic

One-way random-effects ICC of run-1 `strict_correct` within question (k~12 cells/question, pooling all arms/models): **ICC = 0.181**. A non-trivial positive ICC confirms within-question dependence is real (harder questions are harder across arms/models) and justifies clustering by question in every pooled/multi-model test below, rather than treating all 6000 cells as independent.

## 1. NOTA susceptibility: condition A vs B (OpenRouter only, run-1 strict_correct, paired on question)

**What condition B actually is (established after the first pass of this analysis, verified independently here from `run1-6000-with-replicate-status.csv` rather than taken on faith -- see `nota_analysis()` in `scripts/02_primary.py`).** Condition B is NOT a generic prompt/condition variant. Diffing the two condition files shows they share all 500 questions, all question text, and all `correct_letter` values; the only columns that differ are the option that happens to be correct for each question (`option_b`/`option_c`/`option_d`, exactly on the 178/198/124 questions where that letter is correct) and `correct_option_text`. **Every distractor is byte-identical across conditions.** In condition B the correct option takes exactly one value across all 500 questions: *"Ninguna de las respuestas anteriores es correcta."* ("None of the above answers is correct"). Confirmed here by asserting a single unique `correct_option_text` value across all 500 condition-B questions (see `nota_analysis()`), and that `correct_letter` is never `a`.

**Condition B is therefore a none-of-the-above (NOTA) manipulation.** The substantive correct answer is deleted and replaced by a fixed NOTA statement in the same letter slot; the three remaining options are unchanged genuine distractors. To score correct in B, a model must recognise that no listed substantive option is right -- it cannot win by picking the most plausible-sounding content. **"Condition A scored higher than condition B" is true but nearly uninformative; the finding is how many accuracy points each model loses when the correct answer is replaced by none-of-the-above.** Because A and B are paired on identical questions with identical distractors and a single manipulated element, this is the cleanest and most substantively interesting contrast in the study.

Family: 4 per-model exact McNemar tests + 1 pooled GEE test (5 tests), Holm-Bonferroni corrected together.

| Model | n | acc A | acc B (NOTA) | b (A-only) | c (B-only) | McNemar p (raw) | p (Holm) | **NOTA accuracy loss (A-B)** [95% CI] | OR (b/c) [95% CI] |
|---|---|---|---|---|---|---|---|---|---|
| google/gemini-3.6-flash | 500 | 0.982 | 0.900 | 44 | 3 | <0.0001 | <0.0001 | **+8.2 pts** [+5.6, +10.8] | 14.67 [4.70, 73.84] |
| google/gemma-4-26b-a4b-it | 500 | 0.790 | 0.542 | 150 | 26 | <0.0001 | <0.0001 | **+24.8 pts** [+20.1, +29.5] | 5.77 [3.79, 9.12] |
| qwen/qwen3.6-35b-a3b | 500 | 0.884 | 0.716 | 103 | 19 | <0.0001 | <0.0001 | **+16.8 pts** [+12.7, +20.9] | 5.42 [3.30, 9.37] |
| z-ai/glm-5.2 | 500 | 0.938 | 0.778 | 88 | 8 | <0.0001 | <0.0001 | **+16.0 pts** [+12.4, +19.6] | 11.00 [5.34, 26.27] |

Every model loses accuracy under NOTA, ranging from 8.2 points (google/gemini-3.6-flash) to 24.8 points (google/gemma-4-26b-a4b-it), all significant at Holm p<0.0001.

**Pooled (GEE, logistic, exchangeable correlation, cluster=question, 4000 obs over 500 question clusters x 4 models):** OR(A vs B) = 3.21 [2.70, 3.81], Wald p = <0.0001, Holm p = <0.0001.

**Robustness (permutation, whole-question swap, n_perm=20000):** observed pooled NOTA accuracy loss (A-B) = +8.22 pts, permutation p < 0.00005 (0/20000 permutations at least as extreme as observed). GEE is the primary pooled method (it yields an effect size + CI); the permutation test is reported as a distribution-free check on the pooled p-value.

### 1a. NOTA-failure mechanism (why models fail B)

**Not a scoring artefact.** Among the 4000 OpenRouter A+B run-1 cells, `strict_correct` and `letter_correct` disagree on only 1 cell -- the A-vs-B gap is a real answer-selection effect, not an artefact of exact-text matching.

**Option `a` is never the correct answer, in either condition** (178+198+124 = 500 -- the correct letter is always b, c, or d). It is always a genuine distractor. Under NOTA, models select it far more often -- a signature of NOTA-recognition failure, not a random shift:

- Overall: **2.65%** of condition-A cells vs **7.50%** of condition-B cells select option `a` (n=2000 each).

| Model | selected-`a` rate, A | selected-`a` rate, B | fold increase |
|---|---|---|---|
| google/gemini-3.6-flash | 0.20% | 3.00% | 15.0x |
| google/gemma-4-26b-a4b-it | 7.00% | 15.00% | 2.1x |
| qwen/qwen3.6-35b-a3b | 2.40% | 6.80% | 2.8x |
| z-ai/glm-5.2 | 1.00% | 5.20% | 5.2x |

**Every model raises its selection of the never-correct option `a` from A to B, roughly doubling or more in every case** (gemini-3.6-flash 0.2%→3.0%; gemma-4-26b-a4b-it 7.0%→15.0%; qwen3.6-35b-a3b 2.4%→6.8%; glm-5.2 1.0%→5.2%). That uniformity across four otherwise very different models -- all move in the same direction by a similar-or-larger multiple -- is itself a NOTA-failure signature: facing a NOTA item, models become measurably more willing to select an option that is wrong by construction in all 500 questions, consistent with falling back toward distractor-guessing rather than reliably recognising NOTA.

**Per-model distribution of the wrong answer actually picked in B** (among cells scored incorrect in condition B; chance rate for `a` under uniform random guessing among the 3 available wrong options is 33.3% -- `a` is a candidate wrong answer on 100% of questions, while `b`/`c`/`d` are only candidates on the subset of questions where that letter isn't the correct one, so 33.3% is the correct uniform-guessing baseline, not an arbitrary 25%):

| Model | n wrong in B | % picked a | % picked b | % picked c | % picked d |
|---|---|---|---|---|---|
| google/gemini-3.6-flash | 50 | 30.0% | 18.0% | 22.0% | 30.0% |
| google/gemma-4-26b-a4b-it | 229 | 32.8% | 16.6% | 23.6% | 27.1% |
| qwen/qwen3.6-35b-a3b | 142 | 23.9% | 26.1% | 28.2% | 21.8% |
| z-ai/glm-5.2 | 111 | 23.4% | 24.3% | 27.0% | 25.2% |

**Suggestive secondary reading, against the 33.3% chance baseline (not 25%) -- a distribution-of-errors observation, not a claim about model reasoning or "understanding":** gemini-3.6-flash (30.0%, n=50, 95% CI [17.9, 44.6]) and gemma-4-26b-a4b-it (32.8%, n=229, 95% CI [26.7, 39.2]) select `a` at/near chance when they fail B, i.e. their errors spread roughly uniformly across the three available wrong options with no systematic aversion to the never-correct one; qwen3.6-35b-a3b (23.9%, n=142, 95% CI [17.2, 31.8]) and glm-5.2 (23.4%, n=111, 95% CI [15.9, 32.4]) select it clearly below chance, a mild but consistent tilt away from `a` even in failure. Treat this as suggestive rather than established: it rests on 4 small, unequal samples, and gemini's in particular (50 wrong cells) has a wide 95% CI ([17.9, 44.6]) that is not far from the below-chance group's point estimates.

**Option-length surface cue (flagged, not adjusted for).** Average character length across the 500 questions: correct option in A = 68.7 chars, correct option in B (the fixed NOTA string) = 49.0 chars, distractors (byte-identical across conditions) = 65.1 chars (n=1500 distractor instances). In condition A the correct answer is slightly *longer* than distractors -- a model with a length-correlates-with-correctness prior would be helped in A. In condition B the correct (NOTA) answer is conspicuously *shorter* and identical across every item -- a model that had learned "the odd-length option is right" could exploit that, or conversely a model that had learned "longer/more-specific answers are right" would be actively misled toward the distractors. Both directions are plausible; this analysis cannot separate a length cue from genuine NOTA-recognition failure, and flags it for interpretation rather than correcting for it.

## 2. Provider: openrouter_A vs tailscale_A (condition held at A, paired on question)

**Framing (binding):** Provider+prompt-delivery contrast, not a pure transport contrast: TailScale arm uses GIFT prompt ID 13 with server-side MCQ instructions and does not honour OpenRouter's JSON-schema enforcement.

Family: 4 per-model exact McNemar tests + 1 pooled GEE test (5 tests), Holm-Bonferroni corrected together, separate from the condition-A-vs-B family above.

| Model | n | acc OR_A | acc TS_A | b (OR-only) | c (TS-only) | McNemar p (raw) | p (Holm) | risk diff OR-TS [95% CI] | OR (b/c) [95% CI] |
|---|---|---|---|---|---|---|---|---|---|
| google/gemini-3.6-flash | 500 | 0.982 | 0.974 | 5 | 1 | 0.2188 | 0.4375 | +0.008 [-0.002, +0.018] | 5.00 [0.56, 236.49] |
| google/gemma-4-26b-a4b-it | 500 | 0.790 | 0.838 | 21 | 45 | 0.0043 | 0.0171 | -0.048 [-0.080, -0.016] | 0.47 [0.26, 0.80] |
| qwen/qwen3.6-35b-a3b | 500 | 0.884 | 0.902 | 20 | 29 | 0.2529 | 0.4375 | -0.018 [-0.045, +0.009] | 0.69 [0.37, 1.26] |
| z-ai/glm-5.2 | 500 | 0.938 | 0.960 | 6 | 17 | 0.0347 | 0.1041 | -0.022 [-0.041, -0.003] | 0.35 [0.11, 0.94] |

**Pooled (GEE, same specification as Section 1):** OR(OpenRouter_A vs TailScale_A) = 0.79 [0.67, 0.92], Wald p = 0.0025, Holm p = 0.0126.

**Robustness (permutation, n_perm=20000):** observed pooled risk difference (OpenRouter_A - TailScale_A) = -0.0100, permutation p 0.0029 (57/20000 permutations at least as extreme).

**Every conclusion drawn from this section describes a provider+prompt-delivery contrast (transport, GIFT prompt ID 13 vs the OpenRouter payload, and JSON-schema enforcement differ simultaneously) -- it must not be reported as an isolated transport/infrastructure effect.**

## 3. Model main effects on run-1 strict_correct (within each arm)

All 4 models answer the same 500 questions within an arm -> related-samples design. Omnibus test: Cochran's Q (k=4). Family 1 = the 3 omnibus tests (one per arm), Holm-corrected together. Post-hoc: pairwise exact McNemar (6 pairs per arm); each arm's 6 pairs are their own Holm family (3 separate post-hoc families).

### Omnibus (Cochran's Q)

| Arm | n questions | Q | df | p (raw) | p (Holm) |
|---|---|---|---|---|---|
| openrouter_A | 500 | 141.48 | 3 | <0.0001 | <0.0001 |
| openrouter_B | 500 | 218.86 | 3 | <0.0001 | <0.0001 |
| tailscale_A | 500 | 99.33 | 3 | <0.0001 | <0.0001 |

### Post-hoc pairwise (exact McNemar, Holm-corrected within arm)

| Arm | Model i | Model j | n | acc i | acc j | b (i-only) | c (j-only) | p (raw) | p (Holm) | risk diff i-j [95% CI] | OR i vs j [95% CI] |
|---|---|---|---|---|---|---|---|---|---|---|---|
| openrouter_A | google/gemini-3.6-flash | google/gemma-4-26b-a4b-it | 500 | 0.982 | 0.790 | 101 | 5 | <0.0001 | <0.0001 | +0.192 [+0.155, +0.229] | 20.20 [8.38, 63.55] |
| openrouter_A | google/gemini-3.6-flash | qwen/qwen3.6-35b-a3b | 500 | 0.982 | 0.884 | 52 | 3 | <0.0001 | <0.0001 | +0.098 [+0.070, +0.126] | 17.33 [5.61, 86.77] |
| openrouter_A | google/gemini-3.6-flash | z-ai/glm-5.2 | 500 | 0.982 | 0.938 | 26 | 4 | <0.0001 | 0.0001 | +0.044 [+0.023, +0.065] | 6.50 [2.26, 25.63] |
| openrouter_A | google/gemma-4-26b-a4b-it | qwen/qwen3.6-35b-a3b | 500 | 0.790 | 0.884 | 22 | 69 | <0.0001 | <0.0001 | -0.094 [-0.130, -0.058] | 0.32 [0.19, 0.52] |
| openrouter_A | google/gemma-4-26b-a4b-it | z-ai/glm-5.2 | 500 | 0.790 | 0.938 | 12 | 86 | <0.0001 | <0.0001 | -0.148 [-0.185, -0.111] | 0.14 [0.07, 0.26] |
| openrouter_A | qwen/qwen3.6-35b-a3b | z-ai/glm-5.2 | 500 | 0.884 | 0.938 | 14 | 41 | 0.0004 | 0.0004 | -0.054 [-0.083, -0.025] | 0.34 [0.17, 0.64] |
| openrouter_B | google/gemini-3.6-flash | google/gemma-4-26b-a4b-it | 500 | 0.900 | 0.542 | 197 | 18 | <0.0001 | <0.0001 | +0.358 [+0.310, +0.406] | 10.94 [6.75, 18.85] |
| openrouter_B | google/gemini-3.6-flash | qwen/qwen3.6-35b-a3b | 500 | 0.900 | 0.716 | 107 | 15 | <0.0001 | <0.0001 | +0.184 [+0.144, +0.224] | 7.13 [4.14, 13.19] |
| openrouter_B | google/gemini-3.6-flash | z-ai/glm-5.2 | 500 | 0.900 | 0.778 | 76 | 15 | <0.0001 | <0.0001 | +0.122 [+0.086, +0.158] | 5.07 [2.89, 9.49] |
| openrouter_B | google/gemma-4-26b-a4b-it | qwen/qwen3.6-35b-a3b | 500 | 0.542 | 0.716 | 44 | 131 | <0.0001 | <0.0001 | -0.174 [-0.224, -0.124] | 0.34 [0.23, 0.48] |
| openrouter_B | google/gemma-4-26b-a4b-it | z-ai/glm-5.2 | 500 | 0.542 | 0.778 | 37 | 155 | <0.0001 | <0.0001 | -0.236 [-0.286, -0.186] | 0.24 [0.16, 0.34] |
| openrouter_B | qwen/qwen3.6-35b-a3b | z-ai/glm-5.2 | 500 | 0.716 | 0.778 | 44 | 75 | 0.0057 | 0.0057 | -0.062 [-0.104, -0.020] | 0.59 [0.39, 0.86] |
| tailscale_A | google/gemini-3.6-flash | google/gemma-4-26b-a4b-it | 500 | 0.974 | 0.838 | 72 | 4 | <0.0001 | <0.0001 | +0.136 [+0.104, +0.168] | 18.00 [6.73, 67.85] |
| tailscale_A | google/gemini-3.6-flash | qwen/qwen3.6-35b-a3b | 500 | 0.974 | 0.902 | 43 | 7 | <0.0001 | <0.0001 | +0.072 [+0.045, +0.099] | 6.14 [2.74, 16.18] |
| tailscale_A | google/gemini-3.6-flash | z-ai/glm-5.2 | 500 | 0.974 | 0.960 | 12 | 5 | 0.1435 | 0.1435 | +0.014 [-0.002, +0.030] | 2.40 [0.79, 8.70] |
| tailscale_A | google/gemma-4-26b-a4b-it | qwen/qwen3.6-35b-a3b | 500 | 0.838 | 0.902 | 26 | 58 | 0.0006 | 0.0013 | -0.064 [-0.099, -0.029] | 0.45 [0.27, 0.72] |
| tailscale_A | google/gemma-4-26b-a4b-it | z-ai/glm-5.2 | 500 | 0.838 | 0.960 | 7 | 68 | <0.0001 | <0.0001 | -0.122 [-0.154, -0.090] | 0.10 [0.04, 0.22] |
| tailscale_A | qwen/qwen3.6-35b-a3b | z-ai/glm-5.2 | 500 | 0.902 | 0.960 | 9 | 38 | <0.0001 | <0.0001 | -0.058 [-0.084, -0.032] | 0.24 [0.10, 0.50] |

## 4. Secondary: flip rate (898-cell replicate set)

NOT paired -- conditioned on run-1 failure, so the cell sets differ across arms/models. Cluster-robust GEE logistic, cluster=question. Composition is unbalanced across arms because condition B is harder (more NOTA-item failures feed the replicate set): {'openrouter_B': 532, 'openrouter_A': 203, 'tailscale_A': 163}. Pooled/model-level flip-rate statements are therefore weighted toward NOTA items.

Sensitivity: every flip-rate result is reported twice -- with all 898 logical calls, and excluding logical calls where a replicate run (run 2 and/or run 3) was served by the google-vertex routing deviation (openrouter_B / google/gemini-3.6-flash only, 91 affected replicate-run rows in the 1796-row replicate-cell table).

**Replicate-set composition is unbalanced by arm because condition B is harder (more NOTA-item failures enter the replicate pool):**

| arm | n cells in 898-cell replicate set |
|---|---|
| openrouter_B | 532 |
| openrouter_A | 203 |
| tailscale_A | 163 |

`openrouter_B` alone supplies 532/898 (59%) of the replicate set, vs 203 for `openrouter_A` and 163 for `tailscale_A`. Any pooled or cross-arm flip-rate statement is therefore weighted toward NOTA-item failures, not a balanced sample of failure modes.

### Raw flip rates by arm x model

| exclude_vertex | arm | model | n cells | n flipped | flip rate |
|---|---|---|---|---|---|
| False | openrouter_A | google/gemini-3.6-flash | 9 | 0 | 0.000 |
| False | openrouter_A | google/gemma-4-26b-a4b-it | 105 | 14 | 0.133 |
| False | openrouter_A | qwen/qwen3.6-35b-a3b | 58 | 27 | 0.466 |
| False | openrouter_A | z-ai/glm-5.2 | 31 | 10 | 0.323 |
| False | openrouter_B | google/gemini-3.6-flash | 50 | 10 | 0.200 |
| False | openrouter_B | google/gemma-4-26b-a4b-it | 229 | 16 | 0.070 |
| False | openrouter_B | qwen/qwen3.6-35b-a3b | 142 | 41 | 0.289 |
| False | openrouter_B | z-ai/glm-5.2 | 111 | 18 | 0.162 |
| False | tailscale_A | google/gemini-3.6-flash | 13 | 2 | 0.154 |
| False | tailscale_A | google/gemma-4-26b-a4b-it | 81 | 7 | 0.086 |
| False | tailscale_A | qwen/qwen3.6-35b-a3b | 49 | 20 | 0.408 |
| False | tailscale_A | z-ai/glm-5.2 | 20 | 5 | 0.250 |
| True | openrouter_A | google/gemini-3.6-flash | 9 | 0 | 0.000 |
| True | openrouter_A | google/gemma-4-26b-a4b-it | 105 | 14 | 0.133 |
| True | openrouter_A | qwen/qwen3.6-35b-a3b | 58 | 27 | 0.466 |
| True | openrouter_A | z-ai/glm-5.2 | 31 | 10 | 0.323 |
| True | openrouter_B | google/gemini-3.6-flash | 4 | 1 | 0.250 |
| True | openrouter_B | google/gemma-4-26b-a4b-it | 229 | 16 | 0.070 |
| True | openrouter_B | qwen/qwen3.6-35b-a3b | 142 | 41 | 0.289 |
| True | openrouter_B | z-ai/glm-5.2 | 111 | 18 | 0.162 |
| True | tailscale_A | google/gemini-3.6-flash | 13 | 2 | 0.154 |
| True | tailscale_A | google/gemma-4-26b-a4b-it | 81 | 7 | 0.086 |
| True | tailscale_A | qwen/qwen3.6-35b-a3b | 49 | 20 | 0.408 |
| True | tailscale_A | z-ai/glm-5.2 | 20 | 5 | 0.250 |

### Cluster-robust GEE (cluster = question), reference levels: arm=openrouter_A, model=google/gemini-3.6-flash

| exclude_vertex | n cells | family | level (vs reference) | OR | 95% CI | Wald p (raw) | p (Holm, within family) |
|---|---|---|---|---|---|---|---|
| False | 898 | flip_rate_by_arm | openrouter_B | 0.56 | [0.39, 0.82] | 0.0024 | 0.0048 |
| False | 898 | flip_rate_by_arm | tailscale_A | 0.80 | [0.51, 1.25] | 0.3224 | 0.3224 |
| False | 898 | flip_rate_by_model | google/gemma-4-26b-a4b-it | 0.48 | [0.23, 1.00] | 0.0514 | 0.1028 |
| False | 898 | flip_rate_by_model | qwen/qwen3.6-35b-a3b | 2.68 | [1.33, 5.39] | 0.0056 | 0.0169 |
| False | 898 | flip_rate_by_model | z-ai/glm-5.2 | 1.26 | [0.60, 2.63] | 0.5432 | 0.5432 |
| True | 852 | flip_rate_by_arm | openrouter_B | 0.55 | [0.37, 0.80] | 0.0020 | 0.0039 |
| True | 852 | flip_rate_by_arm | tailscale_A | 0.80 | [0.51, 1.26] | 0.3333 | 0.3333 |
| True | 852 | flip_rate_by_model | google/gemma-4-26b-a4b-it | 0.75 | [0.20, 2.91] | 0.6810 | 0.6810 |
| True | 852 | flip_rate_by_model | qwen/qwen3.6-35b-a3b | 4.21 | [1.10, 16.06] | 0.0356 | 0.1068 |
| True | 852 | flip_rate_by_model | z-ai/glm-5.2 | 1.97 | [0.51, 7.68] | 0.3265 | 0.6530 |

## Assumptions and their status

- **McNemar exactness**: exact binomial test on discordant pairs requires no distributional assumption beyond independence of *questions* (not of the arm/condition outcomes within a question, which McNemar is explicitly built to handle). Holds by design -- 500 distinct questions per test.
- **GEE exchangeable correlation, cluster=question**: consistency of GEE point estimates does not require the working correlation structure to be correctly specified (only the mean model), and standard errors are the robust (sandwich) form. The ICC diagnostic above (ICC=0.181) supports exchangeable as a reasonable working structure rather than independence.
- **Cochran's Q chi-square approximation**: assumes a reasonably large number of blocks (questions); n=500 is large, so the chi-square approximation is treated as adequate.
- **Flip-rate GEE**: cells are NOT paired (conditioned on run-1 failure, different cells qualify per arm/model) -- this is an independent-groups cluster-robust logistic regression, not a paired test. Cluster = question to absorb shared question difficulty across the arm/model cells that do co-occur for a question.
- **Run-1 cleanliness**: confirmed directly from `ledger/ATTEMPT_TIMELINE.csv` (all 1856 logged attempt rows are run_index in {2,3}); run 1 has no rows in that deviation-era log and DEVIATIONS.md documents the Vertex routing as starting 2026-08-06, after run-1 collection. No sensitivity exclusion applied to any run-1 (Sections 1-3) result.
- **provider x condition interaction**: not estimable (no tailscale_B); not tested, per STATS_SPEC.md.


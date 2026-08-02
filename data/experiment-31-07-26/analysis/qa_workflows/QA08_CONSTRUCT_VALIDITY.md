# QA08 — construct validity, causal wording, and claim-boundary audit

**Audit date:** 2026-07-31 (Europe/Madrid)  
**Scope:** the current rewritten `REPORT.md`, the A/B source construction, canonical v3 results
and metadata, runtime prompts/options, GIFT/OpenRouter request configuration, and the boundary
between verified findings and unfinished exploratory mechanism work.  
**Mutation policy:** canonical workbooks, database, code, JSON, and report files were inspected
read-only. This audit file is the only artifact created by QA08.

Snapshot used for the wording review:

- `REPORT.md`: SHA-256
  `164cb1698599f770903e8a5470734bd30756e7b08a965281ba03b6d4335a4218`
- `final_analysis_results.json`: SHA-256
  `e420cd5a0e5505ab1c725d2c8ae59fbc722567f12e879b837278bd6b37364f3e`
- `dataset_meta.json`: SHA-256
  `fc4b4d5aa217dcce743f9269583ff8002f4d77360d4668d108ad7a143d7e1148`
- `experiment.sqlite`: SHA-256 recorded and independently checked elsewhere in the release,
  `dec53a3d8ed452676672820a758b4571d061c3fe994c45981095d30216744748`

## Overall verdict

**PASS for the descriptive accuracy results and for most explicit “not supported” boundaries;
FAIL for final-release causal wording.**

The report correctly rejects an isolated memorisation mechanism, equal model robustness,
item-level stability, clean effort/latency inference, a full-population GIFT estimate, and a GIFT
A/B retrieval conclusion. It also keeps the unfinished error-destination, effort, and subgroup
work out of the findings.

Four material issues remain:

1. “Replacing ... reduced” and “produces” attribute the entire OpenRouter contrast to the text
   intervention even though condition was not interleaved and physical provider routing changed.
   The data establish a large observed deployed-system contrast; pure text causation requires an
   additional no-time/no-routing-confounding assumption.
2. The inserted Spanish text is not position-neutral none-of-the-above. It literally refers to
   **preceding** answers. In the analysed set it occurs in slots `b`, `c`, and `d`, referring to
   one, two, or three prior options respectively. Calling every occurrence standard “NOTA” hides
   a material part of the treatment.
3. “GIFT improved” is causal language for a partial comparison of two whole deployed pipelines.
   Retrieval is bundled with provider stack, prompt delivery, response-schema support, serving
   time, and an unpinned retrieval depth; GIFT B is absent.
4. The proposed single keyed-option paraphrase and “insert a neutral NOTA” controls are useful
   starts but are not sufficient to identify memorisation, lexical familiarity, NOTA format, or
   reasoning burden separately.

## 1. What the intervention actually changes

### Mechanical construction — PASS

The workbook and database construction reconcile exactly:

| stage | items | construct implication |
|---|---:|---|
| source | 500 | assembled public-exam item pool, not yet the experimental target |
| A | 474 | excludes 17 three-option items and 9 source-level defects |
| B-eligible subset | 423 | further excludes 51 items for which the substitution was invalid or ambiguous: 30 aggregator-answer, 5 pre-existing-NOTA/ambiguous, and 16 swap-specific items |
| reported A/B set | 318 | from the 423, excludes 19 present declared defects and 91 key-`a` items, with 5 overlapping exclusions |

For every one of the 423 shared A/B items, direct workbook comparison found:

- identical question ID, metadata, stem/context, correct letter, and three non-keyed options;
- exactly one displayed option changed: the option at the original correct letter;
- `correct_option_text` changed to the same string with it;
- no other workbook field changed.

The intervention is therefore mechanically precise, but its target is the **selected,
substitution-compatible 423-item subset**, not all 500 source items or even all 474 A items. The
51 A-only items were excluded for semantic properties directly related to the manipulation. The
four-row analysis exclusion grid begins at 423 and cannot establish robustness to that earlier,
non-random eligibility selection.

### Exact construct induced by B

Condition B does all of the following together:

1. removes the original substantive keyed proposition from the choice set;
2. inserts the recurring meta-option
   `Ninguna de las respuestas anteriores es correcta.` at the same letter;
3. leaves the three original distractors and keyed letter unchanged;
4. changes a medical/content answer into a metalinguistic answer whose interpretation depends on
   its position and, for false/incorrect stems, on question polarity;
5. changes option length, style, lexical content, cross-item repetition, and the requested JSON
   answer text;
6. may change the decision strategy and number of alternatives a model evaluates, but does not
   directly measure that strategy or burden.

The position counts in the 423-item B universe are `a=91`, `b=118`, `c=125`, and `d=89`.
After the declared-defect and key-`a` exclusions, the 318 analysed items are `b=111`, `c=122`,
and `d=85`. Thus excluding slot `a` removes the no-antecedent case but does not make the wording
position-neutral: slots `b` and `c` still refer only to options printed before them.

The keyed-letter distribution is unchanged within matched items. What changes is the base rate of
the **text/genre**: on the paired universe, the exact inserted phrase is the key in 423/423 B
items and occurs in 0/423 corresponding A items. There is no condition in which that same
meta-option is present but unkeyed. Three exact occurrences exist as distractors elsewhere in the
full 474-item A file, but all three items are outside B. Therefore “answer base rate” should not be
read as a change in letter prevalence; it is perfect confounding between this phrase's presence,
condition B, and keyed status.

### Prompt and endpoint implications

OpenRouter A and B received the same `mcq_es_v4` instructions, decoding settings, response schema,
and named model ID; their rendered user prompts differ in the substituted option text. The prompt
frames the task as choosing the best **clinical** answer and asks the model to copy the chosen
option into JSON. B therefore also creates an instruction/answer-genre mismatch that A does not.

The stored endpoint is strict correctness (`letter_correct AND text_correct`). In the database,
strict correctness equals letter correctness for every scored cell in all reported experiments;
there are zero strict-versus-letter discrepancies and zero letter/text conflicts. Consequently,
the 15.50-point primary result is not an artifact of exact-text scoring among the included parsed
cells. Output-text length still contaminates completion-token comparisons, as the report correctly
states.

## 2. Claim-by-claim verdicts and replacement wording

| major report claim | verdict | construct/causal assessment | replacement wording |
|---|---|---|---|
| The A/B workbooks differ at the keyed option text while retaining the key letter | **PASS** | Verified on all 423 shared rows. Add that B is a semantically selected subset of A. | “Among the 423 items judged valid for this manipulation, B leaves the stem, distractors, metadata, and key letter unchanged and replaces only the keyed displayed text and matching gold text.” |
| Accuracy is 89.54% in A versus 74.04% in B, RD −15.50 pp, with every named model negative | **PASS as descriptive** | Counts, intervals, and direction match the canonical results. The pooled estimate is for four fixed model IDs and uncertainty resamples clinical clusters, not model deployments or repeated generations. | “Across 1,271 paired outputs from 318 cleaned, B-eligible items and four named model endpoints, observed keyed-answer accuracy was 15.50 points lower in B (74.04%) than A (89.54%); all four model-specific contrasts were negative.” |
| “Replacing ... reduced” / the substitution “produces” the decline | **FAIL as unconditional causal wording** | Arms were queried at different times and OpenRouter physical routing was not pinned. Routing may be a mediator of prompt properties or a time-varying co-intervention; these data cannot distinguish those cases. Same-backend sensitivities make routing alone less persuasive but do not identify the pure text effect. | “The observed condition-B outputs scored 15.50 points lower than their condition-A counterparts. Interpreting the full contrast as caused by the text-substitution bundle assumes that run timing and unpinned backend routing did not create a systematic arm difference.” |
| “Fixed none-of-the-above/NOTA string” | **FAIL terminologically** | The literal construct is “none of the preceding answers,” and it appears in `b`, `c`, or `d`; only `d` behaves like conventional all-other-options NOTA. | Use “fixed, position-dependent preceding-options meta-answer” for the current intervention. Reserve “position-neutral NOTA” for a future string such as `Ninguna de las demás opciones es correcta.` |
| The contrast is “statistically and specification robust for this benchmark” | **FAIL as overbroad; PASS in the tested sense** | The sign is stable across the reported exclusions, four named models, clinical-cluster analyses, and leave-one-unit checks. The tested specifications do not vary the 51-item B-eligibility rule, provider routing, prompt, generation replicate, domain, or deployment snapshot. | “The negative observed contrast is stable across the reported cleaning choices, clinical-cluster analyses, four named model endpoints, and leave-one-unit checks.” |
| The experiment does not isolate memorisation or familiar-string recognition | **PASS** | This is the most important correct boundary. Original-answer removal, meta-option format, semantics, repetition, position, and provider routing remain bundled. | “The result demonstrates sensitivity to this bundled input change. It does not show that the original answers were memorised or that exact-string recognition caused the difference.” |
| B changes semantics, logical burden, genre, and base rate | **PASS for semantics/genre; FAIL if ‘burden’ is read as measured; base-rate wording needs precision** | The design changes potential decision requirements, but no validated mediator measure establishes greater reasoning burden. Letter base rates are unchanged; the fixed phrase is keyed in every B item and never appears in matched A. | “B changes answer semantics and genre, removes the substantive key, makes one recurring meta-answer correct on every B item, and may change the required decision strategy. The study does not measure reasoning burden directly.” |
| The direction is negative but equal robustness across models is not established | **PASS** | Correctly avoids equivalence and acknowledges scale-dependent interactions. Keep the scope to these four endpoints, this prompt, one run, and this item set. | “All four observed model-specific point estimates are negative. Their magnitudes are not an equivalence result or a general ranking of model robustness, and they need not transfer to other prompts, snapshots, providers, or models.” |
| Provider routing is a caveat; same-backend subsets remain negative | **PASS, but it must qualify the headline** | Independent v3 recomputation gives same-backend `n/RD`: gemini 318/−8.49 pp, gemma 30/−23.33, qwen 80/−18.75, and glm 219/−18.72. These are selected, post-routing subsets; conditioning on them is not a randomized provider control. | Retain the current caveat and add the no-routing/no-time assumption to the executive causal sentence. Do not say routing was ruled out or that it attenuated the effect. |
| “GIFT improved gemma/glm; qwen/gemini did not improve” | **FAIL** | The table numerics pass, but “improved” attributes a selected complete-case difference to GIFT and “did not improve” can imply evidence of no benefit. The comparison bundles two provider pipelines and has one run per cell. | “On the 306 complete-case condition-A items, GIFT-served versus OpenRouter-served accuracy differed by +5.56 pp for gemma, +3.27 for glm, −0.33 for qwen, and −0.98 for gemini. These are observed pipeline differences on the selected subset, not isolated retrieval effects.” |
| The partial GIFT subset does not identify the full condition-A target | **PASS** | Sequential prefix coverage, difficulty imbalance, and the sign-indeterminate missing-outcome bound are clearly reported. Replace remaining uses of “GIFT effect/efficacy” with “pipeline difference” unless the causal system estimand is explicitly defined. | “Pairing supports a within-item description on the observed subset; it does not identify the GIFT-minus-OpenRouter pipeline difference on missing items or the full target.” |
| GIFT B did not run, so there is no retrieval-arm A/B conclusion | **PASS, but incomplete as a retrieval boundary** | Correct. Even completing GIFT B would estimate the substitution contrast in the deployed GIFT pipeline; by itself it would not isolate retrieval from the rest of that pipeline. | “No GIFT A/B substitution contrast exists. A retrieval effect requires a retrieval-on versus retrieval-off comparison within an otherwise identical, pinned pipeline; OpenRouter is not a clean no-retrieval control for GIFT.” |
| Tokens/latency do not establish deliberation or intrinsic speed | **PASS** | The fixed output text, response-format differences, concurrency, provider stack, throughput, and routing invalidate a clean effort mechanism claim. | Keep the current exclusion. Describe any future latency result as an operational endpoint under pinned serving conditions, not latent reasoning burden. |
| Unfinished mechanism, destination, effort, and subgroup workflows are absent from findings | **PASS substantively** | No error-destination, reasoning-token, “deliberated longer,” latency-mechanism, or subgroup-mechanism output is presented as a finding. The retained position-`a`, routing, token-echo, and coverage statements are independently reproducible design/sensitivity facts. | “Unverified exploratory mechanism outputs are not used as findings.” For auditability, name the two stopped workflows and their terminal status rather than giving an unsupported count only. |

## 3. What can and cannot be attributed

| proposed interpretation | supported? | precise boundary |
|---|---|---|
| Lower keyed-answer accuracy under the observed B configuration | **Yes** | Descriptive for the 318 cleaned B-eligible items, four fixed model endpoints, `mcq_es_v4`, and the observed OpenRouter deployment/run. |
| Total effect of the deployed A-versus-B run bundle | **Yes, descriptively** | The bundle includes the text change plus any arm-linked routing/time differences. |
| Pure causal effect of replacing the keyed text | **Not fully identified** | Requires pinned/randomized serving or an assumption that routing and time do not confound the arm contrast. |
| Memorisation of public-exam answers | **No** | No training-exposure evidence and no semantics-preserving lexical control. |
| Lexical familiarity with the original keyed string | **No** | A clean paraphrase contrast was not run. Even such a contrast would show surface-form dependence, not by itself prove training-set memorisation. |
| Increased reasoning burden | **No** | The manipulation plausibly changes decision strategy, but token and latency measures are contaminated and no direct mediator was validated. |
| General NOTA handling ability | **No** | The phrase is position-dependent, always keyed in B, absent from matched A, and never tested as an unkeyed distractor. |
| Equal or ranked model robustness | **No** | One run, four fixed models, scale-dependent heterogeneity, no equivalence margin, and unpinned physical providers. |
| Retrieval benefit | **No** | GIFT A is partial; GIFT B is absent; GIFT versus OpenRouter changes the whole pipeline, not retrieval alone. |
| Provider routing as the cause | **No** | Routing differs and can contribute, but its causal share is not identified. Negative same-backend subsets reduce concern that cross-backend pairs alone generated the sign. |

## 4. Cross-arm prompt and retrieval construct

The report's phrase “run ... with prompt `mcq_es_v4`” is straightforward for OpenRouter but needs
qualification for GIFT:

- OpenRouter receives the full versioned Spanish instruction block in-message and a strict JSON
  response schema.
- GIFT receives only `question_id`, stem, and options in-message; instructions are supplied
  server-side through `X-Prompt-ID: 13`, and GIFT does not receive the OpenRouter JSON schema.
- The repository contains a reference copy of prompt 13 and a parity test against the OpenRouter
  instructions, but the test itself states that it cannot verify the text actually deployed on the
  server.
- All GIFT attempts record prompt ID 13, but `top_k` is null and no `X-Top-K` header was sent. The
  retrieval depth is therefore the unarchived server default, not a pinned experimental setting.
- The request/response artifacts do not archive the retrieved passages or a corpus/index version.

Suggested replacement in the methods:

> OpenRouter received the in-message `mcq_es_v4` template. GIFT calls carried
> `X-Prompt-ID: 13` and a question/options-only user message; the repository reference text for
> prompt 13 matches the OpenRouter instruction block, but the deployed server-side prompt text was
> not archived independently. GIFT retrieval depth used the server default (`top_k` was not pinned).

These facts do not invalidate the descriptive pipeline table. They do prevent interpreting the
table as an isolated retrieval experiment.

## 5. Recommended controls

### A. Identify lexical dependence without calling it memorisation

1. Use multiple clinician-validated, semantics-preserving paraphrases, not one paraphrase.
2. Include both a keyed-option-only paraphrase and an all-options paraphrase/style control. A
   keyed-only rewrite can itself make the correct option stylistically unique.
3. Match length, specificity, polarity, register, and key position; prespecify semantic-equivalence
   adjudication blinded to model outputs.
4. Treat an original-versus-paraphrase difference as **surface-form sensitivity**. To strengthen a
   memorisation/contamination inference, add exposure evidence, novel or securely held-out items,
   and preferably post-training-cutoff/isomorphic items.

### B. Separate meta-option format from removal of the substantive answer

1. Replace `anteriores` with position-neutral wording and either fix the meta-option to the final
   slot or balance/randomize its position by design.
2. Include a matched condition where the same meta-option is present but **unkeyed**, with the true
   substantive answer still present and option count held constant.
3. Include a keyed-meta-option condition with the substantive answer absent. This separates, as
   far as a reauthored matched design permits, mere format presence from keyed status and
   substantive-answer removal.
4. Balance positive and negative stems and validate the meta-option's truth conditions for each.
5. Report the target as items for which all counterfactual versions are independently valid; do
   not generalize from the manipulation-compatible subset to excluded aggregator/ambiguous items.

### C. Identify retrieval rather than a provider-pipeline bundle

Run a randomized/interleaved `substitution (A/B) × retrieval (off/on)` design **within the same
provider stack**. Pin the model snapshot, prompt text/hash, corpus and index version, `top_k`,
response schema, decoding parameters, and backend. Archive retrieved passage IDs/text or hashes.
The retrieval main effect and retrieval-by-substitution interaction then have interpretable
estimands. Completing GIFT A and B without a same-stack retrieval-off arm does not provide this
identification.

### D. Address routing, run variability, and “robustness”

1. Pin the physical OpenRouter provider/model snapshot where possible.
2. Randomize and interleave A/B calls in item/model blocks so condition is not confounded with
   clock time or provider availability.
3. Repeat cells across independent runs/times and prespecify a precision target. “At least three”
   is a useful minimum diagnostic, not a statistically justified stability guarantee.
4. Separate uncertainty over sampled clinical clusters from variability over repeated generations,
   deployment time, and physical providers.
5. Prespecify the model population or describe pooled estimates as fixed-four-model summaries.

## 6. Concise replacement for the executive claim

> On 318 cleaned items selected as valid for the manipulation, the four named OpenRouter model
> endpoints scored the keyed answer 89.54% of the time in A and 74.04% in B, an observed paired
> difference of −15.50 percentage points. The contrast was negative for all four model IDs and was
> stable across the reported clinical-cluster, cleaning, and leave-one-unit checks. B replaces the
> substantive keyed option with the same position-dependent preceding-options meta-answer on every
> item, so the contrast does not isolate memorisation, lexical familiarity, NOTA format, or
> reasoning burden. Because backend routing and run time were not pinned across arms, it should be
> described as the observed deployed-system contrast unless a no-routing/no-time-confounding
> assumption is made.

For the cross-arm paragraph:

> On the 306 complete-case condition-A items, GIFT-served minus OpenRouter-served accuracy was
> +5.56 points for gemma, +3.27 for glm, −0.33 for qwen, and −0.98 for gemini. These are
> model-specific differences between two deployed pipelines on a non-random covered subset, not
> isolated retrieval effects; GIFT B was never run and the full-target difference is not
> identified.

## 7. Minor terminology and numerical checks

- The primary A/B counts, rates, risk differences, bootstrap intervals, sign-flip value,
  exclusion grid, and GIFT complete-case table reconcile to the current canonical artifacts.
- Use **keyed-answer agreement** or **benchmark-key accuracy** when clinical truth is not being
  independently re-adjudicated. The B gold letter is mechanically inherited from A after removing
  the substantive keyed text.
- “Exact” in “exact sign-flip” describes calculation conditional on its sign-exchangeability
  premise; it does not make a non-pinned serving contrast causally randomized.
- Replace broad uses of “effect” and “efficacy” in the GIFT coverage section with “observed
  pipeline difference” unless the causal system intervention and assumptions are defined.
- If the statement that exactly two exploratory workflows were stopped is retained, list their
  names and the evidence that they did not contribute report values.


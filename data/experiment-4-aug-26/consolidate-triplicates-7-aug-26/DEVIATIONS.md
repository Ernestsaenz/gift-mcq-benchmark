# Deviations from protocol

This is the honest record of everything in this study that did not go according
to the frozen design in METHODS.md. Read this before using any number that
touches `openrouter_B` / `google/gemini-3.6-flash`. Nothing below is hidden
elsewhere — if a number in this folder is affected by one of these deviations,
it is affected by something documented on this page.

Scope check first: this affects **1 of 12** arm-model slices. The other 11 ran
to completion at the frozen `temperature=0` protocol with no routing changes.
Coverage overall is 99.6% (1,788/1,796). Do not let the length of this document
overstate its reach — it is long because it is precise, not because the problem
is large.

## The Vertex routing deviation (the one that matters most)

**What changed.** Starting 2026-08-06, `openrouter_B` / `google/gemini-3.6-flash`
requests were issued with

```json
"provider": {"order": ["google-vertex"], "allow_fallbacks": false, "require_parameters": false}
```

in place of the frozen `{"require_parameters": true}` (which lets OpenRouter
pick any provider that honors `temperature`/`top_p`). Everything else in the
request was held byte-identical to the frozen shape: same prompt, same
`mcq_es_v4` version, same JSON schema, and `temperature: 0` / `top_p: 1.0` were
still transmitted in the payload.

**Why it was necessary.** `google/gemini-3.6-flash` is closed-weights, so
OpenRouter can only route it through Google. Of the model's 2 OpenRouter
endpoints, only **1** supports `temperature`/`top_p` at all — Google AI Studio.
(By contrast the study's other three models have 9-27 providers each, all
compatible, which is why only gemini ever stalled.) The account has no BYOK key
for this model, so it draws on OpenRouter's shared AI Studio pool, which became
intermittently rate-limited on 2026-08-06. Measured pool availability against
the frozen payload that day: ~2 of 4 serving at 10:30Z, ~2 of 4 at 13:55Z, 1 of
6 at 14:05Z (this last measurement taken right after a failed resume attempt —
see below — that had just consumed pool capacity). No alternative
provider exists for this model; the OpenRouter catalogue was queried directly
and confirmed AI Studio is the only temperature-compatible endpoint.

**What it costs.** Vertex does not support `temperature` or `top_p`. Per
OpenRouter's own documentation, with `require_parameters: false` a provider
"can still receive the request, but will ignore unknown parameters" — so the
declared `temperature=0` was **silently discarded** and the model sampled at
its default temperature (~1.0) instead. This was measured before
authorization: three repeats of one frozen request returned `['b', 'c', 'b']`
— i.e. Vertex without a seed is not deterministic, and this study measures
run-to-run variance at temperature 0. Folding provider sampling noise into that
measurement means a gemini A-vs-B comparison now contrasts two sampling
regimes, not two prompt conditions.

**Authorization.** This routing change was authorized by the principal
investigator after the evidence above was presented, prior to any Vertex-routed
call being issued.

**Seed was tested as a fix and rejected.** Fixing a seed does restore
repeatability — measured: `['b','b','b','b']` — but it does not restore
`temperature=0`; it only makes a temperature-1.0 draw reproducible. A shared
seed across run 2 and run 3 would force their variance to zero by construction,
which is not a measurement, it's an artifact. Distinct seeds per run would
instead measure injected sampling noise rather than the model's own
consistency. Neither quantity is what this study estimates, and neither arm A
nor run 1 ever sent a seed, so either choice would also break comparability
with the rest of the dataset. Seed was rejected on that basis.

**How to detect affected cells.** This is machine-detectable from the audit
record and does not depend on this document:

```sql
-- upstream that actually served the SCORING attempt (attribution rule below)
SELECT COALESCE(json_extract(pa.request_json, '$.provider.order[0]'), 'google-ai-studio')
FROM provider_attempts pa
WHERE pa.status_code = 200;
```

A row where this evaluates to `google-vertex` is affected. Affected attempts
also record `"provider": "Google"` in `response_json` (Vertex) rather than
`"Google AI Studio"`, and hash to a `request_sha256` different from the frozen
shape.

**Attribute by the upstream that served the scoring attempt, not by attempt
history.** Three of the 91 Vertex-scored cells also carry earlier, failed AI
Studio attempts on the same logical call; counting by full attempt history
would double-count those three. Use the query above (which reads the
successful, scoring attempt only) rather than scanning every attempt row.

**The `openrouter_B` gemini slice is stratified, not uniform:**

| Cells | Regime |
| --- | --- |
| 2 | Google AI Studio, real `temperature=0`, collected 2026-08-05 before the pool blocked |
| 91 | Google Vertex, default temperature (~1.0), collected 2026-08-06 |
| 7 | Exhausted at the five-attempt ceiling, no data |

The 2 AI Studio cells cannot be backfilled under the new routing: they are
already scored, and the executor skips cells that already carry a score (the
same guard that prevents overwriting data). Treat them as a third stratum with
structurally lower expected variance than the other 91 — do not pool all 93 as
if they were collected under one regime.

**Note on the data model.** In this study's own schema, the provider for every
one of these cells is still `openrouter` and the arm is still `openrouter_B` —
Vertex is an upstream *inside* OpenRouter here, not an alternative to it.
Grouping by provider/arm is therefore still structurally correct; the thing
that must be disclosed is the temperature difference, not the provider label.

## Considered and ruled out: `google/gemma-4-26b-a4b-it` cells served by "Google"

Recording what was investigated and cleared is as useful to a reviewer as
recording what was found, so this is included even though the verdict is
"no deviation."

**Finding.** 5 scored `google/gemma-4-26b-a4b-it` cells — 2 in `openrouter_A`,
3 in `openrouter_B` — carry `response_json.provider = "Google"`, the same
provider string that marks the gemini Vertex deviation above: `b326` r2,
`n113` r2, `n039` r2, `b432` r2, `b304` r3.

**Verdict: not a deviation.** These 5 cells are fully compliant with the
frozen protocol. Two facts establish this:

1. **Parameter support differs by model, not just by provider name.** For
   `google/gemma-4-26b-a4b-it`, the Google endpoint (tag `google-vertex/global`)
   supports **both** `temperature` and `top_p`. For `google/gemini-3.6-flash`,
   all three Google/Vertex endpoints (`global`, `flex`, `priority`) support
   **neither**. Same provider, different model, different capability.
2. **The request record confirms it.** All 5 gemma cells carry the frozen
   provider block — `require_parameters = 1`, no `order` override, `temperature
   = 0`, `top_p = 1.0` — confirmed per cell in `provider_attempts`. OpenRouter
   routed them to Google precisely *because* that endpoint satisfies
   `require_parameters` for this model, and `temperature = 0` was honoured, not
   silently dropped.

**The trap, stated explicitly.** Anyone auditing this dataset by grepping
`response_json` for `"provider": "Google"` and treating every hit as
deviation-tainted will reach the wrong conclusion. **Provider identity alone
does not indicate a deviation — parameter compatibility does.** A
Google-served response is compliant for gemma and non-compliant for gemini,
under the identical provider string, because the two models expose different
capabilities at the same upstream. Filter on the routing block
(`provider.order[0] = 'google-vertex'` combined with `require_parameters =
false`, as in the detection query above) and on the model, not on the provider
string alone.

**What this confirms about `require_parameters: true`.** This is the same
flag discussed in METHODS.md as an integrity guarantee rather than a routing
preference. This finding is the clean illustration of why: the exact same
`require_parameters = true` flag blocked gemini for hours (because no
Google-family endpoint serving gemini supports `temperature`/`top_p`) while
letting gemma's Google-served calls through immediately and correctly
(because that model's Google endpoint does support them). The flag isn't
picking a provider brand; it's discriminating on real parameter support,
per model, exactly as designed.

## The 8 cells exhausted at the five-attempt ceiling

These reached the technical-retry ceiling (METHODS.md) without ever producing a
parseable score, and cannot be retried without raising
`--max-provider-attempts`, which would itself be a protocol change:

| Arm | Model | Question | Run(s) exhausted | Failure mode |
| --- | --- | --- | --- | --- |
| openrouter_B | google/gemini-3.6-flash | n012 | 2, 3 | all attempts 429 rate_limited |
| openrouter_B | google/gemini-3.6-flash | n036 | 2, 3 | all attempts 429 rate_limited |
| openrouter_B | google/gemini-3.6-flash | b326 | 2, 3 | all attempts 429 rate_limited |
| openrouter_B | google/gemini-3.6-flash | b373 | 2 | all attempts 429 rate_limited |
| tailscale_A | z-ai/glm-5.2 | b264 | 2 | all attempts 500, four hanging 150.1-150.2s |

That is 7 logical calls on `openrouter_B` gemini and 1 on `tailscale_A` glm — 8
total, matching SPEC.md and the top-level 1,788/1,796 figure.

## The 3 cells whose attempt history spans both routings

**Correction:** SPEC.md originally stated this count as 2. That figure predated
the final Vertex batch and has been corrected in SPEC.md to 3, verified against
the database on 2026-08-07 and recorded here:

```sql
SELECT lc.id, q.question_id, lc.run_index,
       COUNT(DISTINCT pa.request_sha256) AS hashes, COUNT(*) AS attempts
FROM provider_attempts pa
JOIN logical_calls lc ON lc.id = pa.logical_call_id
JOIN questions q ON q.id = lc.question_id
GROUP BY lc.id HAVING hashes > 1;
```

(read-only: use `sqlite3 "file:<path>?mode=ro"` against
`replications/ab520-incorrect-cells-triplicate-2026-08-05/runs/ab520-incorrect-cell-triplicates-2026-08-05.sqlite`
— plain `-readonly` has failed on this machine.)

| Arm | Model | Question | Run | Distinct `request_sha256` | Attempts | Scored |
| --- | --- | --- | --- | --- | --- | --- |
| openrouter_B | google/gemini-3.6-flash | b101 | 2 | 2 | 5 | yes |
| openrouter_B | google/gemini-3.6-flash | b323 | 2 | 2 | 3 | yes |
| openrouter_B | google/gemini-3.6-flash | b373 | 3 | 2 | 5 | yes |

All three carry two distinct request shapes because their earlier attempt(s)
went out under the frozen AI Studio-eligible routing and returned `429`
(no score), and their later attempt(s) went out under the Vertex routing and
succeeded. **The mixed history does not make any score ambiguous**: each of
these three logical calls has exactly one attempt that returned `status_code =
200`, and that attempt — the Vertex one — is unambiguously what was scored.
The failed AI Studio attempts contributed no data; they only cost budget
against the five-attempt ceiling (`b101` and `b373` each used all 5 attempts to
get there; `b323` scored on its 3rd).

**Downstream implication.** The sibling experiment's `finalize_execution.py:284`
asserts exactly one `request_sha256` per logical call. That assertion, as
written, would trip on all three of these cells, because it appears to check
across full attempt history rather than across scoring attempts only. It
should be scoped to attempts where `status_code = 200` (i.e. the attempt that
actually produced the score), not to every attempt a logical call ever made.
This is noted here as a finding for whoever owns that script; it has not been
changed as part of this consolidation.

## The failed resume attempt, 2026-08-06 ~14:00Z

Before the Vertex routing decision, a bounded loop re-invoked the executor 6
times against `openrouter_B` gemini, hoping to pick off the remaining
untried cells opportunistically:

```
round 1: +2  total 2/100  exhausted 2
round 2: +0  total 2/100  exhausted 3
round 3: +0  total 2/100  exhausted 4
round 4: +0  total 2/100  exhausted 5
round 5: +0  total 2/100  exhausted 6
round 6: +0  total 2/100  exhausted 7
```

Net result: 2 scores banked, **5 cells pushed to the exhausted ceiling**, for a
net-negative outcome. Do not repeat this design.

**Design flaw, not bad luck.** The executor selects targets in a fixed order
and aborts the entire invocation on the first 429
(`execute_replicates.py:309`). Because previously attempted cells sort to the
head of the queue, every round of the loop re-attacked the same head cell,
burned two more of its five attempts, and aborted before ever reaching an
untried cell further back in the queue. Each round therefore cost the run
almost exactly one cell pushed to the ceiling, with no net progress on the 88
cells that had never been attempted. This was confirmed afterward from the
attempt-budget distribution: the 88 never-attempted cells were still sitting at
0 attempts, untouched, after all 6 rounds.

Fixed-order-queue-head plus abort-on-first-429 is a combination that
concentrates failure on whatever cell happens to be attempted first, rather
than spreading exposure across the queue — the opposite of what you want when
probing an intermittently available upstream.

## Two hypotheses recorded and later retracted

Both appeared in STATUS.md during the investigation of the 429s and were
disproven by later evidence. Recording the retraction explicitly, as the
original document does, rather than silently correcting it:

1. **"The 429 is arm-specific."** Retracted. The actual cause is that
   `openrouter_B` gemini draws on OpenRouter's shared Google AI Studio pool
   (no BYOK key on the account), and that pool's availability varies over time
   regardless of arm — `openrouter_A` gemini only completed cleanly because it
   happened to run first (16:17-16:33Z on 2026-08-05), before the pool drained.
   The 429 body itself identifies the cause directly:
   `"limit_source": "upstream_provider_shared_pool"`,
   `"provider_name": "Google AI Studio"`, `"is_byok": false"`.
2. **"`provider.require_parameters` is narrowing routing and causing the
   429s."** Retracted. A direct query of the OpenRouter catalogue for every
   endpoint of every model in this study showed `require_parameters: true`
   correctly narrows gemini to its one compatible provider (AI Studio) — which
   is by design, not a bug — while the other three models retained 9-27
   compatible providers each and never stalled. The parameter was doing exactly
   what it is documented to do
   (`code/medrag_eval/providers/openrouter.py:176`): fail loudly rather than
   silently serve a request stripped of `temperature=0`. It was not the source
   of the rate limiting.

A reader relying only on an early read of STATUS.md could still believe either
of these; both are corrected in the final version of that document and in this
one.

## Record-keeping defect: `redacted_command` does not reproduce the actual invocation

This is a defect in the historical **invocation records**, not in the data
itself — the underlying provider attempts and scores are unaffected and fully
recoverable from the database regardless of this issue. It is documented in
full in `ledger/LEDGER_README.md`; it is repeated here, briefly, because
DEVIATIONS.md is where a reader is told to look for every integrity issue in
this folder, and this one would otherwise be missed by anyone who reads only
this file.

**What's wrong.** `execute_replicates.py` built each invocation record's
`redacted_command` field from a fixed five-argument template rather than from
the arguments the invocation actually ran with. As a result, none of the 34
historical invocation records reproduces the command that was really issued.
Concretely: the two Vertex-routed invocations don't show
`--deviation-route-upstream` in their recorded command, and every single-cell
probe lost its `--question-id` / `--run-index` — so the command shown for a
probe would, if copy-pasted, re-run an entire slice instead of the one cell
that was actually targeted.

**What it does not affect.** The deviation itself was never lost: it is
independently recoverable from the database (91 `provider_attempts` rows with
`provider.order[0] = 'google-vertex'`, per the detection query above), and the
scores and prompt hashes for every logical call are correct and untouched.
This is a defect in the human-readable audit trail of *how a command was
invoked*, not in *what was scored*.

**Status.** Fixed going forward in commit `dd3a6b8` (2026-08-07). The 34
historical invocation records were deliberately left unmodified — see
`ledger/LEDGER_README.md` for the full account and the per-invocation detail.

## Recommended remedy (not yet applied to this dataset)

STATUS.md records a recommended fix that was not applied to the data in this
folder: add a Google AI Studio key to the OpenRouter account. This would move
the model onto the account's own rate limits without altering the frozen
request, keeping `openrouter_B` gemini byte-comparable to `openrouter_A`
gemini. It is noted here for completeness; the data as consolidated in this
folder still reflects the Vertex-routed collection described above.

## Cross-check against SPEC.md

SPEC.md and STATUS.md agree on every other figure checked while writing this
document: the 1,788/1,796 total, the per-arm and per-arm-model breakdowns, the
898-cell / 1,796-call design, the list of 8 exhausted cells, the Vertex
routing deviation and its `['b','c','b']` measurement, the seed rejection
reasoning, and the two retracted hypotheses.

One figure was wrong and has since been corrected: SPEC.md originally said 2
cells span both routings; verification against the database on 2026-08-07
found 3 (`b101` run 2, `b323` run 2, `b373` run 3 — table above). SPEC.md has
been updated to 3. This document was updated to match after that
verification.

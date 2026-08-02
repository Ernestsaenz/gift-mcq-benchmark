# QA02 — independent data-quality and analytical-grain audit

**Audit date:** 2026-07-31  
**Mode:** read-only inspection of the SQLite database, flat workbooks, analysis JSON, build code,
`REPORT.md`, and `RUN_STATUS.md`. No canonical file was regenerated or edited.  
**Overall verdict: FAIL for final-report delivery.** The database and the current v2 JSON extracts
are largely internally sound, but the report mixes v1 and v2 results, run completion is
misstated, and the supposedly deterministic extraction query does not actually pin the scored
retry. These are material provenance and reconciliation failures, not cosmetic issues.

## 1. Scope and snapshot

Files treated as authoritative inputs:

- `../experiment.sqlite` — MD5 `1c5fcbb79c93f1a0554c3e8cea0be552`
- `paired_clean.json` — MD5 `0b25b95d082cf00900443d262c84427e`
- `cross_arm_A.json` — MD5 `39148f1f6ae007c0ec549e8e5d5f3d79`
- `gift_coverage.json` — MD5 `09c54f535cf7c7171b99be1232866009`
- source workbook — MD5 `521459bc33b6285b140232a5c0516eaf`, matching the documented hash

All three recorded JSON hashes in `dataset_meta.json` match the files on disk.

### Component verdicts

| component | verdict | reason |
|---|---|---|
| SQLite referential integrity and candidate keys | **PASS** | zero foreign-key violations, grain duplicates, cross-dataset calls, or score recomputation mismatches |
| Flat A/B datasets | **PASS** | row counts, workbook-to-DB values, A/B subset relation, and one-option-only manipulation all reconcile |
| Current v2 JSON rows | **CONDITIONAL PASS** | keys/counts/values match the scored DB rows now, but the build query is nondeterministic across retries |
| Exclusion mechanics | **PASS** | all declared flags and overlap arithmetic reconcile exactly |
| Exclusion evidence/provenance | **CONDITIONAL** | post-hoc 22-item list lacks per-item reasons/citations; three key-defect adjudications cannot be reproduced from the metadata |
| Cluster mapping | **PASS** | no prefix collision or inconsistent assignment; v2 has 201 A/B clusters and 178 cross-arm clusters |
| `REPORT.md` / `RUN_STATUS.md` | **FAIL** | mixed v1/v2 counts and point estimates; completion and failed-attempt statements conflict with the DB |

## 2. Intended grain and duplicate audit

The defensible grains are:

| table/artifact | intended key |
|---|---|
| `questions` | `(dataset_id, question_id)` |
| `logical_calls` | `(experiment_id, question_id, provider, model, run_index, prompt_version)` |
| `provider_attempts` | `(logical_call_id, attempt_index)` |
| scored response | one `scores` row per `logical_call_id`, linked through `scores.parsed_answer_id` |
| `paired_clean.json` | `(question_id, model)` observed in both OpenRouter A and B |
| `cross_arm_A.json` | `(question_id, model)` observed in both GIFT A and OpenRouter A, restricted to the all-four-model GIFT item intersection |

Results:

- Candidate-key duplicate groups: **0** in `questions`, `logical_calls`, and
  `provider_attempts`.
- Actual duplicate `scores.logical_call_id`: **0**; duplicate `scores.parsed_answer_id`: **0**.
- Duplicate parses for the same `provider_attempt_id`: **0**.
- Non-contiguous attempt-index sequences: **0**.
- Exact or lower/trim-normalized duplicate question+four-option+key payloads within either
  dataset: **0**.
- Exact duplicate JSON rows: **0**; duplicate `(question_id, model)` keys: **0** in both exports.
- SQLite `PRAGMA foreign_key_check`: **0 rows**.
- Logical calls whose question belongs to a different dataset from the experiment: **0**.
- Score-to-parse logical-call mismatches: **0**; parse-to-attempt logical-call mismatches: **0**.
- Stored score fields that fail independent recomputation from the scored parse and question key:
  **0** across letter, text, strict, and lenient scoring.
- Invalid/null correctness or selected-letter fields in either JSON export: **0**.

The 59 scored OpenRouter calls with multiple parsed attempts (21 A, 38 B) do **not** represent
duplicate analytical observations: each has exactly one score, and that score points to the latest
successful parse. Retries must nevertheless be joined correctly, as described in section 5.

## 3. Dataset eligibility and A/B integrity

### Source to flat datasets

The eligibility arithmetic is exact and the sets are disjoint:

- Source: **500** items.
- Dataset A: `500 - 17 three-option - 9 source-level QA defects = 474`.
- Dataset B: `474 - 30 aggregator-answer - 5 pre-existing-NOTA/ambiguous - 16
  swap-specific QA defects = 423`.
- B is a strict subset of A: **423 common, 51 A-only, 0 B-only**.

The 17 three-option IDs are:

`b216 b239 b241 b242 b259 b288 b289 b291 b340 b352 b369 b394 b399 b402 b406 b409 b500`

The nine source-level QA exclusions already removed from both flat datasets are:

`b10 b14 b16 b18 b19 b23 b202 b228 b408`

The 51 A-only items break down without overlap as follows:

- Aggregator answer, 30:
  `b1 b20 b34 b41 b53 b60 b67 b70 b72 b75 b80 b100 b103 b108 b117 b118 b119 b120 b126 b127 b128 b129 b138 b139 b144 b149 b162 b164 b263 b420`
- Pre-existing none-of-the-above/ambiguous, 5:
  `b105 b140 b278 b343 b452`
- Swap-specific QA exclusions, 16:
  `b152 b188 b191 b204 b245 b257 b292 b303 b342 b398 b428 b430 b437 b458 b491 b497`

The database declares 474 and 423 rows and contains exactly 474 and 423 distinct question IDs.
All 897 workbook rows match the corresponding DB row on the 13 core fields. For all 423 paired
items:

- metadata, stem, correct letter, and all three non-key options are identical between A and B;
- exactly one option differs;
- B's changed option and `correct_option_text` both equal the declared NOTA string;
- each dataset's `correct_option_text` equals the option at its `correct_letter`.

This is a **PASS** for the mechanical A/B construction.

### Analysis-stage exclusions

Declared post-ingestion item defects:

- Out-of-domain law/administration, 19:
  `b205 b213 b238 b293 b331 b341 b343 b361 b378 b385 b391 b396 b401 b407 b420 b430 b433 b445 b451`
- Adjudicated key defects, 3:
  `b178 b197 b496`

All 22 exist in A. Only **19** exist in B and therefore in the A/B eligible item universe;
`b343`, `b420`, and `b430` had already been removed from B during flattening. The 19 eligible
defect IDs are:

`b178 b197 b205 b213 b238 b293 b331 b341 b361 b378 b385 b391 b396 b401 b407 b433 b445 b451 b496`

There are exactly **91** B items with `correct_letter='a'`, and every one is flagged for the
positionally incoherent NOTA string:

`b3 b8 b15 b17 b40 b58 b62 b63 b74 b84 b91 b94 b96 b97 b102 b109 b130 b135 b145 b146 b150 b165 b169 b187 b189 b195 b214 b219 b220 b225 b230 b231 b236 b238 b249 b251 b253 b255 b258 b269 b275 b280 b290 b298 b302 b305 b308 b312 b315 b316 b324 b328 b331 b337 b347 b350 b351 b356 b365 b377 b378 b380 b382 b389 b391 b397 b404 b410 b412 b419 b424 b426 b429 b436 b438 b439 b445 b448 b453 b454 b461 b463 b465 b466 b468 b476 b477 b482 b488 b492 b495`

Five items overlap the defect and position-a sets: `b238 b331 b378 b391 b445`.

The exact A/B count reconciliation is therefore:

```text
423 eligible B items - 19 eligible item defects - 91 position-a + 5 overlap = 318 items
423*4 theoretical cells - 1 unresolved cell = 1691 observed cells
1691 - 19*4 - 91*4 + 5*4 = 1271 included cells
```

The unresolved cell is `b320 × z-ai/glm-5.2` in OpenRouter A. It is otherwise analysis-eligible,
so the included per-model denominators are 318, 318, 318, and **317 for glm**.

For the cross-arm extract, 319 items have scored GIFT results for all four models; 13 of the 22
declared defects fall in that coverage set. Thus `319 - 13 = 306` items and
`319*4 - 13*4 = 1224` cells. No NOTA-position exclusion applies to condition A.

### Provenance limitation

The exclusion *mechanics* pass, but the post-hoc exclusion *evidence* does not meet the report's
own reproducibility claim. `dataset_meta.json` contains ID lists, not a reason for each ID. In
particular, it does not preserve the adjudication or citations supporting `b178`, `b197`, and
`b496`. `REPORT.md` recommendation 5 says all 22 are "listed with reasons" there; that is false.
The 19 law/administration stems are facially consistent with the category on inspection, but the
three medical-key judgments cannot be independently reproduced from the shipped metadata.

**Severity: Medium; confidence: high.** Preserve a per-ID ledger with category, quoted evidence,
reviewer/refuter disposition, and external citation where medical correctness is asserted.

## 4. Parsed, missing, and retry cells

| experiment | planned cells | logical calls created | provider attempts | parse rows | scored cells | true scored completion |
|---|---:|---:|---:|---:|---:|---:|
| OpenRouter A | 1896 | 1896 | 1930 | 1930 | **1895** | **99.95%** |
| OpenRouter B | 1692 | 1692 | 1745 | 1745 | **1692** | **100%** |
| GIFT A | 1896 | **1566** | 1582 | 1386 | **1384** | **73.0%** |
| GIFT B | 1692 | 0 | 0 | 0 | 0 | 0% |

Important distinctions:

- GIFT reached/created 1566 of 1896 planned logical calls (**82.6% attempted**), but only 1384
  were scored (**73.0% completed**). Calling the arm "83% complete" is wrong.
- Of GIFT's 182 created-but-unscored logical calls: **96** ended in one rate-limit error, **83**
  in one server error, **2** produced an unparseable response, and **1** (`b417 × glm`) has no
  provider attempt. A further **330** planned cells were never created.
- GIFT's all-four-model intersection is 319 items (67.3% of A), which is the correct pre-exclusion
  basis for `cross_arm_A.json`.
- OpenRouter A is not fully scored. `b320 × glm` has **10** provider attempts: attempts 1–5 and
  7–10 ended `finish_reason=length` at 65,536 completion tokens (**9 length attempts** total), and
  attempt 6 ended `finish_reason=error`. All 10 parses are `failed_no_answer_found`; there is no
  score.
- Retried logical calls: **22** OpenRouter A, **38** OpenRouter B, **17** GIFT A. The current score
  always points to the latest successful parsed attempt.

**Severity: High; confidence: high.** Correct `REPORT.md`/`RUN_STATUS.md` so "attempted",
"parsed", and "scored" are separate columns. Replace the statements "GIFT completed 83%",
"OpenRouter A completed 1896", and "five consecutive" b320 failures.

## 5. Retry-deduplication defect in the build script

`build_analysis_data.py::scored_cells` claims to reach the attempt actually scored, but its SQL
does not do so:

```sql
JOIN parsed_answers p    ON p.logical_call_id = lc.id
JOIN provider_attempts a ON a.id = p.provider_attempt_id
```

Because `scores` is joined only by `logical_call_id`, every parse from a retried call is joined to
the one score. Python then silently overwrites duplicate `(question_id, model)` dictionary keys in
undefined SQL row order. The correct join is:

```sql
JOIN parsed_answers p
  ON p.id = s.parsed_answer_id
 AND p.logical_call_id = lc.id
JOIN provider_attempts a
  ON a.id = p.provider_attempt_id
 AND a.logical_call_id = lc.id
```

Current blast radius check: 19 paired-A rows, 38 paired-B rows, and 8 cross-arm OpenRouter rows
refer to calls with multiple parses. On this database and query plan, all exported selected
letters, correctness values, token counts, latencies, and backends happen to match the explicitly
score-linked attempt: **0 current mismatches**. Primary correctness is also read directly from the
single score row. The defect is nevertheless real: a planner/index change or future retry layout
can attach ancillary fields from a superseded attempt, contradicting the script's deterministic
claim.

**Severity: Medium; confidence: high.** Fix the join and add an assertion that the SQL returns one
row per `(question_id, model)` before dictionary construction.

## 6. Cluster mapping

The implementation groups context-bearing items by the first 120 characters of their base
prepended vignette and makes every non-context item a singleton.

Independent checks:

- Dataset A: 474 items, **196** context-bearing and **278** singletons.
- These resolve to 21 base-vignette clusters plus 278 singletons = **299 total clusters** before
  analysis filtering.
- Distinct base-vignette texts mapping to the same 120-character key: **0**. Therefore the
  truncation causes no collision in this dataset.
- The workbook has 32 distinct nonempty context-ID chains; progressive transition chains for
  three cases intentionally collapse to their shared base vignette. No context-ID chain is split
  across clusters.
- Within-question cluster disagreements across models: **0**.
- Cluster mismatches for shared questions between paired and cross-arm JSON: **0**.
- Canonical v2 analysis clusters: **201** A/B and **178** cross-arm, agreeing with the JSON and
  `dataset_meta.json`/v2 status table.

The mapping itself passes. However, `REPORT.md` still says 208 clusters in the leave-one-out and
Kish-effective-cluster passages; those are v1 values and must not be presented as v2.

## 7. Output count reconciliation and material report failures

### Canonical v2 artifacts

| artifact/set | items | cells | clusters | duplicate keys |
|---|---:|---:|---:|---:|
| paired, observed before analysis exclusions | 423 | 1691 | 281 | 0 |
| paired, item defects only | **404** | **1615** | 263 | 0 |
| paired, position-a only | 332 | 1327 | 214 | 0 |
| paired, both/current analysis | **318** | **1271** | **201** | 0 |
| cross-arm, all-four GIFT coverage | 319 | 1276 | — | 0 |
| cross-arm, current analysis | **306** | **1224** | **178** | 0 |

Current A/B included-cell counts are 1138/1271 correct in A and 941/1271 in B, a raw pooled
change of **-15.50 percentage points**. Per-model counts reconcile to the headline rounded
accuracies: gemini 311/318 vs 284/318; gemma 251/318 vs 189/318; qwen 281/318 vs 231/318; glm
295/317 vs 237/317.

### F1 — `REPORT.md` mixes v1 and v2 (Critical)

The report header and headline use v2 (318/1271/201), but section 3 still presents v1 as the
reported analysis:

- `item defects only` is shown as **412/1647**; current v2 is **404/1615**.
- `both (reported)` is shown as **325/1299**; current v2 is **318/1271**.
- The displayed v1 pooled delta is -15.55pp; current raw v2 delta is **-15.50pp**.
- Leave-one-out is described as 208 clusters / 325 items, while current v2 is 201 / 318.
- The Kish sentence says "53 of 208" and must be recomputed on v2 rather than merely relabelled.

The cross-arm table is also v1 under a v2 denominator. Directly from the 306-item v2 extract:

| model | GIFT correct | OpenRouter correct | GIFT | OpenRouter | delta | discordant GIFT+/OR+ |
|---|---:|---:|---:|---:|---:|---:|
| gemini | 298/306 | 301/306 | 97.4% | 98.4% | -1.0pp | 0 / 3 |
| gemma | 270/306 | 253/306 | **88.2%** | **82.7%** | **+5.6pp** | 24 / 7 |
| qwen | 281/306 | 282/306 | **91.8%** | **92.2%** | **-0.3pp** | **11 / 12** |
| glm | 295/306 | 285/306 | **96.4%** | **93.1%** | **+3.3pp** | 11 / 1 |
| pooled | 1144/1224 | 1121/1224 | 93.5% | 91.6% | +1.9pp | 46 / 23 |

`REPORT.md` instead gives the superseded v1 gemma, qwen, and glm percentages and qwen 11/13.
Any inferential statistics derived from those v1 tables must be recomputed rather than copied to a
v2 report.

**Severity: Critical; confidence: high.** Do not deliver the present report as final.

### F2 — Completion reporting is internally contradictory (High)

`RUN_STATUS.md` labels 1896 OpenRouter-A cells completed despite the admitted unscored b320 cell.
Both status and report call GIFT A "83% complete" while also giving 1384/1896 scored cells. The
correct labels are 82.6% attempted and 73.0% scored/completed. The b320 narrative says five length
failures; the DB has nine length failures plus one error response.

### F3 — Reproduction does not reproduce all metadata (Medium)

`dataset_meta.json` was modified nine minutes after the three data JSON files. Its current
postscript fields (`export_version`, superseded counts, measurement caveats, and file hashes) are
not emitted by `build_analysis_data.py`. Running the documented reproduction command overwrites
and removes them. The script also lacks `cross_clusters_analysis`, although the report relies on
178. The `flatten.py` module docstring still advertises obsolete outputs of 483 A / 448 B while
the code and files correctly produce 474 / 423.

**Remediation:** generate the complete metadata object in code, write a versioned manifest rather
than hand-augmenting it, and assert all report-facing counts from that manifest.

## 8. Reproducible audit snippets

All SQL was run read-only:

```bash
DB='file:tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro'
sqlite3 -header -column "$DB"
```

Core integrity and authoritative scored-attempt query:

```sql
PRAGMA foreign_key_check;

SELECT experiment_id, question_id, provider, model, run_index, prompt_version, COUNT(*) n
FROM logical_calls
GROUP BY experiment_id, question_id, provider, model, run_index, prompt_version
HAVING n > 1;

SELECT lc.id, q.question_id, lc.model, s.strict_correct,
       p.selected_letter, a.attempt_index, a.latency_ms, a.completion_tokens
FROM scores s
JOIN logical_calls lc      ON lc.id = s.logical_call_id
JOIN questions q           ON q.id = lc.question_id
JOIN parsed_answers p      ON p.id = s.parsed_answer_id
                           AND p.logical_call_id = lc.id
JOIN provider_attempts a   ON a.id = p.provider_attempt_id
                           AND a.logical_call_id = lc.id
JOIN experiments e         ON e.id = lc.experiment_id
WHERE e.name = 'expA_or_310726';
```

Run-state reconciliation:

```sql
SELECT e.name,
       COUNT(DISTINCT lc.id) logical_calls,
       COUNT(DISTINCT a.id) attempts,
       COUNT(DISTINCT p.id) parses,
       COUNT(DISTINCT s.id) scores
FROM experiments e
LEFT JOIN logical_calls lc     ON lc.experiment_id=e.id
LEFT JOIN provider_attempts a  ON a.logical_call_id=lc.id
LEFT JOIN parsed_answers p     ON p.logical_call_id=lc.id
LEFT JOIN scores s             ON s.logical_call_id=lc.id
GROUP BY e.id;
```

JSON grain and exclusion arithmetic:

```python
import json
from collections import Counter

rows = json.load(open("analysis/paired_clean.json"))
assert not [k for k, n in Counter(
    (r["question_id"], r["model"]) for r in rows
).items() if n > 1]

for name, keep in {
    "none": lambda r: True,
    "defects": lambda r: not r["excl_item_defect"],
    "position_a": lambda r: not r["excl_nota_position_a"],
    "both": lambda r: r["analysis_include"],
}.items():
    part = [r for r in rows if keep(r)]
    print(name, len({r["question_id"] for r in part}), len(part),
          len({r["cluster"] for r in part}))
```

Expected output is `none 423 1691 281`, `defects 404 1615 263`,
`position_a 332 1327 214`, and `both 318 1271 201`.

## 9. Minimum release gate

Before delivery:

1. Fix the score-to-parse join and regenerate versioned artifacts without losing metadata.
2. Recompute every v1-derived robustness and cross-arm statistic on the 318/1271 and 306/1224
   v2 sets; do not merely change labels.
3. Replace completion language with attempted/parsed/scored counts and correct the b320 attempt
   history.
4. Add per-ID evidence for all 22 post-hoc defects, especially the three medical key defects.
5. Add automated assertions for dataset row counts, export composite-key uniqueness, one returned
   scored row per cell, exclusion arithmetic, cluster counts, and report-manifest consistency.

Until those gates pass, the data extracts may be used for controlled recomputation, but the
current prose report should not be treated as a final, internally reconciled deliverable.

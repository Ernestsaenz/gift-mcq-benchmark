# QA09 — final-analysis code and reproducibility review

**Audit date:** 2026-07-31 (Europe/Madrid)  
**Scope:** `analysis/build_analysis_data.py`, `analysis/final_analysis.py`,
`analysis/build_report_artifact.py`, `../flatten.py`, and the current `REPORT.md` / canonical result
artifacts.  
**Mode:** canonical code, data, and result artifacts were not edited or regenerated in place.
Builder runs and every mutation/edge-case test wrote to disposable temporary directories; canonical
DB inspections were read-only. This QA file is the only canonical report created by QA09.

## Verdict: FAIL for release of the portable report artifact; PASS for the current core point estimates

The current v3 data exports and `final_analysis_results.json` reproduce byte-for-byte from the
current frozen inputs. The exclusion arithmetic reconciles, the scored-attempt join now selects
`scores.parsed_answer_id`, and independent checks confirm the McNemar, Holm, exact sign-flip, and
whole-cluster bootstrap primitives.

The release bundle is nevertheless not self-authenticating or currently reproducible end to end.
The checked `report_artifact.json` embeds an older `REPORT.md`; rebuilding it with the current code
silently omits the cross-arm chart and table. Its source records also describe JSON/Markdown files
as SQLite relations and contain SQL that cannot be replayed. `final_analysis.py` records the run-DB
hash but does not compare it with the hash pinned by `dataset_meta.json`, allowing a hybrid result
from exports and run status belonging to different DB versions. Several report-level inferential
numbers are copied constants whose source files are neither loaded nor hashed.

Snapshot reviewed:

| file | SHA-256 |
|---|---|
| `build_analysis_data.py` | `f3b9899ee945d39b7c02502c52060aa72f5df7c2c79d3cb5afa000fc97b78470` |
| `final_analysis.py` | `e0dd41ce353771135a6901a827935340229126cc21cd6a995888d24c9b9aa44d` |
| `build_report_artifact.py` | `d8fe28bd5314f50799d5995448b5ec1614f25687cf41bbd37a58b14802f53884` |
| `flatten.py` | `ddd9497368cb8bfd151971d58cba0752da7cca4c1a560beabbd342d788013173` |
| `dataset_meta.json` | `fc4b4d5aa217dcce743f9269583ff8002f4d77360d4668d108ad7a143d7e1148` |
| `final_analysis_results.json` | `e420cd5a0e5505ab1c725d2c8ae59fbc722567f12e879b837278bd6b37364f3e` |
| `REPORT.md` | `1b04236ec9e5d8c18d2187904a5288b2ff6ed2b65e106bf9c2b18033e21258bf` |
| `report_artifact.json` | `3b097c279963b47e3f1f6beedf0561b5a03a4b5c9af8bb1df93780afe7e6357d` |

## Release-blocking findings

### HIGH-1 — the checked report artifact is stale, and a rebuild silently loses the cross-arm widgets

**Evidence.** `build_report_artifact.py:325-348` conditionally inserts widgets by exact normalized
heading text. The cross-arm branch at `:340` expects
`6_partial_gift_versus_openrouter_result_condition_a_only`, but the current heading is
`REPORT.md:186`, “Partial GIFT-served versus OpenRouter-served…”, which normalizes to a different
ID. A disposable rebuild produced 18 blocks and no `cross_chart_block` / `cross_table_block`; the
checked artifact has 20 blocks because it still embeds the earlier heading and earlier narrative
(`report_artifact.json:471-476,537-539`). It also records `generatedAt=18:00`
(`report_artifact.json:8`) whereas the current builder pins `12:30`
(`build_report_artifact.py:16`). The regenerated SHA-256 was
`4d721993715e850112b52985fff892a9151252df1259c15730b41096296d20ee`, not the checked artifact's
hash. Differences were substantive report prose and block structure, not only the timestamp.

**Impact.** The portable artifact is not the current report contract. Publishing the checked file
publishes superseded claims; rebuilding publishes the current prose but hides the cross-arm visual
evidence even though its chart/table definitions remain in the manifest.

**Fix.** Replace display-heading coupling with stable explicit anchors or a declared section-to-
widget map. Assert that every required insertion point was found, every chart/table/card is
reachable from a block, and no expected widget is orphaned. Regenerate the artifact after the final
`REPORT.md`, and add a CI check that a clean build is byte-identical to the checked artifact.

### HIGH-2 — artifact source provenance is non-replayable and factually mis-typed

**Evidence.** `build_report_artifact.py:34-47` labels every source query as `engine: sqlite` and
fabricates `SELECT * FROM <filename-stem>`. Four declared sources are JSON files and one is Markdown
(`:140-145`), not SQLite relations. The sole actual database query is `SELECT * FROM experiment`,
but the DB table is `experiments`; executing the declared query fails with `no such table:
experiment` (`report_artifact.json:831-839`). The query timestamps come from a constant
(`build_report_artifact.py:16,44`) and no query is executed. No source entry carries a content hash.
The QA data input is lower-case `qa_workflows/qa_summary.json` (`:14,54`), while its manifest source
is the different, currently nonexistent `qa_workflows/QA_SUMMARY.md` (`:145`;
`report_artifact.json:462-465`).

**Impact.** A reader cannot replay or authenticate any widget from the source metadata. The
artifact presents invented query lineage as executed evidence, which defeats the main purpose of a
portable audited report.

**Fix.** Use truthful source types (`sqlite`, `json`, `markdown`) with repo-relative path, SHA-256,
and a real selector/transformation (SQL only for actual DB queries; JSON Pointer/JMESPath or an
explicit builder transformation for JSON). For database-derived status, store the actual SQL and
tables (`experiments`, `logical_calls`, etc.). Use the same QA file for ingestion and provenance,
and hash it. Derive `executed_at` at build time or use a documented `SOURCE_DATE_EPOCH`; do not call
an unexecuted query “executed.”

### HIGH-3 — `final_analysis.py` accepts a run DB that does not match the canonical exports

**Evidence.** `final_analysis.py:382-385` verifies only `paired_clean.json` and
`cross_arm_A.json`. At `:389-394` it records the current DB hash but never compares it with
`meta["input_sha256"]["experiment_database"]`, then recomputes run status from that unchecked DB at
`:398-401`. In a disposable test, changing one GIFT attempt from non-200 to 200 changed the DB hash
from the metadata-pinned
`dec53a3d8ed452676672820a758b4571d061c3fe994c45981095d30216744748` to
`57d67b20efe46158f5b97a387ea91e9e40b6213a048c83fb45daea0beee39730`. The script still succeeded
and emitted the old analysis estimates with `failed_attempts=195` instead of 196.

**Impact.** A single “final” JSON can combine estimates from one DB snapshot and operational status
from another while appearing fully hash-pinned.

**Fix.** Before loading results, require the DB SHA-256 to equal
`meta.input_sha256.experiment_database`; likewise verify every consumed input. Include and verify
the builder/result-code hashes. Fail before any analysis if a hash is missing or mismatched.

### HIGH-4 — report-level inferential results are copied constants, not recomputed or hash-pinned inputs

**Evidence.** The logistic estimates and heterogeneity tests are literals in
`final_analysis.py:235-255`; the cleaned interaction is literal at `:295-299`; the cross-arm
heterogeneity and Manski bound are literals at `:331-336`. Their `source` strings point to QA03,
QA05, and QA06, but those files are never read and are absent from `input_sha256` (`:389-394`). The
current report relies on these values at `REPORT.md:95-107,148-152,205-225`, and the portable
artifact surfaces the model-adjusted OR as a metric.

**Impact.** Editing, removing, or replacing a cited QA source does not invalidate or change the
result bundle. The opening claim that this script “recompute[s]” the compact report results is false
for material secondary results.

**Fix.** Recompute these analyses in versioned code, or ingest machine-readable audited result
files and verify their SHA-256 plus declared input hashes. Do not use Markdown as the sole numeric
source. Add those code/result hashes to the result manifest.

## Medium-severity findings

### MEDIUM-1 — run-status SQL has a many-to-many join and can overcount failed attempts

`final_analysis.py:347-359` joins attempts and scores independently through `logical_calls`, then
uses a plain `SUM(...)` for failed attempts at `:353-354`. The schema does not make
`scores.logical_call_id` unique. A disposable DB with one duplicate score on a recovered GIFT call
had 196 true failed attempt rows, but `run_status()` reported 197. Current canonical data happen to
have one score per call, so the checked value 196 is correct.

**Fix.** Aggregate calls, attempts, failures, and scores in separate CTEs before joining, or at
minimum use `COUNT(DISTINCT CASE WHEN ... THEN a.id END)` for failures. Explicitly assert the
one-score-per-logical-call invariant.

### MEDIUM-2 — scored-parse lineage is correct on current data but does not fail closed on cross-call links

The important join at `build_analysis_data.py:93-98` correctly uses
`p.id = s.parsed_answer_id` and `a.id = p.provider_attempt_id`. However, it does not require
`p.logical_call_id = s.logical_call_id` or `a.logical_call_id = p.logical_call_id`. Those cross-row
invariants are not enforced by the schema. The canonical DB has zero such mismatches. In a
disposable corruption test, assigning the `b2 × gemini` score to another call's parse was silently
accepted; `A_selected`, `A_tokens`, and `A_latency_ms` changed while correctness stayed attached to
the original score.

**Fix.** Add the logical-call equality predicates and preflight integrity assertions. Also verify
one score per call and one output row per `(question_id, model)` before publishing (the latter is
already partly guarded at `:112-114`).

### MEDIUM-3 — the DB snapshot/hash protocol is unsafe for WAL or concurrent writers, and “read-only” creates sidecars

Both builders open `file:...?...mode=ro` (`build_analysis_data.py:70-73` and
`final_analysis.py:341-343`). The database is in WAL mode. A read-only invocation on a clean
temporary copy created `experiment.sqlite-shm` and an empty `experiment.sqlite-wal`, so it is not
filesystem-read-only and can fail on read-only media. `build_analysis_data.py` does not start one
long-lived read transaction; successive queries can observe different commits. It then hashes only
the main DB file at `:325-395` while the connection remains open, ignoring any nonempty WAL.

The canonical WAL was empty and no writer was open during this audit, so the current hashes are
coherent. The implementation is not safe for a live or merely copied WAL database.

**Fix.** Build from a frozen SQLite backup/snapshot, or hold an explicit read transaction and hash
the exact backup used. Checkpoint and verify no WAL before treating the main-file hash as a content
identifier. Use `immutable=1` only for a file known to be immutable, and URI-encode paths rather
than interpolating raw `Path` text.

### MEDIUM-4 — publication is atomic per file, not atomic as a release bundle

`build_analysis_data.py:398-417` stages files but calls `os.replace` four times. A crash leaves a
mixed generation visible; metadata-last helps later consumers detect some mismatches but does not
make the bundle atomic. `final_analysis.py:424` and `build_report_artifact.py:386` write directly to
their canonical targets and can leave truncated JSON.

**Fix.** Write a content-addressed/versioned release directory, fsync it, then atomically update one
manifest/pointer. At minimum use same-directory temporary files plus `os.replace` for the final and
report artifacts, and make every consumer verify the manifest before reading any member.

### MEDIUM-5 — flattened workbook bytes are not reproducible, despite being byte-hashed downstream

`flatten.py:342-350` creates and saves fresh XLSX ZIP containers. Two temporary runs three seconds
apart produced logically identical A/B sheets and identical `flatten_report.json`, but different
SHA-256 values for both workbooks. The current canonical logical sheets also matched both rebuilds.
`build_analysis_data.py:325-395` nevertheless treats the raw XLSX byte hashes as provenance inputs,
so running the documented flattening step changes `dataset_meta.json` even when every import cell is
identical. `flatten.py:257-295` also writes A, then B, then the report directly without staging.

**Fix.** Publish normalized import-content hashes (canonical JSON/CSV over the required columns) as
the semantic identifiers. If byte-identical XLSX is required, canonicalize workbook properties and
ZIP timestamps/order. Stage and validate all three outputs before replacing any canonical file.

### MEDIUM-6 — the report claims Holm-adjusted cluster sign-flips, but the result bundle stores only Holm-adjusted McNemar tests

`cross_arm_analysis()` collects McNemar p-values at `final_analysis.py:307-315` and stores their
Holm adjustment at `:325-327`. It computes cluster sign-flips but never Holm-adjusts them. Yet
`REPORT.md:205-210` says the two positive model results survive Holm correction of the four
**cluster sign-flip** tests. Independent correction confirms the prose conclusion, with adjusted
p-values gemma `0.0279942`, glm `0.0322266`, gemini `0.5`, qwen `1.0`; the stored McNemar-Holm
values are instead `0.0133076`, `0.0190430`, `0.5`, `1.0`.

**Fix.** Add a separately named `holm_adjusted_exact_cluster_signflip_p` field derived from
`signflips`; keep the existing McNemar field explicitly labelled. Have the report builder consume
the cluster field for this claim.

### MEDIUM-7 — artifact QA completeness is optional while the artifact declares ten-workflow QA and `ready`

If `qa_summary.json` is absent, `build_report_artifact.py:54` silently uses an empty list. It still
describes “ten-workflow QA” at `:145,356` and emits `status: ready` at `:367`. At the audited
snapshot neither `qa_summary.json` nor `QA_SUMMARY.md` existed, and the checked artifact contained
zero QA rows while making that claim (`report_artifact.json:7,462-465`).

**Fix.** Make the expected QA summary a required, schema-validated input; require the declared
workflow count and unique IDs before `ready`. Otherwise emit an explicit incomplete status and do
not advertise completed QA.

## Low-severity hardening findings

### LOW-1 — the flatten report calls two semantic no-ops “retained,” but neither is in B

`flatten.py:278` counts `b_note == "negate_equivalent_noop"` across all 500 dispositions, and
`:303` prints “B semantic no-ops retained.” The two counted items are `b23` and `b458`; `b23` is an
`ITEM_DEFECT` and `b458` is a `B_ONLY_DEFECT`, so both are absent from B. The numeric field is a
source-level detector count, not a retained-B count.

**Fix.** Count `b_note` only among `rows_b`, or rename it to
`source_items_detected_semantic_noop` and report retained/dropped counts separately.

### LOW-2 — critical flatten validation disappears under `python -O`

Dataset size, context resolution, schema, answer-key consistency, option uniqueness, and type
checks use `assert` (`flatten.py:154,168,307-337`). Python removes them under optimization.
`read_table()` also silently overwrites duplicate headers/items through dictionary construction
(`:116-124,148-151`), and `build_context_index()` does not reject duplicate/missing part numbers or
inconsistent totals (`:127-143`). Current source data pass all these checks.

**Fix.** Replace data-contract asserts with explicit exceptions and validate header uniqueness,
item-key-set equality, and context part completeness before producing any output.

### LOW-3 — the numerical environment is not pinned or recorded

`final_analysis.py:21` depends on NumPy, while `pyproject.toml` declares unbounded `numpy` in the
analysis extra. The audited byte-identical result used Python 3.13.5, NumPy 2.4.4, SQLite 3.53.0,
and openpyxl 3.1.5, but these versions are absent from the result manifest. The script's
“version-pinned” description therefore pins data/version labels, not the execution environment.

**Fix.** Add a lockfile and record Python, NumPy, SQLite, and openpyxl versions plus bootstrap seed,
replicate count, and quantile method in the manifest.

## Checks that passed

1. `PRAGMA integrity_check` returned `ok`; `PRAGMA foreign_key_check` returned no rows.
2. Canonical score lineage has zero score→parse or parse→attempt logical-call mismatches, zero
   score rows without an attempt, zero non-binary `strict_correct`, and zero score/question key
   mismatches. There is currently at most one score per logical call.
3. A clean temporary run of `build_analysis_data.py` reproduced `paired_clean.json`,
   `cross_arm_A.json`, `gift_coverage.json`, and `dataset_meta.json` byte-for-byte. Repeating with
   `PRAGMA reverse_unordered_selects=ON` also reproduced all four files byte-for-byte.
4. The canonical flat A/B workbooks contain 474/423 rows and match the DB on all imported core
   fields. A temporary `flatten.py` rebuild produced the same logical cell values and the same
   `flatten_report.json`.
5. Flattening arithmetic reconciles: `500 − 17 three-option − 9 source defects = 474` (no overlap),
   then `474 − 35 automated B exclusions − 16 B-only adjudications = 423` (no overlap).
6. Analysis arithmetic reconciles: `423 − 19 defects − 91 position-a + 5 overlap = 318` items;
   the sole missing `b320 × glm` cell gives `318×4−1 = 1,271`. Cross-arm analysis has 319
   all-model-complete items before analysis defects and 306 / 1,224 cells after them.
7. A clean temporary `final_analysis.py` run reproduced `final_analysis_results.json`
   byte-for-byte.
8. `exact_mcnemar()` matched SciPy's exact two-sided binomial test over a 31×31 discordance grid
   (maximum floating difference `5.55e-16`). A tie-containing Holm example matched its closed-form
   expected adjustments. `signflip_exact()` matched brute-force enumeration, and
   `cluster_bootstrap()` matched explicit repeated-cluster row expansion exactly in a seeded test.
9. The bootstrap correctly preserves repeated cluster multiplicity. Current primary and cross-arm
   point estimates, CIs, sign-flip p-values, Kish count, and leave-one-out ranges match the JSON and
   current `REPORT.md`.
10. Fixed local paths are scoped to the experiment directory; no shell execution, dynamic SQL from
    external input, credential export, or obvious path traversal was found. The SQLite URI/WAL and
    atomic-publication portability issues are reported above.

## Recommended fix order

1. Repair stable report anchoring, rebuild `report_artifact.json`, and enforce clean-build equality.
2. Replace the artifact's invented source queries with hashed, replayable provenance and require a
   complete QA summary before `ready`.
3. Enforce the metadata-pinned DB hash and replace copied QA constants with verified computed
   artifacts.
4. Correct the run-status grain, add cross-call lineage assertions, and materialize Holm-adjusted
   cluster sign-flips.
5. Freeze a SQLite snapshot and publish all outputs atomically.
6. Add normalized workbook hashes, explicit flatten validations, and an environment lock/manifest.

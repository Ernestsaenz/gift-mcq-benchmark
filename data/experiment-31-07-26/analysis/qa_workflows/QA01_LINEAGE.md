# QA01 — source lineage and deterministic rebuild

**Audit date:** 2026-07-31 (Europe/Madrid)  
**Scope:** `data/experiment-31-07-26`, especially experiment/dataset identity, source files, database state, checksums, `RUN_STATUS.md`, `REPORT.md`, and `analysis/build_analysis_data.py`.  
**Mutation policy:** canonical files were not executed in place or edited. Rebuilds were redirected to Python temporary directories. This file is the only workspace artifact created by QA01.

## Verdict: FAIL

The current database-to-export lineage is recoverable, and the current `paired_clean.json`, `cross_arm_A.json`, and `gift_coverage.json` reproduce byte-for-byte under the current default SQLite query plan. However, the report is labeled **v2** while several inferential results and the entire robustness section come from **v1** (`325 items / 1299 cells / 208 clusters`). In addition, the advertised deterministic builder does not regenerate canonical `dataset_meta.json` and uses an unordered retry join that can silently change selected-answer, latency, and token fields. Run-completion claims are also internally inconsistent.

Do not deliver `REPORT.md` as a fully v2 report until the high-severity findings below are corrected and the v2 statistics are regenerated and independently checked.

## Severity-ranked discrepancies

### HIGH-1 — `REPORT.md` is labeled v2 but contains v1 inference

Evidence:

- `REPORT.md:3` declares export version v2, and `REPORT.md:25` gives the v2 analysis set: **318 items / 1271 cells / 201 clusters**.
- `REPORT.md:73` nevertheless calls **325 / 1299** “both (reported),” and `REPORT.md:78` reports **208** leave-one-cluster-out and **325** leave-one-item-out refits. Those are the superseded v1 counts recorded in `dataset_meta.json:74-80` and `RUN_STATUS.md:94-98`.
- `REPORT.md:42` says its confidence intervals are bootstraps over **201 clusters**, but `prim_cluster_bootstrap_results.json` records `n_cells=1299`, `n_items=325`, `n_clusters=208`; its v1 intervals exactly match the report.
- `prim_cluster_bootstrap_results.json`, `prim_permutation_results.json`, and `prim_mixed_main_log.json` were written at 10:20–10:21 local time. The v2 exports were written at 10:47. They cannot be v2 analyses.
- The headline percentages were refreshed to v2, but most exact McNemar p-values were copied from v1:

| model | report p | direct v2 exact p | status |
|---|---:|---:|---|
| gemini | `3.5e-06` | `3.4654513001441956e-06` | unchanged because removed items were concordant for this model |
| gemma | `6.1e-11` | `1.6606697571045604e-10` | v1 value in report |
| qwen | `5.3e-09` | `1.4114668409813958e-08` | v1 value in report |
| glm | `1.0e-12` | `1.8077410513282367e-12` | v1 value in report |
| pooled naive | report text `6.3e-35` | `8.679921143805341e-34` | v1 value in report |

The cluster-corrected pooled p (`4.5e-16`), bootstrap intervals, ORs, model-interaction tests, specification curve, exclusion grid, and influence analysis have not been demonstrated on the v2 set. Their qualitative conclusion may survive, but that is not a substitute for a v2 recomputation.

**Required correction:** regenerate every statistic used by the report from the checksum-pinned v2 input, write versioned result files, and make each report table cite its input hash and result artifact. Do not relabel v1 results as v2.

### HIGH-2 — the scored-attempt join is not the join documented by the builder

`build_analysis_data.py:17-19` says the builder follows:

```text
scores -> parsed_answers.provider_attempt_id -> provider_attempts
```

But `build_analysis_data.py:89-94` actually does this:

```sql
FROM scores s
JOIN logical_calls lc ON lc.id = s.logical_call_id
JOIN parsed_answers p ON p.logical_call_id = lc.id
JOIN provider_attempts a ON a.id = p.provider_attempt_id
```

It does **not** join `p.id = s.parsed_answer_id`. The query returns every parse/retry for a scored logical call, has no `ORDER BY`, and then overwrites a dictionary entry at `build_analysis_data.py:99-109`. There are 21 scored OpenRouter-A calls and 38 OpenRouter-B calls with multiple parsed attempts.

The current default-plan export happens to retain the scored parse: comparison with the authoritative `scores.parsed_answer_id` found **0 field mismatches** in 1,691 paired rows and **0** in 1,276 cross-arm rows. This is accidental query-plan behavior, not a SQL guarantee.

Enabling SQLite’s diagnostic `PRAGMA reverse_unordered_selects=ON` against the same immutable database changes:

- **54 records** in `paired_clean.json`; changed fields include `A/B_selected`, `A/B_latency_ms`, and `A/B_tokens`.
- **8 records** in `cross_arm_A.json`; changed fields include `or_selected`, `or_latency_ms`, and `or_tokens`.
- Correctness fields remain tied to `scores`, so primary accuracy counts do not change, but selection/error-destination, latency, token, and potentially backend analyses can silently change.

**Required correction:** replace the parse join with `JOIN parsed_answers p ON p.id = s.parsed_answer_id`; retain `JOIN provider_attempts a ON a.id = p.provider_attempt_id`; assert exactly one score per logical call and one output row per `(question_id, model)`.

### HIGH-3 — the advertised rebuild does not reproduce `dataset_meta.json`

A clean temporary-directory invocation of `build_analysis_data.main()` against the canonical read-only DB produced:

| artifact | result |
|---|---|
| `paired_clean.json` | exact byte match; MD5 `0b25b95d082cf00900443d262c84427e` |
| `cross_arm_A.json` | exact byte match; MD5 `39148f1f6ae007c0ec549e8e5d5f3d79` |
| `gift_coverage.json` | exact byte match; MD5 `09c54f535cf7c7171b99be1232866009` |
| `dataset_meta.json` | **differs**; regenerated MD5 `3155f93d8183d82a2dd2afb773afb1b8`, canonical MD5 `362f5fe865822ec5d97db4235b5fa773` |

The builder omits all canonical fields added after the first write: `export_version`, `export_note`, `superseded_v1_counts`, three measurement caveats, and `file_md5`. File timestamps corroborate the manual second phase: the core exports were written at 10:47:46, while `dataset_meta.json` was modified at 10:56:20.

Running the documented reproduction command in place would therefore silently erase the version and integrity metadata. The builder also overwrites canonical files in place, one at a time, without atomic staging, an input manifest, or a refusal guard.

**Required correction:** make the builder produce the full metadata object, calculate hashes after staging the three data files, include SHA-256 for inputs and outputs, and atomically publish a versioned bundle only after validation succeeds.

### MEDIUM-1 — completion reporting conflates completed/scored cells with progress reached

Database counts are:

| experiment | numeric id | dataset | logical calls | scored calls | correct status |
|---|---:|---|---:|---:|---|
| `expA_or_310726` | 6 | dataset 1 / `balanced_a_310726` | 1896 | **1895** | one unrecovered cell |
| `expB_or_310726` | 7 | dataset 2 / `balanced_b_310726` | 1692 | **1692** | complete |
| `expA_gift_310726` | 8 | dataset 1 / `balanced_a_310726` | 1566 | **1384** | partial |
| `expB_gift_310726` | 9 | dataset 2 / `balanced_b_310726` | 0 | **0** | never started |

Consequences:

- `RUN_STATUS.md:23` says OpenRouter A completed 1896 and is complete, while `RUN_STATUS.md:69` and `REPORT.md:188-189` correctly identify the unrecovered `b320 × glm-5.2` cell. The scored result is 1895/1896.
- `REPORT.md:3` therefore should not call all of OpenRouter “complete.” OpenRouter B is complete; A is missing one cell.
- `1384 / 1896 = 73.0%`, not 83%. The **82.6%** figure is `1566 logical-call records / 1896 planned`, which includes 182 attempted-but-unscored calls. `REPORT.md:118` and `REPORT.md:178` incorrectly say “completed 83%.” Use “the runner reached/created 82.6% of positions; 1384/1896 (73.0%) produced scores.”

### MEDIUM-2 — `RUN_STATUS.md` retains unmarked v1 prose after declaring v2 canonical

- `RUN_STATUS.md:46` says 311 cross-arm items after 14 defects.
- `RUN_STATUS.md:62` says every cross-arm comparison uses 311 items.
- `RUN_STATUS.md:79-81` describes 14 analysis defects.
- The same file later says v2 has **306 cross-arm items** after **22 defects** (`RUN_STATUS.md:89-98`).

The later table identifies the old numbers, but the earlier operational assertions are still written in the present tense. This is exactly the stale-version mixing the version note warns against.

**Required correction:** either remove/superscript the v1 prose as historical or reconcile every present-tense count to v2.

### MEDIUM-3 — experiment artifacts have no Git or complete hash provenance

The nested repository is at commit:

```text
bcf362a420cd6c7a5b7a6c3772e5d2d16c4505d8
```

The entire `data/experiment-31-07-26/` directory is untracked. Therefore Git does not preserve the source workbook, flattening code, run database, builder, exports, or report. The published `data/medrag_eval.sqlite` is tracked and clean: its worktree and HEAD blob are both `bb7e5543d1c4f117b298902158988b52167008b7`, and its current MD5 matches the reported `c6eb43ede71c1c61ffa87f96e5e070f7`.

`dataset_meta.json` records only the basename `experiment.sqlite`, not a hash. It also omits hashes for the source workbook, flattened workbooks, `flatten.py`, `flatten_report.json`, the builder, and itself. The run DB is the actual analytical source; the hash of a separate published DB cannot authenticate it.

Current audit snapshot hashes (not previously pinned by the canonical metadata):

| file | SHA-256 |
|---|---|
| source workbook | `807e83ee0bdaf47a0443b60219764ddf2ee259ac1a683839236ec067da3ca1e5` |
| `balanced-flat-A.xlsx` | `3aca1a61fd3e641c0a698a500194f342cf61cb13cff3e271bf8e5479453e2fc5` |
| `balanced-flat-B.xlsx` | `705a651b372a2d0d027f4028cd928c473c5a441445d9c9f4f35b2c3dd0869e84` |
| `flatten.py` | `f8ffe98088a5e654eaab148f95c3def528021c488c560527d371a7bcf66f0702` |
| `flatten_report.json` | `4ad30406c24126948800ab12e026c47b8e262d64b54c8dc77dbe3690763caeea` |
| `experiment.sqlite` | `dec53a3d8ed452676672820a758b4571d061c3fe994c45981095d30216744748` |
| `build_analysis_data.py` | `ced6b200d1b02861ca1e45ee0b47f86c94aef78a9eeb9c1d6d5fa3a48ea50d8a` |
| `paired_clean.json` | `76b9059cd67a1024cde1655dd3f32083bbfbbb40609728dc65173b25b8835187` |
| `cross_arm_A.json` | `987c632976260d4614056afcc9210fcd4902d322fcfe28b480ebc2e6216c8120` |
| `gift_coverage.json` | `3291caae151082f7be97c7a256e81e63da74052c5ce1b0d5b636e21dbbc942c9` |
| `dataset_meta.json` | `8bb9a01e4375ed9ffcf693f52d2a888cf94e8248a149eda8eb3da308993ae3a8` |

**Required correction:** commit or archive a manifest-addressed release bundle. At minimum, pin the database, scripts, inputs, exports, result artifacts, and report with SHA-256 in a manifest outside the generated files.

### LOW-1 — flattening documentation is stale and its expected-count assertion is tautological

`flatten.py:3-4` says it emits 483 A items and 448 B items, while the current code and outputs contain 474 and 423. The code calls `validate(rows_a, "A", expect=len(rows_a))` and similarly for B, so it does not enforce a predetermined expected count.

A temporary rebuild did validate 474/423 and reproduced all logical workbook cells; `flatten_report.json` matched byte-for-byte. The XLSX ZIP bytes differed because workbook serialization is not byte-deterministic, so logical normalized hashes are preferable:

| dataset | normalized import SHA-256 | rows |
|---|---|---:|
| A | `cf1cec67297a3cf2c58c4e74a73aa337265bf5afa234e36f5bdcbb8862f0f75b` | 474 |
| B | `ce748943921e83182b8cd137249f83eb078aeddea18b2b32d9918a906cd7e94f` | 423 |

### LOW-2 — configuration metadata is hard-coded rather than validated

The builder writes `runs_per_cell=1`, `temperature=0`, and `prompt_version=mcq_es_v4` as constants. Current DB evidence supports them: all reported logical calls have `run_index=1`; all attempts have temperature 0; all experiment/logical-call/attempt prompt versions agree on `mcq_es_v4`; and there are four reported models. A future DB replacement could nevertheless produce metadata that looks valid while describing different data.

**Required correction:** query and assert these values from the input DB; fail closed on more than one value or on an unexpected model/provider/dataset mapping.

## Checks that passed

1. `PRAGMA integrity_check` returned `ok`; `PRAGMA foreign_key_check` returned no rows.
2. The database is in WAL mode, the WAL file was 0 bytes, and `lsof` showed no active writer at audit time.
3. Dataset identity is correct:

   - numeric id 1: `balanced_a_310726`, 474 questions, source path `data/experiment-31-07-26/balanced-flat-A.xlsx`;
   - numeric id 2: `balanced_b_310726`, 423 questions, source path `data/experiment-31-07-26/balanced-flat-B.xlsx`.

4. All 13 imported question fields in both workbooks match their database rows exactly: 474/474 A and 423/423 B, with zero field differences.
5. The source-workbook MD5 is currently `521459bc33b6285b140232a5c0516eaf`, matching `RUN_STATUS.md` and `REPORT.md`. This confirms the current file, but cannot prove the historical phrase “never modified.”
6. Experiment names map to the intended numeric dataset IDs and providers. Reported runs use exactly the four stated models, run index 1, temperature 0, and prompt `mcq_es_v4`.
7. `expB_gift_310726` exists as experiment id 9 on dataset 2 but has zero logical calls, supporting “never started.”
8. `gift_coverage.json` contains 319 all-model completed items. `cross_arm_A.json` contains 1,276 rows before analysis exclusions and 1,224 included rows / 306 items / 178 clusters after v2 exclusions.
9. The three data-export MD5 values currently match `dataset_meta.json:file_md5` exactly.

## Exact commands and evidence

All commands below were run from `/Users/ernestsaenz/Programming/GIFT-abstract-dossier` unless an explicit `cd tier1_mcq` appears.

### Git identity and tracking

```bash
cd tier1_mcq
git status --short -- data/experiment-31-07-26 data/medrag_eval.sqlite
git rev-parse HEAD
git hash-object data/medrag_eval.sqlite
git rev-parse HEAD:data/medrag_eval.sqlite
git diff --quiet -- data/medrag_eval.sqlite
```

Key output:

```text
?? data/experiment-31-07-26/
bcf362a420cd6c7a5b7a6c3772e5d2d16c4505d8
bb7e5543d1c4f117b298902158988b52167008b7
bb7e5543d1c4f117b298902158988b52167008b7
git diff exit 0
```

### Database integrity, identities, and counts

```bash
DB=tier1_mcq/data/experiment-31-07-26/experiment.sqlite
sqlite3 -readonly "$DB" 'PRAGMA integrity_check; PRAGMA foreign_key_check;'
sqlite3 -readonly -header -column "$DB" \
  'SELECT e.id,e.name,e.dataset_id,d.name,e.prompt_version,e.config_json,e.created_at
   FROM experiments e JOIN datasets d ON d.id=e.dataset_id ORDER BY e.id;'
sqlite3 -readonly -header -column "$DB" \
  'SELECT d.id,d.name,d.source_xlsx_path,d.row_count,COUNT(q.id) questions
   FROM datasets d LEFT JOIN questions q ON q.dataset_id=d.id
   GROUP BY d.id,d.name,d.source_xlsx_path,d.row_count ORDER BY d.id;'
```

Key output:

```text
integrity_check = ok
foreign_key_check = no rows
id 5 smoke_gift_310726 dataset 1
id 6 expA_or_310726   dataset 1
id 7 expB_or_310726   dataset 2
id 8 expA_gift_310726 dataset 1
id 9 expB_gift_310726 dataset 2
dataset 1 balanced_a_310726 row_count/questions 474/474
dataset 2 balanced_b_310726 row_count/questions 423/423
```

The scored/logical counts were obtained with separate grouped CTEs to avoid retry-join multiplication:

```sql
WITH lc AS (
  SELECT e.id,e.name,COUNT(l.id) logical_calls
  FROM experiments e LEFT JOIN logical_calls l ON l.experiment_id=e.id
  GROUP BY e.id,e.name
), sc AS (
  SELECT e.id,COUNT(s.id) scores,COUNT(DISTINCT s.logical_call_id) scored_calls
  FROM experiments e LEFT JOIN logical_calls l ON l.experiment_id=e.id
  LEFT JOIN scores s ON s.logical_call_id=l.id GROUP BY e.id
)
SELECT lc.id,lc.name,lc.logical_calls,sc.scores,sc.scored_calls
FROM lc JOIN sc USING(id) ORDER BY lc.id;
```

### Hash verification

```bash
md5 tier1_mcq/data/experiment-31-07-26/balanced-clinical-questionnaire-500-no-image.xlsx
md5 tier1_mcq/data/medrag_eval.sqlite
md5 tier1_mcq/data/experiment-31-07-26/analysis/{paired_clean.json,cross_arm_A.json,gift_coverage.json,dataset_meta.json}
shasum -a 256 tier1_mcq/data/experiment-31-07-26/{balanced-clinical-questionnaire-500-no-image.xlsx,balanced-flat-A.xlsx,balanced-flat-B.xlsx,experiment.sqlite}
shasum -a 256 tier1_mcq/data/experiment-31-07-26/analysis/{build_analysis_data.py,paired_clean.json,cross_arm_A.json,gift_coverage.json,dataset_meta.json}
```

### Safe rebuild test

This imports the builder, redirects `HERE` to a disposable temporary directory, keeps `DB` on the canonical read-only file, and compares bytes. The temporary directory is automatically removed.

```bash
python - <<'PY'
import difflib, hashlib, importlib.util, pathlib, tempfile
src = pathlib.Path('tier1_mcq/data/experiment-31-07-26/analysis/build_analysis_data.py').resolve()
canon = src.parent
spec = importlib.util.spec_from_file_location('qa_build', src)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
with tempfile.TemporaryDirectory(prefix='gift-qa01-') as td:
    m.HERE = pathlib.Path(td)
    m.DB = src.parent.parent / 'experiment.sqlite'
    m.main()
    for name in ['paired_clean.json','cross_arm_A.json','gift_coverage.json','dataset_meta.json']:
        old = (canon/name).read_bytes()
        new = (m.HERE/name).read_bytes()
        print(name, hashlib.md5(new).hexdigest(), 'EXACT_MATCH' if old == new else 'DIFFERS')
PY
```

Output:

```text
paired_clean.json 0b25b95d082cf00900443d262c84427e EXACT_MATCH
cross_arm_A.json 39148f1f6ae007c0ec549e8e5d5f3d79 EXACT_MATCH
gift_coverage.json 09c54f535cf7c7171b99be1232866009 EXACT_MATCH
dataset_meta.json 3155f93d8183d82a2dd2afb773afb1b8 DIFFERS
```

### Direct v2 exact paired test

```bash
python - <<'PY'
import json, math
from collections import defaultdict
rows = [r for r in json.load(open('tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json'))
        if r['analysis_include']]
by = defaultdict(list)
for r in rows: by[r['model']].append(r)
by['POOLED'] = rows
for model, rs in sorted(by.items()):
    b = sum(r['A_correct'] == 1 and r['B_correct'] == 0 for r in rs)
    c = sum(r['A_correct'] == 0 and r['B_correct'] == 1 for r in rs)
    d, k = b + c, min(b, c)
    p = min(1, 2 * sum(math.comb(d, i) for i in range(k + 1)) / 2**d)
    print(model, len(rs), b, c, p)
PY
```

Output:

```text
POOLED                    1271 242 45 8.679921143805341e-34
google/gemini-3.6-flash    318  31  4 3.4654513001441956e-06
google/gemma-4-26b-a4b-it  318  80 18 1.6606697571045604e-10
qwen/qwen3.6-35b-a3b       318  65 15 1.4114668409813958e-08
z-ai/glm-5.2               317  66  8 1.8077410513282367e-12
```

## Release gate

QA01 can move from **FAIL** to **PASS** when all of the following are true:

1. The scored-attempt join uses `p.id = s.parsed_answer_id` and has cardinality assertions.
2. A clean rebuild reproduces all four canonical outputs, including complete version/hash metadata.
3. The run-status language distinguishes scored completion from attempted/reached progress and removes v1 present-tense counts.
4. Every statistic in `REPORT.md` is regenerated from the v2 SHA-256-pinned input; no v1 artifact is presented as v2.
5. A release manifest pins the source workbook, flattened logical content, run DB, scripts, exports, inferential result files, and final report.

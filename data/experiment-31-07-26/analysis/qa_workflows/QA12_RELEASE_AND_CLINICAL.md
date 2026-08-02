# QA12 — release render, clinical readability, and folder-preservation audit

**Reviewer role:** independent adversarial release/render and clinician-readability QA  
**Files audited:** `REPORT.md`, `REPORT.html`, `report_artifact.json`,
`report_source.sqlite`, `RELEASE_MANIFEST.json`, and the complete experiment directory  
**Browser:** local `file://` delivery in headless Chromium at 1440×1000 and 390×844  
**Current verdict:** **PASS**

## Bottom line

The requested reader flow is now correct: Experiment A appears first, Experiment B second, and
the paired A-versus-B comparison third. Each section names its corresponding cluster-aware test,
shows a chart and native tables, and places a physician explanation below the statistical
evidence. The clinician blocks consistently describe examination-key agreement rather than
patient-level diagnostic performance and state the principal construct limitations.

Two display defects found in the first candidate were repaired and independently rechecked:

1. The first Experiment-A pairwise p-values were initially rendered as `0` and `0.01` instead of
   approximately 0.003319 and 0.006638. The rebuilt table now treats displayed p-values as labelled
   text and shows `p = 0.003319` and `p = 0.006638`; no exact or adjusted p-value is displayed as
   zero.
2. Recommendation 1 initially exposed literal Markdown `**...**`. The rebuilt reader contains no
   literal double-asterisk emphasis, hash heading, table-rule, or code-fence residue.

Release integration was then rechecked on a rebuilt candidate containing all twelve QA rows. The
source database contained twelve QA records, the HTML displayed twelve, and every one of the 25
files pinned by the provisional release manifest matched its recorded SHA-256. This QA record is
now final; regenerating the manifest once more after changing its QA12 summary row from PENDING to
PASS is deterministic release bookkeeping, not an unresolved content or rendering defect.

## 1. Requested order and placement

The enhanced reader's section order is:

1. `2. Experiment A: comparison among models`
2. `3. Experiment B: comparison among models`
3. `4. Paired comparison between Experiments A and B`

At desktop width, the final statistical table in each section ends before its clinician block:

| section | final table vertical extent | clinician heading | ordering |
|---|---:|---:|---|
| Experiment A | 3452–3814 px | 3854 px | pass |
| Experiment B | 5019–5381 px | 5421 px | pass |
| paired A/B | 6522–6801 px | 6841 px | pass |

The same order is retained at 390 px. The three clinician headings occur after their respective
tables at document positions 5511, 7477, and 9561 px. No explanation is detached above the result
it explains.

## 2. Statistical-test visibility and p-value rendering

The report visibly supplies the corresponding method in each section:

- Within A: cluster-robust Wald `F(3, 199) = 22.75`, with whole-cluster bootstrap intervals,
  exact clinical-cluster sign flips, and Holm correction across six pairs.
- Within B: cluster-robust Wald `F(3, 199) = 31.84`, with the same cluster-aware pairwise family.
- Paired A/B: exact whole-clinical-cluster sign flips with Holm correction across four model
  endpoints; cluster-robust logistic and conditional-logistic summaries are explicitly secondary.

The native tables render all six A contrasts, all six B contrasts, and five A/B rows. The repaired
Experiment-A values include:

- gemini minus glm: exact `p = 0.003319`, Holm `p = 0.006638`;
- gemini minus qwen: exact `p = 5.40 × 10⁻⁸`, Holm `p = 2.16 × 10⁻⁷`; and
- glm minus qwen: exact and Holm `p = 0.0193`.

No primary table contains a bare zero p-value. Normality is correctly described as inapplicable to
the binary correctness endpoint and the discrete paired change.

## 3. Clinical-language audit

### Experiment A

The explanation converts accuracy into key-matched answers per 100 and immediately states that
these are examination-key results, not diagnostic sensitivity, patient benefit, or bedside
safety. It also declares one run per cell and the need for independent clinical verification.

### Experiment B

The explanation makes clear that B is an artificial, position-dependent meta-answer task. It
does not generalize the result to ordinary none-of-the-above questions or bedside diagnostic
accuracy, and it correctly avoids ranking glm over qwen.

### Paired A versus B

The explanation translates the observed losses into fewer key-matched answers per 100 while
stating that the contrast applies to the complete B configuration. It explicitly rejects a
memorisation inference because content, semantics, genre, repetition, and decision structure all
change together, and it states that patient outcomes were not measured.

I found no treatment recommendation, diagnostic claim, patient-safety claim, or unsupported
clinical generalization in the three physician blocks.

## 4. Desktop and mobile rendering

| check | 1440×1000 | 390×844 |
|---|---:|---:|
| page-level horizontal overflow | 0 px | 0 px |
| native charts with non-zero dimensions | 5/5 | 5/5 |
| native result tables | 11/11 | 11/11 |
| table overflow outside a scroll container | none | none |
| console errors | none | none |
| failed/external network requests | none | none |
| raw Markdown residue | none | none |

The local network log contains only the `file://.../REPORT.html` load. The enhanced reader replaces
the fallback after initialization; the fallback is not simultaneously displayed, so the reader
does not duplicate report text or tables.

## 5. Source drawer and SQL replay

I opened the menu for `Experiment A model accuracy`, selected **View data source**, and verified:

- the Overview, Data preview, and SQL query tabs are present;
- the SQL tab displays `SELECT * FROM condition_a_models` and provides **Copy query**;
- Data preview displays four rows and five columns; and
- the first row is gemini, `310 / 317`, `97.8%`, with CI `[95.93%, 99.26%]`.

Independent replay against `report_source.sqlite` returned four rows, `SUM(correct) = 1136`, and
`SUM(n) = 1268`. SQLite `PRAGMA integrity_check` returned `ok`. The five reader-facing source
queries for `condition_a_models`, `condition_a_pairwise`, `condition_b_models`,
`condition_b_pairwise`, and `primary_results` are all embedded in `report_artifact.json` and return
4, 6, 4, 6, and 5 rows respectively.

## 6. Non-destructive folder organization

The organization pass is additive. `INVENTORY.md`, `analysis/README.md`, and
`analysis/EXPLORATORY_LEDGER.md` distinguish inputs, run evidence, canonical outputs, QA records,
and historical exploratory files without moving dependency-sensitive paths.

The folder-organization workflow recorded a pre-index snapshot of **628 files and 218,218,596
bytes**. Before writing this QA record, the directory contained **634 files and 219,025,136 bytes**.
No source workbook, database or sidecar, script, log, canonical result, exploratory file, or prior
QA path identified by that workflow is absent. Git cannot provide a deletion baseline because the
experiment directory is untracked as one unit, so this conclusion rests on the workflow snapshot,
current path inventory, and explicit canonical-path checks rather than an unsupported Git claim.

## 7. Release-integration check

The integrated candidate passed the following checks before this verdict was finalized:

- `qa_summary.json`, the QA source table, and the rendered QA table each contained twelve unique
  workflows, including QA11 and QA12;
- `REPORT.md` named the two new independent audits and the rendered report retained the requested
  A, B, then A/B order;
- the provisional manifest declared twelve workflows and its 25 pinned paths all matched their
  recorded SHA-256 values; and
- a fresh browser load retained zero horizontal overflow, five non-empty charts, no bare-zero
  p-values, no raw Markdown, a functioning source dialog, no console errors, and only the local
  `file://` network request.

Changing the QA12 summary status from PENDING to PASS necessarily changes the summary, report,
and manifest hashes. The release owner should therefore regenerate the report and manifest once
after this file is complete, then perform a read-only 25-file hash check. QA12 does not require any
further narrative, statistical, clinical, or layout change.

## Final verdict

**PASS.** The rendered report, source drawer, query replay, responsive layout, physician
translations, twelve-workflow integration, and additive folder organization all satisfy this
workflow. The two defects found adversarially were corrected and did not recur.

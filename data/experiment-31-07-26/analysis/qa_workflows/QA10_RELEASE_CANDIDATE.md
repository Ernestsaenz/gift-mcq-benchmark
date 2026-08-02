# QA10 — release-candidate claim and render audit

**Audit date:** 2026-07-31 (Europe/Madrid)  
**Scope:** final Markdown, primary and audited result bundles, v3 metadata, materialized report
source, portable artifact, portable HTML, and QA01–QA09. Canonical files were inspected read-only;
this audit record is the only file created by QA10.

## Final verdict after rebuild: PASS

The rebuilt release candidate resolves the rendering and table-content blockers. QA10 approves it
for delivery, subject only to the administrative finalization step of changing the QA10 summary
row from `PENDING` to `PASS` and rebuilding the package once so the delivered QA table reflects
this verdict.

Focused recheck evidence:

- Zero visible raw pipe-delimited paragraphs and zero literal Markdown fences at both 1440×1000
  and 390×844.
- The six report tables render once as native tables: dataset construction (2 rows), analysis
  exclusions (3), primary results (5), sensitivity (4), cross-pipeline results (5), and execution
  status (4). The QA table has 10 rows.
- The primary and cross-pipeline tables again include their cell-weighted pooled rows. The
  cross-pipeline chart remains correctly model-only through its separate four-row chart dataset.
- All five primary McNemar values display as nonnumeric Unicode scientific strings, including
  `3.47 × 10⁻⁶` and pooled `8.68 × 10⁻³⁴`; none is rounded to zero.
- All three reproduction commands render as inline-code list items.
- The primary source drawer opens; its SQL tab shows `SELECT * FROM primary_results`; its data
  preview contains five rows, the pooled row, and the scientific p-values.
- All ten declared SQLite query datasets replayed with row/value equality, including exact binary
  float equality, and all 17 manifest source hashes matched files on disk.
- Both viewports have zero document-level horizontal overflow; wide tables remain inside scroll
  containers. Chromium logged no console errors and only one successful local `file://` network
  request.
- Required cross-pipeline chart/table content is present. No stale causal or retrieval-efficacy
  wording reappeared.

Final checked package hashes before the administrative QA-row update:

| file | SHA-256 |
|---|---|
| `REPORT.md` | `00604b1b4cbc38019f92242eed4a2be2cc3f3ca7c0b8d15a2ab9640467781f49` |
| `report_artifact.json` | `5400cb9426a1f80ed4aeec2c53798320fb227d776e5b52f4a8784aad3c0c794e` |
| `report_source.sqlite` | `70259305db5f6484e520ab231ee156bd1327b996eba5af0a6e0cb570a66c753f` |
| `REPORT.html` | `97e64effd19903653b77733fd1405787373ba09f5ecbbca0bda3efffb65c1428` |

## Initial candidate verdict (superseded): FAIL — one portable-HTML rendering blocker

The analytical release candidate passes claim-to-evidence, provenance-query, causal-language, and
responsive-overflow checks. The portable HTML is not ready to deliver because all six Markdown
tables are visibly rendered twice: first as raw pipe-delimited Markdown and then as the intended
formatted table. The reproduction code fence is also rendered as literal backticks and inline text.
This is a presentation-layer defect; it does not change any reported estimate.

### Release blocker — Markdown tables and code fences are duplicated/mis-rendered

Using `/browse` against `REPORT.html`, QA10 found six visible `<p>` nodes beginning with a literal
pipe (`| dataset ...`, `| rule ...`, `| model ...`, `| exclusions ...`, the cross-pipeline table,
and the run-status table). Each has `display:block`, `visibility:visible`, and non-zero geometry.
The page also contains the corresponding six formatted `table.rich-markdown-table` elements, so a
reader sees both copies. At 390 px the duplicated raw text materially lengthens and degrades the
report. Section 9 similarly displays the fenced command block as literal ````bash ... ```` text
instead of a preformatted block.

**Required fix:** repair the portable Markdown rendering/packaging so source Markdown tables and
fences are consumed once, rebuild `report_artifact.json` and `REPORT.html`, then rerun the desktop,
mobile, console, network, overflow, and source-drawer checks. Do not hide the raw paragraphs with a
broad CSS selector unless the same fix is verified for ordinary prose containing pipe characters.

The QA summary currently and correctly marks QA10 as `PENDING`; after this blocker is fixed and
rechecked, replace that row with the final verdict and rebuild once more.

## Evidence that passed

### Claim-to-evidence

- Direct recomputation from `paired_clean.json` reproduced the reported 318 items, 1,271 cells,
  201 clusters, every model denominator/correct count, and every A/B point estimate.
- Direct recomputation from `cross_arm_A.json` reproduced the 306 items, 1,224 cells, 178 clusters,
  and all four partial cross-pipeline point estimates.
- `final_analysis_results.json` pins and matches the current pair export, cross-pipeline export,
  v3 metadata, frozen run database, audited-secondary bundle, final-analysis code, and QA03/05/06
  source hashes.
- The report's bootstrap intervals, exact cluster sign-flip results, McNemar labels, Kish effective
  cluster count, sensitivity ranges, position interaction, cross-pipeline heterogeneity, missing-
  outcome bound, and operational denominators agree with the pinned primary or audited-secondary
  fields at the stated precision.
- Causal wording is appropriately narrow: the report distinguishes observed deployed-system
  contrasts from pure text causation, memorisation, retrieval efficacy, latency, and token effort;
  it documents GIFT B and the control arms as missing.

### Replayable report sources

All seven declared SQLite queries executed successfully against `report_source.sqlite`:

- `SELECT * FROM summary`
- `SELECT * FROM primary_accuracy`
- `SELECT * FROM primary_results`
- `SELECT * FROM sensitivity`
- `SELECT * FROM cross_arm`
- `SELECT * FROM run_status`
- `SELECT * FROM qa_results`

Every returned row and value, including the exact IEEE-754 float values, matched the corresponding
artifact snapshot. The source database SHA-256 is
`40b65e2a4f8547bd6751bdfc45bda1bdcd9f3720d2bf145f2458e8321310cc66`, matching every declared
query source. All 14 declared file/source hashes matched the files on disk. The interactive source
drawer opens, its overview is populated, the SQL tab shows the correct query, and data preview is
available.

### Artifact completeness and browser behavior

- Manifest: 21 blocks, 3 metric cards, 3 charts, and 5 data tables.
- Required primary, sensitivity, cross-pipeline, run-status, and ten-row QA datasets are present.
- Cross-pipeline chart and table are reachable from the block list; none of the required widgets is
  orphaned.
- At 1440×1000 and 390×844, the document has no page-level horizontal overflow. Wide tables are
  contained in horizontal-scroll wrappers on mobile.
- Chromium reported no console errors. The only network request was the local `file://` HTML, with
  status 200; the report made no external requests.
- No stale headline wording such as “GIFT improved,” “retrieval helps,” a pure causal claim, or the
  superseded effective-n warning was visible.

## Audited snapshot

| file | SHA-256 |
|---|---|
| `REPORT.md` | `1b04236ec9e5d8c18d2187904a5288b2ff6ed2b65e106bf9c2b18033e21258bf` |
| `final_analysis_results.json` | `63410cd734f8c6e233f6ca4315e3ae652dc4d1c75793bd93dfb9a0cb9550e963` |
| `audited_secondary_results.json` | `1554f1fa2edbbed41b5a28638c946851288b731a0cccc11e56bdf766a7ff4667` |
| `dataset_meta.json` | `74c95d88fc49640343012de73d38c6e4693fc41adde53ea6fe120721d9260fdf` |
| `report_artifact.json` | `e059c04e7ad9bb8171fe5b45735111c4bfa8c7064c69ec497ad5627172d9feb7` |
| `report_source.sqlite` | `40b65e2a4f8547bd6751bdfc45bda1bdcd9f3720d2bf145f2458e8321310cc66` |
| `REPORT.html` | `9e98e2c0c7ff32d2af3e19db8c619d67b2c934a8b0c005deb3d3176812ba9068` |

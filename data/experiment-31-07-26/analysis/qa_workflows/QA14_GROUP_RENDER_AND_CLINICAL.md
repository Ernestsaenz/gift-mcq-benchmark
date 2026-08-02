# QA14 — Group-comparison render, source, and clinical-language audit

**Reviewer:** independent adversarial QA subagent  
**Date:** 2026-07-31 (Europe/Madrid)  
**Scope:** `REPORT.html`, `REPORT.md`, `report_artifact.json`, `report_source.sqlite`,
`paired_clean.json`, and the source run database `../experiment.sqlite`  
**Final verdict:** **PASS — ready to share.** The initial stale-HTML finding was repaired, the
fully integrated 15-workflow artifact was rebuilt through the pinned `uv` environment, and the
final portable HTML passed the independent hash, source, desktop, mobile, and clinical-language
seal.

## Initial release-integrity finding — resolved

The portable HTML inspected in the initial pass had modification time `14:20:27` and SHA-256
`8534533b9abccee68f8bee7f596fda15f3077af9c9dc4efe46d515dc43f9bf28`. The current source files
were newer:

- `REPORT.md` — `14:23:20`, SHA-256
  `e2557909e40d8c55788551cb4ccaf0abdf75ee123a6018fbe72ba2cd45c7d0c1`
- `report_artifact.json` — `14:23:37`, SHA-256
  `3554cbd342eb95c9aaf26714e34a574dcdbdc2f26b8c34bdbd6b06ee05619057`
- `report_source.sqlite` — `14:23:37`, SHA-256
  `9b6ab6f5e4279177f66a796f86146bc427d740eec229c65e24f5d843b55c2383`

The current Markdown and artifact say, “These are exploratory fixed contrasts requested after the
main model analysis.” The inspected HTML did not contain that sentence. That caveat is material to
the post-hoc subgroup interpretation, so the source/HTML mismatch blocks a final release seal even
though the displayed numerical results are correct.

**Resolution:** the report was rebuilt twice as source documentation and QA rows were finalized.
The final integrated HTML contains the post-hoc caveat, the three `uv run python` reproduction
commands, and all 15 QA rows. The stale HTML is superseded.

## Final integrated release seal

The final release inspected after all repairs is pinned by:

- `REPORT.html` — SHA-256
  `a96f20bfbf25ce1037a1eaa8b7c3f81dbfe1f1f1db165a2ae1626653ed7dbd89`
- `REPORT.md` — SHA-256
  `229f96ebb0ca2d06667e49faac0c04601bfd61183fe64bc43a3da37162519cc5`
- `report_artifact.json` — SHA-256
  `6372d68c3acc1e6391e2807847d32d63e8ef6c4823dd102451f1c3825f97a986`
- `report_source.sqlite` — SHA-256
  `3dacff7b8c9c19449c239314ff6b076aca0733e45a9d53a4e25f7bd54b0e0c8d`
- `final_analysis_results.json` — SHA-256
  `d8aeb39b305d9301e84373946a4a657fdce32bf0f135488fa241928f45c8f144`
- `qa_workflows/qa_summary.json` — SHA-256
  `a8c24bc5b7de8c3152b3ab0d87c3fd7200b3e41abd99f4ca2d77f77321ad000d`

On the final HTML, document width again equalled viewport width at **1440/1440** and **390/390**.
All five group tables rendered with row counts **2, 2, 4, 2, 2**, local horizontal scrolling, no
raw Markdown, and no console or network failures. The final source drawer again passed Data preview
and SQL query checks, including both Experiment-A group rows and
`SELECT * FROM condition_a_group_contrasts`. `report_source.sqlite` retained
`PRAGMA integrity_check = ok`, contained **15 QA rows**, and matched all six group datasets in the
final artifact exactly.

## Independent source and calculation checks

### Raw SQLite lineage

The raw run database passed `PRAGMA integrity_check = ok`. I independently joined
`scores → parsed_answers → provider_attempts → logical_calls → questions → experiments`, restricted
to `expA_or_310726` and `expB_or_310726`, and compared every scored response with the canonical
317-item complete-case population.

- Expected model×item×condition cells: **2,536**
- Raw scored rows: **2,536**
- Unique raw keys: **2,536**
- Duplicate keys: **0**
- Raw-to-`paired_clean.json` correctness mismatches: **0**

The complete-case population independently reproduced **317 items, 1,268 cells per condition, and
200 clinical clusters**.

### Group point estimates

Direct sums of the raw-source-backed complete cases reproduced:

| Condition | Group | Correct / cells | Accuracy |
|---|---|---:|---:|
| A | large | 605 / 634 | 95.4259% |
| A | small | 531 / 634 | 83.7539% |
| A | open-model | 826 / 951 | 86.8559% |
| A | proprietary (gemini) | 310 / 317 | 97.7918% |
| B | large | 520 / 634 | 82.0189% |
| B | small | 419 / 634 | 66.0883% |
| B | open-model | 656 / 951 | 68.9800% |
| B | proprietary (gemini) | 283 / 317 | 89.2744% |

These produce the reported fixed-panel contrasts: A large−small **+11.67 pp**, A open−gemini
**−10.94 pp**, B large−small **+15.93 pp**, and B open−gemini **−20.29 pp**. Group-specific B−A
changes are **−13.41 pp** (large), **−17.67 pp** (small), **−17.88 pp** (open-model), and
**−8.52 pp** (gemini).

### Exact inference replay

I reimplemented the exact two-sided clinical-cluster sign-flip distribution independently with
integer-scaled cluster contributions, rather than calling the report builder. The six primary raw
p-values, Holm adjustments, four grouped declines, and six secondary triangulation tests matched
`final_analysis_results.json` exactly to machine precision. Key interaction results reproduced:

- large-change minus small-change: **+4.2587 pp**, exact p = **0.0924796432**, Holm p =
  **0.0924796432**
- open-model change minus gemini change: **−9.3586 pp**, exact p = **0.000160692777**, Holm p =
  **0.000321385553**
- within-large gemini-minus-GLM change interaction: **+9.7792 pp**, Holm p = **0.00150054**
- within-open GLM-minus-mean(qwen, gemma) change interaction: **−0.6309 pp**, Holm p = **0.858751**

`report_source.sqlite` also passed `PRAGMA integrity_check = ok`. Its six new group datasets matched
the corresponding `report_artifact.json` rows exactly, field for field:

1. `model_group_classification`
2. `condition_a_group_contrasts`
3. `condition_b_group_contrasts`
4. `group_a_vs_b_changes`
5. `group_interactions`
6. `secondary_group_triangulation`

## Browser and responsive checks

The required `/browse` workflow was run at desktop **1440 px** and mobile **390 px** against the
portable `file://` report.

### Passed checks

- Document width equalled viewport width at both sizes: **1440/1440** and **390/390**; there was no
  page-level horizontal overflow.
- All five new group tables rendered with their expected headers and row counts: 2, 2, 4, 2, and 2.
- Wide tables use local `overflow-x: auto`; mobile scrolling reached the rightmost p-value or
  conclusion content without generating page overflow.
- All three “Clinical interpretation for physicians” blocks appear after their respective A, B,
  and paired A/B evidence sections.
- Rendered body text contained no leaked `**` or `##` Markdown markers.
- The page loaded with **zero console errors** and only local-file network requests, all HTTP/file
  status 200.
- The Experiment-A group-table options menu opened; “View data source” opened the source drawer;
  the Overview, Data preview, and SQL query tabs changed state correctly. Data preview showed both
  group rows and the SQL tab showed `SELECT * FROM condition_a_group_contrasts`.

The mobile header uses a deliberate ellipsis in the narrow sticky title, while the full report
title is visible immediately below; this is not a content-loss defect. Wide data cells are
horizontally scrollable rather than forcing document overflow.

## Clinical and construct-language review

**PASS.** The physician-facing explanations consistently use “matched the exam key” or
“key-matched answers,” not diagnostic accuracy. They explicitly state that the results are not
estimates of diagnostic sensitivity, patient benefit, bedside safety, or patient outcomes.

The fixed-model grouping limitations are also prominent and correctly repeated:

- “large” and “small” are requester-defined analytical labels, not a parameter-matched taxonomy;
- “open-model” does not adjudicate license terms;
- there is no small proprietary model, so size and access are not a complete factorial design;
- the access comparison is three named endpoints versus gemini alone;
- statistically detectable access-group interaction must not be generalized into a proprietary
  model-class advantage or used as a clinical procurement class effect;
- the B manipulation is an artificial, position-dependent meta-answer configuration and does not
  isolate memorisation or standard none-of-the-above handling.

No sentence reviewed generalized the four fixed deployments to all large/small,
open/proprietary, or clinical-use models. No sentence implied a patient outcome.

## Finalization checklist

- [x] Raw SQLite integrity and cell-level reconciliation
- [x] Independent group point estimates and exact sign-flip/Holm replay
- [x] Artifact-to-report-source SQLite equality
- [x] Desktop 1440 render
- [x] Mobile 390 render and horizontal-scroll behavior
- [x] Console/network health
- [x] Source drawer flow
- [x] Clinical and construct-language review
- [x] Rebuild portable HTML from the current artifact
- [x] Rerun browser/source seal and record the final HTML hash

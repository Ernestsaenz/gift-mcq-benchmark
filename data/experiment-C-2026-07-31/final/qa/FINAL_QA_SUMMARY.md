# Experiment C final Excel — QA summary

Date: 2026-07-31

## Release decision

The original draft's 99 biomarker / 86 anatomy candidates are retained for audit, not released as clinically key-preserving. The runner-ready release contains the 16 base questions that survived item-by-item adversarial review in both conditions:

`b2, b3, b4, b24, b26, b27, b28, b29, b31, b35, b36, b38, b43, b45, b46, b460`

Each appears as CTRL, BM, and AN, producing 48 unique master rows. The condition workbooks contain 16 rows each.

## Five adversarial QA reviews

1. `qa_insertion_lineage` — PASS. Reproduced all 474 source mappings and all 185 draft insertion strings with zero discrepancies.
2. `qa_workbook_integrity` — FAIL on draft. Found fragmented pagination, clipped fixed-height rows, and missing explicit fonts. Remediated in the final workbook with Arial, separate machine tables, and one-item review cards.
3. `qa_methodology_clinical` — FAIL on draft. Found false exclusions, unsafe strict admissions, placement defects, and clinical contradictions. Manually adjudicated all 37 original strict-paired items; 16 passed both conditions and 21 were excluded.
4. `qa_report_crosscheck` — FAIL on draft. Corrected the false claim that an unchanged key forces a zero accuracy delta, the corpus-wide ceiling claim, relaxed key-preservation wording, and several numeric/prose defects. The draft Word report is not designated final.
5. `qa_repro_security` — FAIL on draft. Found non-portable paths, removable assertions, non-atomic writes, document nondeterminism, and an evaluator-incompatible workbook. The finalizer uses CLI paths, hash-bound inputs, explicit validation, atomic output, and evaluator-ready sheets.

## Final artifact verification

- Source SHA-256: `3aca1a61fd3e641c0a698a500194f342cf61cb13cff3e271bf8e5479453e2fc5`
- Canonical SHA-256: `7414e0bbf7a9e7f8e7054662f847bca2ec61a1edf782dfd934174dca13f19911`
- ZIP/OOXML CRC: PASS for all four workbooks
- Formula cells: 0
- External links: 0
- Populated cells without Arial: 0
- Text cells over Excel's 32,767-character limit: 0
- Source answer/option/provenance mutations: 0
- Non-insertion text changes in BM/AN: 0
- `medrag_eval.excel_io` import: 48/16/16/16 rows, zero warnings, under normal and optimized Python
- LibreOffice render: PASS, 56 US-Letter pages
- PDF syntax: PASS with `qpdf --check`
- Review cards: 48 pages, 48 unique IDs, one card per page, all keys and source references present

Final output hashes are recorded in `outputs/final-manifest.json`.

## Interpretation constraint

Accuracy remains a valid behavioral-impact outcome: the fabricated sentence may change the model's selected letter even though the official key is unchanged. Accuracy alone cannot identify whether the model recognized, endorsed, or invented properties for the fabricated entity. That recognition endpoint requires a requested and normalized rationale or an explicit entity-recognition probe.

## Security scan limitation

Snyk Code was attempted on the finalizer after the final edit. It returned `401 Unauthorized (SNYK-0005)` before analysis, so no passing Snyk result is claimed.

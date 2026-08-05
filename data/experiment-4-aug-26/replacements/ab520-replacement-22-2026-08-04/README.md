# Proposed 22-question August replacement cohort

Status: **provisional, pending the remaining protocol QA; no provider calls were issued**.

This isolated workspace proposes 22 new questions for the six ambiguous/model-sensitive items and the 16 unique overlength questions. The often-quoted 64 long-question failures are 16 questions × four GIFT models, not 64 distinct questions.

The replacements are a **new matched cohort**. They do not overwrite the old question IDs, do not recover any original unresolved cell, and must not be reported as if they were the same items. If approved, the 22 new questions should be run across the same four models in OpenRouter A, OpenRouter B, and GIFT/TailScale A: 22 × 4 × 3 = **264 new cells**. GIFT B remains outside the original design.

## What is here

- `selection-spec.json`: exact old-question → candidate → new-ID map.
- `replacement-manifest.json`: full A/B text, official provenance, hashes, review state, and prompt lengths.
- `replacement-22-A.csv` and `replacement-22-B.csv`: audit-ready 22-row forms using the benchmark column contract.
- `benchmark-500-with-provisional-replacements.json`: a proposed 500-item JSON with replacements applied in place; the canonical 500 is untouched.
- `run-matrix-264.csv`: exact planned provider/condition/model matrix, with every row marked not run.
- `selected-source-packets.jsonl`, `selected-sourcing-reviews.jsonl`, and `selected-prior-qa-reviews.jsonl`: compact provenance extracts from the pinned dossier.
- `manual-adjudications.json`: current medical checks for candidates that lacked an upstream sourcing record.
- `similarity-audit.json`: nearest retained question under a reproducible token-overlap heuristic.
- `REJECTED_CANDIDATES.md`: important exclusions, including B-condition traps.
- `QA_REPORT.md`: independent QA-agent result; generated after the package audit.
- `checksums.sha256`: file hashes for the package.

The source workbook remains read-only at:

`/Users/ernestsaenz/Programming/gift-project-compile/second-project/workbook-repairs-2026-07-30/outputs/all-regions-aparato-digestivo.corrected.xlsx`

Pinned SHA-256: `18f6becd4e51f1b9ef6a5a8ab68421e905cfe2584ec32a0e303b76f3cacf1e46`.

## Selection rules

Every proposed item has four distinct options, a key in B/C/D, no inherited case context, no visual dependency, no pre-existing none/aggregate option, and an unchanged keyed letter. Condition B changes only the keyed option and `correct_option_text` to:

`Ninguna de las respuestas anteriores es correcta.`

The original answer-letter distribution is preserved exactly: B=7, C=7, D=8. Exact source keys and stems do not collide with the retained 478 questions. The GIFT user-message target is ≤4,500 characters, below the downstream 5,000-character hard limit.

No eligible unused Illes Balears clinical-case question survives the self-contained, non-negated filter, so region/year/formal-type matching for the 16 long questions is impossible. These replacements prioritize short, self-contained, medically stable questions.

## QA gate

The upstream protocol calls for a sourcing PASS and two distinct blinded QA PASS records per question. The user requested one QA subagent for this pass, so this package remains provisional wherever that second independent review is still missing. Do not execute `run-matrix-264.csv` until the QA report and remaining review deficits are resolved.

## Rebuild

From the repository root:

```bash
python3 data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/build_replacement_package.py
```

The builder is deterministic and writes only in this directory. It performs no network or provider operations. Spreadsheet authoring support required by the workspace spreadsheet policy was not available in this session, so the package intentionally uses CSV/JSON rather than creating an unverified `.xlsx`; convert only after protocol approval.

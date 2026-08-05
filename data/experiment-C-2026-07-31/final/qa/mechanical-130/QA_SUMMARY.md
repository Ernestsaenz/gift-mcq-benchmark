# Experiment C mechanical 100 + 30 reserve — QA summary

## Outcome

- Biomarker: 100 primary + 30 reserve, built from 99 locked legacy rows + 1 new primary + 30 new reserves.
- Anatomy: 100 primary + 30 reserve, built from 86 locked legacy rows + 14 new primaries + 30 new reserves.
- No duplicate base IDs or normalized control-question text within either 130-row workbook.
- Cross-arm reuse is intentional: the predecessor pools already shared 58 source IDs. BM and AN remain separate experimental arms and each receives a different rotated manipulation.

## Source and mutation contract

- Source: `balanced-flat-A.xlsx` (474 rows), SHA-256 `3aca1a61fd3e641c0a698a500194f342cf61cb13cff3e271bf8e5479453e2fc5`.
- Canonical rules: `canonical.json`, SHA-256 `7414e0bbf7a9e7f8e7054662f847bca2ec61a1edf782dfd934174dca13f19911`.
- New alterations are exact single insertions: `control[:offset] + inserted_sentence + copied_source_separator + control[offset:]`.
- Question source text, options, correct letter/text, metadata, and provenance are unchanged.
- The 99-row BM and 86-row AN predecessor workbooks retain their original SHA-256 values and every legacy altered string and variant assignment is unchanged.

## Review and adversarial QA

- Twenty distinct blinded reviewers covered all 763 missing candidate-arm pairs exactly once: 375 BM and 388 AN.
- First-pass eligible candidates: 90 BM and 81 AN.
- Three independent QA agents each audited all 356 blinded records (185 locked legacy + 171 new-review-pass records):
  - `qa_01`: 341 pass, 15 fail; SHA-256 `70b912c02b0cc378a184ad53ac971310b29cbf3ad37d0cd21da967fa97f9cf31`.
  - `qa_02`: 342 pass, 14 fail; SHA-256 `3a244769364321d2166e6614d27587751dbac9a820c55960d3c44a7d0b9c388b`.
  - `qa_03`: 339 pass, 17 fail; SHA-256 `f0423f4ad301b839baabf76df19f1ffd3174ee36a8d24316a670b7f0cb8ae4ff`.
- Unanimous new approvals after hard QA and deduplication: 80 BM and 71 AN.
- Selected: 31 BM and 44 AN; ordered overflow retained in the selection manifest: 49 BM and 27 AN.
- Duplicate exclusions at selection: 0 BM and 0 AN.

## Locked legacy flag

- Anatomy `b5` received two QA passes and one clinical-contradiction flag because the source says the patient reports no symptoms while the inserted examination finding reports elicited tenderness.
- This is not an insertion-contract failure: all three agents passed exact delta and placement. The row is a locked predecessor item, remains byte-for-byte unchanged, and is marked `LEGACY_QA_FLAG_2_OF_3` in the workbook instead of being silently replaced.

## Final validation

- Both workbooks contain exactly 130 unique rows, split 100 primary / 30 reserve.
- All 260 control rows match the source workbook exactly.
- All 185 legacy alterations match the predecessor workbooks exactly.
- All 75 new alterations satisfy the exact insertion equation.
- Options and answer keys match source for all 260 rows.
- Formula count: 0. External-link count: 0. ZIP CRC: clean. Populated non-Arial cells: 0.
- Unit tests: 5 passed. Ruff: passed. Python byte-compilation: passed.
- LibreOffice render succeeded; generated PDFs passed `qpdf --check` (291 BM pages and 267 AN pages). Representative table, paired-card, and legacy-flag pages were visually inspected.
- Snyk Code was invoked after the final code changes, but the local CLI stopped before analysis because it is not authenticated (`Use snyk auth to authenticate`). This is an environment limitation, not a clean security result.

## Output hashes

- Biomarker workbook SHA-256: `422b3a0d424fd29eece3ac50bc15d059c0ba1a09579f37dbb17d32441fa4c832`.
- Anatomy workbook SHA-256: `3d925d52fd0a9f95419d6b93db6551225a2963339fc937a079dd9ddd700711ae`.
- Selection manifest SHA-256: `68ce2365d4956b1f13b794e0eadc980b049e630217cb7ffa1a3cf365a222ec52`.

# experiment-4-aug-26 — full 500-question A/B benchmark dataset

Assembled 2026-08-04. This folder contains the **complete 500-question** Aparato-Digestivo
A/B benchmark = **318 previously-run questions + 182 new non-negated replacements**, in the
exact format the `medrag_eval` harness consumes, plus readable/JSON copies and full traceability.

The August gapfill has now been executed and consolidated. Canonical results are at
[`results/ab520-gapfill-2026-08-04/`](results/ab520-gapfill-2026-08-04/README.md): **5,930 of
6,000 cells scored, 70 explicitly unresolved**. The 20 reserves remain documented but unrun.

---

## 1. What each question set is

| Set | Count | `origin` tag | `question_id` | Status |
|---|---|---|---|---|
| **Retained (already run)** | **318** | `retained318` | `b2`, `b7`, … (previous scheme) | Already scored in the previous experiment (A & B) |
| **New** | **182** | `new182` | `n001` … `n182` | Executed in the August gapfill; see canonical results |
| **Total** | **500** | | | |

### The 318 retained
These are the **clean A/B analysis population of the previous experiment** (`data/experiment-31-07-26`).
Its own metadata (`analysis/dataset_meta.json`) defines this set as `ab_items_analysis = 318`: the 423
paired items minus the documented exclusions — out-of-domain/law items, adjudicated answer-key defects,
and `nota_position_a` (items whose correct letter is **a**, where the "…anteriores…" swap is nonsensical
in the first slot). Its region composition matches the ab182 `retained_318` target exactly (Illes
Balears 106, Navarra 29, Andalucía/Aragón/CLM/Galicia 25, …), confirming it is the same set.

⚠️ **105 of these 318 are negative-stem** (`negated_stem = true`) — the previous study deliberately kept
"choose the false/incorrect" items to measure the negation effect. They are **carried through unchanged**
here (their results already exist), and each is flagged in the `negated_stem` column so you can include or
exclude them in analysis. The 213 non-negated + 105 negated = 318.

### The 182 new
Selected and cleaned in the **ab182** project (`/private/tmp/ab182-q5i3oBTb/`). Every one is:
- a **genuine, verbatim** official Aparato-Digestivo corpus question (SHA-256 verified against the pinned
  corpus `all-regions-aparato-digestivo.corrected.xlsx`, sha `18f6becd…`);
- **not** in the original 500 (true replacements);
- mechanically eligible: exactly 4 distinct options, correct letter ∈ {b, c, d} (never **a**), no
  pre-existing "none-of-the-above", no aggregate key;
- **non-negated** (verified by combined regex + LLM classification — see §4);
- **valid in Condition B**: after the swap, the other three options are all false, so "none of the above"
  is the unique answer;
- backed by **1 sourcing PASS + 2 distinct blinded QA PASS**.

QA provenance of the 182: **121 carry the original `gpt-5.6-sol` double-QA; 61 were reviewed by a Claude
model during expansion.** A ready-to-run handoff to re-QA those 61 (and 18 single-review reserves) with
`gpt-5.6-sol` for uniform provenance is at `/private/tmp/ab182-q5i3oBTb/GPT56_HANDOFF.md`. This is a
provenance polish, not a correctness gap — all 182 are already non-negated, corpus-faithful, and double-reviewed.

---

## 2. Files in this folder

| File | Purpose |
|---|---|
| **`flat-A.xlsx`** / **`flat-B.xlsx`** | The full 500, Condition A / Condition B. **Drop-in for `medrag_eval`** (21-column import contract; `origin`/`negated_stem` are extra trailing columns the importer ignores). |
| `flat-A.csv` / `flat-B.csv` | Same content, human-readable. |
| **`new-182-flat-A.xlsx`** / **`new-182-flat-B.xlsx`** | ONLY the 182 to run (subset of the above). Use these to run just the missing questions. |
| `benchmark-500.json` | Combined — one object per question with both its A and B forms + metadata. |
| `build_dataset.py` | The deterministic build script (re-runnable; sources are read-only). |
| `inputs/retained_318_ids.json` | The definitive 318 ids + their `negated_stem` flag. |
| `inputs/new_182_ids.json` | The 182 new candidate ids (ab182 `cNNNN`). |
| `README.md` | This document. |
| **`results/ab520-gapfill-2026-08-04/`** | Canonical database, logs, exports, manifests, retry status, workbook, and presentation. |

### Column contract (both flat files)
`question_id, region, year, specialty, exam_part, question_number, question_text, option_a, option_b,
option_c, option_d, correct_letter, correct_option_text, flags, page_in_exam_pdf, source_exam_pdf,
source_answer_key_pdf, content_sha256, source_key, selection_score, context_ids, origin, negated_stem`

Condition **B** differs from **A** in exactly two cells per row: `option_{correct_letter}` and
`correct_option_text` both become `"Ninguna de las respuestas anteriores es correcta."`; `correct_letter`
is unchanged. (For the retained-318 negated rows this is the previous experiment's own B form, preserved.)

---

## 3. Results and reproduction

The harness lives in `code/medrag_eval/` (see the repository `README.md`). It imports the flat workbooks and
scores A vs B across the OpenRouter (no-RAG) and GIFT (RAG) arms.

- Use `results/ab520-gapfill-2026-08-04/exports/benchmark-6000-cell-results.csv` as the
  complete fail-closed cell ledger; join keys and score origins are explicit.
- Use `results/ab520-gapfill-2026-08-04/exports/benchmark-520-question-catalog.csv` for the
  500 primary questions plus 20 reserves.
- Rebuild instructions, database snapshots, provider retry logs, checksums, and the final
  5,930/70 status are documented in the canonical results README and `STATUS.md`.
- GIFT/TailScale Condition B was not part of the authorized scope and remains unrun.

---

## 4. Logic & history — how the 182 were produced (traceability)

1. **Goal:** complete a clean 500-question A/B benchmark. The previous experiment yielded 318 usable A/B
   items; **182 were missing** to reach 500.
2. **Sourcing pool:** the pinned corpus (`all-regions-aparato-digestivo.corrected.xlsx`, 2909 questions) →
   mechanical prefilter → 1186 eligible packets (not in the original 500, 4 distinct options, key ∈ {b,c,d},
   valid 2-field B-swap, no pre-existing none-of-the-above).
3. **Review:** each candidate got **1 sourcing PASS + 2 distinct blinded QA PASS** against a frozen rubric
   whose check #6 is exactly "after the B swap, the other three options must all be false."
4. **Negated-stem removal (the key correction):** an initial regex under-counted negative-stem items (it
   missed "¿cuál **no** es…?", "…EXCEPTO", "no forma parte"). Switching to **LLM classification** as ground
   truth revealed **~53% of the corpus is negative-stem**. The selection was rebuilt to be genuinely
   non-negated. Detection now **combines a high-recall regex with an LLM judge** (the regex flags obvious
   cases; the LLM catches phrasings the regex misses and removes false positives where "no/salvo" is only
   in the clinical vignette). Labels: `/private/tmp/ab182-q5i3oBTb/negstem-labels.json`.
5. **Final 182 + 20 reserves:** 0 negated (LLM-verified), all corpus-faithful, all double-reviewed;
   deterministic audit passed (`/private/tmp/ab182-q5i3oBTb/deterministic-final-audit.json`). Source of the
   182 packets: `/private/tmp/ab182-q5i3oBTb/selected-packets.jsonl`.

### Source-of-truth map
- 318 A/B rows ⟵ `data/experiment-31-07-26/balanced-flat-A.xlsx` / `-B.xlsx` (by `question_id`).
- 318 membership + negated flag ⟵ `data/experiment-31-07-26/analysis/paired_clean.json` +
  `analysis/dataset_meta.json` (exclusion rules applied in `build_dataset.py`).
- 182 A form ⟵ `selected-packets.jsonl` `raw_fields`; 182 B form ⟵ the 2-field swap in `build_dataset.py`.
- Full ab182 selection dossier + the gpt-5.6 re-QA handoff: `/private/tmp/ab182-q5i3oBTb/` (see
  `GPT56_HANDOFF.md`, `FINAL_READ_ONLY_REPORT.md`, `selection-manifest.json`).

---

## 5. Independent QA & the dedup fix

An independent reviewer agent verified the built dataset end-to-end (schema, a real `medrag_eval`
importer run = 500/500, 0 errors; retained-318 byte-identical to the prior experiment; all 182 A-forms
faithful to the packets; all 182 B-swaps mechanically exact; negated flags correct; JSON consistent).

It caught one real defect: **3 duplicate-*stem* pairs** the upstream ab182 dedup missed (it keyed on
options, not the bare stem) — `b250`↔`n076` (crossed the retained/new boundary), `n089`↔`n165`,
`n066`↔`n178` (internal to the 182; all same-stem but different options). **This was fixed**: the 3 new
duplicates (`c2772`, `c0225`, `c1152`) were swapped for 3 stem-distinct non-negated replacements
(`c2253`, `c2605`, `c1425`), and `build_dataset.py` now enforces a **stem-level dedup guard** over the full
500. Post-fix: **0 duplicate stems, 0 duplicate source_keys.**

## 6. Known caveats
- **105 negated items live inside the retained 318** (flagged). If the new experiment must be fully
  non-negated, filter `negated_stem == false` (leaves 213 + 182 = 395) — but that is **not** a 500-item set.
- **QA provenance of the 182:** 121 carry original `gpt-5.6-sol` double-QA; **61** carry Claude expansion QA;
  **1 (`c1425`)** has a single QA review (the 2-review replacement supply was exhausted at 2 after the dedup
  swap). Uniform `gpt-5.6-sol` re-QA handoff: `/private/tmp/ab182-q5i3oBTb/GPT56_HANDOFF.md`.
- **Region strings**: the 318 use display names ("Illes Balears"); the 182 were mapped to the same display
  names. `source_key` (slug form) is the stable join key across both.

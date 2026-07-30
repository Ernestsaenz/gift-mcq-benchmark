# Tier 1 — Parser Correction Note

**Status: code fixed, corrected statistics published alongside the originals. The
abstract's Tier-1 numbers have NOT been rewritten — see §5 for the decision this
leaves open.**

An audit of `code/medrag_eval/` found two answer-extraction defects. Both are now
fixed, with regression tests. The shipped ground-truth database
`data/medrag_eval.sqlite` is **unmodified** — corrected figures are re-derived from
the same raw responses by `rescore_with_fixed_parser.py`, which opens the DB
read-only.

---

## 1. What was verified as correct first

Before the defects, the pipeline was checked end-to-end and passed:

- Re-running the committed parser + scorer over **all 2,520 stored raw responses**
  reproduced the database exactly — **0 mismatches** in `parse_status`,
  `selected_letter`, or `strict_correct`. The scoring pipeline is deterministic and
  the DB was not hand-edited.
- An **independent reimplementation** of Cochran's Q and the exact-McNemar/Holm
  chain (pure stdlib, no statsmodels) reproduced the published values to the digit:
  Q = 117.454, p = 2.727e-25; Gemini vs Qwen 3.7 Max b=13, c=9, Holm p = 0.5234670639.
- `reproduction.md` §A executes verbatim and returns its documented output.

The defects below are extraction bugs, not fabrication. Everything in the dossier
traces to real logged model output.

---

## 2. Defect 1 — declaration outranked by incidental mention (HIGH)

`parser.py::_find_letter` ranked candidate matches by **pattern order alone** and
returned the first pattern that matched *anywhere* in the response. Position was
never considered. Models state their answer in the opening sentence and then
enumerate options while justifying it, so a later incidental mention could outrank
the model's own declaration.

Two GIFT-arm answers were scored wrong:

| Question | Model declared (char ~25) | Parser took | From | Gold |
|---|---|---|---|---|
| `g134` | "La opción correcta es la **d.**" | `a` | `(Opción a)` at char **1283** | d |
| `g261` | "La respuesta **INCORRECTA** es la **c**" | `a` | `(Opción a)` at char **1025** | c |

No pattern covered the Spanish declaration phrasings `opción/respuesta correcta es
la X` or the negative-stem `respuesta INCORRECTA es la X`, while the weak
`\bopci[oó]n\s+([a-d])\b` pattern matched enumeration bullets and sat *earlier* in
the tuple.

**Both errors are false negatives — the model was right and was marked wrong.**

### Fix

`_find_letter` now ranks candidates by **(tier, position)**:

| Tier | Contents | Rule |
|---|---|---|
| 0 — authoritative | `"selected_letter": "X"` JSON key | wins anywhere, at any distance |
| 1 — declaration | English `(the) (correct\|right\|best) (answer\|option\|choice) is X` or `answer is/: X`; Spanish `la opción/respuesta [más] correcta/incorrecta/probable… es la X` | **earliest** match wins |
| 2 — incidental | `(Opción a)`, bare `option a` (an enumeration label, not a declaration), bare `a)` / `a.` | consulted only if no declaration exists |

Position now dominates within a tier, so a model's stated answer beats a later
aside. Tier 2 is retained as a genuine fallback.

## 3. Defect 2 — markdown fences forced structured answers onto the regex path (MEDIUM)

`parse_openai_response` called `json.loads` on the raw message content, so a
response wrapped in a ` ```json ` fence failed to parse and fell through to the
regex fallback. Gemma wrapped **every** GIFT-arm response this way: 315/315 of its
answers were regex-extracted. Arm-level exposure was **31.5% regex on GIFT
(397/1260) vs 0.5% on OpenRouter (6/1260)** — an undisclosed asymmetry beneath
`EVIDENCE.md` §5's "apples-to-apples" claim.

### Fix

A fence-stripping retry, attempted **only after a plain `json.loads` has already
failed**, so it cannot alter any response that previously parsed. This moved
**313 rows** from `regex_primary` to `json_string` **without changing a single
answer** — which is also the evidence that the regex path had not been silently
disagreeing with the JSON.

Remaining regex-fallback rows: **90** (84 GIFT + 6 OpenRouter). These are *not* all
prose — the measured breakdown is:

| Residual rows | Resolved by | Note |
|---|---|---|
| **82** | tier-0 authoritative `"selected_letter"` key | extraction is exact, not heuristic |
| **8** | tier-1/tier-2 prose patterns | all `tailscale`/gemini: g110, g130, g134, g156, g157, g191, g261, g322 |

By structured-parse failure reason: 76 `failed_content_json_invalid` (JSON emitted
alongside prose, so the whole content is not a JSON document and `_strip_code_fence`
correctly declines — it only strips a fence spanning the *entire* content), and 14
`failed_invalid_option_text` — complete, valid JSON answer objects rejected solely
because `selected_option_text` was not verbatim (e.g. letter-prefixed
`"b. Distancia al margen de resección de 1,5 mm."`). That rejection is the §4
backfill rule, not a fence problem.

So **only 8 of 2,520 rows depend on the prose heuristics at all**, and exactly one
(gemini g157) relies on the tier-2 incidental patterns. All 8 extract correctly
under the fixed parser.

## 4. Defect 3 — `strict_correct` is degenerate; the evidence document's defense of it was wrong

`EVIDENCE.md` §5 claimed strict scoring makes 86.9% "a floor, not an inflated lenient
score", and that "a right-letter/paraphrased-text answer does **not** count."

Row-level check across all 2,520 scored rows:

```
strict ≠ letter: 0     strict ≠ lenient: 0     text ≠ letter: 0
```

Strict and lenient are **numerically identical**. `parser.py` backfills
`selected_option_text` from the letter when text is absent, and rejects
non-verbatim text as a *parse failure* rather than a wrong answer — so
`text_correct` can only diverge on `ok_conflict` rows, of which there is exactly
one in the DB, and it is not in the final scored set.

**The 86.9% figure is correct; the stated justification for it was not.** No code
change was made here (changing the backfill would alter the measurement
definition). The `EVIDENCE.md` claim has been corrected and the behaviour is locked
in by `tests/test_parser_extraction.py::test_letter_only_answer_backfills_text_making_strict_equal_letter`.

## 5. Effect on the published numbers — and the decision left open

| Quantity | Published | Corrected |
|---|---|---|
| GIFT gemini | 95.56% (301/315) | **96.19% (303/315)** |
| GIFT aggregate | 86.9048% (1095/1260) | **87.0635% (1097/1260)** |
| GIFT Cochran's Q | 117.454 (p = 2.727e-25) | 124.042 (p = 1.040e-26) |
| Gemini vs Qwen 3.7 Max, Holm p | 0.5235 | **0.2632** |
| OpenRouter control aggregate | 87.9365% (1108/1260) | 87.9365% — **unchanged** |

Three things follow, and all of them favour the dossier:

1. **The abstract's conclusions are unchanged.** The two top models remain
   statistically indistinguishable (Holm p = 0.263, still ≫ 0.05); Cochran's Q
   still rejects. Nothing in the Discussion needs rewriting.
2. **The errors were conservative.** The published numbers *understate* GIFT.
3. **Provider robustness gets stronger.** Corrected GIFT gemini (303/315) now
   matches the OpenRouter arm exactly (303/315) — the two arms agree to the
   question. The control arm did not move at all, which is what makes the fix
   demonstrably scope-safe.

**Open decision (not taken here).** Whether to restate the abstract as 87.1% /
96.2% is a scientific-communication call, not a code call — the abstract may
already be submitted, and a committee may prefer "the published figure, with a
documented conservative bias" over a late restatement. This note gives both sets
of numbers with full provenance so the decision can be made deliberately.

Note that a restatement touches **three** abstract figures, not two: the aggregate
(86.9 → 87.1), gemini (95.6 → 96.2), **and the quoted Holm p-value (0.523 → 0.263)**
— which remains non-significant, so the sentence's *claim* survives unchanged.

If the abstract is restated, all of the following carry an affected figure and must
be updated in the same pass:

| File | Locations |
|---|---|
| `01_claim_ledger.md` | rows **1.4** (aggregate), **1.6** (gemini), **1.8** (Holm p) |
| `00_ABSTRACT_annotated.md` | lines 42, 44, 92 |
| `02_committee_defense.md` | lines 11, 49 |
| dossier-root `README.md` | lines 22, 35, 39 |
| `03_reproduce_everything.md` | lines 9, 22 |
| `tier1_mcq/EVIDENCE.md` | §§1, 4, 6 |

### Cross-arm analyses also superseded

`rescore_with_fixed_parser.py` re-derives the *within*-arm statistics and now also
the GIFT-vs-OpenRouter provider comparison (§6). Two committed artifacts under
`data/statistical_analysis/` are **superseded but not overwritten** — the files are
unchanged on disk, and the corrected values live alongside them:

| Artifact | Published | Corrected |
|---|---|---|
| `provider_mcnemar.csv` (Gemini row) | b=3, c=1, p=0.625, diff +0.00635 | b=1, c=1, p=1.000, diff 0.000 |
| `gee_provider_model_wald_terms.csv` (`provider_c`) | p = 0.317 | p = 1.000 |

Both move **in the dossier's favour** — the corrected GIFT gemini arm matches the
OpenRouter arm exactly, so the provider effect vanishes entirely. The GEE
interaction term is essentially unmoved (0.4147 → 0.4339). No conclusion changes.

---

## 6. Reproducing this

```bash
# from the repository root

# re-derive corrected statistics from the untouched DB; --check asserts that
# EXACTLY the two audited answers changed and the control arm did not move.
# Standard library only — no install required.
python3 rescore_with_fixed_parser.py --check

# regression tests for both defects (39 tests)
pip install -e ".[dev]" && pytest

# or simply:
make check
```

`rescore_with_fixed_parser.py` is standard-library only (Cochran's Q, exact
McNemar and Holm are implemented in it) so it runs on a bare `python3` with no
environment setup. Outputs go to `data/statistical_analysis_corrected/`, leaving
the original `data/statistical_analysis/` intact for side-by-side comparison.

## 7. Files changed

| File | Change |
|---|---|
| `code/medrag_eval/parser.py` | `_find_letter` tiered/position ranking; `_strip_code_fence` + fenced-JSON retry |
| `code/tests/test_parser_extraction.py` | **new** — 39 regression tests; `g134`/`g261` fixtures are verbatim contiguous prefixes of the stored responses, with their character offsets asserted |
| `pyproject.toml` | retargeted `src/` layout + readme path to the delivered layout (package was not installable as delivered); later moved from `code/` to the repository root |
| `rescore_with_fixed_parser.py` | **new** — read-only re-scoring + corrected within-arm and cross-arm statistics |
| `data/statistical_analysis_corrected/` | **new** — corrected report, CSVs, change log |
| `EVIDENCE.md` (was `README.md`) | post-audit banner added above §1; §5 strict-scoring claim corrected; §5 extraction-asymmetry note added; §8 strict-scoring sentence brought into line with §5 |
| `CORRECTION_NOTE.md` | **new** — this document |

`data/medrag_eval.sqlite` and `data/statistical_analysis/` are **unchanged on
disk** (DB md5 `c6eb43ede71c1c61ffa87f96e5e070f7`); see §5 for the two artifacts in
`data/statistical_analysis/` that are superseded in value.

## 8. Provenance of this correction

The two defects were found by a code audit; the fixes were then reviewed by four
independent adversarial reviewers (regex-breaking, statistics/scope-safety,
documentation accuracy, reproducibility), each finding verified by a separate
refutation pass. 27 findings were raised, 7 survived verification, and all 7 are
addressed here. That review caught a **regression introduced by the first version
of the fix**: the tier-1 English pattern was written with both the qualifier and
the copula optional, so the enumeration label "Option a" parsed as a declaration
and `"Option a is wrong. The correct answer is d."` returned `a`. It never fired on
any of the 2,520 stored responses (the corpus is Spanish), but it was a real
regression on plausible input. The pattern now requires an explicit declaration
cue, and the five reviewer-supplied inputs are regression tests.

The test suite is **mutation-tested**: reverting the position ranking, removing the
fence fix, or restoring the over-broad English pattern each causes failures
(2, 5 and 5 respectively). An earlier version of the suite passed against the
pattern-order mutant — it was strengthened until it did not.

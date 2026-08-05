# Final execution report

Generated: 2026-08-04T14:30:43.068488+00:00

The authorized OpenRouter A, OpenRouter B, and TailScale A gapfill run is complete. The frozen 6,000-cell ledger contains **5,930 scored cells** and **70 fail-closed unresolved cells**. TailScale B was excluded from this run.

## Coverage and strict accuracy

| Arm | Required | Scored | Unresolved | Strict correct | Accuracy among scored |
|---|---:|---:|---:|---:|---:|
| openrouter_A | 2000 | 1998 | 2 | 1784 | 89.29% |
| openrouter_B | 2000 | 2000 | 0 | 1468 | 73.40% |
| tailscale_A | 2000 | 1932 | 68 | 1765 | 91.36% |

OpenRouter has 1,998/2,000 scored A/B pairs. On those same paired cells, A strict accuracy is 89.29%, B strict accuracy is 73.42%, and B − A is -15.87%.

## Unresolved cells

| Failure class | Cells |
|---|---:|
| openrouter_glm_length_no_parse_after_retries | 2 |
| tailscale_glm_server_error_150s_after_retries | 4 |
| tailscale_http500_correlated_overlength_exact_input | 64 |

The 64 correlated TailScale overlength failures cover 16 linked-context questions. Their exact A text was preserved; no truncation, chunk removal, or protocol change was used. The 4 remaining TailScale failures are GLM server errors at the 150-second backend boundary. The 2 OpenRouter failures are GLM responses ending by length without a parseable answer after bounded retries.

## Deliverables

- `exports/benchmark-520-question-catalog.csv`: the single-table 520-question catalog (500 primary + 20 documented reserves), with historical and current coverage markers and full provenance.
- `exports/benchmark-6000-cell-results.csv`: every authorized question/model/arm cell, including exact input fields, score origin, selected answer, correctness, attempts, hashes, and failure class.
- `exports/openrouter-paired-ab-results.csv`: 2,000 OpenRouter A/B pair slots with paired-score availability and per-cell A/B outcomes.
- `exports/unresolved-cells.csv`: the complete fail-closed exception ledger.
- `exports/benchmark-results-and-traceability.xlsx`: the same material split into documented worksheets.
- `manifests/execution-manifest-final.json`: hashes, counts, validation, and methodology notes.

## Interpretation constraints

- The results combine a hash-pinned July reusable cohort with the August gapfill cohort; use `score_origin` when auditing or analyzing time-dependent performance.
- Accuracy denominators in the summary are scored cells, not the nominal 2,000 when unresolved cells remain.
- TailScale B was not run, so this execution does not supply a TailScale A/B comparison.
- Three original reserves were promoted during the final stem-dedup repair. The catalog restores 20 unique reserves with three deterministic frozen-rank backfills from the fully passing pool; each backfill has a sourcing PASS and one expansion-QA PASS and is explicitly labeled.
- The archived 520 master predates the final non-negated rebuild and duplicate-stem swaps. Only its unchanged retained-318 lineage was reused; all current new and reserve rows were rebuilt from the final candidate IDs and packet records.
- Model-only execution and QA are not a substitute for human specialist certification.

## Security note

A diagnostic command earlier in the session exposed credential values in the tool transcript. No secret is written to these artifacts, but the OpenRouter key and GIFT credential should be rotated after the run.

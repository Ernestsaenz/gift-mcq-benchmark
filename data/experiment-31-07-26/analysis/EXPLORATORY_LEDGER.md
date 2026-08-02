# Preserved exploratory-analysis ledger

The analysis root contains 539 exploratory scripts and outputs. They remain in place because many
use bare sibling imports, relative file reads, or exact paths cited by QA records. This ledger
organizes them conceptually without breaking those dependencies.

| Prefix family | Main topic | Release status |
|---|---|---|
| `prim_*` | Primary OpenRouter A/B inference, permutation, bootstrap, mixed models | Preserved; superseded by `final_analysis_results.json` unless explicitly hash-pinned in `audited_secondary_results.json` |
| `sens_*` | Exclusions, position artifact, influence, specification sensitivity | Preserved; final accepted values are in the canonical result bundles |
| `stats_*` | Data structure, normality, confidence intervals, power, multiplicity | Preserved methods trail; not a direct report source |
| `ca_*` | Partial GIFT/OpenRouter condition-A comparison, coverage, latency, harm/help | Preserved; final accepted subset is in `cross_arm_A.json` and the canonical result bundles |
| `mech_*` | Mechanism, error destinations, effort, negation, difficulty | Preserved exploratory work; stopped/unverified mechanism claims are excluded from the report |

Common suffixes describe workflow roles:

- `_ref_`, `_refute_`, or `_validate` — independent challenge or verification.
- `_out.json`, `_results.json`, `_report.txt`, or `_log.json` — generated output from a neighboring
  script.
- `_lib.py` — helper imported by sibling exploratory scripts.

## Safe use

1. Start with `REPORT.md`, `final_analysis_results.json`, and `dataset_meta.json`.
2. Use an exploratory artifact only to trace how a result was challenged or derived.
3. Check its input denominators and export version; several preserved files predate v3.
4. Do not move an exploratory file independently from its sibling modules and inputs.
5. Do not quote a mechanism finding unless it is explicitly accepted in the final report.

Nothing in this ledger deletes, renames, or reclassifies the underlying evidence. It provides a
stable navigation layer over the complete preserved analysis history.

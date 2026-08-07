# Final QA and execution report

Generated: 2026-08-05T10:58:29Z

Verdict: **PASS — QA complete and adjusted benchmark complete**.

## QA gates

- Formal sourcing: 22/22 PASS.
- Blinded QA1: 22/22 PASS.
- Blinded QA2: 22/22 PASS, with a distinct reviewer for every candidate.
- Condition B mechanical transformation: 22/22 exact two-field swaps.
- Official workbook, exam PDF, and definitive-key bindings: 22/22 verified.
- Duplicate adjudication for c0369: PASS; the historical three-option variant is absent from the active benchmark and is not a full-content collision.

## Execution integrity

- Frozen replacement ledger: 264 unique cells, 88 per arm.
- Replacement database: 264 logical calls, 266 provider attempts, 264 scores, integrity check `ok`.
- Every replacement cell has exactly one score and an unchanged question, prompt, model, condition, and input hash.
- All GIFT attempts use prompt ID 13; no TailScale B calls exist.
- No `--force`, reasoning-disable, answer inference, input truncation, or score reassignment was used.
- Two rejected first attempts were retained as diagnostic evidence and did not create scores; isolated exact-input retries recovered both.

## Adjusted benchmark reconciliation

- Canonical source: 6,000 cells, 5,930 scored and 70 unresolved.
- Removed with the 22 rejected originals: 264 cells, including all 70 unresolved cells.
- Retained: 5,736/5,736 scored cells from 478 questions.
- Added: 264/264 scored cells from the 22 QA-approved replacements.
- Final: **6,000/6,000 scored, 2,000/2,000 per arm, zero unresolved**.
- OpenRouter paired A/B coverage: 2,000/2,000.
- Reserve catalog: 14 active collision-free reserves; six of the 20 historical slots remain vacant pending new QA after seven reserve promotions and one reviewed backfill.

## Arm results

| Arm | Scored | Strict correct | Strict accuracy |
|---|---:|---:|---:|
| openrouter_A | 2,000 | 1,797 | 89.85% |
| openrouter_B | 2,000 | 1,468 | 73.40% |
| tailscale_A | 2,000 | 1,837 | 91.85% |

The complete per-cell audit trail, QA coverage, production evidence, invocations, database snapshots, and checksums remain in this directory. A Snyk Code scan was attempted separately; the installed CLI rejected its credentials with HTTP 401, so no successful Snyk result is claimed.

Spreadsheet limitation: the adjusted `.xlsx` remains blocked because the mandated artifact-tool dependency loader is unavailable. CSV outputs and the standalone statistical HTML presentation were regenerated and verified.

# Experiment status

Updated: 2026-08-04T14:35:18Z

## Final state

| Arm | Completed/scored | Running | Queued | Unresolved | Required |
|---|---:|---:|---:|---:|---:|
| OpenRouter A | 1,998 | 0 | 0 | 2 | 2,000 |
| OpenRouter B | 2,000 | 0 | 0 | 0 | 2,000 |
| GIFT/TailScale A | 1,932 | 0 | 0 | 68 | 2,000 |
| **Total** | **5,930** | **0** | **0** | **70** | **6,000** |

Invariant: **scored + unresolved = 5,930 + 70 = 6,000**.

## Baseline and queue audit

The frozen pre-retry state was 5,928 scored and 72 unresolved:

| Arm | Baseline scored | Baseline unresolved |
|---|---:|---:|
| OpenRouter A | 1,998 | 2 |
| OpenRouter B | 1,999 | 1 |
| GIFT/TailScale A | 1,931 | 69 |

Harness dry-runs reconfirmed exactly three OpenRouter cells and 69 GIFT cells:

- OpenRouter: `1 + 1 + 1 = 3` GLM cells.
- GIFT: `16 + 16 + 16 + 20 + 1 = 69` cells.

The exact baseline target list is `manifests/retry-targets-pre-retry.csv` (72 data rows;
SHA-256 `8804396c1f6394f3d55acf14cb385e3f5179221492e4965492d90934727d430b`).
The SQLite snapshot was created at 2026-08-04T14:15:34Z and passes `PRAGMA
integrity_check`.

## Production gate

- Required backend commit: `29af9a4f1581f6ffc1921a44d96a2a2cbe36a84e`.
- Latest `main` run for deployment workflow `229572888`: run `30629235833`, exact required
  SHA, completed successfully; deploy job and all steps succeeded.
- Fresh backend health at 2026-08-04T14:14:12Z: HTTP 200, `status=healthy`, RAG,
  retrieval, and streaming healthy.
- Fresh authenticated provider check passed before GIFT calls.

Status: **gate satisfied by latest deployment evidence plus live health**. The live health
payload does not itself expose a build SHA; this limitation is explicit in
`manifests/production-evidence.json`.

## Retry timeline

All timestamps are UTC.

| Time | State/action | Concurrency | Outcome |
|---|---|---:|---|
| 13:17:31–13:24:25 | OpenRouter A GLM `n169` retry already present before snapshot | 1 | HTTP 200 ended by length; unresolved |
| 13:26:59–13:28:02 | OpenRouter A GLM `b320` retry already present before snapshot | 1 | timeout/request error; unresolved |
| 14:15:34 | Pre-retry SQLite snapshot frozen | 0 | integrity `ok`; 5,928/72 |
| 14:18:45–14:19:04 | OpenRouter B GLM `n032` | 1 | recovered; parsed `d`, key `c`, strict incorrect |
| 14:23:26–14:23:27 | Representative long-context GIFT GLM probe `b141` | 1 | HTTP 500 in 79 ms; unresolved |
| 14:23:42–14:26:15 | Remaining GIFT GLM batch: 15 overlength + 5 independent | 5 | `b264` recovered; 19 unresolved |
| 14:30:49 | Exports/workbook regenerated | 0 | 5,930/70; 6,000 exact input matches |
| 14:31:33 | Statistical presentation regenerated | 0 | dynamic 5,930/70 coverage |

Because the probe repeated the immediate HTTP 500, the 48 equivalent non-GLM overlength
calls were not issued. Active concurrency is now 0.

## Recovered cells

| Cell | Provider/arm | Result | Score count | Immutability |
|---|---|---|---:|---|
| `openrouter|B|n032|galicia|2016|main|7|z-ai/glm-5.2|1` | OpenRouter B | parsed `d`; strict incorrect | 1 | question, model, system/user prompt hashes unchanged |
| `tailscale_medical_rag|A|b264|galicia|2022|reserva-especifica|101|z-ai/glm-5.2|1` | GIFT A | parsed `a`; strict incorrect | 1 | question, model, system/user prompt hashes unchanged |

No baseline unresolved key disappeared except these two, and no new unresolved key appeared.

## Residual failure causes

| Failure class | Cells | Action/status |
|---|---:|---|
| `tailscale_http500_correlated_overlength_exact_input` | 64 | probe reproduced immediate 500; 48 non-GLM equivalents intentionally not reissued; all fail-closed |
| `tailscale_glm_server_error_150s_after_retries` | 4 | fresh bounded retries repeated HTTP 500 at about 151 s |
| `openrouter_glm_length_no_parse_after_retries` | 2 | length/transport failures remain unparseable |

## Verification

- Current database SHA-256:
  `c3dee485f8de1a6f28f2e38c7416ba412f0ebf30bc751c250af79b006a180888`;
  integrity `ok`.
- 6,000 result rows, 6,000 unique cell keys, and 6,000 exact database-input matches.
- Every recovered cell has exactly one score; unresolved cells remain explicitly missing.
- Workbook: seven expected sheets, zero formulas, zero Excel error cells, Arial throughout.
- Presentation: eight slides rendered in `/browse`, distinct QA screenshots, no console errors,
  no failed network requests.
- Harness tests: 60 passed.


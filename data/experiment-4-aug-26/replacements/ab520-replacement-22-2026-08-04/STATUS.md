# Replacement execution status

Updated: 2026-08-05T10:58:29Z

QA gate: **PASS — 22/22 sourcing, 22/22 QA1, 22/22 QA2**.

| Arm | Original cells retained | Replacement cells scored | Final scored | Queued | Unresolved |
|---|---:|---:|---:|---:|---:|
| OpenRouter A | 1,912 | 88 | 2,000 | 0 | 0 |
| OpenRouter B | 1,912 | 88 | 2,000 | 0 | 0 |
| GIFT/TailScale A | 1,912 | 88 | 2,000 | 0 | 0 |

Execution window: `2026-08-05T01:06:29Z` to `2026-08-05T01:31:05Z`. Active concurrency: **0**.

Production gate: **PASS**. Required SHA `29af9a4f1581f6ffc1921a44d96a2a2cbe36a84e` was the latest successful main deployment; deployment run `30629235833` and the live health/authentication checks passed before GIFT traffic.

Final recovery: **264/264 replacement cells scored**. Two rejected first attempts were recovered by isolated exact-input retries: one OpenRouter GLM length-terminated response and one GIFT Qwen non-answer response. Residual replacement failures: **0**.

Adjusted analysis: **6,000/6,000 scored**, comprising 5,736 retained canonical scores and 264 QA-approved replacement scores. The 22 rejected original questions and all 264 of their former cells are excluded; no result was inferred or reassigned.

Reserve status: seven historical reserves were promoted into the primary replacement cohort. Thirteen prior reserves remain active and the frozen reviewed pool supplied one collision-free backfill (`c0989`), leaving **14 active reserves and six explicitly vacant reserve slots pending new QA**.

Workbook note: the adjusted CSV, JSON, and HTML artifacts are complete. A new adjusted `.xlsx` was not authored because the required `load_workspace_dependencies`/`@oai/artifact-tool` runtime is unavailable in this environment.

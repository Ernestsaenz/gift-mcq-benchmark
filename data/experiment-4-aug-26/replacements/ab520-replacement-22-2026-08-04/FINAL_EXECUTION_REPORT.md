# Final adjusted execution report

Generated: 2026-08-05T10:58:29Z

The replacement workflow completed with **6,000/6,000 scored cells** and no unresolved cells. Each authorized arm contains exactly 2,000 scores. The result combines 5,736 unchanged retained scores with 264 scores from 22 fully QA-approved replacement questions.

The 22 rejected original questions were removed as questions, so none of their scored or failed cells contributes to the adjusted analysis. This is a replacement-cohort result, not a retry-based recovery of the rejected items.

OpenRouter A/B has 2,000/2,000 exact matched pairs. Condition A strict accuracy is 89.85%; condition B is 73.40%; B minus A is -16.45%.

Two provider responses failed closed on their first attempt: OpenRouter GLM r018 ended by length without a parseable answer, and GIFT Qwen r004 returned a non-answer message. Both exact-input isolated retries succeeded, while the rejected responses remain recorded as attempts and never received inferred scores.

See `exports/`, `presentation/`, `RUN_LEDGER.csv`, `STATUS.md`, and `manifests/execution-manifest-final.json` for the reproducible outputs and provenance.

Reserve lineage is kept separate from the scored result: 13 prior reserves remain active, `c0989` is the sole eligible reviewed backfill in the frozen pool, and six historical reserve slots remain vacant pending new QA. No duplicate reserve was silently retained.

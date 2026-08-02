# Fifteen-workflow independent QA summary

The release was checked through fifteen separately scoped workflows. Each workflow began from the
database, workbooks, canonical exports, code, or rendered artifact appropriate to its remit rather
than trusting the preceding narrative. The table in `qa_summary.json` preserves each initial
verdict and the corresponding resolution.

Workflows QA01–QA08 identified and corrected stale-version counts, a nondeterministic retry join,
mislabelled tests, incomplete missingness treatment, operational denominator errors, and overly
causal wording. QA09 independently confirmed that the v3 core estimates reproduce, then blocked
the first portable report build because its prose was stale and its source metadata was not
replayable. Those packaging defects are repaired in the release candidate.

QA10 initially blocked delivery because the portable renderer duplicated Markdown tables, showed
the reproduction fence literally, omitted pooled rows from native replacements, and rounded tiny
p-values to zero. After two rebuilds it passed the Markdown, machine-readable artifact, replayable
source database, source drawer, and portable HTML at desktop and mobile widths. The final package
was then expanded for the requested model-comparison revision.

QA11 independently reconstructed the common 317-item Experiment-A and Experiment-B comparisons
and the all-available-pair A/B comparison. It matched every denominator, point estimate, CR1
omnibus F test, cluster sign-flip p-value, Holm adjustment, and 100,000-replicate bootstrap limit.
QA12 adversarially checked physician-facing language, block order, source replay, desktop/mobile
rendering, folder preservation, and release hashes. It blocked two interim builds for p-value
coercion and a leaked Markdown emphasis marker; both presentation defects were corrected before
release.

QA13 independently rebuilt every requested large/small and open-model/proprietary comparison from
the canonical pairs, including the common population, seeded whole-cluster intervals, exact
cluster sign flips, and all three Holm families; it found zero discrepancies. QA14 rejected a
stale interim HTML build, then passed the rebuilt group tables, source drawer, physician-facing
restraint, local-only loading, and responsive behavior at 1440 px and 390 px. QA15 audited the
implementation and release chain, added a machine-readable final QA status so readiness fails
closed, verified deterministic rebuilds in the project `uv` environment, and sealed the v3.2
manifest. The final package has fifteen resolved QA rows and no pending workflow.

The detailed evidence is retained in `QA01_LINEAGE.md` through
`QA15_GROUP_CODE_RELEASE.md`; an initial FAIL means the audited version was rejected, not that
its finding was silently discarded.

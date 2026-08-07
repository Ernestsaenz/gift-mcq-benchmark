# Model taxonomy — audit trail for the open/closed and big/small groupings

**Owner:** Agent 3 (groupings). **Scope:** documents how every model-level
label used in `GROUPING_TESTS.md` and `scripts/03_groupings.py` was formed,
and marks explicitly what is repo-established fact versus what is
unverifiable. Written 2026-08-07.

**Standing instruction this file exists to satisfy:** do not invent, estimate,
or silently look up a parameter count and present it as fact. `UNVERIFIED` is
an acceptable, final answer for a field — it is not a placeholder for future
research. No web lookup was performed for this file; see "Why no external
lookup was attempted" at the bottom.

## The four models

| Model slug | Developer | Weight availability | Basis for weight-availability label | Parameter count | Basis / status | Architecture |
|---|---|---|---|---|---|---|
| `google/gemini-3.6-flash` | Google | **Closed** | Served only through provider APIs (OpenRouter → Google AI Studio / Google Vertex; see `../consolidate-triplicates-7-aug-26/exports/EXPORTS_README.md`). No weights file, checkpoint, or open license is referenced anywhere in this repo. Gemini as a product line is proprietary API-only. | `UNVERIFIED` | Not disclosed by the developer; not established anywhere in this repo. **Not looked up.** | `UNVERIFIED` (proprietary; internal architecture not disclosed) |
| `google/gemma-4-26b-a4b-it` | Google | **Open** | Gemma is Google's separate, openly-licensed model line (distinct from Gemini), released with downloadable weights. | 26B total / ~4B active | The slug itself encodes the size (`26b-a4b` = 26B total parameters, 4B active). This is the same figure STATS_SPEC.md states as a design fact and that this analysis inherited; it was **not** independently re-derived from a model card inside this repo, so treat it as repo-supplied rather than repo-verified. | MoE (mixture-of-experts) — total ≠ active parameters |
| `qwen/qwen3.6-35b-a3b` | Alibaba / Qwen team | **Open** | Qwen is released with downloadable weights under an open license. | 35B total / ~3B active | Same basis as gemma: slug-encoded (`35b-a3b`), repo-supplied via STATS_SPEC.md, not independently re-derived from a model card. | MoE — total ≠ active parameters |
| `z-ai/glm-5.2` | Z.ai / Zhipu AI | **Open** | GLM is historically released with downloadable weights; STATS_SPEC.md's design-fact table places it in the open group and no contradicting evidence exists in this repo. | `UNVERIFIED` | **No parameter count is established anywhere in this repo for this exact version string.** The slug does not encode a size the way the other two do. Not looked up externally. | `UNVERIFIED` |

## Why the open/closed weight-availability labels are still usable, but the size labels are not

Weight availability is a **binary, family-level policy fact** (does the
vendor ship weights for this product line at all, yes/no) that does not
require knowing an exact parameter count. Gemini has never shipped weights
for any version; Gemma, Qwen, and GLM are lines that do. That distinction
holds for `gemini-3.6-flash` / `gemma-4-26b-a4b-it` / `qwen3.6-35b-a3b` /
`glm-5.2` on the same basis it holds for every other version in each family,
so classifying by family policy is defensible even though these exact
version strings were not individually checked against a live model card.
**This is a family-level classification carried over from STATS_SPEC.md's
design-fact table, not a citation to a specific release page for these exact
version numbers** — flagged here so the distinction isn't lost.

Parameter count is different: it is a **per-version fact**, not a family
policy, and two of the four models fail to clear that bar (see table above).
That is why open/closed is computed below (as a labeled, confound-heavy
descriptive result) while big/small is not computed at all.

## Big vs small: declared INFEASIBLE

STATS_SPEC.md offered three options: (a) restrict to the two models with
published sizes and accept n_models=2; (b) operationalise as total-vs-active
parameters for the two MoE models only; (c) declare the comparison
infeasible. **Option (c) was chosen. No big-vs-small statistical test was
run.**

Reasoning:

1. **Two of four models have no defensible size at all.** `z-ai/glm-5.2` has
   no parameter count established anywhere in this repo. `google/gemini-3.6-flash`
   is proprietary with an undisclosed size. Any grouping that includes either
   model requires fabricating a number. That alone rules out any 4-model or
   3-vs-1 split.

2. **Restricting to the two models with real numbers (gemma, qwen — option
   (a)/(b)) does not rescue a binary "big vs small" label**, because the two
   plausible size metrics disagree about which model is bigger:

   | Model | Total parameters | Active parameters (MoE) |
   |---|---:|---:|
   | `google/gemma-4-26b-a4b-it` | 26B | ~4B |
   | `qwen/qwen3.6-35b-a3b` | 35B | ~3B |

   By total parameters, qwen (35B) is the larger model. By active
   parameters — arguably the more relevant number for inference-time cost
   and, plausibly, for reasoning capacity per forward pass — gemma (4B) is
   the larger model. **The ordering inverts depending on which parameter
   definition is used.** There is no non-arbitrary way to pick a "big" and
   a "small" model out of this pair without first picking a size metric
   that this study has no independent reason to prefer, and picking one
   metric over the other would determine the answer before any data is
   examined. That is a defensible reason to decline the grouping, not a
   defect this analysis found and hid.

3. Even setting aside point 2, a two-model comparison (n_models=1 per side)
   dressed up as a "size" grouping would carry exactly the same
   single-model-confound problem documented for open-vs-closed below, with
   the added defect of an ill-defined grouping variable. It would not be a
   size test; it would be "gemma vs qwen" wearing a size label.

**No parameter count for `z-ai/glm-5.2` or `google/gemini-3.6-flash` was
invented, estimated, or looked up to work around this.** The two figures
used above (gemma, qwen) are the ones already stated as design facts in
`../STATS_SPEC.md`; this file does not add any parameter count STATS_SPEC.md
did not already supply.

## Why no external lookup was attempted

This repo's model slugs (`gemini-3.6-flash`, `glm-5.2`, `qwen3.6-35b-a3b`,
`gemma-4-26b-a4b-it`) are internal identifiers for this experiment; the
version numbers do not correspond to any model line whose specifications
this analysis can independently verify from within the repo, and
STATS_SPEC.md explicitly prohibits inventing, estimating, or looking up a
parameter count and presenting it as fact. Consistent with that instruction
and with the precedent already set elsewhere in this repo (see
`../../experiment-31-07-26/analysis/comparison_workflows/GROUP_COMPARISONS_STATS.md`,
which treated "large"/"small"/"open model" as "supplied analytical labels,
not independently audited parameter-count or software-licensing
determinations"), this analysis does not attempt to resolve `glm-5.2` or
`gemini-3.6-flash` parameter counts via outside search. `UNVERIFIED` is the
final answer for both fields, not a gap to be filled later.

## What downstream readers should and should not do with this file

- **Do** cite this file when reporting `n_models` per group for the
  open/closed comparison in `GROUPING_TESTS.md`.
- **Do not** describe the open/closed result as being about "open-source
  models" as a class — see the confound statement in `GROUPING_TESTS.md`.
- **Do not** construct a big/small comparison from this data using any
  parameter count not already in the table above. If a future need arises
  to resolve `glm-5.2`'s or `gemini-3.6-flash`'s size, that requires a
  primary source (an official model card or developer disclosure) cited by
  URL and version, not an inference from naming convention or general
  knowledge.

"""Fix for the NAIVE item-difficulty slope bootstrap.

BUG in the first pass: the generic cluster bootstrap resamples whole clusters
with replacement and hands the statistic a flat list of rows.  Any statistic
that RE-GROUPS those rows BY question_id then silently merges a cluster that
was drawn twice into one 8-cell "item", so the 0..4 difficulty score inflates
to 0..8 and the slope is biased toward zero.  Symptom: the reported 95% CI
[+0.0003,+0.0281] did not contain its own point estimate +0.1179.

Fix: tag every resampled cluster with the draw index and group on
(question_id, draw_index) so duplicate draws stay distinct items.

Statistics that only aggregate per-row quantities (medians, correlations,
logistic fits, the LOMO slopes) are unaffected -- their precomputed per-row
fields already carry the item context.
"""
import math, random
from collections import defaultdict
from mech_merge import load_merged
from mech_lib_effort import mean, quantile, MODELS

rows = load_merged()


def slope_from_items(items):
    """items: list of (diff_A, drop)."""
    xs = [a for a, _ in items]
    ys = [b for _, b in items]
    mx, my = mean(xs), mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den


def items_from_rows(rs):
    by = defaultdict(list)
    for r in rs:
        by[r["question_id"]].append(r)
    return [(sum(x["A_correct"] for x in g),
             mean([x["A_correct"] for x in g]) - mean([x["B_correct"] for x in g]))
            for g in by.values()]


point = slope_from_items(items_from_rows(rows))

# correct cluster bootstrap: keep duplicate cluster draws distinct
by_cluster = defaultdict(list)
for r in rows:
    by_cluster[r["cluster"]].append(r)
keys = list(by_cluster.keys())
K = len(keys)
rng = random.Random(61)
reps = []
for _ in range(4000):
    items = []
    for draw in range(K):
        cl = by_cluster[keys[rng.randrange(K)]]
        byq = defaultdict(list)
        for r in cl:
            byq[r["question_id"]].append(r)
        for g in byq.values():
            items.append((sum(x["A_correct"] for x in g),
                          mean([x["A_correct"] for x in g])
                          - mean([x["B_correct"] for x in g])))
    v = slope_from_items(items)
    if v is not None:
        reps.append(v)
reps.sort()

print("=" * 96)
print("NAIVE difficulty slope, corrected cluster bootstrap")
print("=" * 96)
print(f"  point estimate                  = {point:+.4f} drop per extra model-correct in A")
print(f"  cluster-bootstrap 95% CI        = [{quantile(reps,.025):+.4f}, "
      f"{quantile(reps,.975):+.4f}]  (4000 reps, percentile)")

# the same statistic under the no-item-effects parametric null
rng2 = random.Random(7)
accA = {m: mean([r["A_correct"] for r in rows if r["model"] == m]) for m in MODELS}
accB = {m: mean([r["B_correct"] for r in rows if r["model"] == m]) for m in MODELS}
sims = []
for _ in range(3000):
    by = defaultdict(list)
    for r in rows:
        by[r["question_id"]].append(
            (1 if rng2.random() < accA[r["model"]] else 0,
             1 if rng2.random() < accB[r["model"]] else 0))
    items = [(sum(a for a, _ in g),
              mean([a for a, _ in g]) - mean([b for _, b in g]))
             for g in by.values()]
    v = slope_from_items(items)
    if v is not None:
        sims.append(v)
sims.sort()
print(f"  PARAMETRIC NULL (independent Bernoulli at each model's marginal rate,")
print(f"  i.e. every item equally hard, A and B unlinked; 3000 draws):")
print(f"      expected slope = {mean(sims):+.4f}  "
      f"95% range [{quantile(sims,.025):+.4f}, {quantile(sims,.975):+.4f}]")
print(f"  observed {point:+.4f} is BELOW the pure-artifact expectation "
      f"{mean(sims):+.4f}")
frac = sum(1 for v in sims if v <= point) / len(sims)
print(f"      fraction of null draws <= observed = {frac:.4f}")
print()
print("  Interpretation: a naive 'harder items drop more' test on this design is")
print("  not merely contaminated -- the artifact is LARGER than the observed")
print("  gradient, so the naive statistic carries no usable signal about")
print("  difficulty.  Use the LOMO / retention analysis instead.")

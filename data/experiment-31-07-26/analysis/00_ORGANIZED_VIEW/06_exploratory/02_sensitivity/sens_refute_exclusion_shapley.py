#!/usr/bin/env python3
"""
sens_refute_exclusion_shapley.py

The claim decomposes the total headline shift S4-S1 by dropping posA FIRST.
That ordering is arbitrary and the decomposition is not order-invariant.  With
two rules there are exactly two orderings, so the Shapley value of each rule is
just the average of its two marginal contributions:

  Shapley(posA)   = [ (S3-S1) + (S4-S2) ] / 2
  Shapley(defect) = [ (S2-S1) + (S4-S3) ] / 2
  Shapley(posA) + Shapley(defect) = S4 - S1   exactly.

Shares are bootstrapped on the SAME paired cluster resamples (one draw of the
281 unfiltered clusters per replicate, all four filters recomputed on it).
95% percentile CI.  Pooled cells only -> fast.
"""

import json, os, math, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = json.load(open(os.path.join(HERE, "paired_clean.json")))
R, SEED = 20000, 7654321

SETS = {"S1": lambda r: True,
        "S2": lambda r: not r["excl_item_defect"],
        "S3": lambda r: not r["excl_nota_position_a"],
        "S4": lambda r: r["analysis_include"]}
SIDS = list(SETS)

agg = defaultdict(lambda: {s: [0, 0, 0] for s in SIDS})
for r in ROWS:
    for s, f in SETS.items():
        if f(r):
            t = agg[r["cluster"]][s]
            t[0] += 1; t[1] += r["A_correct"]; t[2] += r["B_correct"]
flat = [tuple(tuple(agg[c][s]) for s in SIDS) for c in sorted(agg)]
C = len(flat)


def d(tot):
    return {s: ((tot[i][2] - tot[i][1]) / tot[i][0] if tot[i][0] else None) for i, s in enumerate(SIDS)}


def acc_of(idxs):
    tot = [[0, 0, 0] for _ in SIDS]
    for ix in idxs:
        row = flat[ix]
        for i in range(len(SIDS)):
            tot[i][0] += row[i][0]; tot[i][1] += row[i][1]; tot[i][2] += row[i][2]
    return d(tot)


OBS = acc_of(range(C))
rng = random.Random(SEED)
reps = [acc_of([rng.randrange(C) for _ in range(C)]) for _ in range(R)]


def pct(v, q):
    v = sorted(v); i = q * (len(v) - 1)
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return v[lo] if lo == hi else v[lo] + (v[hi] - v[lo]) * (i - lo)


def ci_p(vals):
    nle = sum(1 for x in vals if x <= 0); nge = sum(1 for x in vals if x >= 0)
    return pct(vals, .025), pct(vals, .975), min(1.0, 2 * min(nle, nge) / len(vals))


def sh_posA(x):  return ((x["S3"] - x["S1"]) + (x["S4"] - x["S2"])) / 2
def sh_def(x):   return ((x["S2"] - x["S1"]) + (x["S4"] - x["S3"])) / 2
def total(x):    return x["S4"] - x["S1"]


print("=" * 96)
print("ORDER-AVERAGED (SHAPLEY) ATTRIBUTION OF THE TOTAL HEADLINE SHIFT S4-S1")
print("paired cluster bootstrap, R=20000, seed 7654321, 95% percentile CI")
print("=" * 96)
print(f"  total S4-S1                = {total(OBS):+.4f}")
for nm, fn in [("Shapley(posA rule)  ", sh_posA), ("Shapley(defect rule)", sh_def)]:
    vals = [fn(x) for x in reps]
    lo, hi, p = ci_p(vals)
    print(f"  {nm} = {fn(OBS):+.4f}  [{lo:+.4f},{hi:+.4f}]  p={p:.4f}")
print(f"  check: {sh_posA(OBS)+sh_def(OBS):+.6f} == {total(OBS):+.6f}")

print()
print("  SHARES (ratio estimator; denominator CI nearly touches 0 -> Fieller-unstable)")
for nm, fn in [("posA share  ", sh_posA), ("defect share", sh_def)]:
    vals = [fn(x) / total(x) for x in reps if abs(total(x)) > 1e-12]
    print(f"  {nm} = {fn(OBS)/total(OBS):6.1%}   95% CI [{pct(vals,.025):6.1%},{pct(vals,.975):6.1%}]"
          f"   80% CI [{pct(vals,.10):6.1%},{pct(vals,.90):6.1%}]")
vals = [sh_def(x) / total(x) for x in reps if abs(total(x)) > 1e-12]
print(f"  P(defect share > 5%)  = {sum(1 for v in vals if v > .05)/len(vals):.3f}")
print(f"  P(defect share > 10%) = {sum(1 for v in vals if v > .10)/len(vals):.3f}")
print(f"  P(defect share > 25%) = {sum(1 for v in vals if v > .25)/len(vals):.3f}")

print()
print("=" * 96)
print("PRACTICAL-SIGNIFICANCE FRAMING (the part of the claim that DOES survive)")
print("=" * 96)
print(f"  headline delta on the analysis set S4 = {OBS['S4']:+.4f}")
print(f"  defect rule's Shapley shift {sh_def(OBS):+.4f} = {abs(sh_def(OBS)/OBS['S4']):.2%} of the headline effect")
print(f"  posA rule's  Shapley shift {sh_posA(OBS):+.4f} = {abs(sh_posA(OBS)/OBS['S4']):.2%} of the headline effect")
print("  -> the defect rule is PRACTICALLY negligible for the pooled headline; that is a different")
print("     and much better-supported statement than 'statistically indistinguishable from zero'")
print("     or 'the posA rule does essentially 100% of the movement'.")

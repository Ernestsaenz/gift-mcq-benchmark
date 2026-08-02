#!/usr/bin/env python3
"""
sens_refute_exclusion_shares2.py -- follow-up to sens_refute_exclusion_shares.py

The pooled "defect rule does nothing" null is decomposed by model.  Same PAIRED
cluster bootstrap as before (one resample of the 281 unfiltered clusters per
replicate, all filters recomputed on that resample, contrasts formed
replicate-wise; 95% percentile CI; two-sided p = 2*min(P(d<=0),P(d>=0))).
R=20000, seed 987654321.

Also: raw per-model cell counts and deltas on the excluded subsets, so the
reader can see the cancellation directly without any resampling at all.
"""

import json, os, math, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = json.load(open(os.path.join(HERE, "paired_clean.json")))
MODELS = sorted(set(r["model"] for r in ROWS))
KEYS = ["*"] + MODELS
R, SEED = 20000, 987654321

ALL = {
    "S1_none":        lambda r: True,
    "S2_drop_defect": lambda r: not r["excl_item_defect"],
    "S3_drop_posA":   lambda r: not r["excl_nota_position_a"],
    "S4_drop_both":   lambda r: r["analysis_include"],
    "X_defect_only":  lambda r: r["excl_item_defect"],
    "X_posA_only":    lambda r: r["excl_nota_position_a"],
}
AIDS = list(ALL)

print("=" * 104)
print("(A) NO RESAMPLING AT ALL -- raw per-model deltas.  delta = mean(B_correct) - mean(A_correct)")
print("=" * 104)
print(f"  {'model':<24}{'n_all':>7}{'d_all':>9}{'n_def':>7}{'d_defect':>10}{'n_posA':>8}{'d_posA':>9}"
      f"{'d_kept(S2)':>12}{'shift S2-S1':>13}")
for k in KEYS:
    sel = ROWS if k == "*" else [r for r in ROWS if r["model"] == k]
    def d(rs):
        return (sum(r["B_correct"] for r in rs) - sum(r["A_correct"] for r in rs)) / len(rs) if rs else float("nan")
    dfc = [r for r in sel if r["excl_item_defect"]]
    pa = [r for r in sel if r["excl_nota_position_a"]]
    kept = [r for r in sel if not r["excl_item_defect"]]
    nm = "POOLED" if k == "*" else k.split("/")[-1]
    print(f"  {nm:<24}{len(sel):>7}{d(sel):>+9.4f}{len(dfc):>7}{d(dfc):>+10.4f}{len(pa):>8}{d(pa):>+9.4f}"
          f"{d(kept):>+12.4f}{d(kept)-d(sel):>+13.4f}")

# ------------------------------------------------------------- paired bootstrap
tab = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0, 0, 0])))
for r in ROWS:
    for sid, f in ALL.items():
        if not f(r):
            continue
        for k in (r["model"], "*"):
            t = tab[r["cluster"]][sid][k]
            t[0] += 1; t[1] += r["A_correct"]; t[2] += r["B_correct"]
clusters = sorted(tab); C = len(clusters)
flat = [[(sid, k, v[0], v[1], v[2]) for sid in AIDS for k, v in tab[c][sid].items()] for c in clusters]


def blank():
    return {s: {k: [0, 0, 0] for k in KEYS} for s in AIDS}


def deltas(acc):
    return {s: {k: ((acc[s][k][2] - acc[s][k][1]) / acc[s][k][0] if acc[s][k][0] else None)
                for k in KEYS} for s in AIDS}


A0 = blank()
for cf in flat:
    for (sid, k, n, sa, sb) in cf:
        a = A0[sid][k]; a[0] += n; a[1] += sa; a[2] += sb
OBS = deltas(A0)

rng = random.Random(SEED)
reps = []
for _ in range(R):
    acc = blank()
    for _ in range(C):
        for (sid, k, n, sa, sb) in flat[rng.randrange(C)]:
            a = acc[sid][k]; a[0] += n; a[1] += sa; a[2] += sb
    reps.append(deltas(acc))


def pct(v, q):
    v = sorted(v); i = q * (len(v) - 1)
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return v[lo] if lo == hi else v[lo] + (v[hi] - v[lo]) * (i - lo)


def ci_p(vals):
    lo, hi = pct(vals, 0.025), pct(vals, 0.975)
    nle = sum(1 for x in vals if x <= 0); nge = sum(1 for x in vals if x >= 0)
    return lo, hi, min(1.0, 2 * min(nle, nge) / len(vals)), sum(1 for x in vals if x == 0)


print()
print("=" * 104)
print("(B) PER-MODEL PAIRED CONTRASTS, FULL CIs (R=20000, seed 987654321)")
print("    'the defect rule's marginal contribution is not distinguishable from zero' is tested here")
print("=" * 104)
for a, b in [("S2_drop_defect", "S1_none"), ("S4_drop_both", "S3_drop_posA")]:
    print(f"\n  {a} - {b}")
    for k in KEYS:
        vals = [rep[a][k] - rep[b][k] for rep in reps if rep[a][k] is not None and rep[b][k] is not None]
        lo, hi, p, ties = ci_p(vals)
        obs = OBS[a][k] - OBS[b][k]
        nm = "POOLED" if k == "*" else k.split("/")[-1]
        flag = "  <-- CI EXCLUDES 0" if (lo > 0 or hi < 0) else ""
        print(f"    {nm:<24}{obs:+.4f}  [{lo:+.4f},{hi:+.4f}]  p={p:.4f}  ties@0={ties}{flag}")

print()
print("=" * 104)
print("(C) HETEROGENEITY OF THE DEFECT-RULE SHIFT ACROSS MODELS")
print("    max-minus-min of the per-model S2-S1 shift, paired cluster bootstrap")
print("=" * 104)
vals = []
for rep in reps:
    xs = [rep["S2_drop_defect"][m] - rep["S1_none"][m] for m in MODELS]
    vals.append(max(xs) - min(xs))
obs = max(OBS["S2_drop_defect"][m] - OBS["S1_none"][m] for m in MODELS) - \
      min(OBS["S2_drop_defect"][m] - OBS["S1_none"][m] for m in MODELS)
print(f"  observed spread = {obs:+.4f}   95% CI [{pct(vals,.025):+.4f},{pct(vals,.975):+.4f}]"
      f"   P(spread <= 0) = {sum(1 for x in vals if x <= 0)/len(vals):.4f}")
print(f"  for comparison, the POOLED total headline shift S4-S1 = "
      f"{OBS['S4_drop_both']['*'] - OBS['S1_none']['*']:+.4f}")
print("  -> a per-model spread of the same order as the entire pooled shift means the pooled")
print("     'null' is a cancellation of opposite-signed model-level effects, not their absence.")

print()
print("=" * 104)
print("(D) EQUIVALENCE FRAMING: what does the S2-S1 CI actually rule out?")
print("=" * 104)
lo, hi, p, _ = ci_p([rep["S2_drop_defect"]["*"] - rep["S1_none"]["*"] for rep in reps])
tot = OBS["S4_drop_both"]["*"] - OBS["S1_none"]["*"]
print(f"  S2-S1 = {OBS['S2_drop_defect']['*']-OBS['S1_none']['*']:+.4f}  CI [{lo:+.4f},{hi:+.4f}]")
print(f"  as a fraction of the total shift S4-S1={tot:+.4f}: point {(OBS['S2_drop_defect']['*']-OBS['S1_none']['*'])/tot:.1%},"
       f"  CI  [{lo/tot:.1%}, {hi/tot:.1%}]")
lo2, hi2, _, _ = ci_p([rep["S4_drop_both"]["*"] - rep["S3_drop_posA"]["*"] for rep in reps])
print(f"  S4-S3 = {OBS['S4_drop_both']['*']-OBS['S3_drop_posA']['*']:+.4f}  CI [{lo2:+.4f},{hi2:+.4f}]"
      f"  -> as fraction of total: [{lo2/tot:.1%}, {hi2/tot:.1%}]")
print("  The interval is NOT an equivalence interval: it fails to exclude contributions of up to")
print("  ~40% of the headline movement.  'Indistinguishable from zero' != 'shown to be ~zero'.")

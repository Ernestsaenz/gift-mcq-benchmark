#!/usr/bin/env python3
"""
sens_refute_exclusion_shares3.py

Fixes the one invalid test in sens_refute_exclusion_shares2.py section (C):
max(x)-min(x) is non-negative by construction, so P(spread<=0)~0 is vacuous.

Replaced with:
  (C1) proper pairwise between-model contrasts of the defect-rule shift
       [ (S2-S1)_i - (S2-S1)_j ], paired cluster bootstrap, 95% percentile CI,
       two-sided p = 2*min(P(d<=0),P(d>=0)).
  (C2) a permutation-style null for heterogeneity: recentre each model's shift
       at the pooled mean shift, then compare the observed spread to the
       bootstrap spread of the recentred (homogeneous) system.
  (C3) Holm step-down multiplicity control over the 4 per-model tests.
"""

import json, os, math, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = json.load(open(os.path.join(HERE, "paired_clean.json")))
MODELS = sorted(set(r["model"] for r in ROWS))
R, SEED = 20000, 424242

SETS = {
    "S1": lambda r: True,
    "S2": lambda r: not r["excl_item_defect"],
    "S3": lambda r: not r["excl_nota_position_a"],
    "S4": lambda r: r["analysis_include"],
}
SIDS = list(SETS)

tab = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0, 0, 0])))
for r in ROWS:
    for sid, f in SETS.items():
        if f(r):
            t = tab[r["cluster"]][sid][r["model"]]
            t[0] += 1; t[1] += r["A_correct"]; t[2] += r["B_correct"]
clusters = sorted(tab); C = len(clusters)
flat = [[(sid, k, v[0], v[1], v[2]) for sid in SIDS for k, v in tab[c][sid].items()] for c in clusters]


def blank():
    return {s: {m: [0, 0, 0] for m in MODELS} for s in SIDS}


def deltas(acc):
    return {s: {m: ((acc[s][m][2] - acc[s][m][1]) / acc[s][m][0] if acc[s][m][0] else None)
                for m in MODELS} for s in SIDS}


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
    nle = sum(1 for x in vals if x <= 0); nge = sum(1 for x in vals if x >= 0)
    return pct(vals, .025), pct(vals, .975), min(1.0, 2 * min(nle, nge) / len(vals))


def shift(rep, m, a="S2", b="S1"):
    return rep[a][m] - rep[b][m]


print("=" * 100)
print("(C1) BETWEEN-MODEL CONTRASTS OF THE DEFECT-RULE SHIFT (S2-S1)_i - (S2-S1)_j")
print("     paired cluster bootstrap, R=20000, seed 424242")
print("=" * 100)
for i in range(len(MODELS)):
    for j in range(i + 1, len(MODELS)):
        mi, mj = MODELS[i], MODELS[j]
        vals = [shift(rep, mi) - shift(rep, mj) for rep in reps]
        obs = shift(OBS, mi) - shift(OBS, mj)
        lo, hi, p = ci_p(vals)
        flag = "  <-- CI EXCLUDES 0" if (lo > 0 or hi < 0) else ""
        print(f"  {mi.split('/')[-1]:<20} - {mj.split('/')[-1]:<20} {obs:+.4f}  [{lo:+.4f},{hi:+.4f}]  p={p:.4f}{flag}")

print()
print("=" * 100)
print("(C2) HETEROGENEITY OF THE DEFECT-RULE SHIFT -- recentred-null spread test")
print("     statistic = max_m (S2-S1)_m  -  min_m (S2-S1)_m")
print("     null distribution = same bootstrap replicates with each model's shift recentred on the")
print("     mean across models (i.e. forced homogeneous), so the statistic keeps its sampling noise")
print("     but loses its true between-model signal.")
print("=" * 100)
obs_sp = max(shift(OBS, m) for m in MODELS) - min(shift(OBS, m) for m in MODELS)
null = []
for rep in reps:
    xs = [shift(rep, m) for m in MODELS]
    mu = sum(xs) / len(xs)
    obs_mu = sum(shift(OBS, m) for m in MODELS) / len(MODELS)
    ys = [x - mu for x in xs]              # recentred -> common mean 0
    null.append(max(ys) - min(ys))
p_het = sum(1 for x in null if x >= obs_sp) / len(null)
print(f"  observed spread = {obs_sp:+.4f}")
print(f"  recentred-null spread: median {pct(null,.5):+.4f}, 95th pct {pct(null,.95):+.4f}")
print(f"  one-sided p (null spread >= observed) = {p_het:.4f}")

print()
print("=" * 100)
print("(C3) HOLM STEP-DOWN over the 4 per-model tests of 'defect-rule shift == 0'")
print("=" * 100)
for a, b, lab in [("S2", "S1", "S2-S1  (defect rule alone)"),
                  ("S4", "S3", "S4-S3  (defect rule on top of posA)")]:
    print(f"\n  {lab}")
    res = []
    for m in MODELS:
        vals = [rep[a][m] - rep[b][m] for rep in reps]
        lo, hi, p = ci_p(vals)
        res.append((p, m, OBS[a][m] - OBS[b][m], lo, hi))
    res.sort()
    k = len(res)
    prev = 0.0
    for idx, (p, m, obs, lo, hi) in enumerate(res):
        adj = min(1.0, max(prev, (k - idx) * p)); prev = adj
        mark = "SIGNIFICANT after Holm" if adj < 0.05 else ""
        print(f"    {m.split('/')[-1]:<22}{obs:+.4f} [{lo:+.4f},{hi:+.4f}]  raw p={p:.4f}  Holm p={adj:.4f}  {mark}")

print()
print("=" * 100)
print("(C4) SIGN OF THE DEFECT-RULE SHIFT BY MODEL (is it one-directional, as 'a nuisance of size ~0'")
print("     would imply, or does it move different models in opposite directions?)")
print("=" * 100)
for a, b, lab in [("S2", "S1", "S2-S1"), ("S4", "S3", "S4-S3")]:
    signs = {m: shift(OBS, m, a, b) for m in MODELS}
    pos = [m.split("/")[-1] for m in MODELS if signs[m] > 0]
    neg = [m.split("/")[-1] for m in MODELS if signs[m] < 0]
    print(f"  {lab}:  positive (less degradation) -> {pos}")
    print(f"  {' '*len(lab)}   negative (MORE degradation) -> {neg}")
    frac = sum(1 for rep in reps
               if len({(shift(rep, m, a, b) > 0) for m in MODELS}) > 1) / R
    print(f"        bootstrap P(models do not all share one sign) = {frac:.3f}")

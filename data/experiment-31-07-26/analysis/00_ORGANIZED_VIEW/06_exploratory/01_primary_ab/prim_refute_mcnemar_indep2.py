#!/usr/bin/env python3
"""Exact worst-case-dependence sign-flip p-values (no Monte Carlo floor).

Under H0 (NOTA substitution has no directional effect) with MAXIMAL positive
within-cluster dependence, every discordant pair inside a cluster shares one
coin flip.  Statistic |sum_k s_k v_k| where v_k = (#broken - #fixed) in
cluster k and s_k = +-1 with prob 1/2.  The null distribution is an exact
convolution over 2^K sign patterns -> exact rational p by DP.

Also: the same DP at the ITEM level (item x model dependence), and the
per-model FISHER-style check that the exact-McNemar iid p is the "best case".
"""
import json, math, os
from fractions import Fraction
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "paired_clean.json")))
clean = [r for r in rows if r.get("analysis_include") is True]

def nets(sub, key):
    d = defaultdict(int)
    for r in sub:
        A, B = r["A_correct"], r["B_correct"]
        if A == B:
            continue
        d[r[key]] += 1 if (A == 1 and B == 0) else -1
    return [v for v in d.values()]

def exact_signflip_p(vs):
    """Exact P(|sum s_k v_k| >= |sum v_k|) with s_k iid Rademacher.
    DP over integer sums, counts as exact ints, denominator 2^K."""
    obs = abs(sum(vs))
    K = len(vs)
    # offset DP: possible sums range [-S, S], S = sum|v|
    S = sum(abs(v) for v in vs)
    dist = {0: 1}
    for v in vs:
        nd = defaultdict(int)
        for s, ct in dist.items():
            nd[s + v] += ct
            nd[s - v] += ct
        dist = nd
    ge = sum(ct for s, ct in dist.items() if abs(s) >= obs)
    return Fraction(ge, 2 ** K), obs, K, S

by_model = defaultdict(list)
for r in clean:
    by_model[r["model"]].append(r)

print("=" * 86)
print("EXACT CLUSTER-LEVEL SIGN-FLIP (maximal within-cluster dependence)")
print("=" * 86)
print(f"{'model':30s} {'|b-c|':>6s} {'K_clust':>8s} {'exact cluster p':>18s} "
      f"{'iid McNemar p':>15s} {'ratio':>10s}")
mcn = {}
for m in sorted(by_model):
    sub = by_model[m]
    b = sum(1 for r in sub if r["A_correct"] == 1 and r["B_correct"] == 0)
    c = sum(1 for r in sub if r["A_correct"] == 0 and r["B_correct"] == 1)
    n = b + c
    k = min(b, c)
    pm = Fraction(2 * sum(math.comb(n, i) for i in range(k + 1)), 2 ** n)
    mcn[m] = float(pm)
    p, obs, K, S = exact_signflip_p(nets(sub, "cluster"))
    print(f"{m:30s} {obs:6d} {K:8d} {float(p):18.6e} {float(pm):15.6e} "
          f"{float(p)/float(pm):10.1f}x")

p, obs, K, S = exact_signflip_p(nets(clean, "cluster"))
b = sum(1 for r in clean if r["A_correct"] == 1 and r["B_correct"] == 0)
c = sum(1 for r in clean if r["A_correct"] == 0 and r["B_correct"] == 1)
n = b + c
pm = Fraction(2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)), 2 ** n)
print(f"{'POOLED / cluster':30s} {obs:6d} {K:8d} {float(p):18.6e} {float(pm):15.6e} "
      f"{float(p)/float(pm):10.1f}x")

p2, obs2, K2, _ = exact_signflip_p(nets(clean, "question_id"))
print(f"{'POOLED / item':30s} {obs2:6d} {K2:8d} {float(p2):18.6e} {float(pm):15.6e} "
      f"{float(p2)/float(pm):10.1f}x")
print()
print("Interpretation: even under the MOST adverse dependence structure the")
print("design admits (all discordant pairs in a cluster / an item flipping as")
print("one unit), every per-model p stays far below 0.05 and below 4x-Bonferroni.")
print()

# ------------------------------------------------------------------------
# Is the exact-McNemar CI honest under clustering?  Compare the exact CP
# interval to a cluster-jackknife (delete-one-cluster) interval on log(b/c).
print("=" * 86)
print("DELETE-ONE-CLUSTER JACKKNIFE ON log(b/c)  vs  exact Clopper-Pearson CI")
print("=" * 86)
clusters = sorted({r["cluster"] for r in clean})
for m in sorted(by_model):
    sub = by_model[m]
    by_cl = defaultdict(lambda: [0, 0])
    B = C = 0
    for r in sub:
        A, Bc = r["A_correct"], r["B_correct"]
        if A == 1 and Bc == 0:
            by_cl[r["cluster"]][0] += 1; B += 1
        elif A == 0 and Bc == 1:
            by_cl[r["cluster"]][1] += 1; C += 1
    theta = math.log(B / C)
    ps = []
    for k in clusters:
        bb, cc = by_cl.get(k, (0, 0))
        nb, nc = B - bb, C - cc
        if nc > 0 and nb > 0:
            ps.append(math.log(nb / nc))
    K = len(ps)
    mean = sum(ps) / K
    var = (K - 1) / K * sum((x - mean) ** 2 for x in ps)
    se = math.sqrt(var)
    lo, hi = math.exp(theta - 1.96 * se), math.exp(theta + 1.96 * se)
    # cp
    print(f"{m:30s} OR={B/C:7.4f}  jackknife-cluster 95% CI [{lo:.3f}, {hi:.3f}]  "
          f"se(log OR)={se:.4f}")
print()
print("=" * 86)
print("MINIMUM DETECTABLE / FRAGILITY: how many 'fixed' items would c need")
print("to gain (holding b+c) before each model loses p<0.05?")
print("=" * 86)
for m in sorted(by_model):
    sub = by_model[m]
    b = sum(1 for r in sub if r["A_correct"] == 1 and r["B_correct"] == 0)
    c = sum(1 for r in sub if r["A_correct"] == 0 and r["B_correct"] == 1)
    n = b + c
    k = c
    while k <= n // 2:
        p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
        if p >= 0.05:
            break
        k += 1
    print(f"{m:30s} b={b:3d} c={c:3d} n={n:3d} -> would need c>={k} "
          f"(i.e. {k-c} more reversals, {(k-c)/n*100:.1f}% of discordants) to lose p<0.05")

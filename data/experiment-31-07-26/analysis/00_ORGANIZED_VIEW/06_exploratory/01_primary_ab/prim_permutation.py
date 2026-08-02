#!/usr/bin/env python3
"""
prim_permutation.py -- randomisation tests for the NOTA (none-of-the-above) swap.

Design: paired binary outcome. Condition A = verbatim item, condition B = same item
with the correct option's TEXT replaced by a NOTA string (letter unchanged).
Items are crossed with 4 models and nested in 208 clinical-context clusters.

Three sign-flip (randomisation) schemes, increasing conservatism:
  S1 CELL    : flip A/B independently within each item x model cell      (1299 units)
  S2 ITEM    : flip A/B for an item, all 4 models flip together          ( 325 units)
  S3 CLUSTER : flip A/B for a cluster, all cells in it flip together     ( 208 units)

Standard library only. No numpy/scipy.
"""

import json
import random
from collections import defaultdict, OrderedDict
from fractions import Fraction

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")

NPERM = 20000
SEED = 20260731

# ----------------------------------------------------------------------------
# Load + filter
# ----------------------------------------------------------------------------
with open(DATA) as fh:
    raw = json.load(fh)

rows = [r for r in raw if r["analysis_include"] is True]

print("=" * 78)
print("0. DATA INTEGRITY")
print("=" * 78)
print(f"rows in file                : {len(raw)}")
print(f"analysis_include == true    : {len(rows)}")
print(f"distinct question_id        : {len({r['question_id'] for r in rows})}")
print(f"distinct cluster            : {len({r['cluster'] for r in rows})}")
models = sorted({r["model"] for r in rows})
print(f"distinct model              : {len(models)} -> {models}")

# every cell must be a distinct (question_id, model) pair
keys = [(r["question_id"], r["model"]) for r in rows]
assert len(keys) == len(set(keys)), "duplicate item x model cells present"
# each item must be under exactly one cluster
i2c = {}
for r in rows:
    i2c.setdefault(r["question_id"], r["cluster"])
    assert i2c[r["question_id"]] == r["cluster"], "item spans >1 cluster"
print("uniqueness of (item, model) : OK")
print("item -> cluster is a function: OK")

# ----------------------------------------------------------------------------
# 1. Observed rates  (method: unweighted proportion over cells)
# ----------------------------------------------------------------------------
print()
print("=" * 78)
print("1. OBSERVED RATES  (recomputed from paired_clean.json)")
print("=" * 78)

by_model = defaultdict(list)
for r in rows:
    by_model[r["model"]].append(r)

def rates(rs):
    n = len(rs)
    a = sum(r["A_correct"] for r in rs)
    b = sum(r["B_correct"] for r in rs)
    return n, a, b, a / n, b / n, (a - b) / n

print(f"{'model':<26}{'n':>6}{'A%':>9}{'B%':>9}{'delta_pp':>11}"
      f"{'b(A1B0)':>9}{'c(A0B1)':>9}")
obs = OrderedDict()
disc = OrderedDict()   # model -> (b, c)
for m in models:
    rs = by_model[m]
    n, ca, cb, pa, pb, d = rates(rs)
    b_ = sum(1 for r in rs if r["A_correct"] == 1 and r["B_correct"] == 0)
    c_ = sum(1 for r in rs if r["A_correct"] == 0 and r["B_correct"] == 1)
    obs[m] = d
    disc[m] = (b_, c_)
    print(f"{m:<26}{n:>6}{pa*100:>9.2f}{pb*100:>9.2f}{d*100:>11.2f}{b_:>9}{c_:>9}")

n_all, ca, cb, pa, pb, d_all = rates(rows)
b_all = sum(1 for r in rows if r["A_correct"] == 1 and r["B_correct"] == 0)
c_all = sum(1 for r in rows if r["A_correct"] == 0 and r["B_correct"] == 1)
obs["POOLED"] = d_all
disc["POOLED"] = (b_all, c_all)
print(f"{'POOLED':<26}{n_all:>6}{pa*100:>9.2f}{pb*100:>9.2f}{d_all*100:>11.2f}"
      f"{b_all:>9}{c_all:>9}")
LEVELS = list(obs.keys())

# ----------------------------------------------------------------------------
# 2. Exact McNemar (analytic counterpart of the CELL-level permutation)
#    method: conditional on b+c discordant pairs, #(A>B) ~ Binom(b+c, 1/2).
#    Two-sided p = 2 * P(X <= min(b,c)), capped at 1. Exact rational arithmetic.
# ----------------------------------------------------------------------------
def binom_tail_exact(k, n):
    """P(X <= k) for X ~ Binom(n, 1/2), exact Fraction."""
    if n == 0:
        return Fraction(1)
    tot = 0
    for i in range(k + 1):
        # C(n,i)
        c = 1
        for j in range(i):
            c = c * (n - j) // (j + 1)
        tot += c
    return Fraction(tot, 1 << n)

print()
print("=" * 78)
print("2. EXACT McNEMAR  (analytic check on scheme S1; sign test on discordants)")
print("=" * 78)
print(f"{'level':<26}{'b':>7}{'c':>7}{'b+c':>7}{'p_exact_2sided':>20}")
mcnemar = {}
for lv in LEVELS:
    b_, c_ = disc[lv]
    nd = b_ + c_
    p = min(Fraction(1), 2 * binom_tail_exact(min(b_, c_), nd))
    mcnemar[lv] = float(p)
    print(f"{lv:<26}{b_:>7}{c_:>7}{nd:>7}{float(p):>20.3e}")

# ----------------------------------------------------------------------------
# Permutation machinery
# ----------------------------------------------------------------------------
# d_i = A_correct - B_correct in {-1,0,+1}. Flipping the A/B label negates d_i.
# Statistic for level L = (1/n_L) * sum_{i in L} s_i * d_i, s_i in {-1,+1}.
for r in rows:
    r["_d"] = r["A_correct"] - r["B_correct"]

N = {m: len(by_model[m]) for m in models}
N["POOLED"] = n_all

def summarise(obs_val, null_vals, label):
    """Two-sided p = (1 + #{|T*| >= |T_obs|}) / (B + 1)."""
    B = len(null_vals)
    a = abs(obs_val)
    tol = 1e-12
    hits = sum(1 for v in null_vals if abs(v) >= a - tol)
    p = (1 + hits) / (B + 1)
    mean = sum(null_vals) / B
    var = sum((v - mean) ** 2 for v in null_vals) / (B - 1)
    sd = var ** 0.5
    z = (obs_val - mean) / sd if sd > 0 else float("nan")
    # Monte-Carlo SE of the p-value estimate
    mcse = ((p * (1 - p)) / B) ** 0.5
    return dict(label=label, obs=obs_val, hits=hits, B=B, p=p, mcse=mcse,
                null_mean=mean, null_sd=sd, z=z)

def report(res_by_level, title, note):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)
    print(note)
    print(f"{'level':<26}{'obs_pp':>10}{'null_sd_pp':>12}{'z':>8}"
          f"{'hits':>7}{'p':>12}{'+-MCSE':>10}")
    for lv in LEVELS:
        r = res_by_level[lv]
        print(f"{lv:<26}{r['obs']*100:>10.2f}{r['null_sd']*100:>12.3f}"
              f"{r['z']:>8.2f}{r['hits']:>7}{r['p']:>12.5f}{r['mcse']:>10.5f}")

# ----------------------------------------------------------------------------
# S1: CELL-level sign flip
# ----------------------------------------------------------------------------
# Only discordant cells (d != 0) move the statistic; concordant cells contribute
# 0 under every relabelling. Since d_i = +-1 on discordants and s_i is uniform
# +-1, the products s_i*d_i are i.i.d. Rademacher -- so the null draw for a level
# with n_disc discordants is (2*Binom(n_disc,1/2) - n_disc)/n. We still draw the
# raw bits (one per discordant cell) so the pooled and per-model statistics come
# from the SAME realised relabelling, exactly as a real permutation would.
rng = random.Random(SEED)
disc_cells_by_model = {m: [r for r in by_model[m] if r["_d"] != 0] for m in models}
nd_by_model = {m: len(disc_cells_by_model[m]) for m in models}

print()
print("S1 discordant-cell counts:",
      {m.split('/')[-1]: nd_by_model[m] for m in models},
      "pooled:", sum(nd_by_model.values()))

s1 = {lv: [] for lv in LEVELS}
for _ in range(NPERM):
    pooled_sum = 0
    for m in models:
        nd = nd_by_model[m]
        # nd independent fair bits; bit=1 -> s=+1, bit=0 -> s=-1
        bits = rng.getrandbits(nd) if nd else 0
        k = bits.bit_count()
        ssum = 2 * k - nd          # sum of s_i * d_i over this model's cells
        s1[m].append(ssum / N[m])
        pooled_sum += ssum
    s1["POOLED"].append(pooled_sum / N["POOLED"])

s1res = {lv: summarise(obs[lv], s1[lv], lv) for lv in LEVELS}
report(s1res, f"3. SCHEME S1 -- CELL-level sign flip ({NPERM} permutations)",
       "exchangeable unit = one item x model cell (1299 units); "
       "null: within a cell the A/B labels are swappable")

# ----------------------------------------------------------------------------
# S2: ITEM-level sign flip (all 4 models for an item flip together)
# ----------------------------------------------------------------------------
items = sorted({r["question_id"] for r in rows})
item_idx = {q: i for i, q in enumerate(items)}
# D_item[q][m] = sum of d over that item's cells for model m (0 or 1 cell)
D_item = [defaultdict(int) for _ in items]
for r in rows:
    D_item[item_idx[r["question_id"]]][r["model"]] += r["_d"]
# keep only items that can move anything
item_vecs = []
for q in items:
    dd = D_item[item_idx[q]]
    vec = tuple(dd.get(m, 0) for m in models)
    if any(vec):
        item_vecs.append(vec)

rng = random.Random(SEED + 1)
s2 = {lv: [] for lv in LEVELS}
n_iv = len(item_vecs)
mi = list(range(len(models)))
for _ in range(NPERM):
    bits = rng.getrandbits(n_iv)
    acc = [0] * len(models)
    for j, vec in enumerate(item_vecs):
        s = 1 if (bits >> j) & 1 else -1
        for k in mi:
            if vec[k]:
                acc[k] += s * vec[k]
    for k, m in enumerate(models):
        s2[m].append(acc[k] / N[m])
    s2["POOLED"].append(sum(acc) / N["POOLED"])

s2res = {lv: summarise(obs[lv], s2[lv], lv) for lv in LEVELS}
report(s2res, f"4. SCHEME S2 -- ITEM-level sign flip ({NPERM} permutations)",
       f"exchangeable unit = one item, all 4 models flip together "
       f"({n_iv} items with any discordance, of {len(items)}); "
       "respects item x model dependence")

# ----------------------------------------------------------------------------
# S3: CLUSTER-level sign flip (all cells in a cluster flip together)
# ----------------------------------------------------------------------------
clusters = sorted({r["cluster"] for r in rows})
cl_idx = {c: i for i, c in enumerate(clusters)}
D_cl = [defaultdict(int) for _ in clusters]
for r in rows:
    D_cl[cl_idx[r["cluster"]]][r["model"]] += r["_d"]
cl_vecs = []
for c in clusters:
    dd = D_cl[cl_idx[c]]
    vec = tuple(dd.get(m, 0) for m in models)
    if any(vec):
        cl_vecs.append(vec)

rng = random.Random(SEED + 2)
s3 = {lv: [] for lv in LEVELS}
n_cv = len(cl_vecs)
for _ in range(NPERM):
    bits = rng.getrandbits(n_cv)
    acc = [0] * len(models)
    for j, vec in enumerate(cl_vecs):
        s = 1 if (bits >> j) & 1 else -1
        for k in mi:
            if vec[k]:
                acc[k] += s * vec[k]
    for k, m in enumerate(models):
        s3[m].append(acc[k] / N[m])
    s3["POOLED"].append(sum(acc) / N["POOLED"])

s3res = {lv: summarise(obs[lv], s3[lv], lv) for lv in LEVELS}
report(s3res, f"5. SCHEME S3 -- CLUSTER-level sign flip ({NPERM} permutations)",
       f"exchangeable unit = one clinical-context cluster, every cell in it "
       f"flips together ({n_cv} clusters with any discordance, of "
       f"{len(clusters)}); robust to arbitrary within-cluster dependence")

# ----------------------------------------------------------------------------
# 6. Variance inflation: how much does coarsening the unit widen the null?
# ----------------------------------------------------------------------------
print()
print("=" * 78)
print("6. NULL-DISTRIBUTION WIDTH BY SCHEME  (design-effect diagnostic)")
print("=" * 78)
print(f"{'level':<26}{'sd_S1_pp':>11}{'sd_S2_pp':>11}{'sd_S3_pp':>11}"
      f"{'S2/S1':>8}{'S3/S1':>8}")
for lv in LEVELS:
    a, b_, c_ = s1res[lv]["null_sd"], s2res[lv]["null_sd"], s3res[lv]["null_sd"]
    print(f"{lv:<26}{a*100:>11.4f}{b_*100:>11.4f}{c_*100:>11.4f}"
          f"{b_/a:>8.3f}{c_/a:>8.3f}")

# ----------------------------------------------------------------------------
# 7. Resolution floor of each scheme
# ----------------------------------------------------------------------------
print()
print("=" * 78)
print("7. SMALLEST ATTAINABLE p AND EXTREME-TAIL CHECK")
print("=" * 78)
print(f"min attainable p with B={NPERM} permutations: {1/(NPERM+1):.3e}")
print(f"{'level':<26}{'S1 max|T*|pp':>15}{'S2 max|T*|pp':>15}"
      f"{'S3 max|T*|pp':>15}{'obs|T|pp':>11}")
for lv in LEVELS:
    print(f"{lv:<26}"
          f"{max(abs(v) for v in s1[lv])*100:>15.3f}"
          f"{max(abs(v) for v in s2[lv])*100:>15.3f}"
          f"{max(abs(v) for v in s3[lv])*100:>15.3f}"
          f"{abs(obs[lv])*100:>11.3f}")

# exact one-sided cluster-level bound for POOLED: how many of the 208 cluster
# totals point the same way, and what is the sign-test p on cluster totals?
print()
print("Cluster-total sign test (POOLED, exact binomial on cluster D values):")
Dc_pooled = [sum(v) for v in cl_vecs]
pos = sum(1 for x in Dc_pooled if x > 0)
neg = sum(1 for x in Dc_pooled if x < 0)
nd_c = pos + neg
p_cl = min(Fraction(1), 2 * binom_tail_exact(min(pos, neg), nd_c))
print(f"  clusters with A>B: {pos}   A<B: {neg}   ties: {len(cl_vecs)-nd_c}"
      f"   exact 2-sided p = {float(p_cl):.3e}")

# ----------------------------------------------------------------------------
# 8. Dump machine-readable results
# ----------------------------------------------------------------------------
out = {"nperm": NPERM, "seed": SEED, "n_cells": n_all,
       "n_items": len(items), "n_clusters": len(clusters),
       "observed_delta_pp": {lv: obs[lv] * 100 for lv in LEVELS},
       "discordant_bc": {lv: disc[lv] for lv in LEVELS},
       "mcnemar_exact_p": mcnemar,
       "S1_cell": {lv: {k: v for k, v in s1res[lv].items() if k != "label"}
                   for lv in LEVELS},
       "S2_item": {lv: {k: v for k, v in s2res[lv].items() if k != "label"}
                   for lv in LEVELS},
       "S3_cluster": {lv: {k: v for k, v in s3res[lv].items() if k != "label"}
                      for lv in LEVELS}}
dest = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/prim_permutation_results.json")
with open(dest, "w") as fh:
    json.dump(out, fh, indent=1)
print(f"\nwrote {dest}")

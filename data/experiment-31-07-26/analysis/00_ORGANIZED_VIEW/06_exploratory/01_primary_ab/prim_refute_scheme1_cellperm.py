#!/usr/bin/env python
"""
INDEPENDENT REFUTATION SCRIPT for the SCHEME-1 (cell-level sign-flip permutation) claim.

Nothing is imported from any existing prim_*/stats_* module on purpose.
Standard library only. Exact integer / Fraction arithmetic.

What we recompute from scratch:
  1. Shape of the clean subset (cells, items, clusters, models) and the A/B accuracies.
  2. Per-model and pooled discordance counts b, c and K = b + c.
  3. EXACT two-sided sign-flip permutation p via integer convolution DP over all 2^K
     sign vectors, statistic T = sum_u s_u * D_u, D_u = A_correct - B_correct.
  4. EXACT binomial McNemar p = 2 * P(X <= min(b,c)), X ~ Binom(b+c, 1/2), in Fractions.
  5. Null SD of T rescaled to percentage points.
  6. A brute-force cross-check of the DP on small K, and a Monte-Carlo cross-check.
  7. The dependence-structure question: is the cell-level scheme's independence
     assumption defensible given the crossed item x model design?
"""

import json
import random
from fractions import Fraction
from collections import defaultdict
from itertools import product

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")

# ----------------------------------------------------------------------------
# 1. Load + shape
# ----------------------------------------------------------------------------
with open(DATA) as fh:
    raw = json.load(fh)

rows = [r for r in raw if r.get("analysis_include") is True]

print("=" * 78)
print("1. SHAPE OF CLEAN SUBSET")
print("=" * 78)
print(f"rows total in file        : {len(raw)}")
print(f"rows analysis_include=T   : {len(rows)}")
print(f"distinct question_id      : {len(set(r['question_id'] for r in rows))}")
print(f"distinct cluster          : {len(set(r['cluster'] for r in rows))}")
models = sorted(set(r["model"] for r in rows))
print(f"distinct model            : {len(models)} -> {models}")

# cells per model -- the 1299 vs 4*325=1300 question
per_model_n = defaultdict(int)
for r in rows:
    per_model_n[r["model"]] += 1
print("\ncells per model:")
for m in models:
    print(f"  {m:28s} n = {per_model_n[m]}")
print(f"  sum = {sum(per_model_n.values())}   (4 x 325 would be 1300)")

# which item is missing a model?
items = sorted(set(r["question_id"] for r in rows))
seen = defaultdict(set)
for r in rows:
    seen[r["question_id"]].add(r["model"])
incomplete = {q: sorted(set(models) - v) for q, v in seen.items() if len(v) != 4}
print(f"\nitems NOT observed under all 4 models: {len(incomplete)}")
for q, miss in sorted(incomplete.items()):
    print(f"  question_id={q!r} missing {miss}")

# ----------------------------------------------------------------------------
# 2. Accuracies + discordance
# ----------------------------------------------------------------------------
print()
print("=" * 78)
print("2. ACCURACIES AND DISCORDANCE (recomputed)")
print("=" * 78)


def summarize(sub):
    n = len(sub)
    a = sum(r["A_correct"] for r in sub)
    b_ = sum(r["B_correct"] for r in sub)
    # b = A right / B wrong ; c = A wrong / B right
    b = sum(1 for r in sub if r["A_correct"] == 1 and r["B_correct"] == 0)
    c = sum(1 for r in sub if r["A_correct"] == 0 and r["B_correct"] == 1)
    return dict(n=n, accA=a / n, accB=b_ / n, delta=(b_ - a) / n, b=b, c=c, K=b + c)


stats = {}
print(f"{'model':30s} {'n':>5s} {'A%':>7s} {'B%':>7s} {'delta pp':>9s} "
      f"{'b':>4s} {'c':>4s} {'K':>4s}")
for m in models:
    s = summarize([r for r in rows if r["model"] == m])
    stats[m] = s
    print(f"{m:30s} {s['n']:5d} {100*s['accA']:7.2f} {100*s['accB']:7.2f} "
          f"{100*s['delta']:9.2f} {s['b']:4d} {s['c']:4d} {s['K']:4d}")
s = summarize(rows)
stats["POOLED"] = s
print(f"{'POOLED':30s} {s['n']:5d} {100*s['accA']:7.2f} {100*s['accB']:7.2f} "
      f"{100*s['delta']:9.2f} {s['b']:4d} {s['c']:4d} {s['K']:4d}")

print("\nsum of per-model K =", sum(stats[m]["K"] for m in models),
      " vs pooled K =", stats["POOLED"]["K"])

# ----------------------------------------------------------------------------
# 3. EXACT sign-flip permutation via integer convolution DP
# ----------------------------------------------------------------------------
print()
print("=" * 78)
print("3. EXACT CELL-LEVEL SIGN-FLIP PERMUTATION (integer convolution DP)")
print("=" * 78)


def exact_signflip(D):
    """
    D: list of per-cell differences A_correct - B_correct, in {-1,0,+1}.
    Statistic T = sum_u s_u * D_u with s_u iid uniform on {-1,+1},
    independently for every cell (SCHEME 1 = cell-level).
    Returns (T_obs, K, p_two_sided as Fraction, null variance of T).

    counts[t] = number of the 2^K sign vectors (over the K non-zero cells)
    that give T = t.  Zero cells contribute nothing to T but DO multiply the
    total sign-vector count by 2 each; that cancels in the ratio, so we
    enumerate only the K discordant cells and normalise by 2^K.
    """
    nz = [d for d in D if d != 0]
    K = len(nz)
    T_obs = sum(D)
    # DP over offsets: shift index by K so range is [0, 2K]
    counts = [0] * (2 * K + 1)
    counts[K] = 1  # T = 0 with 1 way (empty product)
    for _ in range(K):          # every non-zero |d| == 1, sign is flipped anyway
        nxt = [0] * (2 * K + 1)
        for i, v in enumerate(counts):
            if v:
                nxt[i - 1] += v   # s_u * d_u = -1
                nxt[i + 1] += v   # s_u * d_u = +1
        counts = nxt
    total = 1 << K
    assert sum(counts) == total, "DP lost mass"
    thr = abs(T_obs)
    extreme = sum(v for i, v in enumerate(counts) if abs(i - K) >= thr)
    p = Fraction(extreme, total)
    # null variance: E[T]=0, Var = sum d_u^2 = K
    return T_obs, K, p, K


def exact_mcnemar(b, c):
    """2 * P(X <= min(b,c)), X ~ Binom(b+c, 1/2), exact Fractions, capped at 1."""
    n = b + c
    m = min(b, c)
    # sum_{k=0}^{m} C(n,k) / 2^n
    from math import comb
    tail = sum(comb(n, k) for k in range(m + 1))
    p = Fraction(2 * tail, 1 << n)
    return min(p, Fraction(1))


CLAIMED = {
    "google/gemini-3.6-flash": (3.4655e-06, 35, 1.82),
    "qwen/qwen3.6-35b-a3b":    (5.2573e-09, 82, 2.79),
    "google/gemma-4-26b-a4b-it": (6.1478e-11, 100, 3.08),
    "z-ai/glm-5.2":            (1.0099e-12, 75, 2.67),
    "POOLED":                  (6.2745e-35, 292, 1.32),
}

print(f"{'group':30s} {'K':>4s} {'T_obs':>6s} {'p_perm(exact)':>16s} "
      f"{'p_McNemar(exact)':>18s} {'match':>6s} {'nullSD_pp':>10s}")
results = {}
for key in models + ["POOLED"]:
    sub = rows if key == "POOLED" else [r for r in rows if r["model"] == key]
    D = [r["A_correct"] - r["B_correct"] for r in sub]
    T_obs, K, p_perm, var = exact_signflip(D)
    b, c = stats[key]["b"], stats[key]["c"]
    p_mc = exact_mcnemar(b, c)
    identical = (p_perm == p_mc)
    null_sd_pp = 100.0 * (var ** 0.5) / len(sub)
    results[key] = dict(K=K, T_obs=T_obs, p_perm=float(p_perm),
                        p_mcnemar=float(p_mc), identical=identical,
                        null_sd_pp=null_sd_pp, n=len(sub), b=b, c=c,
                        p_perm_exact=p_perm)
    print(f"{key:30s} {K:4d} {T_obs:6d} {float(p_perm):16.6e} "
          f"{float(p_mc):18.6e} {str(identical):>6s} {null_sd_pp:10.4f}")

print()
print("Claimed vs recomputed:")
print(f"{'group':30s} {'K_claim':>8s} {'K_mine':>7s} {'p_claim':>14s} "
      f"{'p_mine':>14s} {'rel.err':>10s} {'SD_claim':>9s} {'SD_mine':>8s}")
for key in models + ["POOLED"]:
    pc, kc, sdc = CLAIMED[key]
    r = results[key]
    rel = abs(r["p_perm"] - pc) / pc
    print(f"{key:30s} {kc:8d} {r['K']:7d} {pc:14.4e} {r['p_perm']:14.4e} "
          f"{rel:10.2e} {sdc:9.2f} {r['null_sd_pp']:8.2f}")

# ----------------------------------------------------------------------------
# 4. Cross-checks of the DP itself
# ----------------------------------------------------------------------------
print()
print("=" * 78)
print("4. CROSS-CHECKS OF THE DP")
print("=" * 78)

# (a) brute force over all 2^K sign vectors for small synthetic K
ok = True
for K in range(1, 15):
    for b in range(K + 1):
        c = K - b
        D = [1] * b + [-1] * c
        T_obs = sum(D)
        brute_extreme = 0
        for signs in product((-1, 1), repeat=K):
            T = sum(s * d for s, d in zip(signs, D))
            if abs(T) >= abs(T_obs):
                brute_extreme += 1
        p_brute = Fraction(brute_extreme, 1 << K)
        _, _, p_dp, _ = exact_signflip(D)
        if p_brute != p_dp:
            ok = False
            print(f"  MISMATCH brute vs DP at K={K} b={b}: {p_brute} vs {p_dp}")
print(f"(a) brute force vs DP, all (K<=14, b) combos exhaustively: "
      f"{'ALL MATCH' if ok else 'FAILED'}")

# (b) DP vs exact-binomial McNemar for a wide grid, incl. the b == c edge case
mismatch_bc = []
for K in range(1, 60):
    for b in range(K + 1):
        c = K - b
        D = [1] * b + [-1] * c
        _, _, p_dp, _ = exact_signflip(D)
        p_mc = exact_mcnemar(b, c)
        if p_dp != p_mc:
            mismatch_bc.append((K, b, c, float(p_dp), float(p_mc)))
print(f"(b) DP vs exact binomial McNemar over K=1..59, all b: "
      f"{len(mismatch_bc)} mismatches")
for mm in mismatch_bc[:8]:
    print(f"      K={mm[0]} b={mm[1]} c={mm[2]}  p_dp={mm[3]:.6f} p_mc={mm[4]:.6f}")
if mismatch_bc:
    print("      (all mismatches are the b==c tie case, where the uncapped "
          "2*P(X<=min) formula exceeds 1)")
    print("      b==c only? ",
          all(mm[1] == mm[2] for mm in mismatch_bc))

# (c) Monte-Carlo sign-flip for the one model where p is large enough to hit
rng = random.Random(20260731)
key = "google/gemini-3.6-flash"
D = [r["A_correct"] - r["B_correct"] for r in rows if r["model"] == key]
nz = [d for d in D if d != 0]
T_obs = sum(D)
NSIM = 4_000_000
hits = 0
tsum = 0.0
tsq = 0.0
for _ in range(NSIM):
    T = 0
    for d in nz:
        T += d if rng.getrandbits(1) else -d
    tsum += T
    tsq += T * T
    if abs(T) >= abs(T_obs):
        hits += 1
mc_p = hits / NSIM
mc_sd = (tsq / NSIM - (tsum / NSIM) ** 2) ** 0.5
print(f"(c) Monte-Carlo sign-flip, {key}, {NSIM:,} draws:")
print(f"      hits = {hits}  ->  p_MC = {mc_p:.3e}   (exact = "
      f"{results[key]['p_perm']:.3e})")
print(f"      MC null SD of T = {mc_sd:.4f}  vs theoretical sqrt(K) = "
      f"{results[key]['K'] ** 0.5:.4f}")
print(f"      MC null SD on pp scale = "
      f"{100 * mc_sd / results[key]['n']:.4f}")

# ----------------------------------------------------------------------------
# 5. Is the null SD denominator the right one?
# ----------------------------------------------------------------------------
print()
print("=" * 78)
print("5. NULL SD ON THE pp SCALE -- denominator check")
print("=" * 78)
for key in models + ["POOLED"]:
    r = results[key]
    print(f"{key:30s} sqrt(K)={r['K']**0.5:8.4f}  n={r['n']:5d}  "
          f"100*sqrt(K)/n = {100*r['K']**0.5/r['n']:7.4f}  "
          f"(claim {CLAIMED[key][2]})")

# ----------------------------------------------------------------------------
# 6. DEPENDENCE STRUCTURE -- what SCHEME 1 assumes vs what the design is
# ----------------------------------------------------------------------------
print()
print("=" * 78)
print("6. DEPENDENCE STRUCTURE: cell-level flips vs the crossed design")
print("=" * 78)
print("SCHEME 1 flips the A/B label independently in each item x model cell.")
print("But condition B is ONE physically-modified item shown to all 4 models,")
print("so an item's A/B assignment is shared across its 4 cells.  Below: how")
print("much the pooled null SD grows if the flip is constrained to the item")
print("level (all 4 cells of an item flip together), which is what the actual")
print("design would license.")

by_item = defaultdict(list)
for r in rows:
    by_item[r["question_id"]].append(r["A_correct"] - r["B_correct"])

# cell-level pooled null variance
var_cell = sum(1 for r in rows if r["A_correct"] != r["B_correct"])
# item-level pooled null variance: Var(sum_i s_i * S_i) = sum_i S_i^2, S_i = sum of D over the item's cells
var_item = sum(sum(v) ** 2 for v in by_item.values())
n_pool = len(rows)
print(f"\n  pooled T_obs                      = {sum(sum(v) for v in by_item.values())}")
print(f"  cell-level  null Var(T) = K       = {var_cell}   "
      f"SD = {var_cell**0.5:.3f}   -> {100*var_cell**0.5/n_pool:.3f} pp")
print(f"  item-level  null Var(T) = sum S^2 = {var_item}   "
      f"SD = {var_item**0.5:.3f}   -> {100*var_item**0.5/n_pool:.3f} pp")
print(f"  variance inflation factor (item / cell) = {var_item/var_cell:.3f}")

# cluster-level too
by_cluster = defaultdict(int)
for r in rows:
    by_cluster[r["cluster"]] += r["A_correct"] - r["B_correct"]
var_clust = sum(v ** 2 for v in by_cluster.values())
print(f"  cluster-level null Var(T)         = {var_clust}   "
      f"SD = {var_clust**0.5:.3f}   -> {100*var_clust**0.5/n_pool:.3f} pp")
print(f"  variance inflation factor (cluster / cell) = {var_clust/var_cell:.3f}")

# normal-approx z under each scheme, pooled, just to show the ordering
T_pool = sum(sum(v) for v in by_item.values())
for nm, v in (("cell", var_cell), ("item", var_item), ("cluster", var_clust)):
    print(f"  pooled normal-approx z, {nm:7s} scheme = {T_pool / v**0.5:8.3f}")

print()
print("Per-model, the item-level and cell-level schemes coincide exactly")
print("(one cell per item within a model), so per-model p-values are")
print("unaffected by this concern; only the POOLED number is.")
for m in models:
    sub = [r for r in rows if r["model"] == m]
    vc = sum(1 for r in sub if r["A_correct"] != r["B_correct"])
    bi = defaultdict(int)
    for r in sub:
        bi[r["question_id"]] += r["A_correct"] - r["B_correct"]
    vi = sum(v ** 2 for v in bi.values())
    print(f"  {m:30s} Var_cell={vc:4d}  Var_item={vi:4d}  equal={vc==vi}")

# ----------------------------------------------------------------------------
# 7. Save
# ----------------------------------------------------------------------------
out = {
    "n_cells": len(rows),
    "n_items": len(items),
    "n_clusters": len(set(r["cluster"] for r in rows)),
    "per_model_n": dict(per_model_n),
    "incomplete_items": {k: v for k, v in incomplete.items()},
    "results": {k: {kk: vv for kk, vv in v.items() if kk != "p_perm_exact"}
                for k, v in results.items()},
    "accuracies": {k: {kk: vv for kk, vv in v.items()} for k, v in stats.items()},
    "dependence": {
        "pooled_T": T_pool,
        "var_cell": var_cell, "var_item": var_item, "var_cluster": var_clust,
        "vif_item_over_cell": var_item / var_cell,
        "vif_cluster_over_cell": var_clust / var_cell,
    },
    "mc_check": {"model": key, "nsim": NSIM, "p_mc": mc_p, "sd_mc": mc_sd},
}
with open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
          "experiment-31-07-26/analysis/prim_refute_scheme1_out.json", "w") as fh:
    json.dump(out, fh, indent=2, default=str)
print("\nwrote prim_refute_scheme1_out.json")

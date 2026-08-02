"""PRIMARY cross-arm inference: GIFT (RAG) vs OpenRouter (direct), condition A.

Per model and pooled:
  * exact McNemar (conditional binomial on the discordant pairs, math.comb)
  * cluster bootstrap CI for the risk difference over the 183 item clusters
  * permutation test swapping the arm label (three dependence levels)
  * discordant (conditional) odds ratio with an exact CI
  * Holm correction across the 4 per-model tests
"""
import json, os, sys, math, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_prim_lib import (mcnemar_exact, mcnemar_chi2, discordant_or, holm,
                         LCG, percentile, bca, phi, phi_inv)

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, 'cross_arm_A.json')
SEED = 20260731
B_BOOT = 20000
R_PERM = 50000
ALPHA = 0.05

rows_all = json.load(open(SRC))
rows = [r for r in rows_all if r.get('analysis_include')]

MODELS = sorted({r['model'] for r in rows})
CLUSTERS = sorted({r['cluster'] for r in rows})
ITEMS = sorted({r['question_id'] for r in rows})

out = {"seed": SEED, "B_bootstrap": B_BOOT, "R_permutation": R_PERM,
       "n_rows_file": len(rows_all), "n_cells": len(rows),
       "n_items": len(ITEMS), "n_clusters": len(CLUSTERS), "models": MODELS}

print(f"cells={len(rows)}  items={len(ITEMS)}  clusters={len(CLUSTERS)}  models={len(MODELS)}")

# integrity: every cell must be a complete pair with 0/1 outcomes
bad = [r for r in rows if r['gift_correct'] not in (0, 1) or r['or_correct'] not in (0, 1)]
assert not bad, f"{len(bad)} cells with non-binary outcome"
per_model_items = {m: sorted(r['question_id'] for r in rows if r['model'] == m) for m in MODELS}
assert all(v == ITEMS for v in per_model_items.values()), "models do not share an identical item set"
out["balanced_design_verified"] = True


# ------------------------------------------------------------- 2x2 tables
def table(sub):
    a = b = c = d = 0
    for r in sub:
        g, o = r['gift_correct'], r['or_correct']
        if g and o:
            a += 1
        elif g and not o:
            b += 1
        elif (not g) and o:
            c += 1
        else:
            d += 1
    return a, b, c, d


def rd(sub):
    n = len(sub)
    if n == 0:
        return None
    return (sum(r['gift_correct'] for r in sub) - sum(r['or_correct'] for r in sub)) / n


subsets = {m: [r for r in rows if r['model'] == m] for m in MODELS}
subsets['POOLED'] = rows
KEYS = MODELS + ['POOLED']

desc = {}
for k in KEYS:
    sub = subsets[k]
    a, b, c, d = table(sub)
    n = len(sub)
    gacc = (a + b) / n
    oacc = (a + c) / n
    desc[k] = {"n_cells": n, "a_both_correct": a, "b_gift_only": b,
               "c_or_only": c, "d_both_wrong": d,
               "gift_acc": gacc, "or_acc": oacc,
               "risk_diff_pp": 100 * (gacc - oacc),
               "n_discordant": b + c,
               "pct_discordant": 100 * (b + c) / n}
    print(f"{k:28s} n={n:5d} GIFT={100*gacc:6.2f}%  OR={100*oacc:6.2f}%  "
          f"RD={100*(gacc-oacc):+5.2f}pp  b={b:3d} c={c:3d} (a={a} d={d})")
out['descriptives'] = desc


# ------------------------------------------------------- exact McNemar + OR
tests = {}
for k in KEYS:
    b, c = desc[k]['b_gift_only'], desc[k]['c_or_only']
    ex = mcnemar_exact(b, c)
    as_ = mcnemar_chi2(b, c, continuity=False)
    ascc = mcnemar_chi2(b, c, continuity=True)
    orr = discordant_or(b, c, ALPHA)
    tests[k] = {"exact_mcnemar": ex,
                "asymptotic_chi2_uncorrected": as_,
                "asymptotic_chi2_continuity": ascc,
                "discordant_or": orr}
    print(f"{k:28s} exact McNemar p={ex['p_exact']:.6f} ({ex['p_exact_frac']}) "
          f"| chi2={as_['chi2']:.3f} p={as_['p']:.4f} "
          f"| OR={orr['or']} CI=({orr['or_ci'][0]:.4f},{orr['or_ci'][1]:.4f})")
out['tests'] = tests


# --------------------------------------------------------- cluster bootstrap
# The resampling unit is the item cluster (a shared clinical-case vignette).
# All cells belonging to a drawn cluster travel together, which preserves both
# the within-case correlation and, for POOLED, the cross-model correlation.
by_cluster = collections.defaultdict(list)
for r in rows:
    by_cluster[r['cluster']].append(r)
clus_list = [by_cluster[c] for c in CLUSTERS]

# precompute per-cluster sums per key: (gift_sum, or_sum, n)
pre = {}
for k in KEYS:
    arr = []
    for cl in clus_list:
        sub = cl if k == 'POOLED' else [r for r in cl if r['model'] == k]
        arr.append((sum(r['gift_correct'] for r in sub),
                    sum(r['or_correct'] for r in sub), len(sub)))
    pre[k] = arr

K = len(clus_list)
rng = LCG(SEED)
# one shared set of resampled cluster-index draws => bootstrap replicates for
# every key are mutually consistent (same resampled corpus each replicate)
draws = [[rng.randrange(K) for _ in range(K)] for _ in range(B_BOOT)]

boot = {k: [] for k in KEYS}
for idxs in draws:
    for k in KEYS:
        arr = pre[k]
        gs = os_ = ns = 0
        for i in idxs:
            g, o, n = arr[i]
            gs += g; os_ += o; ns += n
        if ns:
            boot[k].append((gs - os_) / ns)
for k in KEYS:
    boot[k].sort()

# cluster delete-one jackknife for the BCa acceleration
jack = {}
for k in KEYS:
    arr = pre[k]
    tg = sum(x[0] for x in arr); to = sum(x[1] for x in arr); tn = sum(x[2] for x in arr)
    vals = []
    for i in range(K):
        g, o, n = arr[i]
        if tn - n > 0:
            vals.append(((tg - g) - (to - o)) / (tn - n))
    jack[k] = vals

bootres = {}
for k in KEYS:
    bs = boot[k]
    theta = rd(subsets[k])
    lo, hi = percentile(bs, ALPHA / 2), percentile(bs, 1 - ALPHA / 2)
    blo, bhi, z0, acc = bca(bs, theta, jack[k], ALPHA)
    mean = sum(bs) / len(bs)
    se = math.sqrt(sum((v - mean) ** 2 for v in bs) / (len(bs) - 1))
    # bootstrap two-sided p by inverting the percentile interval (achieved level)
    n_le0 = sum(1 for v in bs if v <= 0.0)
    p_boot = 2 * min(n_le0 + 1, len(bs) - n_le0 + 1) / (len(bs) + 1)
    p_boot = min(1.0, p_boot)
    bootres[k] = {"theta_pp": 100 * theta,
                  "percentile_ci_pp": (100 * lo, 100 * hi),
                  "bca_ci_pp": (100 * blo, 100 * bhi),
                  "boot_se_pp": 100 * se, "boot_mean_pp": 100 * mean,
                  "bias_pp": 100 * (mean - theta),
                  "z0": z0, "acceleration": acc,
                  "p_bootstrap_two_sided": p_boot,
                  "frac_replicates_favouring_gift": sum(1 for v in bs if v > 0) / len(bs)}
    print(f"{k:28s} RD={100*theta:+5.2f}pp  pct95=({100*lo:+5.2f},{100*hi:+5.2f})  "
          f"BCa95=({100*blo:+5.2f},{100*bhi:+5.2f})  SE={100*se:.2f}pp  p_boot={p_boot:.4f}")
out['cluster_bootstrap'] = bootres

# naive (cell-independent) SE for the design-effect comparison
naive = {}
for k in KEYS:
    b, c = desc[k]['b_gift_only'], desc[k]['c_or_only']
    n = desc[k]['n_cells']
    var = (b + c - (b - c) ** 2 / n) / n ** 2   # standard paired-binary variance
    naive[k] = {"se_pp": 100 * math.sqrt(max(var, 0)),
                "design_effect_var_ratio":
                    (bootres[k]['boot_se_pp'] ** 2) / (100 ** 2 * max(var, 1e-18))}
out['naive_se_and_design_effect'] = naive


# ------------------------------------------------------------- permutation
# H0: within a cell the arm label is exchangeable. Swapping (gift, or) changes
# the statistic only for discordant cells, so the reference distribution is a
# random signed count. Three schemes differ in the unit that is swapped.
def perm_p(units, R, seed):
    """Monte-Carlo permutation p for |risk difference|.

    units: list of exchangeable units, each a list of (gift, or) cell outcomes.
    Swapping the arm label within a unit negates that unit's net discordance
    delta = sum(gift - or); the cell count n is invariant, so |sum(delta)| is a
    monotone function of |risk difference| and is used directly as the statistic.
    """
    rr = LCG(seed)
    deltas = [sum(g - o for g, o in u) for u in units]
    base = abs(sum(deltas))
    nz = [d for d in deltas if d != 0]          # zero-delta units never move
    ge = 0
    for _ in range(R):
        s = 0
        for dlt in nz:
            s += -dlt if rr.randbit() else dlt
        if abs(s) >= base - 1e-12:
            ge += 1
    return (ge + 1) / (R + 1), len(nz)


perm = {}
for k in KEYS:
    sub = subsets[k]
    # scheme 1: cell-level swap (each item x model cell independent)
    u1 = [[(r['gift_correct'], r['or_correct'])] for r in sub]
    p1, nz1 = perm_p(u1, R_PERM, SEED + 1)
    # scheme 2: cluster x model swap
    g2 = collections.defaultdict(list)
    for r in sub:
        g2[(r['cluster'], r['model'])].append((r['gift_correct'], r['or_correct']))
    p2, nz2 = perm_p(list(g2.values()), R_PERM, SEED + 2)
    # scheme 3: cluster-level swap (all models in a cluster flip together)
    g3 = collections.defaultdict(list)
    for r in sub:
        g3[r['cluster']].append((r['gift_correct'], r['or_correct']))
    p3, nz3 = perm_p(list(g3.values()), R_PERM, SEED + 3)
    perm[k] = {"p_cell_swap": p1, "p_cluster_by_model_swap": p2,
               "p_cluster_swap_all_models": p3,
               "n_units_cell": len(u1), "n_units_clusxmodel": len(g2),
               "n_units_cluster": len(g3),
               "n_nonzero_units_cell": nz1, "n_nonzero_units_clusxmodel": nz2,
               "n_nonzero_units_cluster": nz3}
    print(f"{k:28s} perm p: cell={p1:.5f}  clusxmodel={p2:.5f}  cluster={p3:.5f}")
out['permutation'] = perm


# ------------------------------------------------------------------- Holm
praw = {m: tests[m]['exact_mcnemar']['p_exact'] for m in MODELS}
out['holm_exact_mcnemar'] = holm(praw, ALPHA)
print("\nHolm over the 4 per-model exact McNemar tests:")
for m in MODELS:
    h = out['holm_exact_mcnemar'][m]
    print(f"  {m:28s} p={h['p_raw']:.6f} rank={h['rank']} thr={h['threshold']:.4f} "
          f"p_holm={h['p_holm_adj']:.4f} reject={h['reject_at_0.05']}")

# Holm on the cluster-permutation p-values too (dependence-robust variant)
praw2 = {m: perm[m]['p_cluster_by_model_swap'] for m in MODELS}
out['holm_cluster_permutation'] = holm(praw2, ALPHA)

json.dump(out, open(os.path.join(BASE, 'ca_prim_01_primary.json'), 'w'), indent=1, default=str)
print("\nwrote ca_prim_01_primary.json")

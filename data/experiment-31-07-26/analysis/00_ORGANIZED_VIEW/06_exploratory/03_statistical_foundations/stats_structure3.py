#!/usr/bin/env python3
"""
stats_structure3.py -- resolve the conflict between the ANOVA cluster ICC
(+0.27) and the multi-item-cluster-only ANOVA ICC (+0.016), and settle which
source of non-independence actually matters.

Method: the pairwise / Fleiss-Cuzick intraclass correlation, which is the
estimator DEFF = 1 + (m-1)*rho is actually derived from:

    rho = [ sum_c sum_{i<j in c} (y_i - p)(y_j - p) / P ] / (p(1-p))
    P   = sum_c n_c(n_c-1)/2

It uses only WITHIN-cluster pairs, so singleton clusters contribute nothing
(they have no pairs) instead of silently inflating MSB the way one-way ANOVA
does. For non-binary y (delta in {-1,0,1}) the same formula with the sample
variance in the denominator.

Also: empirical DEFF from robust variance ratios (the operational answer).
Stdlib only.
"""
import json
import math
import random
import statistics
from collections import defaultdict, Counter

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")
random.seed(31072026)
NBOOT = 3000

raw = json.load(open(DATA))
rows = [r for r in raw if r.get("analysis_include") is True]
models = sorted({r["model"] for r in rows})
item_cluster = {r["question_id"]: r["cluster"] for r in rows}

A = lambda r: float(r["A_correct"])
Bv = lambda r: float(r["B_correct"])
D = lambda r: float(r["B_correct"] - r["A_correct"])


def pairwise_icc(groups, center=None):
    """groups: gid -> list of values. center: grand mean to use (default sample).
    Returns rho, n_pairs, n_groups_with_pairs, total N."""
    allv = [x for v in groups.values() for x in v]
    N = len(allv)
    mu = center if center is not None else sum(allv) / N
    var = sum((x - mu) ** 2 for x in allv) / N
    num = 0.0
    P = 0
    gp = 0
    for v in groups.values():
        n = len(v)
        if n < 2:
            continue
        gp += 1
        s = sum(x - mu for x in v)
        ss = sum((x - mu) ** 2 for x in v)
        num += (s * s - ss) / 2.0
        P += n * (n - 1) // 2
    if P == 0 or var == 0:
        return None
    return dict(rho=(num / P) / var, pairs=P, groups_with_pairs=gp, N=N, var=var, mu=mu)


def build(rs, gk, fn):
    g = defaultdict(list)
    for r in rs:
        g[gk(r)].append(fn(r))
    return g


print("=" * 78)
print("1. PAIRWISE (Fleiss-Cuzick) ICC -- singleton-robust")
print("=" * 78)

print("\n1a. CLUSTER level, within each model (units = items):")
res_store = {}
for lab, fn in (("A_correct", A), ("B_correct", Bv), ("delta", D)):
    vals = []
    for m in models:
        sub = [r for r in rows if r["model"] == m]
        res = pairwise_icc(build(sub, lambda r: r["cluster"], fn))
        vals.append(res["rho"])
        print(f"  {lab:10s} {m.split('/')[-1]:22s} rho={res['rho']:+.4f} "
              f"pairs={res['pairs']} clusters_with_pairs={res['groups_with_pairs']} N={res['N']}")
    res_store[lab] = sum(vals) / len(vals)
    print(f"  {lab:10s} {'MEAN of 4 models':22s} rho={res_store[lab]:+.4f}  "
          f"(range {min(vals):+.4f}..{max(vals):+.4f})")

print("\n1b. CLUSTER level, item means over the 4 models (325 item scores):")
im = defaultdict(list)
imd = defaultdict(list)
imb = defaultdict(list)
for r in rows:
    im[r["question_id"]].append(r["A_correct"])
    imb[r["question_id"]].append(r["B_correct"])
    imd[r["question_id"]].append(r["B_correct"] - r["A_correct"])
for lab, src in (("mean A_correct", im), ("mean B_correct", imb), ("mean delta", imd)):
    g = defaultdict(list)
    for q in src:
        g[item_cluster[q]].append(statistics.mean(src[q]))
    res = pairwise_icc(g)
    print(f"  {lab:16s} rho={res['rho']:+.4f} pairs={res['pairs']} N={res['N']}")

print("\n1c. ITEM level across models (units = the 4 models' cells for one item),")
print("    model-mean-centred so the model main effect cannot inflate it:")
mm = {}
for lab, fn in (("A_correct", A), ("B_correct", Bv), ("delta", D)):
    mm[lab] = {m: statistics.mean([fn(r) for r in rows if r["model"] == m]) for m in models}
for lab, fn in (("A_correct", A), ("B_correct", Bv), ("delta", D)):
    g = defaultdict(list)
    for r in rows:
        g[r["question_id"]].append(fn(r) - mm[lab][r["model"]])
    res = pairwise_icc(g, center=0.0)
    res_store["item_" + lab] = res["rho"]
    # uncentred version for comparison
    g2 = build(rows, lambda r: r["question_id"], fn)
    res2 = pairwise_icc(g2)
    print(f"  {lab:10s} rho(model-centred)={res['rho']:+.4f}  "
          f"rho(uncentred)={res2['rho']:+.4f}  pairs={res['pairs']} items={res['groups_with_pairs']}")

# bootstrap CIs (resample clusters)
print(f"\n1d. cluster-bootstrap 95pct CIs (B={NBOOT}, resample the 208 clusters):")
by_cluster = defaultdict(list)
for r in rows:
    by_cluster[r["cluster"]].append(r)
cids = list(by_cluster)


def boot(statfn):
    out = []
    for _ in range(NBOOT):
        pick = [random.choice(cids) for _ in cids]
        rs = []
        for j, c in enumerate(pick):
            for r in by_cluster[c]:
                rr = dict(r)
                rr["_bc"] = (j, c)
                rr["_bi"] = (j, r["question_id"])
                rs.append(rr)
        v = statfn(rs)
        if v is not None and not math.isnan(v):
            out.append(v)
    out.sort()
    return (out[int(0.025 * (len(out) - 1))], out[int(0.975 * (len(out) - 1))],
            statistics.median(out), len(out))


def stat_cluster_withinmodel(fn):
    def f(rs):
        vs = []
        for m in models:
            sub = [r for r in rs if r["model"] == m]
            res = pairwise_icc(build(sub, lambda r: r["_bc"], fn))
            if res:
                vs.append(res["rho"])
        return sum(vs) / len(vs) if vs else None
    return f


def stat_item_centred(lab, fn):
    def f(rs):
        g = defaultdict(list)
        for r in rs:
            g[r["_bi"]].append(fn(r) - mm[lab][r["model"]])
        res = pairwise_icc(g, center=0.0)
        return res["rho"] if res else None
    return f


for lab, fn in (("A_correct", A), ("delta", D)):
    lo, hi, med, B = boot(stat_cluster_withinmodel(fn))
    print(f"  CLUSTER-level rho, {lab:10s} = {res_store[lab]:+.4f}  "
          f"boot95 [{lo:+.4f}, {hi:+.4f}] (B={B})")
for lab, fn in (("A_correct", A), ("delta", D)):
    lo, hi, med, B = boot(stat_item_centred(lab, fn))
    print(f"  ITEM-level    rho, {lab:10s} = {res_store['item_'+lab]:+.4f}  "
          f"boot95 [{lo:+.4f}, {hi:+.4f}] (B={B})")

# --------------------------------------------------------------------------
print()
print("=" * 78)
print("2. WHY THE ONE-WAY ANOVA CLUSTER ICC IS INFLATED (singleton artefact)")
print("=" * 78)
cl_items = defaultdict(set)
for r in rows:
    cl_items[r["cluster"]].add(r["question_id"])
multi = {c for c, v in cl_items.items() if len(v) >= 2}
sing = {c for c, v in cl_items.items() if len(v) == 1}
for lab, fn in (("A_correct", A), ("delta", D)):
    sub_m = [r for r in rows if r["cluster"] in multi]
    sub_s = [r for r in rows if r["cluster"] in sing]
    pm = sum(fn(r) for r in sub_m) / len(sub_m)
    ps = sum(fn(r) for r in sub_s) / len(sub_s)
    vm = statistics.pvariance([fn(r) for r in sub_m])
    vs = statistics.pvariance([fn(r) for r in sub_s])
    vall = statistics.pvariance([fn(r) for r in rows])
    print(f"  {lab:10s} mean(multi)={pm:+.4f} var(multi)={vm:.4f} | "
          f"mean(single)={ps:+.4f} var(single)={vs:.4f} | var(all)={vall:.4f}")
print("  -> one-way ANOVA takes MSW only from the 11 multi-item clusters but MSB")
print("     from all 208 groups incl. 197 singletons whose deviation IS the total")
print("     variance. Bernoulli mean-variance coupling (case items are easier =>")
print("     lower within-variance) then manufactures a large positive ICC that is")
print("     NOT within-case correlation. The pairwise estimator above is immune.")

# --------------------------------------------------------------------------
print()
print("=" * 78)
print("3. DESIGN EFFECT AND EFFECTIVE SAMPLE SIZE -- FINAL TABLE")
print("=" * 78)
mbar_items = 325 / 208
mbar_cells_per_item = 1299 / 325
mbar_cells_per_cluster = 1299 / 208


def show(label, N, mbar, rho):
    de = 1 + (mbar - 1) * rho
    print(f"  {label:56s} N={N:5d} m={mbar:6.3f} rho={rho:+.4f} DEFF={de:6.3f} "
          f"ESS={N/de:8.1f}")


print("\n  (a) items within clusters, one model at a time:")
show("A_correct  (pairwise rho, mean of 4 models)", 325, mbar_items, res_store["A_correct"])
show("delta      (pairwise rho, mean of 4 models)", 325, mbar_items, res_store["delta"])
print("\n  (b) same item answered by 4 models:")
show("A_correct  (pairwise rho, model-centred)", 1299, mbar_cells_per_item, res_store["item_A_correct"])
show("delta      (pairwise rho, model-centred)", 1299, mbar_cells_per_item, res_store["item_delta"])
print("\n  (c) both at once -- cluster as the top-level unit over all 1299 cells:")
for lab, fn in (("A_correct", A), ("delta", D)):
    g = defaultdict(list)
    for r in rows:
        g[r["cluster"]].append(fn(r) - mm[lab][r["model"]])
    res = pairwise_icc(g, center=0.0)
    show(f"{lab:10s} (pairwise rho over cells, model-centred)", 1299,
         mbar_cells_per_cluster, res["rho"])

# --------------------------------------------------------------------------
print()
print("=" * 78)
print("4. EMPIRICAL DEFF FROM ROBUST VARIANCE RATIOS (the operational answer)")
print("=" * 78)


def robust_deff(fn, label):
    y = [fn(r) for r in rows]
    n = len(y)
    mu = sum(y) / n
    v_iid = sum((x - mu) ** 2 for x in y) / (n - 1) / n
    out = {}
    for gname, gk in (("item", lambda r: r["question_id"]),
                      ("cluster", lambda r: r["cluster"])):
        S = defaultdict(float)
        C = Counter()
        for r in rows:
            S[gk(r)] += fn(r)
            C[gk(r)] += 1
        K = len(S)
        sq = sum((S[k] - C[k] * mu) ** 2 for k in S)
        v = sq / (n * n) * (K / (K - 1))
        out[gname] = (v, K)
    print(f"\n  {label}: mean={mu:+.6f}")
    print(f"    SE_iid                      = {math.sqrt(v_iid):.6f}")
    for gname in ("item", "cluster"):
        v, K = out[gname]
        print(f"    SE_robust[{gname:7s}] (G={K:3d}) = {math.sqrt(v):.6f}   "
              f"DEFF = {v/v_iid:.4f}")
    di = out["item"][0] / v_iid
    dc = out["cluster"][0] / v_iid
    print(f"    -> item repetition explains DEFF {di:.4f}; adding cluster raises it to "
          f"{dc:.4f} (a further x{dc/di:.4f})")
    print(f"    -> ESS: naive {len(rows)} | item-robust {len(rows)/di:.1f} | "
          f"cluster-robust {len(rows)/dc:.1f}")
    return di, dc


robust_deff(A, "A_correct")
robust_deff(Bv, "B_correct")
robust_deff(D, "delta = B_correct - A_correct")

# a "model-blocked" version: delta averaged within item first
print("\n  cross-check -- collapse to 325 item-level mean deltas, then cluster-robust:")
qs = sorted(imd)
y = [statistics.mean(imd[q]) for q in qs]
n = len(y)
mu = sum(y) / n
v_iid = sum((x - mu) ** 2 for x in y) / (n - 1) / n
S = defaultdict(float)
C = Counter()
for q, val in zip(qs, y):
    S[item_cluster[q]] += val
    C[item_cluster[q]] += 1
K = len(S)
sq = sum((S[k] - C[k] * mu) ** 2 for k in S)
v = sq / (n * n) * (K / (K - 1))
print(f"    mean item-level delta={mu:+.6f}  SE_iid={math.sqrt(v_iid):.6f} "
      f"SE_cluster(K={K})={math.sqrt(v):.6f}  DEFF={v/v_iid:.4f}  ESS={n/(v/v_iid):.1f}")
print()

#!/usr/bin/env python3
"""
stats_structure.py -- characterise the data-generating structure of the
Tier-1 MCQ paired experiment (experiment-31-07-26).

Stdlib only. No numpy/scipy/pandas.

Outputs:
  1. counts (cells / items / clusters / models), balance checks
  2. cluster-size distribution (items per cluster, cells per cluster)
  3. one-way random-effects ICC (ANOVA / method-of-moments, Searle) for
       - A_correct and delta = B_correct - A_correct
       - grouping = CLUSTER (within each model, and pooled over all cells)
       - grouping = ITEM   (units = the 4 models' answers to the same item)
  4. nested variance decomposition cluster > item > cell (model main effect
     removed as a fixed effect), giving sigma_C^2, sigma_I^2, sigma_e^2
  5. DEFF = 1 + (m_bar - 1) * ICC and effective sample sizes
  6. cluster bootstrap CIs for every ICC (resample clusters with replacement)
"""

import json
import math
import random
import statistics
from collections import defaultdict, Counter

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")

random.seed(20260731)
B_BOOT = 2000

# ----------------------------------------------------------------------------
# load
# ----------------------------------------------------------------------------
raw = json.load(open(DATA))
rows = [r for r in raw if r.get("analysis_include") is True]

print("=" * 78)
print("1. STRUCTURAL COUNTS")
print("=" * 78)
print(f"records in file            : {len(raw)}")
print(f"analysis_include == true   : {len(rows)}")

items = sorted({r["question_id"] for r in rows})
clusters = sorted({r["cluster"] for r in rows})
models = sorted({r["model"] for r in rows})
print(f"distinct items (question_id): {len(items)}")
print(f"distinct clusters           : {len(clusters)}")
print(f"distinct models             : {len(models)}  -> {models}")

# balance: models per item
models_per_item = defaultdict(set)
for r in rows:
    models_per_item[r["question_id"]].add(r["model"])
mpi = Counter(len(v) for v in models_per_item.values())
print(f"models per item histogram   : {dict(sorted(mpi.items()))}")

# cells per (item,model) -- should be exactly 1 (runs=1)
cell_key = Counter((r["question_id"], r["model"]) for r in rows)
print(f"cells per (item,model) hist : {dict(sorted(Counter(cell_key.values()).items()))}")

# item -> cluster must be unique
item_cluster = {}
bad = 0
for r in rows:
    q = r["question_id"]
    if q in item_cluster and item_cluster[q] != r["cluster"]:
        bad += 1
    item_cluster[q] = r["cluster"]
print(f"items with inconsistent cluster: {bad}")

# per-model cell counts
per_model = Counter(r["model"] for r in rows)
print("\ncells and raw accuracy per model:")
for m in models:
    sub = [r for r in rows if r["model"] == m]
    a = sum(r["A_correct"] for r in sub) / len(sub)
    b = sum(r["B_correct"] for r in sub) / len(sub)
    print(f"  {m:28s} n={len(sub):4d}  A={a:.4f}  B={b:.4f}  d={b-a:+.4f}")
allA = sum(r["A_correct"] for r in rows) / len(rows)
allB = sum(r["B_correct"] for r in rows) / len(rows)
print(f"  {'POOLED':28s} n={len(rows):4d}  A={allA:.4f}  B={allB:.4f}  d={allB-allA:+.4f}")

# ----------------------------------------------------------------------------
# 2. cluster size distribution
# ----------------------------------------------------------------------------
print()
print("=" * 78)
print("2. CLUSTER-SIZE DISTRIBUTION")
print("=" * 78)

cluster_items = defaultdict(set)
cluster_cells = Counter()
for r in rows:
    cluster_items[r["cluster"]].add(r["question_id"])
    cluster_cells[r["cluster"]] += 1

sizes_items = sorted(len(v) for v in cluster_items.values())
sizes_cells = sorted(cluster_cells.values())


def describe(vals, label):
    n = len(vals)
    v = sorted(vals)
    mean = sum(v) / n
    med = statistics.median(v)
    q1 = v[int(0.25 * (n - 1))]
    q3 = v[int(0.75 * (n - 1))]
    print(f"{label}: k={n} min={v[0]} q1={q1} median={med} q3={q3} max={v[-1]} "
          f"mean={mean:.4f} sd={statistics.pstdev(v):.4f} total={sum(v)}")
    return mean


mbar_items = describe(sizes_items, "items per cluster ")
mbar_cells = describe(sizes_cells, "cells per cluster ")
print(f"items-per-cluster histogram: {dict(sorted(Counter(sizes_items).items()))}")
print(f"cells-per-cluster histogram: {dict(sorted(Counter(sizes_cells).items()))}")
sing = sum(1 for s in sizes_items if s == 1)
print(f"singleton clusters (1 item): {sing}  ({100*sing/len(sizes_items):.2f}% of clusters, "
      f"{100*sing/len(items):.2f}% of items)")
print(f"items living in clusters of size >=2: {sum(s for s in sizes_items if s >= 2)}")
big = sorted(((len(v), c) for c, v in cluster_items.items()), reverse=True)[:8]
print(f"largest clusters (n_items, cluster_id): {big}")

# ----------------------------------------------------------------------------
# ICC machinery: one-way random effects, unbalanced (Searle 1971, eq. for ICC(1))
#   MSB = sum_g n_g (ybar_g - ybar_w)^2 / (k-1)
#   MSW = sum_g sum_j (y - ybar_g)^2 / (N-k)
#   n0  = (N - sum n_g^2 / N) / (k-1)
#   ICC = (MSB - MSW) / (MSB + (n0-1) MSW)
# Groups of size 1 contribute 0 to MSB numerator and 0 df to MSW; they are kept
# (they carry information about n0 / the grand mean) -- reported both ways.
# ----------------------------------------------------------------------------


def icc_oneway(groups, drop_singletons=False):
    """groups: dict gid -> list of numeric values. Returns dict of results."""
    g = {k: v for k, v in groups.items() if len(v) >= (2 if drop_singletons else 1)}
    k = len(g)
    N = sum(len(v) for v in g.values())
    if k < 2 or N <= k:
        return None
    grand = sum(sum(v) for v in g.values()) / N
    msb_num = 0.0
    msw_num = 0.0
    sum_n2 = 0
    for v in g.values():
        n = len(v)
        m = sum(v) / n
        msb_num += n * (m - grand) ** 2
        msw_num += sum((x - m) ** 2 for x in v)
        sum_n2 += n * n
    MSB = msb_num / (k - 1)
    MSW = msw_num / (N - k)
    n0 = (N - sum_n2 / N) / (k - 1)
    denom = MSB + (n0 - 1) * MSW
    icc = (MSB - MSW) / denom if denom > 0 else float("nan")
    return dict(k=k, N=N, MSB=MSB, MSW=MSW, n0=n0, icc=icc,
                mbar=N / k, grand=grand)


def deff(mbar, icc):
    return 1.0 + (mbar - 1.0) * icc


def boot_icc(rows_, groupkey, valuefn, drop_singletons=False, B=B_BOOT,
             resample="cluster"):
    """Cluster bootstrap: resample CLUSTERS with replacement, rebuild groups."""
    by_cluster = defaultdict(list)
    for r in rows_:
        by_cluster[r["cluster"]].append(r)
    cids = list(by_cluster)
    out = []
    for b in range(B):
        draw = [random.choice(cids) for _ in cids]
        groups = defaultdict(list)
        for j, c in enumerate(draw):
            for r in by_cluster[c]:
                # make group ids unique per draw so a twice-drawn cluster
                # counts as two independent clusters
                groups[(j, groupkey(r))].append(valuefn(r))
        res = icc_oneway(groups, drop_singletons=drop_singletons)
        if res and not math.isnan(res["icc"]):
            out.append(res["icc"])
    out.sort()
    if len(out) < 50:
        return None
    lo = out[int(0.025 * (len(out) - 1))]
    hi = out[int(0.975 * (len(out) - 1))]
    return lo, hi, statistics.median(out), len(out)


def build(rows_, groupkey, valuefn):
    g = defaultdict(list)
    for r in rows_:
        g[groupkey(r)].append(valuefn(r))
    return g


A = lambda r: float(r["A_correct"])
Bc = lambda r: float(r["B_correct"])
D = lambda r: float(r["B_correct"] - r["A_correct"])

print()
print("=" * 78)
print("3. ICC -- ONE-WAY RANDOM EFFECTS (ANOVA / method of moments)")
print("=" * 78)

# ---- 3a. CLUSTER level, WITHIN each model (one obs per item, no model reuse)
print("\n3a. grouping = CLUSTER, computed separately WITHIN each model")
print("    (units = items; no item appears twice -> pure item-within-cluster ICC)")
for var, fn in (("A_correct", A), ("B_correct", Bc), ("delta=B-A", D)):
    print(f"\n  variable: {var}")
    vals = []
    for m in models:
        sub = [r for r in rows if r["model"] == m]
        res = icc_oneway(build(sub, lambda r: r["cluster"], fn))
        vals.append(res["icc"])
        print(f"    {m:28s} k={res['k']:3d} N={res['N']:4d} n0={res['n0']:.4f} "
              f"ICC={res['icc']:+.4f}  DEFF={deff(res['mbar'], res['icc']):.4f} "
              f"ESS={res['N']/deff(res['mbar'], res['icc']):.1f}")
    mean_icc = sum(vals) / len(vals)
    print(f"    {'MEAN over 4 models':28s} ICC={mean_icc:+.4f}   "
          f"(range {min(vals):+.4f} .. {max(vals):+.4f})")

# ---- 3b. CLUSTER level, ALL cells pooled (this is the operative DEFF for
#          cluster-robust inference: it absorbs BOTH item-in-cluster and
#          model-on-same-item dependence)
print("\n3b. grouping = CLUSTER, ALL 1299 cells pooled")
print("    (absorbs BOTH sources: items within cluster AND 4 models per item)")
for var, fn in (("A_correct", A), ("B_correct", Bc), ("delta=B-A", D)):
    res = icc_oneway(build(rows, lambda r: r["cluster"], fn))
    ci = boot_icc(rows, lambda r: r["cluster"], fn)
    de = deff(res["mbar"], res["icc"])
    print(f"  {var:12s} k={res['k']} N={res['N']} mbar={res['mbar']:.4f} "
          f"n0={res['n0']:.4f} ICC={res['icc']:+.4f} "
          f"[boot95 {ci[0]:+.4f},{ci[1]:+.4f}] DEFF={de:.4f} ESS={res['N']/de:.1f}")

# ---- 3c. ITEM level across models
print("\n3c. grouping = ITEM, units = the 4 models' answers to the SAME item")
for var, fn in (("A_correct", A), ("B_correct", Bc), ("delta=B-A", D)):
    res = icc_oneway(build(rows, lambda r: r["question_id"], fn))
    ci = boot_icc(rows, lambda r: r["question_id"], fn)
    de = deff(res["mbar"], res["icc"])
    print(f"  {var:12s} k={res['k']} N={res['N']} mbar={res['mbar']:.4f} "
          f"n0={res['n0']:.4f} ICC={res['icc']:+.4f} "
          f"[boot95 {ci[0]:+.4f},{ci[1]:+.4f}] DEFF={de:.4f} ESS={res['N']/de:.1f}")

# ---- 3c'. ITEM level after removing the model main effect (fixed) -- the model
#           main effect inflates within-item agreement only trivially, but check
print("\n3c'. grouping = ITEM, after subtracting each model's own mean "
      "(model main effect removed)")
mmeanA = {m: statistics.mean([r["A_correct"] for r in rows if r["model"] == m]) for m in models}
mmeanB = {m: statistics.mean([r["B_correct"] for r in rows if r["model"] == m]) for m in models}
mmeanD = {m: statistics.mean([r["B_correct"] - r["A_correct"] for r in rows if r["model"] == m])
          for m in models}
for var, fn in (("A_correct", lambda r: r["A_correct"] - mmeanA[r["model"]]),
                ("B_correct", lambda r: r["B_correct"] - mmeanB[r["model"]]),
                ("delta=B-A", lambda r: (r["B_correct"] - r["A_correct"]) - mmeanD[r["model"]])):
    res = icc_oneway(build(rows, lambda r: r["question_id"], fn))
    de = deff(res["mbar"], res["icc"])
    print(f"  {var:12s} ICC={res['icc']:+.4f} DEFF={de:.4f} ESS={res['N']/de:.1f}")

# ---- 3d. cluster-level ICC of the ITEM-MEAN A_correct and ITEM-MEAN delta
#          (i.e. after averaging the 4 models -> 325 independent-ish item scores)
print("\n3d. grouping = CLUSTER, units = ITEM MEANS over the 4 models (325 values)")
item_meanA = defaultdict(list)
item_meanD = defaultdict(list)
for r in rows:
    item_meanA[r["question_id"]].append(r["A_correct"])
    item_meanD[r["question_id"]].append(r["B_correct"] - r["A_correct"])
gA = defaultdict(list)
gD = defaultdict(list)
for q in item_meanA:
    gA[item_cluster[q]].append(statistics.mean(item_meanA[q]))
    gD[item_cluster[q]].append(statistics.mean(item_meanD[q]))
for var, g in (("mean A_correct", gA), ("mean delta", gD)):
    res = icc_oneway(g)
    de = deff(res["mbar"], res["icc"])
    print(f"  {var:16s} k={res['k']} N={res['N']} mbar={res['mbar']:.4f} "
          f"ICC={res['icc']:+.4f} DEFF={de:.4f} ESS={res['N']/de:.1f}")

# ----------------------------------------------------------------------------
# 4. nested variance decomposition  cluster > item > cell
# ----------------------------------------------------------------------------
print()
print("=" * 78)
print("4. NESTED VARIANCE DECOMPOSITION (cluster > item > cell)")
print("   model main effect removed as fixed; Searle unbalanced-nested EMS")
print("=" * 78)


def nested_components(rows_, fn):
    # y centred by model mean already handled by fn
    by_item = defaultdict(list)
    for r in rows_:
        by_item[r["question_id"]].append(fn(r))
    by_cluster_items = defaultdict(list)
    for q in by_item:
        by_cluster_items[item_cluster[q]].append(q)

    N = sum(len(v) for v in by_item.values())
    I = len(by_item)
    C = len(by_cluster_items)
    grand = sum(sum(v) for v in by_item.values()) / N

    item_n = {q: len(v) for q, v in by_item.items()}
    item_mean = {q: sum(v) / len(v) for q, v in by_item.items()}
    clus_n = {c: sum(item_n[q] for q in qs) for c, qs in by_cluster_items.items()}
    clus_mean = {c: sum(sum(by_item[q]) for q in qs) / clus_n[c]
                 for c, qs in by_cluster_items.items()}

    SS_err = sum((x - item_mean[q]) ** 2 for q, v in by_item.items() for x in v)
    SS_item = sum(item_n[q] * (item_mean[q] - clus_mean[item_cluster[q]]) ** 2
                  for q in by_item)
    SS_clus = sum(clus_n[c] * (clus_mean[c] - grand) ** 2 for c in by_cluster_items)

    df_err = N - I
    df_item = I - C
    df_clus = C - 1
    MS_err = SS_err / df_err
    MS_item = SS_item / df_item
    MS_clus = SS_clus / df_clus

    S1 = sum(sum(item_n[q] ** 2 for q in qs) / clus_n[c]
             for c, qs in by_cluster_items.items())
    S2 = sum(item_n[q] ** 2 for q in by_item) / N
    S3 = sum(clus_n[c] ** 2 for c in by_cluster_items) / N
    k1 = (N - S1) / df_item
    k2 = (S1 - S2) / df_clus
    k3 = (N - S3) / df_clus

    var_I = (MS_item - MS_err) / k1
    var_C = (MS_clus - MS_err - k2 * var_I) / k3
    var_e = MS_err
    return dict(N=N, I=I, C=C, MS_err=MS_err, MS_item=MS_item, MS_clus=MS_clus,
                k1=k1, k2=k2, k3=k3, var_e=var_e, var_I=var_I, var_C=var_C)


for var, fn in (("A_correct", lambda r: r["A_correct"] - mmeanA[r["model"]]),
                ("B_correct", lambda r: r["B_correct"] - mmeanB[r["model"]]),
                ("delta=B-A", lambda r: (r["B_correct"] - r["A_correct"]) - mmeanD[r["model"]])):
    c = nested_components(rows, fn)
    tot = c["var_C"] + c["var_I"] + c["var_e"]
    icc_c = c["var_C"] / tot
    icc_i = (c["var_C"] + c["var_I"]) / tot
    print(f"\n  {var}")
    print(f"    N={c['N']} items={c['I']} clusters={c['C']}  "
          f"k1={c['k1']:.4f} k2={c['k2']:.4f} k3={c['k3']:.4f}")
    print(f"    MS_cluster={c['MS_clus']:.6f}  MS_item(cluster)={c['MS_item']:.6f}  "
          f"MS_cell={c['MS_err']:.6f}")
    print(f"    sigma2_cluster={c['var_C']:+.6f}  sigma2_item={c['var_I']:+.6f}  "
          f"sigma2_cell={c['var_e']:.6f}   total={tot:.6f}")
    print(f"    share  cluster={100*c['var_C']/tot:+.2f}%  item={100*c['var_I']/tot:+.2f}%  "
          f"cell(model x item)={100*c['var_e']/tot:.2f}%")
    print(f"    rho(same item, diff model)      = (s2C+s2I)/tot = {icc_i:+.5f}")
    print(f"    rho(diff item, same cluster)    = s2C/tot       = {icc_c:+.5f}")

# ----------------------------------------------------------------------------
# 5. DEFF table
# ----------------------------------------------------------------------------
print()
print("=" * 78)
print("5. DESIGN EFFECTS AND EFFECTIVE SAMPLE SIZES")
print("=" * 78)


def line(label, N, mbar, icc):
    de = deff(mbar, icc)
    print(f"  {label:52s} N={N:5d} mbar={mbar:6.3f} ICC={icc:+.4f} "
          f"DEFF={de:6.3f} ESS={N/de:8.1f}")


# cluster-level ICC of A within model (mean of 4)
vals = []
for m in models:
    sub = [r for r in rows if r["model"] == m]
    vals.append(icc_oneway(build(sub, lambda r: r["cluster"], A))["icc"])
icc_clust_A_withinmodel = sum(vals) / len(vals)
vals = []
for m in models:
    sub = [r for r in rows if r["model"] == m]
    vals.append(icc_oneway(build(sub, lambda r: r["cluster"], D))["icc"])
icc_clust_D_withinmodel = sum(vals) / len(vals)

res_item_A = icc_oneway(build(rows, lambda r: r["question_id"], A))
res_item_D = icc_oneway(build(rows, lambda r: r["question_id"], D))
res_clus_A = icc_oneway(build(rows, lambda r: r["cluster"], A))
res_clus_D = icc_oneway(build(rows, lambda r: r["cluster"], D))

print("\n  LEVEL 1 -- items within clusters (single model, 325 items / 208 clusters):")
line("A_correct, cluster ICC (mean of 4 models)", 325, mbar_items, icc_clust_A_withinmodel)
line("delta,     cluster ICC (mean of 4 models)", 325, mbar_items, icc_clust_D_withinmodel)

print("\n  LEVEL 2 -- same item answered by 4 models (1299 cells / 325 items):")
line("A_correct, item ICC across models", res_item_A["N"], res_item_A["mbar"], res_item_A["icc"])
line("delta,     item ICC across models", res_item_D["N"], res_item_D["mbar"], res_item_D["icc"])

print("\n  COMBINED -- all cells, cluster as the top-level independent unit:")
line("A_correct, cluster ICC over all cells", res_clus_A["N"], res_clus_A["mbar"], res_clus_A["icc"])
line("delta,     cluster ICC over all cells", res_clus_D["N"], res_clus_D["mbar"], res_clus_D["icc"])

print("\n  multiplicative check (nested approximation "
      "DEFF_total ~ DEFF_item x DEFF_cluster_of_item_means):")
for lab, iiA, icA, mb in (("A_correct", res_item_A["icc"], icc_clust_A_withinmodel, mbar_items),
                          ("delta    ", res_item_D["icc"], icc_clust_D_withinmodel, mbar_items)):
    d1 = deff(4.0, iiA)
    d2 = deff(mb, icA)
    print(f"    {lab}: DEFF_item={d1:.4f} x DEFF_cluster={d2:.4f} = {d1*d2:.4f}")
print(f"    observed pooled-cluster DEFF: A={deff(res_clus_A['mbar'], res_clus_A['icc']):.4f} "
      f"delta={deff(res_clus_D['mbar'], res_clus_D['icc']):.4f}")

# ----------------------------------------------------------------------------
# 6. pairwise model agreement (concrete read of the item-level ICC)
# ----------------------------------------------------------------------------
print()
print("=" * 78)
print("6. PAIRWISE MODEL AGREEMENT (concrete reading of the item-level ICC)")
print("=" * 78)
bym = defaultdict(dict)
for r in rows:
    bym[r["question_id"]][r["model"]] = r
for i in range(len(models)):
    for j in range(i + 1, len(models)):
        m1, m2 = models[i], models[j]
        pairs = [(v[m1], v[m2]) for v in bym.values() if m1 in v and m2 in v]
        agrA = sum(1 for a, b in pairs if a["A_correct"] == b["A_correct"]) / len(pairs)
        agrD = sum(1 for a, b in pairs
                   if (a["B_correct"] - a["A_correct"]) == (b["B_correct"] - b["A_correct"])) / len(pairs)
        # chance agreement on A given marginals
        p1 = sum(a["A_correct"] for a, b in pairs) / len(pairs)
        p2 = sum(b["A_correct"] for a, b in pairs) / len(pairs)
        pe = p1 * p2 + (1 - p1) * (1 - p2)
        kappa = (agrA - pe) / (1 - pe)
        print(f"  {m1.split('/')[-1]:22s} vs {m2.split('/')[-1]:22s} n={len(pairs)} "
              f"agree_A={agrA:.4f} (chance {pe:.4f}, kappa={kappa:+.4f})  agree_delta={agrD:.4f}")

# how many items are unanimous under A
unan = Counter()
for q, v in bym.items():
    s = sum(x["A_correct"] for x in v.values())
    unan[s] += 1
print(f"\n  items by #models correct under A (0..4): {dict(sorted(unan.items()))}")
unanD = Counter()
for q, v in bym.items():
    s = sum(x["B_correct"] - x["A_correct"] for x in v.values())
    unanD[s] += 1
print(f"  items by sum of delta over 4 models     : {dict(sorted(unanD.items()))}")

# delta distribution
dc = Counter(r["B_correct"] - r["A_correct"] for r in rows)
print(f"  cell-level delta distribution           : {dict(sorted(dc.items()))}")
print()

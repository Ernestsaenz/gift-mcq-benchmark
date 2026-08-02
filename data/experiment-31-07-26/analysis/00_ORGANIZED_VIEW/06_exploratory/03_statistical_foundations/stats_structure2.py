#!/usr/bin/env python3
"""
stats_structure2.py -- follow-ups to stats_structure.py

  A. the missing cell (1299 = 4*325 - 1): which item/model
  B. anatomy of the clustering: singleton vs multi-item clusters, what the
     multi-item clusters are (exam_part / region / year), ICC restricted to
     the 11 non-singleton clusters
  C. permutation tests for ICC > 0 (cluster level and item level)
  D. bootstrap CIs for the within-model cluster ICCs
  E. what the DEFF costs a concrete paired test on delta
Stdlib only.
"""
import json
import math
import random
import statistics
from collections import defaultdict, Counter

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")
random.seed(11071926)
NPERM = 5000
NBOOT = 2000

raw = json.load(open(DATA))
rows = [r for r in raw if r.get("analysis_include") is True]
models = sorted({r["model"] for r in rows})
item_cluster = {r["question_id"]: r["cluster"] for r in rows}

# ---------------------------------------------------------------- A
print("=" * 78)
print("A. THE MISSING CELL")
print("=" * 78)
seen = defaultdict(set)
for r in rows:
    seen[r["question_id"]].add(r["model"])
for q, ms in seen.items():
    if len(ms) != 4:
        miss = set(models) - ms
        print(f"  item {q} (cluster {item_cluster[q]}) has {len(ms)} models; MISSING: {sorted(miss)}")
        for rr in raw:
            if rr["question_id"] == q:
                print(f"    raw row: model={rr['model']:28s} include={rr['analysis_include']} "
                      f"excl_defect={rr['excl_item_defect']} excl_nota_a={rr['excl_nota_position_a']} "
                      f"A={rr['A_correct']} B={rr['B_correct']} Asel={rr['A_selected']} Bsel={rr['B_selected']}")
print(f"  => cells = 4*325 - 1 = {4*325-1}; observed {len(rows)}")

# ---------------------------------------------------------------- B
print()
print("=" * 78)
print("B. ANATOMY OF THE CLUSTERING")
print("=" * 78)
cl_items = defaultdict(set)
for r in rows:
    cl_items[r["cluster"]].add(r["question_id"])
multi = {c: v for c, v in cl_items.items() if len(v) >= 2}
sing = {c: v for c, v in cl_items.items() if len(v) == 1}
print(f"  clusters total={len(cl_items)}  multi-item={len(multi)}  singleton={len(sing)}")
print(f"  items in multi-item clusters={sum(len(v) for v in multi.values())}  "
      f"items in singletons={len(sing)}")
print(f"  multi-item cluster ids and sizes: "
      f"{sorted(((c, len(v)) for c, v in multi.items()), key=lambda t: -t[1])}")
print(f"  singleton cluster id range: min={min(sing)} max={max(sing)}")
print(f"  multi-item cluster id range: min={min(multi)} max={max(multi)}")

# what distinguishes multi vs singleton
print("\n  exam_part composition:")
for lab, cset in (("multi-item clusters", set(multi)), ("singleton clusters", set(sing))):
    c = Counter(r["exam_part"] for r in rows if r["cluster"] in cset)
    print(f"    {lab:22s} {dict(c.most_common())}")
print("  has_context composition:")
for lab, cset in (("multi-item clusters", set(multi)), ("singleton clusters", set(sing))):
    c = Counter(r["has_context"] for r in rows if r["cluster"] in cset)
    print(f"    {lab:22s} {dict(c.most_common())}")
print("  qlen (mean chars):")
for lab, cset in (("multi-item clusters", set(multi)), ("singleton clusters", set(sing))):
    v = [r["qlen"] for r in rows if r["cluster"] in cset]
    print(f"    {lab:22s} mean={statistics.mean(v):.1f} median={statistics.median(v)} n={len(v)}")
print("  accuracy:")
for lab, cset in (("multi-item clusters", set(multi)), ("singleton clusters", set(sing))):
    sub = [r for r in rows if r["cluster"] in cset]
    a = sum(r["A_correct"] for r in sub) / len(sub)
    b = sum(r["B_correct"] for r in sub) / len(sub)
    print(f"    {lab:22s} n={len(sub):4d} A={a:.4f} B={b:.4f} delta={b-a:+.4f}")


def icc_oneway(groups):
    g = {k: v for k, v in groups.items() if len(v) >= 1}
    k = len(g)
    N = sum(len(v) for v in g.values())
    if k < 2 or N <= k:
        return None
    grand = sum(sum(v) for v in g.values()) / N
    msb = msw = 0.0
    s2 = 0
    for v in g.values():
        n = len(v)
        m = sum(v) / n
        msb += n * (m - grand) ** 2
        msw += sum((x - m) ** 2 for x in v)
        s2 += n * n
    MSB = msb / (k - 1)
    MSW = msw / (N - k)
    n0 = (N - s2 / N) / (k - 1)
    den = MSB + (n0 - 1) * MSW
    return dict(k=k, N=N, n0=n0, mbar=N / k, icc=(MSB - MSW) / den if den else float("nan"))


def build(rs, gk, fn):
    g = defaultdict(list)
    for r in rs:
        g[gk(r)].append(fn(r))
    return g


A = lambda r: float(r["A_correct"])
D = lambda r: float(r["B_correct"] - r["A_correct"])

print("\n  ICC restricted to the 11 MULTI-ITEM clusters only (within model):")
for lab, fn in (("A_correct", A), ("delta", D)):
    vals = []
    for m in models:
        sub = [r for r in rows if r["model"] == m and r["cluster"] in multi]
        res = icc_oneway(build(sub, lambda r: r["cluster"], fn))
        vals.append(res["icc"])
    print(f"    {lab:10s} per-model ICC={[f'{v:+.4f}' for v in vals]} "
          f"mean={sum(vals)/len(vals):+.4f}  (k=11 clusters, N=128 items)")

print("\n  ICC restricted to multi-item clusters, all cells pooled:")
for lab, fn in (("A_correct", A), ("delta", D)):
    sub = [r for r in rows if r["cluster"] in multi]
    res = icc_oneway(build(sub, lambda r: r["cluster"], fn))
    de = 1 + (res["mbar"] - 1) * res["icc"]
    print(f"    {lab:10s} k={res['k']} N={res['N']} mbar={res['mbar']:.3f} "
          f"ICC={res['icc']:+.4f} DEFF={de:.3f} ESS={res['N']/de:.1f}")

# ---------------------------------------------------------------- C
print()
print("=" * 78)
print("C. PERMUTATION TESTS FOR ICC > 0  (randomisation, %d perms)" % NPERM)
print("=" * 78)


def perm_p(observed, null_draws):
    """one-sided upper p, add-one correction"""
    ge = sum(1 for x in null_draws if x >= observed - 1e-12)
    return (ge + 1) / (len(null_draws) + 1)


# C1: cluster ICC, within model -- permute item values across clusters
print("\n  C1. cluster ICC within model (permute item->cluster assignment):")
for lab, fn in (("A_correct", A), ("delta", D)):
    for m in models:
        sub = [r for r in rows if r["model"] == m]
        obs = icc_oneway(build(sub, lambda r: r["cluster"], fn))["icc"]
        cl = [r["cluster"] for r in sub]
        vals = [fn(r) for r in sub]
        null = []
        for _ in range(NPERM):
            random.shuffle(vals)
            g = defaultdict(list)
            for c, v in zip(cl, vals):
                g[c].append(v)
            null.append(icc_oneway(g)["icc"])
        print(f"    {lab:10s} {m.split('/')[-1]:22s} ICC={obs:+.4f} "
              f"null_mean={statistics.mean(null):+.4f} p={perm_p(obs, null):.4f}")

# C1b: cluster ICC on item means over models (325 values)
print("\n  C1b. cluster ICC of ITEM MEANS over the 4 models:")
im = defaultdict(list)
imd = defaultdict(list)
for r in rows:
    im[r["question_id"]].append(r["A_correct"])
    imd[r["question_id"]].append(r["B_correct"] - r["A_correct"])
for lab, src in (("mean A_correct", im), ("mean delta", imd)):
    qs = sorted(src)
    vals = [statistics.mean(src[q]) for q in qs]
    cls = [item_cluster[q] for q in qs]
    g = defaultdict(list)
    for c, v in zip(cls, vals):
        g[c].append(v)
    obs = icc_oneway(g)["icc"]
    null = []
    vv = list(vals)
    for _ in range(NPERM):
        random.shuffle(vv)
        gg = defaultdict(list)
        for c, v in zip(cls, vv):
            gg[c].append(v)
        null.append(icc_oneway(gg)["icc"])
    print(f"    {lab:16s} ICC={obs:+.4f} null_mean={statistics.mean(null):+.4f} "
          f"p={perm_p(obs, null):.4f}")

# C2: item ICC across models -- permute cells across items WITHIN model
print("\n  C2. item ICC across models (permute cell->item within each model,"
      " preserving each model's marginal):")
for lab, fn in (("A_correct", A), ("delta", D)):
    obs = icc_oneway(build(rows, lambda r: r["question_id"], fn))["icc"]
    bym = defaultdict(list)
    for r in rows:
        bym[r["model"]].append(r)
    qs_by_model = {m: [r["question_id"] for r in v] for m, v in bym.items()}
    vs_by_model = {m: [fn(r) for r in v] for m, v in bym.items()}
    null = []
    for _ in range(NPERM):
        g = defaultdict(list)
        for m in bym:
            vv = vs_by_model[m][:]
            random.shuffle(vv)
            for q, v in zip(qs_by_model[m], vv):
                g[q].append(v)
        null.append(icc_oneway(g)["icc"])
    print(f"    {lab:10s} ICC={obs:+.4f} null_mean={statistics.mean(null):+.4f} "
          f"null_sd={statistics.pstdev(null):.4f} p={perm_p(obs, null):.4f}")

# ---------------------------------------------------------------- D
print()
print("=" * 78)
print("D. CLUSTER BOOTSTRAP CIs FOR THE WITHIN-MODEL CLUSTER ICC (mean of 4)")
print("=" * 78)
by_cluster = defaultdict(list)
for r in rows:
    by_cluster[r["cluster"]].append(r)
cids = list(by_cluster)
for lab, fn in (("A_correct", A), ("delta", D)):
    draws = []
    for _ in range(NBOOT):
        pick = [random.choice(cids) for _ in cids]
        per_model = []
        for m in models:
            g = defaultdict(list)
            for j, c in enumerate(pick):
                for r in by_cluster[c]:
                    if r["model"] == m:
                        g[(j, c)].append(fn(r))
            res = icc_oneway(g)
            if res and not math.isnan(res["icc"]):
                per_model.append(res["icc"])
        if per_model:
            draws.append(sum(per_model) / len(per_model))
    draws.sort()
    lo = draws[int(0.025 * (len(draws) - 1))]
    hi = draws[int(0.975 * (len(draws) - 1))]
    print(f"  {lab:10s} mean-of-4 cluster ICC boot95 = [{lo:+.4f}, {hi:+.4f}] "
          f"median={statistics.median(draws):+.4f} (B={len(draws)})")

# ---------------------------------------------------------------- E
print()
print("=" * 78)
print("E. WHAT THE DEFF COSTS THE HEADLINE PAIRED TEST ON delta")
print("=" * 78)
d = [r["B_correct"] - r["A_correct"] for r in rows]
n = len(d)
mean_d = sum(d) / n
sd_d = statistics.stdev(d)
se_naive = sd_d / math.sqrt(n)
# cluster-robust SE: sum over clusters of cluster totals
cl_sum = defaultdict(float)
cl_n = Counter()
for r in rows:
    cl_sum[r["cluster"]] += (r["B_correct"] - r["A_correct"])
    cl_n[r["cluster"]] += 1
K = len(cl_sum)
# CR SE of the mean: sqrt( sum_c (S_c - n_c*mean)^2 ) / n , with small-sample factor
sq = sum((cl_sum[c] - cl_n[c] * mean_d) ** 2 for c in cl_sum)
se_cr = math.sqrt(sq) / n
fac = math.sqrt(K / (K - 1))
se_cr_hc1 = se_cr * fac
print(f"  n cells={n}  mean delta={mean_d:+.6f}  sd={sd_d:.6f}")
print(f"  naive SE (iid)          = {se_naive:.6f}   z = {mean_d/se_naive:+.3f}")
print(f"  cluster-robust SE (K={K}) = {se_cr_hc1:.6f}   z = {mean_d/se_cr_hc1:+.3f}")
print(f"  variance inflation (SE_cr/SE_naive)^2 = DEFF_empirical = "
      f"{(se_cr_hc1/se_naive)**2:.4f}")
# item-level robust (ignoring cluster)
it_sum = defaultdict(float)
it_n = Counter()
for r in rows:
    it_sum[r["question_id"]] += (r["B_correct"] - r["A_correct"])
    it_n[r["question_id"]] += 1
I = len(it_sum)
sqi = sum((it_sum[q] - it_n[q] * mean_d) ** 2 for q in it_sum)
se_it = math.sqrt(sqi) / n * math.sqrt(I / (I - 1))
print(f"  item-robust SE   (I={I}) = {se_it:.6f}   z = {mean_d/se_it:+.3f}   "
      f"DEFF_empirical = {(se_it/se_naive)**2:.4f}")
# model-robust (4 clusters only -- for reference)
mo_sum = defaultdict(float)
mo_n = Counter()
for r in rows:
    mo_sum[r["model"]] += (r["B_correct"] - r["A_correct"])
    mo_n[r["model"]] += 1
sqm = sum((mo_sum[m] - mo_n[m] * mean_d) ** 2 for m in mo_sum)
se_mo = math.sqrt(sqm) / n * math.sqrt(4 / 3)
print(f"  model-robust SE  (M=4)  = {se_mo:.6f}   z = {mean_d/se_mo:+.3f}   "
      f"DEFF_empirical = {(se_mo/se_naive)**2:.4f}  [only 4 groups -- not usable]")
print()

#!/usr/bin/env python3
"""
stats_structure4.py -- DEFF with UNEQUAL cluster sizes.

Cluster sizes here range 3..80 cells (CV is large), so DEFF = 1+(m_bar-1)rho
understates the inflation. The correct multiplier for unequal sizes is the
size-weighted mean cluster size
        m_eff = sum_c n_c^2 / sum_c n_c
(Kish). This script computes DEFF both ways and validates against the
empirical robust-variance DEFF computed in stats_structure3.py.
Stdlib only.
"""
import json
import math
import statistics
from collections import defaultdict, Counter

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")
rows = [r for r in json.load(open(DATA)) if r.get("analysis_include") is True]
models = sorted({r["model"] for r in rows})
item_cluster = {r["question_id"]: r["cluster"] for r in rows}
A = lambda r: float(r["A_correct"])
Bv = lambda r: float(r["B_correct"])
D = lambda r: float(r["B_correct"] - r["A_correct"])


def pairwise_icc(groups, center=None):
    allv = [x for v in groups.values() for x in v]
    N = len(allv)
    mu = center if center is not None else sum(allv) / N
    var = sum((x - mu) ** 2 for x in allv) / N
    num = 0.0
    P = 0
    for v in groups.values():
        n = len(v)
        if n < 2:
            continue
        s = sum(x - mu for x in v)
        ss = sum((x - mu) ** 2 for x in v)
        num += (s * s - ss) / 2.0
        P += n * (n - 1) // 2
    return (num / P) / var if P and var else None


def kish(sizes):
    N = sum(sizes)
    return sum(s * s for s in sizes) / N


print("=" * 78)
print("CLUSTER-SIZE INEQUALITY AND THE CORRECT DEFF MULTIPLIER")
print("=" * 78)

cells_per_cluster = Counter(r["cluster"] for r in rows)
items_per_cluster = Counter()
for q, c in item_cluster.items():
    items_per_cluster[c] += 1
cells_per_item = Counter(r["question_id"] for r in rows)

for lab, cnt, N in (("cells per cluster", cells_per_cluster, 1299),
                    ("items per cluster", items_per_cluster, 325),
                    ("cells per item   ", cells_per_item, 1299)):
    s = list(cnt.values())
    mbar = N / len(s)
    me = kish(s)
    cv = statistics.pstdev(s) / mbar
    print(f"  {lab}: groups={len(s)} N={N} m_bar={mbar:.4f} "
          f"m_eff(Kish)={me:.4f} CV={cv:.4f}  ratio m_eff/m_bar={me/mbar:.3f}")

mm = {}
for lab, fn in (("A", A), ("B", Bv), ("D", D)):
    mm[lab] = {m: statistics.mean([fn(r) for r in rows if r["model"] == m]) for m in models}

print()
print("=" * 78)
print("DEFF TABLE -- m_bar vs m_eff, validated against empirical robust DEFF")
print("=" * 78)


def emp_deff(fn, gk):
    y = [fn(r) for r in rows]
    n = len(y)
    mu = sum(y) / n
    v_iid = sum((x - mu) ** 2 for x in y) / (n - 1) / n
    S = defaultdict(float)
    C = Counter()
    for r in rows:
        S[gk(r)] += fn(r)
        C[gk(r)] += 1
    K = len(S)
    sq = sum((S[k] - C[k] * mu) ** 2 for k in S)
    return (sq / (n * n) * (K / (K - 1))) / v_iid


rows_out = []
for lab, key, fn in (("A_correct", "A", A), ("B_correct", "B", Bv), ("delta", "D", D)):
    # ITEM level (cells grouped by item), model-centred
    g = defaultdict(list)
    for r in rows:
        g[r["question_id"]].append(fn(r) - mm[key][r["model"]])
    rho_i = pairwise_icc(g, center=0.0)
    mb_i, me_i = 1299 / 325, kish(list(cells_per_item.values()))
    # CLUSTER level over all cells, model-centred
    g2 = defaultdict(list)
    for r in rows:
        g2[r["cluster"]].append(fn(r) - mm[key][r["model"]])
    rho_c = pairwise_icc(g2, center=0.0)
    mb_c, me_c = 1299 / 208, kish(list(cells_per_cluster.values()))
    # CLUSTER level, items within cluster (mean of the 4 within-model estimates)
    vv = []
    for m in models:
        sub = [r for r in rows if r["model"] == m]
        gg = defaultdict(list)
        for r in sub:
            gg[r["cluster"]].append(fn(r))
        vv.append(pairwise_icc(gg))
    rho_ic = sum(vv) / len(vv)
    mb_ic, me_ic = 325 / 208, kish(list(items_per_cluster.values()))

    print(f"\n  {lab}")
    print(f"    ITEM level  (4 models / item):   rho={rho_i:+.4f}  "
          f"DEFF(m_bar={mb_i:.3f})={1+(mb_i-1)*rho_i:.4f}  "
          f"DEFF(m_eff={me_i:.3f})={1+(me_i-1)*rho_i:.4f}  "
          f"| empirical(item-robust)={emp_deff(fn, lambda r: r['question_id']):.4f}")
    print(f"    ITEMS in CLUSTER (1 model):      rho={rho_ic:+.4f}  "
          f"DEFF(m_bar={mb_ic:.3f})={1+(mb_ic-1)*rho_ic:.4f}  "
          f"DEFF(m_eff={me_ic:.3f})={1+(me_ic-1)*rho_ic:.4f}")
    print(f"    CLUSTER over all cells (BOTH):   rho={rho_c:+.4f}  "
          f"DEFF(m_bar={mb_c:.3f})={1+(mb_c-1)*rho_c:.4f}  "
          f"DEFF(m_eff={me_c:.3f})={1+(me_c-1)*rho_c:.4f}  "
          f"| empirical(cluster-robust)={emp_deff(fn, lambda r: r['cluster']):.4f}")
    de_c = 1 + (me_c - 1) * rho_c
    de_i = 1 + (me_i - 1) * rho_i
    print(f"    ESS: naive=1299  item-level={1299/de_i:.1f}  "
          f"cluster-level(all sources)={1299/de_c:.1f}")

print()
print("=" * 78)
print("ATTRIBUTION: how much of the total inflation is item-reuse vs clustering")
print("=" * 78)
for lab, fn in (("A_correct", A), ("B_correct", Bv), ("delta", D)):
    di = emp_deff(fn, lambda r: r["question_id"])
    dc = emp_deff(fn, lambda r: r["cluster"])
    print(f"  {lab:10s} DEFF_item={di:.4f}  DEFF_cluster(total)={dc:.4f}  "
          f"item share of log-inflation = {math.log(di)/math.log(dc)*100:.1f}%  "
          f"cluster adds x{dc/di:.4f}")
print()

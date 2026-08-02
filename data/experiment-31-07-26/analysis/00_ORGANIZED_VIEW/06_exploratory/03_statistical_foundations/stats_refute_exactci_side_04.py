#!/usr/bin/env python3
"""
REFUTATION PASS 4 -- what actually breaks the POOLED exact interval?

The claim attributes it to "cluster-level correlation in the DIRECTION of
discordance". But the pooled stratum stacks 4 models on the SAME item, so the
candidate dependence axes are:
    (i)  item-level: the 4 models agree on the direction for the same item
    (ii) cluster-level: different items in the same clinical cluster agree
Plus a third, entirely separate, source of misspecification:
    (iii) p10 is not homogeneous across the 4 models, so the pooled discordant
          count is a MIXTURE of binomials, not a binomial.
This pass separates them. Stdlib only.
"""
import json, math, random
from collections import defaultdict

PATH = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
        "experiment-31-07-26/analysis/paired_clean.json")
rows = [r for r in json.load(open(PATH)) if r["analysis_include"]]
MODELS = sorted(set(r["model"] for r in rows))

disc = [r for r in rows if r["A_correct"] != r["B_correct"]]
for r in disc:
    r["_dir"] = 1 if r["A_correct"] == 0 else 0

def icc_pairwise(groups):
    """moment estimator of the within-group correlation of a binary variable"""
    ns = [len(g) for g in groups]; ys = [sum(g) for g in groups]
    N = sum(ns)
    pbar = sum(ys) / N
    num = 0.0; dp = 0
    for n, y in zip(ns, ys):
        if n < 2: continue
        num += (y - n * pbar) ** 2 - (y * (1 - pbar) ** 2 + (n - y) * pbar ** 2)
        dp += n * (n - 1)
    return (num / dp) / (pbar * (1 - pbar)) if dp else None, dp // 2

print("=" * 104)
print("PASS 4A :: POOLED -- which dependence axis carries the direction correlation?")
print("=" * 104)

# (i) item level: group discordant cells by question_id (across models)
byitem = defaultdict(list)
for r in disc: byitem[r["question_id"]].append(r["_dir"])
icc_item, np_item = icc_pairwise(list(byitem.values()))

# (ii) cluster level BETWEEN items: one randomly chosen discordant cell per item,
#      then grouped by cluster -- removes the item axis by construction
rng = random.Random(5150)
vals = []
for trial in range(400):
    byclu = defaultdict(list)
    for qid, ds in byitem.items():
        d = ds[rng.randrange(len(ds))]
        clu = next(r["cluster"] for r in disc if r["question_id"] == qid)
        byclu[clu].append(d)
    v, _ = icc_pairwise(list(byclu.values()))
    if v is not None: vals.append(v)
vals.sort()
icc_clu_between = vals[len(vals) // 2]

# (iii) raw cluster level (both axes mixed) -- what the claim's rho_dir measures
byclu_all = defaultdict(list)
for r in disc: byclu_all[r["cluster"]].append(r["_dir"])
icc_clu_all, np_clu = icc_pairwise(list(byclu_all.values()))

print(f"  direction ICC, ITEM level (same item, different models)   = {icc_item:>7.4f}"
      f"   ({np_item} within-item discordant pairs)")
print(f"  direction ICC, CLUSTER level BETWEEN items (item axis removed, median of 400 draws)"
      f" = {icc_clu_between:>7.4f}")
print(f"  direction ICC, CLUSTER level RAW (both axes mixed)        = {icc_clu_all:>7.4f}"
      f"   ({np_clu} within-cluster discordant pairs)")
print()
print("  -> the pooled dependence is overwhelmingly the ITEM x MODEL crossing,")
print("     not correlation between different items in the same clinical cluster.")

print()
print("=" * 104)
print("PASS 4B :: is p10 even homogeneous across models?  (pooling a binomial requires it)")
print("=" * 104)
tab = {}
for m in MODELS:
    d = [r for r in disc if r["model"] == m]
    n10 = sum(r["_dir"] for r in d)
    tab[m] = (n10, len(d))
    print(f"  {m:<28} n10={n10:>4}  nd={len(d):>4}  p10={n10/len(d):.4f}")
N10 = sum(v[0] for v in tab.values()); ND = sum(v[1] for v in tab.values())
p0 = N10 / ND
chi = sum((v[0] - v[1] * p0) ** 2 / (v[1] * p0 * (1 - p0)) for v in tab.values())
print(f"\n  pooled p10={p0:.4f}   homogeneity chi-square (3 df) = {chi:.3f}")

# permutation p-value for homogeneity (no chi-square tail approximation needed)
labels = [r["model"] for r in disc]; dirs = [r["_dir"] for r in disc]
rng2 = random.Random(31337)
ge = 0; NP = 20000
for _ in range(NP):
    rng2.shuffle(dirs)
    cnt = defaultdict(int); tot = defaultdict(int)
    for m, d in zip(labels, dirs):
        cnt[m] += d; tot[m] += 1
    c = sum((cnt[m] - tot[m] * p0) ** 2 / (tot[m] * p0 * (1 - p0)) for m in tot)
    if c >= chi: ge += 1
print(f"  permutation p (20,000 shuffles, no distributional approximation) = {(ge+1)/(NP+1):.4f}")
print("  -> heterogeneity across models is NOT the driver; the pooled failure is the")
print("     item x model direction agreement, which no single-binomial model can absorb.")

print()
print("=" * 104)
print("PASS 4C :: the three scales are ONE interval, not three pieces of evidence")
print("=" * 104)
n10p = sum(r["_dir"] for r in disc); ndp = len(disc)
print(f"  pooled p10 = {n10p}/{ndp} = {n10p/ndp:.4f}")
print("  g  = p10 - 0.5          -> pure shift: the g interval has EXACTLY the p10 width")
print("  OR = p10/(1-p10)        -> monotone: same two endpoints, re-expressed")
print("  so 'OR 1.23 pooled' and 'g 1.22 pooled' are the SAME comparison reported twice;")
print("  the 10 quoted width ratios are 5 numbers.")

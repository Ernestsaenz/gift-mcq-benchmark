#!/usr/bin/env python3
"""
prim_permutation_depstruct.py -- quantify the dependence that decides which
randomisation null is appropriate, and run the single most conservative test.

If discordances were independent across cells, coarsening the sign-flip unit
would not widen the null at all. It does widen it, and by exactly the amount
implied by the within-unit agreement of d = A_correct - B_correct.
"""
import json
from collections import defaultdict
from fractions import Fraction

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")
with open(DATA) as fh:
    rows = [r for r in json.load(fh) if r["analysis_include"] is True]
for r in rows:
    r["_d"] = r["A_correct"] - r["B_correct"]
models = sorted({r["model"] for r in rows})

print("=" * 88)
print("A. WITHIN-ITEM AGREEMENT ACROSS THE 4 MODELS  (drives S1 -> S2 inflation)")
print("=" * 88)
it = defaultdict(list)
for r in rows:
    it[r["question_id"]].append(r["_d"])
D_item = {q: sum(v) for q, v in it.items()}
n_disc_cells_in_item = {q: sum(1 for x in v if x != 0) for q, v in it.items()}
hist = defaultdict(int)
for q in it:
    hist[n_disc_cells_in_item[q]] += 1
print("items by number of models showing a discordance (of 4):")
for k in sorted(hist):
    print(f"   {k} model(s) discordant : {hist[k]:>4} items")
sumD_item = sum(abs(v) for v in D_item.values())
sumd_cell = sum(abs(r["_d"]) for r in rows)
print(f"sum|D_item| = {sumD_item}   sum|d_cell| = {sumd_cell}   "
      f"ratio = {sumD_item/sumd_cell:.3f}")
print("   ratio 1.000 => models fail the SAME items in the SAME direction "
      "(max dependence)")
print("   ratio ~0.5  => the 4 models' discordances are unrelated "
      "(independence, ratio -> E|sum|/E sum| )")
# how many items have all 4 models discordant and all in the same direction
allsame = sum(1 for q, v in it.items()
              if all(x != 0 for x in v) and len({x for x in v}) == 1)
print(f"items where ALL models present are discordant in the SAME direction: "
      f"{allsame}")

print()
print("=" * 88)
print("B. WITHIN-CLUSTER AGREEMENT  (drives S2 -> S3 inflation)")
print("=" * 88)
cl = defaultdict(list)
cl_items = defaultdict(set)
for r in rows:
    cl[r["cluster"]].append(r["_d"])
    cl_items[r["cluster"]].add(r["question_id"])
D_cl = {c: sum(v) for c, v in cl.items()}
sizes = defaultdict(int)
for c in cl_items:
    sizes[len(cl_items[c])] += 1
print("clusters by number of items nested inside:")
for k in sorted(sizes):
    print(f"   {k} item(s) : {sizes[k]:>4} clusters")
print(f"sum|D_cluster| = {sum(abs(v) for v in D_cl.values())}   "
      f"sum|D_item| = {sumD_item}   "
      f"ratio = {sum(abs(v) for v in D_cl.values())/sumD_item:.3f}")

print()
print("=" * 88)
print("C. MOST CONSERVATIVE TEST OF ALL: cluster-level DIRECTION sign test")
print("   (flip whole clusters AND discard magnitude -- each cluster votes once)")
print("=" * 88)
def binom_tail(k, n):
    if n == 0:
        return Fraction(1)
    tot = 0
    for i in range(k + 1):
        c = 1
        for j in range(i):
            c = c * (n - j) // (j + 1)
        tot += c
    return Fraction(tot, 1 << n)

print(f"{'level':<26}{'clus A>B':>10}{'clus A<B':>10}{'tied':>7}"
      f"{'exact 2-sided p':>18}")
for m in models + ["POOLED"]:
    acc = defaultdict(int)
    for r in rows:
        if m == "POOLED" or r["model"] == m:
            acc[r["cluster"]] += r["_d"]
    pos = sum(1 for v in acc.values() if v > 0)
    neg = sum(1 for v in acc.values() if v < 0)
    tie = sum(1 for v in acc.values() if v == 0)
    p = min(Fraction(1), 2 * binom_tail(min(pos, neg), pos + neg))
    print(f"{m:<26}{pos:>10}{neg:>10}{tie:>7}{float(p):>18.4e}")

print()
print("=" * 88)
print("D. HOW BIG A NULL EFFECT WOULD THE MOST CONSERVATIVE TEST STILL REJECT?")
print("=" * 88)
accp = defaultdict(int)
for r in rows:
    accp[r["cluster"]] += r["_d"]
pos = sum(1 for v in accp.values() if v > 0)
neg = sum(1 for v in accp.values() if v < 0)
nd = pos + neg
# smallest k such that 2*P(X<=k) > 0.05 for X~Binom(nd,1/2)
k = 0
while float(min(Fraction(1), 2 * binom_tail(k, nd))) <= 0.05:
    k += 1
print(f"pooled: {nd} non-tied clusters, {pos} favour A. "
      f"Significance at 0.05 is lost only once the minority count reaches "
      f"{k} of {nd} (observed minority = {neg}).")
print(f"i.e. {k - neg} clusters would have to reverse direction before the "
      f"cluster-level result stopped being significant.")

#!/usr/bin/env python3
"""
Part 3: pin down the bootstrap width to sub-MC precision, test spec ambiguities
(ratio vs fixed denominator; percentile vs basic), and check the missing 1300th cell.
"""
import json, random, math, statistics
from collections import defaultdict, Counter

BASE = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
rows = json.load(open(f"{BASE}/paired_clean.json"))
inc = [r for r in rows if r["analysis_include"]]
n = len(inc)
pooled = sum(r["B_correct"] - r["A_correct"] for r in inc) / n

# --- the unbalanced cell ---
bym = defaultdict(set)
for r in inc:
    bym[r["model"]].add(r["question_id"])
allitems = set().union(*bym.values())
for m, s in bym.items():
    miss = allitems - s
    if miss:
        print(f"model {m} missing items: {sorted(miss)}  (n={len(s)})")
print(f"analysis items: {len(allitems)}; cells {n} vs 4*{len(allitems)}={4*len(allitems)}")

by_cluster = defaultdict(list)
for r in inc:
    by_cluster[r["cluster"]].append(r["B_correct"] - r["A_correct"])
clusters = sorted(by_cluster)
K = len(clusters)
sums = [sum(by_cluster[c]) for c in clusters]
ns = [len(by_cluster[c]) for c in clusters]

def boot(seed, reps, fixed_denom=False):
    rng = random.Random(seed); rr = rng.randrange
    out = []
    for _ in range(reps):
        s = 0; m = 0
        for _ in range(K):
            j = rr(K); s += sums[j]; m += ns[j]
        out.append(s / (n if fixed_denom else m))
    out.sort()
    return out

print("\n--- bootstrap width at high precision (ratio denominator, percentile) ---")
ws = []
for sd in (2001, 2002, 2003, 2004, 2005):
    d = boot(sd, 200000)
    lo, hi = d[5000] * 100, d[195000] * 100
    ws.append(hi - lo)
    print(f"  B=200000 seed={sd}: [{lo:.4f}, {hi:.4f}] width {hi-lo:.4f}")
print(f"  converged width ~ {statistics.mean(ws):.4f} (sd {statistics.stdev(ws):.4f})")
print(f"  CLAIMED width 6.33 -> deviation {6.33-statistics.mean(ws):+.4f} pp")

print("\n--- spec ambiguity: fixed denominator n instead of resampled m ---")
d = boot(3001, 200000, fixed_denom=True)
lo, hi = d[5000] * 100, d[195000] * 100
print(f"  fixed-denom percentile: [{lo:.4f}, {hi:.4f}] width {hi-lo:.4f}")

print("\n--- spec ambiguity: basic (reverse-percentile) instead of percentile ---")
d = boot(4001, 200000)
lo_p, hi_p = d[5000], d[195000]
print(f"  basic: [{(2*pooled-hi_p)*100:.4f}, {(2*pooled-lo_p)*100:.4f}] "
      f"width {(hi_p-lo_p)*100:.4f}")

print("\n--- influence of the largest clusters on the BASELINE itself ---")
order = sorted(range(K), key=lambda i: -ns[i])
for i in order[:5]:
    s2 = sum(sums) - sums[i]; n2 = n - ns[i]
    print(f"  drop cluster {clusters[i]} (n={ns[i]}, sum={sums[i]}): "
          f"delta -> {s2/n2*100:.4f} pp (shift {(s2/n2-pooled)*100:+.4f})")

print("\n--- unfiltered set (no exclusions at all) for context ---")
n_all = len(rows)
d_all = sum(r["B_correct"] - r["A_correct"] for r in rows) / n_all
a_all = sum(r["A_correct"] for r in rows) / n_all
b_all = sum(r["B_correct"] for r in rows) / n_all
t = Counter((r["A_correct"], r["B_correct"]) for r in rows)
print(f"  n={n_all} A={a_all*100:.4f}% B={b_all*100:.4f}% delta={d_all*100:.4f} pp "
      f"1->0={t[(1,0)]} 0->1={t[(0,1)]} tie={t[(1,1)]+t[(0,0)]}")
# position-a-only subset
pa = [r for r in rows if r["excl_nota_position_a"] and not r["excl_item_defect"]]
d_pa = sum(r["B_correct"] - r["A_correct"] for r in pa) / len(pa)
print(f"  position-a-only cells n={len(pa)} delta={d_pa*100:.4f} pp")
df = [r for r in rows if r["excl_item_defect"]]
print(f"  defect-item cells n={len(df)} delta="
      f"{sum(r['B_correct']-r['A_correct'] for r in df)/len(df)*100:.4f} pp")

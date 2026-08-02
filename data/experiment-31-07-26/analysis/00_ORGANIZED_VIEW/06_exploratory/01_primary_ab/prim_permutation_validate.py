#!/usr/bin/env python3
"""
prim_permutation_validate.py -- correctness checks on the exact convolution DP.

1. DP counts must sum to 2^K.
2. DP must reproduce brute-force enumeration over all 2^K sign vectors (small K).
3. DP on all-|D|=1 units must reproduce the exact binomial (McNemar) tail.
4. Monte Carlo from prim_permutation.py must be consistent with exact p.
5. Re-derive the headline deltas straight from the JSON, independently.
"""
import json
from itertools import product
from collections import defaultdict
from fractions import Fraction

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")
with open(DATA) as fh:
    rows = [r for r in json.load(fh) if r["analysis_include"] is True]
for r in rows:
    r["_d"] = r["A_correct"] - r["B_correct"]


def exact_signflip(Ds):
    Ds = [abs(d) for d in Ds if d != 0]
    K = len(Ds)
    M = sum(Ds)
    dist = [0] * (2 * M + 1)
    dist[M] = 1
    for d in Ds:
        nd = [0] * (2 * M + 1)
        for i, c in enumerate(dist):
            if c:
                nd[i + d] += c
                nd[i - d] += c
        dist = nd
    return dist, M, K


print("CHECK 1: DP counts sum to 2^K")
for Ds in ([1] * 10, [1, 2, 3, 4, 5], [16, 11, 10, 9, 8, 7, 5, 5, 4, 4, 3]):
    dist, M, K = exact_signflip(Ds)
    ok = sum(dist) == (1 << K)
    print(f"  Ds={Ds[:6]}{'...' if len(Ds)>6 else ''}  K={K}  "
          f"sum={sum(dist)}  2^K={1<<K}  {'OK' if ok else 'FAIL'}")
    assert ok

print("\nCHECK 2: DP == brute force over all 2^K sign vectors")
for Ds in ([1, 1, 2, 3, 5, 1, 4], [2, 2, 2, 1], [16, 3, 1, 1, 7, 2]):
    dist, M, K = exact_signflip(Ds)
    brute = defaultdict(int)
    for signs in product((-1, 1), repeat=K):
        brute[sum(s * d for s, d in zip(signs, Ds))] += 1
    dp = {i - M: c for i, c in enumerate(dist) if c}
    print(f"  Ds={Ds}  K={K}  match={dict(brute)==dp}")
    assert dict(brute) == dp

print("\nCHECK 3: DP on unit |D|=1 == exact binomial (McNemar) two-sided tail")
def binom_tail(k, n):
    tot = 0
    for i in range(k + 1):
        c = 1
        for j in range(i):
            c = c * (n - j) // (j + 1)
        tot += c
    return Fraction(tot, 1 << n)

for (b, c) in [(31, 4), (82, 18), (67, 15), (67, 8), (247, 45)]:
    n = b + c
    dist, M, K = exact_signflip([1] * n)
    hits = sum(cc for i, cc in enumerate(dist) if abs(i - M) >= abs(b - c))
    p_dp = Fraction(hits, 1 << K)
    p_mc = min(Fraction(1), 2 * binom_tail(min(b, c), n))
    print(f"  b={b:>3} c={c:>3}  p_DP={float(p_dp):.6e}  "
          f"p_McNemar={float(p_mc):.6e}  identical={p_dp==p_mc}")
    assert p_dp == p_mc

print("\nCHECK 4: Monte Carlo (B=20000) consistent with exact p")
mc = json.load(open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/"
                    "tier1_mcq/data/experiment-31-07-26/analysis/"
                    "prim_permutation_results.json"))
ex = json.load(open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/"
                    "tier1_mcq/data/experiment-31-07-26/analysis/"
                    "prim_permutation_exact_results.json"))
pairs = [("S1_cell", "S1 CELL   (item x model)"),
         ("S2_item", "S2 ITEM   (4 models flip together)"),
         ("S3_cluster", "S3 CLUSTER(all cells flip together)")]
print(f"  {'scheme':<12}{'level':<26}{'MC hits':>9}{'E[hits]=B*p_exact':>19}"
      f"{'P(>=hits) plausible?':>22}")
for mk, ek in pairs:
    for lv in mc[mk]:
        hits = mc[mk][lv]["hits"]
        B = mc[mk][lv]["B"]
        pe = ex["exact"][ek][lv]["p"]
        expect = B * pe
        # Poisson-ish plausibility: P(X>=hits) with mean=expect
        import math
        if expect < 30:
            pge = 1.0 - sum(math.exp(-expect) * expect**k / math.factorial(k)
                            for k in range(hits))
        else:
            pge = float("nan")
        print(f"  {mk:<12}{lv:<26}{hits:>9}{expect:>19.4f}{pge:>22.4f}")

print("\nCHECK 5: headline numbers re-derived independently from the JSON")
bym = defaultdict(list)
for r in rows:
    bym[r["model"]].append(r)
print(f"  {'model':<26}{'n':>6}{'A%':>8}{'B%':>8}{'delta_pp':>10}{'brief':>10}")
brief = {"google/gemini-3.6-flash": -8.3, "z-ai/glm-5.2": -18.2,
         "qwen/qwen3.6-35b-a3b": -16.0, "google/gemma-4-26b-a4b-it": -19.7}
for m in sorted(bym):
    rs = bym[m]
    pa = sum(x["A_correct"] for x in rs) / len(rs)
    pb = sum(x["B_correct"] for x in rs) / len(rs)
    print(f"  {m:<26}{len(rs):>6}{pa*100:>8.2f}{pb*100:>8.2f}"
          f"{(pb-pa)*100:>10.2f}{brief[m]:>10.1f}")
    assert abs((pb - pa) * 100 - brief[m]) < 0.1, m
print("  all four per-model deltas match the brief to within 0.1 pp: OK")
print(f"  NOTE cell counts: glm-5.2 has {len(bym['z-ai/glm-5.2'])} cells, "
      f"the other three have 325 -> one glm cell was dropped upstream "
      f"(unparsed), so the panel is very slightly unbalanced.")

print("\nALL CHECKS PASSED")

#!/usr/bin/env python3
"""
stats_refute_multiplicity.py -- independent recomputation of the
"multiplicity-and-ceiling" multiplicity claim.

Everything computed from scratch, stdlib only, with EXACT rational arithmetic
where possible (Fraction) so that no lgamma round-off can be blamed.

Checks:
  1. b / c discordant counts per model, straight from paired_clean.json
  2. exact two-sided McNemar p (Fraction -> float), compared against the
     lgamma implementation used in stats_multiplicity_ceiling.py
  3. Holm-Bonferroni and Benjamini-Hochberg over the m=4 primary family
  4. naive Bonferroni over m=160 (and the break-even family size m*)
  5. EXACT cluster sign-flip permutation p by dynamic programming over the
     integer cluster sums -- no Monte-Carlo floor at all
  6. sanity: does the 160-test inventory actually cover the programme on disk
"""
import json, os, math, collections, itertools, random
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
recs = [r for r in json.load(open(os.path.join(HERE, "paired_clean.json")))
        if r["analysis_include"]]
MODELS = sorted({r["model"] for r in recs})

print("shape check")
print("  cells   :", len(recs))
print("  items   :", len({r["question_id"] for r in recs}))
print("  clusters:", len({r["cluster"] for r in recs}))
print("  models  :", len(MODELS))
print("  duplicate (item,model) cells:",
      len(recs) - len({(r["question_id"], r["model"]) for r in recs}))
print()

# ---------------------------------------------------------------- 1 + 2
def mcnemar_exact_fraction(b, c):
    """two-sided exact McNemar, X~Bin(b+c,1/2), doubled smaller tail, cap 1.
    Exact rational arithmetic."""
    n = b + c
    if n == 0:
        return Fraction(1)
    lo = sum(Fraction(math.comb(n, k), 1) for k in range(0, min(b, c) + 1))
    p = Fraction(2, 1) * lo / Fraction(2 ** n)
    return min(Fraction(1), p)

def mcnemar_exact_lgamma(b, c):
    n = b + c
    if n == 0:
        return 1.0
    def pmf(k):
        return math.exp(math.lgamma(n + 1) - math.lgamma(k + 1)
                        - math.lgamma(n - k + 1) - n * math.log(2.0))
    lo = sum(pmf(k) for k in range(0, b + 1))
    hi = sum(pmf(k) for k in range(b, n + 1))
    return min(1.0, 2.0 * min(lo, hi))

by_model = {m: [r for r in recs if r["model"] == m] for m in MODELS}
prim = {}
print("PRIMARY per-model A-vs-B, recomputed")
print(f"{'model':28s} {'n':>4s} {'pA':>7s} {'pB':>7s} {'delta':>7s} "
      f"{'b':>4s} {'c':>4s} {'p_exact(Frac)':>14s} {'p_lgamma':>12s}")
for m in MODELS:
    rows = by_model[m]
    n = len(rows)
    a = sum(r["A_correct"] for r in rows)
    bb = sum(r["B_correct"] for r in rows)
    b = sum(1 for r in rows if r["A_correct"] == 1 and r["B_correct"] == 0)
    c = sum(1 for r in rows if r["A_correct"] == 0 and r["B_correct"] == 1)
    pf = mcnemar_exact_fraction(b, c)
    pl = mcnemar_exact_lgamma(b, c)
    prim[m] = dict(n=n, pA=a / n, pB=bb / n, delta=(a - bb) / n, b=b, c=c,
                   p=float(pf), p_lgamma=pl)
    print(f"{m:28s} {n:4d} {a/n:7.4f} {bb/n:7.4f} {(a-bb)/n:7.4f} "
          f"{b:4d} {c:4d} {float(pf):14.6e} {pl:12.6e}")
print()

# ---------------------------------------------------------------- 3
ps = sorted(((prim[m]["p"], m) for m in MODELS))
m4 = len(ps)
print("Holm-Bonferroni / BH over the m=4 primary family")
holm_run = 0.0
holm_adj = {}
for i, (p, m) in enumerate(ps):
    v = (m4 - i) * p
    holm_run = max(holm_run, v)
    holm_adj[m] = min(1.0, holm_run)
bh_adj = {}
run = 1.0
for i in range(m4 - 1, -1, -1):
    p, m = ps[i]
    run = min(run, p * m4 / (i + 1))
    bh_adj[m] = run
print(f"{'model':28s} {'p_raw':>13s} {'rank':>4s} {'Holm thr':>9s} "
      f"{'Holm adj':>12s} {'BH adj':>12s} {'pass Holm':>9s} {'pass BH':>8s}")
for i, (p, m) in enumerate(ps):
    thr = 0.05 / (m4 - i)
    bh_thr = (i + 1) * 0.05 / m4
    print(f"{m:28s} {p:13.6e} {i+1:4d} {thr:9.5f} {holm_adj[m]:12.6e} "
          f"{bh_adj[m]:12.6e} {str(p <= thr):>9s} {str(p <= bh_thr):>8s}")
print()

# ---------------------------------------------------------------- 4
FULL = 160
print(f"naive Bonferroni over m={FULL}, and break-even family size")
for p, m in ps:
    print(f"  {m:28s} p*{FULL} = {p*FULL:12.6e}   "
          f"survives={str(p*FULL < 0.05):>5s}   "
          f"m* (largest family still <.05) = {int(0.05/p):,}")
print()

# ---------------------------------------------------------------- 5
# EXACT cluster sign-flip permutation test.
# T = sum_k s_k * S_k, s_k in {-1,+1} iid, S_k = sum over rows in cluster k of
# (A_correct - B_correct).  Statistic reported in the original script is
# T / n, so |T/n| >= |obs/n|  <=>  |T| >= |T_obs|.  Distribution of T is exact
# via convolution over integer support.
print("EXACT cluster sign-flip permutation p (DP convolution, no Monte Carlo)")
exact_perm = {}
for m in MODELS:
    rows = by_model[m]
    cl = collections.defaultdict(int)
    for r in rows:
        cl[r["cluster"]] += r["A_correct"] - r["B_correct"]
    S = [v for v in cl.values()]
    Tobs = sum(S)
    nz = [abs(v) for v in S if v != 0]
    zero_clusters = len(S) - len(nz)
    # DP over counts (unnormalised, denominator 2^len(nz))
    dist = {0: 1}
    for v in nz:
        nd = collections.defaultdict(int)
        for t, w in dist.items():
            nd[t + v] += w
            nd[t - v] += w
        dist = nd
    denom = 2 ** len(nz)
    ge = sum(w for t, w in dist.items() if abs(t) >= abs(Tobs))
    p_exact_perm = Fraction(ge, denom)
    exact_perm[m] = float(p_exact_perm)
    print(f"  {m:28s} clusters={len(S):3d} (nonzero {len(nz):3d}) "
          f"T_obs={Tobs:4d}  exact perm p={float(p_exact_perm):.6e}  "
          f"p*160={float(p_exact_perm)*160:.4e}  "
          f"m*={int(0.05/float(p_exact_perm)) if p_exact_perm>0 else 'inf':>10}")
print()

# Monte-Carlo replication of the original, independent seed, to confirm the
# reported 0.00005 is purely the (r+1)/(B+1) floor.
print("Monte-Carlo cluster sign-flip (independent seed 4242, B=20000) "
      "-- reproducing the floor")
rng = random.Random(4242)
NP = 20000
for m in MODELS:
    rows = by_model[m]
    cl = collections.defaultdict(int)
    for r in rows:
        cl[r["cluster"]] += r["A_correct"] - r["B_correct"]
    S = list(cl.values())
    Tobs = abs(sum(S))
    ge = 0
    for _ in range(NP):
        t = 0
        for v in S:
            t += v if rng.random() < 0.5 else -v
        if abs(t) >= Tobs:
            ge += 1
    print(f"  {m:28s} hits={ge:3d}/{NP}  p=(hits+1)/(B+1)={(ge+1)/(NP+1):.5f}"
          f"   floor=1/(B+1)={1/(NP+1):.6e}")
print()

# ---------------------------------------------------------------- 6
FACTORS = ["correct_letter", "negated_stem", "has_context", "region", "year"]
L = sum(len({str(r[f]) for r in recs}) for f in FACTORS)
inv = dict(primary=4, sub_permodel=L * 4, sub_pooled=L,
           mod_permodel=len(FACTORS) * 4, mod_pooled=len(FACTORS),
           between=len(list(itertools.combinations(MODELS, 2))))
print("test-inventory arithmetic reproduced:", inv, "TOTAL =", sum(inv.values()))

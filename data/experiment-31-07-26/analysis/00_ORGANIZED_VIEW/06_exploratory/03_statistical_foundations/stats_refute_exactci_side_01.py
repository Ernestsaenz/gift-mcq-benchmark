#!/usr/bin/env python3
"""
REFUTATION PASS 1 -- independent recomputation of:
  (a) the 2x2 discordance tables,
  (b) Clopper-Pearson exact intervals for p10 -> OR -> Cohen g,
  (c) cluster bootstrap percentile intervals for OR and g,
  (d) the width ratios boot/exact quoted in the claim,
  (e) the *leverage structure*: how much of the discordance actually sits in
      multi-discordant clusters (the only place a direction-ICC can bite).

Stdlib only. All tails computed from scratch.
"""
import json, math, random
from collections import defaultdict

PATH = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
        "experiment-31-07-26/analysis/paired_clean.json")

# ------------------------------------------------------------------ incomplete beta
def betacf(a, b, x):
    MAXIT, EPS, FPMIN = 400, 3e-16, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < FPMIN: d = FPMIN
    d = 1.0 / d; h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d; d = FPMIN if abs(d) < FPMIN else d; d = 1.0 / d
        c = 1.0 + aa / c; c = FPMIN if abs(c) < FPMIN else c
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d; d = FPMIN if abs(d) < FPMIN else d; d = 1.0 / d
        c = 1.0 + aa / c; c = FPMIN if abs(c) < FPMIN else c
        de = d * c; h *= de
        if abs(de - 1.0) < EPS: break
    return h

def betai(a, b, x):
    if x <= 0.0: return 0.0
    if x >= 1.0: return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                  + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * betacf(a, b, x) / a
    return 1.0 - bt * betacf(b, a, 1.0 - x) / b

def beta_q(p, a, b, iters=60):
    lo, hi = 0.0, 1.0
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if betai(a, b, mid) < p: lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)

def cp(k, n, alpha=0.05):
    """Clopper-Pearson exact interval for a binomial proportion."""
    if n == 0: return (0.0, 1.0)
    lo = 0.0 if k == 0 else beta_q(alpha / 2.0, k, n - k + 1)
    hi = 1.0 if k == n else beta_q(1.0 - alpha / 2.0, k + 1, n - k)
    return lo, hi

# --- independent cross-check of cp() against a directly summed binomial tail ---
def binom_tail_ge(k, n, p):
    """P(X >= k) summed exactly with lgamma coefficients."""
    if k <= 0: return 1.0
    if k > n: return 0.0
    if p <= 0.0: return 0.0
    if p >= 1.0: return 1.0
    lp, lq = math.log(p), math.log1p(-p)
    tot = 0.0
    for i in range(k, n + 1):
        tot += math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                        + i * lp + (n - i) * lq)
    return min(1.0, tot)

def binom_tail_le(k, n, p):
    if k >= n: return 1.0
    if k < 0: return 0.0
    return min(1.0, 1.0 - binom_tail_ge(k + 1, n, p)) if p < 1 else 0.0

def cp_bisect(k, n, alpha=0.05):
    """Clopper-Pearson by root-finding on the exact binomial tail (independent path)."""
    lo, hi = 0.0, 1.0
    if k > 0:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = 0.5 * (a + b)
            if binom_tail_ge(k, n, m) < alpha / 2.0: a = m
            else: b = m
        lo = 0.5 * (a + b)
    if k < n:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = 0.5 * (a + b)
            if binom_tail_le(k, n, m) > alpha / 2.0: a = m
            else: b = m
        hi = 0.5 * (a + b)
    return lo, hi

def or_of(p):   return p / (1.0 - p) if p < 1 else float('inf')
def g_of(p):    return p - 0.5

# ------------------------------------------------------------------ data
rows = [r for r in json.load(open(PATH)) if r["analysis_include"]]
MODELS = sorted(set(r["model"] for r in rows))
print("=" * 100)
print("PASS 1 :: independent recomputation")
print("=" * 100)
print(f"cells={len(rows)}  items={len(set(r['question_id'] for r in rows))}  "
      f"clusters={len(set(r['cluster'] for r in rows))}  models={len(MODELS)}")

def stratum_rows(label):
    return rows if label == "POOLED" else [r for r in rows if r["model"] == label]

STRATA = ["POOLED"] + MODELS
BOOT = 20000
SEED = 31072026

summary = {}
print()
print("-" * 100)
print("2x2 tables, exact CP intervals, and cluster-bootstrap percentile intervals")
print("-" * 100)
hdr = (f"{'stratum':<26}{'n10':>5}{'n01':>5}{'nd':>6}{'p10':>8}"
       f"{'  exact CP p10':<24}{'  boot p10':<24}")
print(hdr)
for label in STRATA:
    rs = stratum_rows(label)
    n10 = sum(1 for r in rs if r["A_correct"] == 0 and r["B_correct"] == 1)
    n01 = sum(1 for r in rs if r["A_correct"] == 1 and r["B_correct"] == 0)
    n11 = sum(1 for r in rs if r["A_correct"] == 1 and r["B_correct"] == 1)
    n00 = sum(1 for r in rs if r["A_correct"] == 0 and r["B_correct"] == 0)
    nd = n10 + n01
    p10 = n10 / nd
    lo, hi = cp(n10, nd)
    lo2, hi2 = cp_bisect(n10, nd)
    assert abs(lo - lo2) < 1e-9 and abs(hi - hi2) < 1e-9, (label, lo, lo2, hi, hi2)

    # cluster bootstrap
    byclu = defaultdict(list)
    for r in rs:
        byclu[r["cluster"]].append((r["A_correct"], r["B_correct"]))
    clus = list(byclu.values())
    K = len(clus)
    rng = random.Random(SEED + hash(label) % 10000)
    bp, bor, bg = [], [], []
    deg_lo = deg_hi = 0
    for _ in range(BOOT):
        a = b = 0
        for _ in range(K):
            for (ac, bc) in clus[rng.randrange(K)]:
                if ac == 0 and bc == 1: a += 1
                elif ac == 1 and bc == 0: b += 1
        if a + b == 0: continue
        p = a / (a + b)
        bp.append(p)
        if a == 0: deg_lo += 1
        if b == 0: deg_hi += 1
        bor.append(a / b if b > 0 else float('inf'))
        bg.append(p - 0.5)
    bp.sort()
    def pct(v, q):
        i = q * (len(v) - 1)
        f = math.floor(i); c = min(f + 1, len(v) - 1)
        return v[f] + (i - f) * (v[c] - v[f])
    blo, bhi = pct(bp, 0.025), pct(bp, 0.975)

    summary[label] = dict(n10=n10, n01=n01, n11=n11, n00=n00, nd=nd, p10=p10,
                          cp=(lo, hi), boot_p10=(blo, bhi),
                          deg_lo=deg_lo, deg_hi=deg_hi, nboot=len(bp), K=K)
    print(f"{label:<26}{n10:>5}{n01:>5}{nd:>6}{p10:>8.4f}"
          f"  [{lo:.4f}, {hi:.4f}]      [{blo:.4f}, {bhi:.4f}]")

print()
print("-" * 100)
print("WIDTH RATIOS  (bootstrap / exact) -- the numbers the claim quotes")
print("  all three scales are 1-1 monotone transforms of p10, so the SAME interval endpoints")
print("  are simply re-expressed;  OR = p/(1-p),  g = p - 0.5")
print("-" * 100)
print(f"{'stratum':<26}{'ratio_p10':>11}{'ratio_g':>10}{'ratio_OR':>10}"
      f"{'   exact OR':<22}{'   boot OR':<22}")
for label in STRATA:
    s = summary[label]
    lo, hi = s["cp"]; blo, bhi = s["boot_p10"]
    w_e_p, w_b_p = hi - lo, bhi - blo
    w_e_g, w_b_g = w_e_p, w_b_p                       # g is a shift: identical width
    w_e_o = or_of(hi) - or_of(lo)
    w_b_o = or_of(bhi) - or_of(blo)
    print(f"{label:<26}{w_b_p/w_e_p:>11.3f}{w_b_g/w_e_g:>10.3f}{w_b_o/w_e_o:>10.3f}"
          f"   [{or_of(lo):.3f}, {or_of(hi):.3f}]      [{or_of(blo):.3f}, {or_of(bhi):.3f}]")

print()
print("-" * 100)
print("BOOTSTRAP DEGENERACY  (replicates with n10=0 or n01=0 -> OR at a boundary)")
print("-" * 100)
for label in STRATA:
    s = summary[label]
    print(f"{label:<26} reps={s['nboot']:>6}  n10=0 in {s['deg_lo']:>5} "
          f"({100*s['deg_lo']/s['nboot']:.2f}%)   n01=0 in {s['deg_hi']:>5} "
          f"({100*s['deg_hi']/s['nboot']:.2f}%)")

print()
print("-" * 100)
print("LEVERAGE: where the discordant pairs actually live")
print("  a direction-ICC can only affect inference through clusters holding >=2 discordant pairs")
print("-" * 100)
print(f"{'stratum':<26}{'nd':>6}{'clusters w/ nd>=1':>19}{'clusters w/ nd>=2':>19}"
      f"{'pairs in nd>=2 clu':>20}{'% of nd':>9}{'max nd/clu':>12}")
lev = {}
for label in STRATA:
    rs = stratum_rows(label)
    dbyclu = defaultdict(int)
    for r in rs:
        if r["A_correct"] != r["B_correct"]:
            dbyclu[r["cluster"]] += 1
    nd = sum(dbyclu.values())
    c1 = sum(1 for v in dbyclu.values() if v >= 1)
    c2 = sum(1 for v in dbyclu.values() if v >= 2)
    inpairs = sum(v for v in dbyclu.values() if v >= 2)
    mx = max(dbyclu.values())
    lev[label] = dict(nd=nd, c2=c2, inpairs=inpairs, sizes=sorted(dbyclu.values(), reverse=True))
    print(f"{label:<26}{nd:>6}{c1:>19}{c2:>19}{inpairs:>20}{100*inpairs/nd:>8.1f}%{mx:>12}")

print()
print("  discordant-pairs-per-cluster distributions (descending, non-zero only):")
for label in STRATA:
    print(f"    {label:<26}{lev[label]['sizes'][:22]}")

json.dump({k: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in v.items()}
           for k, v in summary.items()},
          open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
               "experiment-31-07-26/analysis/stats_refute_exactci_side_01_out.json", "w"), indent=1)
print("\n[wrote stats_refute_exactci_side_01_out.json]")

#!/usr/bin/env python3
"""
Why the exact-binomial interval misbehaves, and on which scale it is still valid.

The conditional exact method treats the discordant total n_d as fixed. On the p10 scale
(and therefore on the OR and Cohen-g scales, which are 1-1 functions of p10) that is the
right conditional target. On the RISK DIFFERENCE scale it is not, because
    RD = (n_d/N) * (2*p10 - 1)
also inherits the sampling variability of n_d. Analytically, with iid pairs,
    Var(RD)_true / Var(RD)_conditional = [1 - pi_d*(2p-1)^2] / [1 - (2p-1)^2]
which blows up as the discordant split becomes lopsided. Both the algebra and the
simulated coverage of the p10 interval are reported here.
"""
import json, math, random
from collections import defaultdict

random.seed(28071977)
PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
SENS = json.load(open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
                      "experiment-31-07-26/analysis/stats_mde_sensitivity_out.json"))

def betacf(a, b, x):
    MAXIT, EPS, FPMIN = 300, 3e-16, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < FPMIN: d = FPMIN
    d = 1.0 / d; h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d;  d = FPMIN if abs(d) < FPMIN else d;  d = 1.0 / d
        c = 1.0 + aa / c;  c = FPMIN if abs(c) < FPMIN else c
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d;  d = FPMIN if abs(d) < FPMIN else d;  d = 1.0 / d
        c = 1.0 + aa / c;  c = FPMIN if abs(c) < FPMIN else c
        de = d * c; h *= de
        if abs(de - 1.0) < EPS: break
    return h

def betai(a, b, x):
    if x <= 0.0: return 0.0
    if x >= 1.0: return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                  + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0): return bt * betacf(a, b, x) / a
    return 1.0 - bt * betacf(b, a, 1.0 - x) / b

def beta_q(p, a, b, iters=55):
    lo, hi = 0.0, 1.0
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if betai(a, b, mid) < p: lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)

def cp(k, n, alpha=0.05):
    lo = 0.0 if k == 0 else beta_q(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta_q(1 - alpha / 2, k + 1, n - k)
    return lo, hi

def beta_ab(mu, rho):
    if rho <= 1e-6 or mu <= 1e-9 or mu >= 1 - 1e-9: return None
    r = min(rho, 0.95); s = (1 - r) / r
    a, b = mu * s, (1 - mu) * s
    return (a, b) if a > 1e-9 and b > 1e-9 else None

def rbeta(ab):
    a, b = ab
    x = random.gammavariate(a, 1.0); y = random.gammavariate(b, 1.0)
    t = x + y
    return x / t if t > 0 else 0.5

rows = [r for r in json.load(open(PATH)) if r["analysis_include"]]
MODELS = sorted(set(r["model"] for r in rows))

print("=" * 98)
print("ANALYTIC variance-ratio  Var(RD)_true / Var(RD)_conditional-exact   (iid pairs, no clustering)")
print("=" * 98)
print(f"{'stratum':<26}{'pi_d':>8}{'2p-1':>9}{'var ratio':>11}{'SE ratio':>10}"
      f"{'-> exact CI too narrow by':>27}")
for label in ["POOLED"] + MODELS:
    o = SENS[label]
    pi_d, delta = o["pi_d"], o["rd"]
    t = delta / pi_d                       # = 2p-1
    ratio = (1 - pi_d * t * t) / (1 - t * t)
    print(f"{label:<26}{pi_d:>8.4f}{t:>9.4f}{ratio:>11.3f}{math.sqrt(ratio):>10.3f}"
          f"{100*(1-1/math.sqrt(ratio)):>26.1f}%")

NSIM = 4000
print("\n" + "=" * 98)
print(f"SIMULATED coverage of the exact (Clopper-Pearson) interval for p10 "
      f"-- the scale the OR and Cohen g live on")
print(f"({NSIM} sims per stratum, same calibrated cluster models)")
print("=" * 98)
print(f"{'stratum':<26}{'rho_dir':>9}{'p10_true':>10}{'cov_p10_exact':>15}{'mean width':>12}")
for label in ["POOLED"] + MODELS:
    byclu = defaultdict(list)
    for r in rows:
        if label != "POOLED" and r["model"] != label: continue
        byclu[r["cluster"]].append((r["A_correct"], r["B_correct"]))
    sizes = [len(v) for v in byclu.values()]
    o = SENS[label]
    pi_d, delta, rho_dir = o["pi_d"], o["rd"], o["rdir"]
    p_true = (1 + delta / pi_d) / 2.0
    ab = beta_ab(p_true, rho_dir)
    cov = 0; wid = 0.0
    for _ in range(NSIM):
        n10t = n01t = 0
        for nc in sizes:
            pdc = rbeta(ab) if ab else p_true
            nd = sum(1 for _ in range(nc) if random.random() < pi_d)
            n10 = sum(1 for _ in range(nd) if random.random() < pdc)
            n10t += n10; n01t += nd - n10
        ndt = n10t + n01t
        if ndt == 0: continue
        lo, hi = cp(n10t, ndt)
        if lo <= p_true <= hi: cov += 1
        wid += hi - lo
    print(f"{label:<26}{rho_dir:>9.3f}{p_true:>10.4f}{cov/NSIM:>15.3f}{wid/NSIM:>12.4f}")
print(f"\nnominal 0.950; MC SE at 0.95 with {NSIM} sims = {math.sqrt(0.95*0.05/NSIM):.4f}")

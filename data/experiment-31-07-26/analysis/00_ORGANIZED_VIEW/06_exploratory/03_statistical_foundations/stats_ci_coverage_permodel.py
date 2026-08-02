#!/usr/bin/env python3
"""Per-model coverage of the exact-binomial vs cluster-robust interval for RD,
under each model's own calibrated cluster model (direction-ICC variant)."""
import json, math, random
from collections import defaultdict
import importlib.util, sys

spec = importlib.util.spec_from_file_location(
    "cov", "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
           "experiment-31-07-26/analysis/stats_ci_coverage.py")
# re-implement locally rather than importing (that module runs on import)

random.seed(9091977)
Z975 = 1.959963984540054
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
NSIM = 4000
print("=" * 96)
print(f"PER-MODEL coverage of nominal 95% RD intervals ({NSIM} sims each, "
      f"direction-ICC model calibrated per model)")
print("=" * 96)
print(f"{'stratum':<26}{'DEFF':>7}{'rho_dir':>9}{'cov_exact':>11}{'w_exact':>9}"
      f"{'cov_robust':>12}{'w_robust':>10}")
for label in MODELS:
    byclu = defaultdict(list)
    for r in rows:
        if r["model"] == label: byclu[r["cluster"]].append((r["A_correct"], r["B_correct"]))
    sizes = [len(v) for v in byclu.values()]
    N = sum(sizes)
    o = SENS[label]
    pi_d, delta, rho_dir = o["pi_d"], o["rd"], o["rdir"]
    p_true = (1 + delta / pi_d) / 2.0
    ab = beta_ab(p_true, rho_dir)
    ce = cw = 0; we = ww = 0.0
    for _ in range(NSIM):
        tot = 0; Ss = []; n10t = n01t = 0
        for nc in sizes:
            pdc = rbeta(ab) if ab else p_true
            nd = sum(1 for _ in range(nc) if random.random() < pi_d)
            n10 = sum(1 for _ in range(nd) if random.random() < pdc)
            n01 = nd - n10
            n10t += n10; n01t += n01
            Sc = n10 - n01; Ss.append((Sc, nc)); tot += Sc
        rd = tot / N
        se_c = math.sqrt(sum((Sc - nc * rd) ** 2 for Sc, nc in Ss)) / N
        ndt = n10t + n01t
        if ndt == 0: lo_e, hi_e = -1.0, 1.0
        else:
            lp, hp = cp(n10t, ndt)
            lo_e, hi_e = (ndt / N) * (2 * lp - 1), (ndt / N) * (2 * hp - 1)
        lo_w, hi_w = rd - Z975 * se_c, rd + Z975 * se_c
        if lo_e <= delta <= hi_e: ce += 1
        if lo_w <= delta <= hi_w: cw += 1
        we += hi_e - lo_e; ww += hi_w - lo_w
    print(f"{label:<26}{o['deff']:>7.3f}{rho_dir:>9.3f}{ce/NSIM:>11.3f}{we/NSIM:>9.4f}"
          f"{cw/NSIM:>12.3f}{ww/NSIM:>10.4f}")
print(f"\nMC SE at coverage ~0.9 with {NSIM} sims = {math.sqrt(0.9*0.1/NSIM):.4f}")

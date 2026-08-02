#!/usr/bin/env python3
"""
Which 95% interval should be believed: the exact-binomial (Clopper-Pearson on the
discordant pairs, conditioning on the discordant total) or the cluster bootstrap?

Answered by simulation under the calibrated cluster model for the POOLED stratum
(direction-ICC model C from stats_mde_sensitivity.py, which reproduces the observed
cluster-robust SE at the observed effect). Coverage target = the true population RD.
Also reports observed CI widths for both methods side by side.
"""
import json, math, random
from collections import defaultdict

random.seed(30071977)
Z975 = 1.959963984540054
PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
SENS = json.load(open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
                      "experiment-31-07-26/analysis/stats_mde_sensitivity_out.json"))
MAIN = json.load(open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
                      "experiment-31-07-26/analysis/stats_effect_size_power_out.json"))

# ---- incomplete beta (same routines as the main script) ----
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

def beta_q(p, a, b, iters=60):
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
    s = (1 - min(rho, 0.95)) / min(rho, 0.95)
    a, b = mu * s, (1 - mu) * s
    return (a, b) if a > 1e-9 and b > 1e-9 else None

def rbeta(ab):
    a, b = ab
    x = random.gammavariate(a, 1.0); y = random.gammavariate(b, 1.0)
    t = x + y
    return x / t if t > 0 else 0.5

rows = [r for r in json.load(open(PATH)) if r["analysis_include"]]
MODELS = sorted(set(r["model"] for r in rows))

print("=" * 100)
print("OBSERVED 95% CI WIDTHS: cluster bootstrap vs exact binomial on discordant pairs")
print("=" * 100)
print(f"{'stratum':<26}{'quantity':<6}{'bootstrap CI':>24}{'w_b':>8}"
      f"{'exact CI':>24}{'w_e':>8}{'w_b/w_e':>9}")
for label in ["POOLED"] + MODELS:
    m = MAIN[label]
    for q, bk, ek in (("RD", "boot_RD", "exact_RD"), ("OR", "boot_OR", "exact_OR"),
                      ("g", "boot_g", "exact_g")):
        b, e = m[bk], m[ek]
        wb, we = b[1] - b[0], e[1] - e[0]
        print(f"{label if q=='RD' else '':<26}{q:<6}"
              f"[{b[0]:>9.4f},{b[1]:>9.4f}]{wb:>8.4f}"
              f"[{e[0]:>9.4f},{e[1]:>9.4f}]{we:>8.4f}{wb/we:>9.2f}")

# ---------------- coverage simulation, POOLED ----------------
byclu = defaultdict(list)
for r in rows: byclu[r["cluster"]].append((r["A_correct"], r["B_correct"]))
sizes = [len(v) for v in byclu.values()]
N = sum(sizes)
o = SENS["POOLED"]
pi_d, delta, rho_dir = o["pi_d"], o["rd"], o["rdir"]
p_true = (1 + delta / pi_d) / 2.0
ab = beta_ab(p_true, rho_dir)
NSIM = 4000

print("\n" + "=" * 100)
print(f"COVERAGE of nominal 95% intervals, POOLED design (N={N} cells, {len(sizes)} clusters)")
print(f"generative model: direction-ICC={rho_dir:.3f} calibrated to the observed cluster-robust SE;")
print(f"true RD={delta:.4f}, pi_discordant={pi_d:.4f}; {NSIM} simulated datasets")
print("=" * 100)

cov_e = cov_w = cov_ni = 0
wid_e = wid_w = 0.0
for _ in range(NSIM):
    tot = 0; Ss = []; n10t = 0; n01t = 0
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
    # exact conditional interval
    lo_p, hi_p = cp(n10t, ndt)
    lo_e, hi_e = (ndt / N) * (2 * lo_p - 1), (ndt / N) * (2 * hi_p - 1)
    # cluster-robust Wald (stand-in for the cluster bootstrap; SEs agree to ~2%)
    lo_w, hi_w = rd - Z975 * se_c, rd + Z975 * se_c
    # naive iid Wald
    se_n = math.sqrt(max(ndt - (n10t - n01t) ** 2 / N, 0.0)) / N
    lo_n, hi_n = rd - Z975 * se_n, rd + Z975 * se_n
    if lo_e <= delta <= hi_e: cov_e += 1
    if lo_w <= delta <= hi_w: cov_w += 1
    if lo_n <= delta <= hi_n: cov_ni += 1
    wid_e += hi_e - lo_e; wid_w += hi_w - lo_w

mc_se = lambda c: math.sqrt(c * (1 - c) / NSIM)
ce, cw, cn = cov_e / NSIM, cov_w / NSIM, cov_ni / NSIM
print(f"  exact-binomial (conditional on discordant total): coverage = {ce:.3f} "
      f"(MC SE {mc_se(ce):.3f})   mean width = {wid_e/NSIM:.4f}")
print(f"  cluster-robust Wald  (~ cluster bootstrap)      : coverage = {cw:.3f} "
      f"(MC SE {mc_se(cw):.3f})   mean width = {wid_w/NSIM:.4f}")
print(f"  naive iid Wald                                  : coverage = {cn:.3f} "
      f"(MC SE {mc_se(cn):.3f})")
print(f"\n  nominal = 0.950. Shortfall of the exact interval = {0.95-ce:+.3f}")

#!/usr/bin/env python3
"""
Coverage of the exact Clopper-Pearson interval for p10 AND of the cluster
bootstrap, under a simulation that is CONDITIONED ON THE OBSERVED PER-CLUSTER
DISCORDANT COUNTS and whose single free parameter (the direction ICC) is
calibrated to the DIRECTLY MEASURED design effect of the direction of
discordance -- not to the cluster-robust SE of the risk difference.

Why this matters.  The dossier's diagnosis script takes rho_dir from
stats_mde_sensitivity_out.json, where it was chosen so that a beta-binomial
model with the DISCORDANCE-rate ICC FORCED TO ZERO reproduces the observed
cluster-robust SE of RD.  That deliberately loads 100% of the observed RD
clustering onto the direction channel -- the one channel that damages the
conditional exact interval.  The direction DEFF is directly estimable from the
data with no such assumption, so we use that instead, and we carry its
sampling uncertainty.

With per-cluster discordant counts nd_c held fixed and p_c ~ Beta(mu, rho),
   Var(p10hat) = mu(1-mu)/nd * [1 + rho * sum_c nd_c(nd_c-1) / nd]
so rho is recovered in closed form from a target DEFF.
"""
import json, math, random
from collections import defaultdict

PATH = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
        "experiment-31-07-26/analysis/paired_clean.json")
MDE = json.load(open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
                     "experiment-31-07-26/analysis/stats_mde_sensitivity_out.json"))
rows = [r for r in json.load(open(PATH)) if r["analysis_include"]]
MODELS = sorted(set(r["model"] for r in rows))

# ---------------------------------------------------------------- CP interval
def _logpmf(i, n, p):
    if p <= 0.0:  return 0.0 if i == 0 else float("-inf")
    if p >= 1.0:  return 0.0 if i == n else float("-inf")
    return (math.lgamma(n+1)-math.lgamma(i+1)-math.lgamma(n-i+1)
            + i*math.log(p) + (n-i)*math.log1p(-p))

def _tail(p, k, n, upper):
    rng = range(k, n+1) if upper else range(0, k+1)
    t = [x for x in (_logpmf(i, n, p) for i in rng) if x != float("-inf")]
    if not t: return 0.0
    mx = max(t)
    return math.exp(mx)*sum(math.exp(x-mx) for x in t)

_CP_CACHE = {}
def cp(k, n, alpha=0.05):
    key = (k, n)
    if key in _CP_CACHE: return _CP_CACHE[key]
    if n == 0: return (0.0, 1.0)
    if k == 0: lo = 0.0
    else:
        a, b = 0.0, 1.0
        for _ in range(60):
            m = 0.5*(a+b)
            if _tail(m, k, n, True) < alpha/2: a = m
            else: b = m
        lo = 0.5*(a+b)
    if k == n: hi = 1.0
    else:
        a, b = 0.0, 1.0
        for _ in range(60):
            m = 0.5*(a+b)
            if _tail(m, k, n, False) < alpha/2: b = m
            else: a = m
        hi = 0.5*(a+b)
    _CP_CACHE[key] = (lo, hi)
    return lo, hi

# ---------------------------------------------------------------- data
def disc_by_cluster(model=None, unit="cluster"):
    """-> list of (n10_c, nd_c) over clusters that contain >=1 discordant cell."""
    g = defaultdict(lambda: [0, 0])
    for r in rows:
        if model is not None and r["model"] != model: continue
        a, b = r["A_correct"], r["B_correct"]
        if a == b: continue
        key = r["cluster"] if unit == "cluster" else r["question_id"]
        g[key][1] += 1
        if a == 0 and b == 1: g[key][0] += 1
    return [(v[0], v[1]) for v in g.values()]

def deff_direction(pairs):
    n10 = sum(x for x, _ in pairs); nd = sum(n for _, n in pairs)
    p = n10/nd
    var_cl = sum((x - p*n)**2 for x, n in pairs)/nd**2
    var_bin = p*(1-p)/nd
    return p, nd, var_cl/var_bin

def rho_from_deff(pairs, deff):
    nd = sum(n for _, n in pairs)
    s = sum(n*(n-1) for _, n in pairs)
    if s == 0: return 0.0
    return max(0.0, (deff-1.0)*nd/s)

def pct(sv, q):
    n = len(sv); idx = q*(n-1)
    lo = int(math.floor(idx)); hi = int(math.ceil(idx))
    return sv[lo] if lo == hi else sv[lo] + (idx-lo)*(sv[hi]-sv[lo])

def beta_ab(mu, rho):
    if rho <= 1e-6: return None
    s = (1-rho)/rho
    return (mu*s, (1-mu)*s)

def rbeta(rnd, ab):
    a, b = ab
    x = rnd.gammavariate(a, 1.0); y = rnd.gammavariate(b, 1.0)
    t = x+y
    return x/t if t > 0 else 0.5

# ---------------------------------------------------------------- simulation
def coverage(pairs, mu, rho, nsim, seed, boot_reps=0):
    """Coverage of CP (and optionally of the cluster bootstrap percentile CI)
       for p10, with per-cluster discordant counts held at their observed values."""
    rnd = random.Random(seed)
    ab = beta_ab(mu, rho)
    nd = sum(n for _, n in pairs); K = len(pairs)
    cov_cp = cov_bt = 0; w_cp = w_bt = 0.0; used = 0
    for _ in range(nsim):
        sim = []
        tot10 = 0
        for _, n in pairs:
            pc = rbeta(rnd, ab) if ab else mu
            k = sum(1 for _ in range(n) if rnd.random() < pc)
            sim.append((k, n)); tot10 += k
        lo, hi = cp(tot10, nd)
        if lo <= mu <= hi: cov_cp += 1
        w_cp += hi-lo
        if boot_reps:
            draws = []
            for _ in range(boot_reps):
                s10 = s_nd = 0
                for _ in range(K):
                    x, n = sim[rnd.randrange(K)]
                    s10 += x; s_nd += n
                draws.append(s10/s_nd if s_nd else float("nan"))
            draws = sorted(d for d in draws if d == d)
            blo, bhi = pct(draws, .025), pct(draws, .975)
            if blo <= mu <= bhi: cov_bt += 1
            w_bt += bhi-blo
        used += 1
    return (cov_cp/used, w_cp/used,
            (cov_bt/used, w_bt/used) if boot_reps else None)

def boot_deff_ci(pairs, reps, seed):
    """Cluster bootstrap CI for the empirical direction DEFF itself."""
    rnd = random.Random(seed); K = len(pairs); out = []
    for _ in range(reps):
        s = [pairs[rnd.randrange(K)] for _ in range(K)]
        n10 = sum(x for x, _ in s); nd = sum(n for _, n in s)
        if nd == 0: continue
        p = n10/nd
        if p <= 0 or p >= 1: continue
        vc = sum((x-p*n)**2 for x, n in s)/nd**2
        out.append(vc/(p*(1-p)/nd))
    out.sort()
    return pct(out, .025), pct(out, .975)

NSIM = 4000
print("="*112)
print("A. DIRECTION DEFF: directly measured vs the value implied by the dossier's")
print("   rho_dir (calibrated to the RD cluster-robust SE with disc-ICC forced to 0)")
print("="*112)
print(f"{'stratum':<26}{'K_disc':>7}{'nd':>6}{'p10':>8}{'DEFF_emp':>10}"
      f"{'[95% cluster-boot CI]':>26}{'rho(emp)':>10}{'rho_dossier':>13}{'DEFF(dossier)':>15}")
CAL = {}
for label in ["POOLED"] + MODELS:
    pairs = disc_by_cluster(None if label == "POOLED" else label)
    p, nd, deff = deff_direction(pairs)
    lo, hi = boot_deff_ci(pairs, 4000, 909090)
    r_emp = rho_from_deff(pairs, deff)
    r_dos = MDE[label]["rdir"]
    s = sum(n*(n-1) for _, n in pairs)
    deff_dos = 1 + r_dos*s/nd
    CAL[label] = dict(pairs=pairs, p=p, nd=nd, deff=deff, r_emp=r_emp,
                      r_dos=r_dos, deff_dos=deff_dos,
                      r_lo=rho_from_deff(pairs, lo), r_hi=rho_from_deff(pairs, hi),
                      deff_lo=lo, deff_hi=hi)
    print(f"{label:<26}{len(pairs):>7}{nd:>6}{p:>8.4f}{deff:>10.3f}"
          f"{f'[{lo:.3f}, {hi:.3f}]':>26}{r_emp:>10.3f}{r_dos:>13.3f}{deff_dos:>15.3f}")

print("\n" + "="*112)
print(f"B. COVERAGE of the 95% CP interval for p10, {NSIM} sims, per-cluster nd_c fixed at observed")
print("   (i)  rho = dossier value   (ii) rho from the measured DEFF   (iii) rho=0")
print("   plus coverage of the CLUSTER BOOTSTRAP percentile CI (600 sims x 800 reps) at (ii)")
print("="*112)
print(f"{'stratum':<26}{'cov(dossier rho)':>18}{'cov(emp rho)':>14}"
      f"{'cov at DEFF_hi':>16}{'cov(rho=0)':>12}{'CPwidth':>9}{'boot cov':>10}{'bootW':>8}")
for label in ["POOLED"] + MODELS:
    c = CAL[label]
    cd, wd, _ = coverage(c["pairs"], c["p"], c["r_dos"], NSIM, 1001)
    ce, we, _ = coverage(c["pairs"], c["p"], c["r_emp"], NSIM, 1002)
    ch, wh, _ = coverage(c["pairs"], c["p"], c["r_hi"], NSIM, 1004)
    c0, w0, _ = coverage(c["pairs"], c["p"], 0.0, NSIM, 1003)
    _, _, bt = coverage(c["pairs"], c["p"], c["r_emp"], 600, 1005, boot_reps=800)
    print(f"{label:<26}{cd:>18.3f}{ce:>14.3f}{ch:>16.3f}{c0:>12.3f}"
          f"{we:>9.4f}{bt[0]:>10.3f}{bt[1]:>8.4f}")
print(f"\nnominal 0.950;  MC SE at 0.95 = {math.sqrt(.95*.05/NSIM):.4f} (4000 sims), "
      f"{math.sqrt(.95*.05/600):.4f} (600 sims)")

print("\n" + "="*112)
print("C. WHERE DOES THE POOLED DEPENDENCE LIVE?  DEFF of the direction by grouping unit")
print("="*112)
print(f"{'stratum':<26}{'by clinical cluster':>21}{'by item':>10}{'by model':>10}")
for label in ["POOLED"] + MODELS:
    pc = deff_direction(disc_by_cluster(None if label == "POOLED" else label, "cluster"))[2]
    pi = deff_direction(disc_by_cluster(None if label == "POOLED" else label, "item"))[2]
    if label == "POOLED":
        g = defaultdict(lambda: [0, 0])
        for r in rows:
            if r["A_correct"] == r["B_correct"]: continue
            g[r["model"]][1] += 1
            if r["A_correct"] == 0: g[r["model"]][0] += 1
        pm = deff_direction([(v[0], v[1]) for v in g.values()])[2]
        print(f"{label:<26}{pc:>21.3f}{pi:>10.3f}{pm:>10.3f}")
    else:
        print(f"{label:<26}{pc:>21.3f}{pi:>10.3f}{'--':>10}")

#!/usr/bin/env python3
"""
REFUTATION PASS 3 -- coverage of the exact CP interval for p10 (== the OR and
Cohen-g intervals, which are 1-1 monotone re-expressions of it), simulated
CONDITIONAL ON THE OBSERVED per-cluster discordant counts -- i.e. exactly the
conditional frame the claim invokes.

Two things the claim never establishes:
  (A) the CONSERVATISM BASELINE. Clopper-Pearson is guaranteed >= nominal under
      independence, and at these n it actually sits at 0.96-0.99. So "coverage
      0.958" is NOT "at nominal" -- it is already erosion, masked by CP's
      discreteness slack. The correct benchmark is CP's own rho=0 coverage.
  (B) coverage at direction-ICCs the data CANNOT RULE OUT (pass 2 showed the
      per-model ICC CIs span nearly the whole admissible range).

Also simulates the cluster-bootstrap percentile interval under the same DGP, to
check whether the recommended fallback is itself calibrated.
Stdlib only.
"""
import json, math, random
from collections import defaultdict

PATH = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
        "experiment-31-07-26/analysis/paired_clean.json")

# ---------------------------------------------------------------- incomplete beta
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
    if x < (a + 1.0) / (a + b + 2.0): return bt * betacf(a, b, x) / a
    return 1.0 - bt * betacf(b, a, 1.0 - x) / b

def beta_q(p, a, b, iters=60):
    lo, hi = 0.0, 1.0
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if betai(a, b, mid) < p: lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)

_CPC = {}
def cp(k, n, alpha=0.05):
    key = (k, n)
    if key in _CPC: return _CPC[key]
    lo = 0.0 if k == 0 else beta_q(alpha / 2.0, k, n - k + 1)
    hi = 1.0 if k == n else beta_q(1.0 - alpha / 2.0, k + 1, n - k)
    _CPC[key] = (lo, hi)
    return lo, hi

# ------------------------------------------------------------------ data
rows = [r for r in json.load(open(PATH)) if r["analysis_include"]]
MODELS = sorted(set(r["model"] for r in rows))
STRATA = ["POOLED"] + MODELS

def disc_sizes(label):
    d = defaultdict(int)
    tot1 = 0; tot = 0
    for r in rows:
        if label != "POOLED" and r["model"] != label: continue
        if r["A_correct"] == r["B_correct"]: continue
        d[r["cluster"]] += 1
        tot += 1
        if r["A_correct"] == 0: tot1 += 1
    return list(d.values()), tot1 / tot

def beta_ab(mu, rho):
    if rho <= 1e-9: return None
    r = min(rho, 0.98); s = (1 - r) / r
    return (mu * s, (1 - mu) * s)

def sim_ys(sizes, p, ab, rng):
    ys = []
    for n in sizes:
        if ab:
            a, b = ab
            x = rng.gammavariate(a, 1.0); y = rng.gammavariate(b, 1.0)
            t = x + y; pc = x / t if t > 0 else 0.5
        else:
            pc = p
        c = 0
        for _ in range(n):
            if rng.random() < pc: c += 1
        ys.append(c)
    return ys

RHOS = [0.0, 0.15, 0.25, 0.38, 0.50]
NSIM = 6000

print("=" * 112)
print("PASS 3A :: coverage of the EXACT Clopper-Pearson interval for p10")
print("           (identical interval to the OR and Cohen-g intervals, monotone re-expressed)")
print("           conditional on the OBSERVED per-cluster discordant counts;  %d sims" % NSIM)
print("=" * 112)
print(f"{'stratum':<26}{'nd':>5}{'p10':>8}" + "".join(f"{'rho='+str(r):>11}" for r in RHOS))
print(f"{'':<26}{'':>5}{'':>8}" + f"{'(BASELINE)':>11}" + "".join(f"{'':>11}" for r in RHOS[1:]))

cov_tab = {}
for label in STRATA:
    sizes, p10 = disc_sizes(label)
    nd = sum(sizes)
    line = f"{label:<26}{nd:>5}{p10:>8.4f}"
    cov_tab[label] = {}
    for rho in RHOS:
        ab = beta_ab(p10, rho)
        rng = random.Random(20260731 + int(rho * 1000) + len(label))
        cov = 0
        for _ in range(NSIM):
            k = sum(sim_ys(sizes, p10, ab, rng))
            lo, hi = cp(k, nd)
            if lo <= p10 <= hi: cov += 1
        c = cov / NSIM
        cov_tab[label][rho] = c
        line += f"{c:>11.3f}"
    print(line)
print(f"\n  nominal 0.950;  MC SE at 0.95 with {NSIM} sims = {math.sqrt(0.95*0.05/NSIM):.4f}")
print("  rho=0 column is CP's OWN conservatism baseline. Coverage must be read against THAT,")
print("  not against 0.950 -- any drop below it is real erosion bought out of CP's slack.")

print()
print("=" * 112)
print("PASS 3B :: EROSION -- coverage lost relative to CP's own rho=0 baseline")
print("=" * 112)
print(f"{'stratum':<26}{'baseline':>10}" + "".join(f"{'rho='+str(r):>11}" for r in RHOS[1:]))
for label in STRATA:
    b = cov_tab[label][0.0]
    line = f"{label:<26}{b:>10.3f}"
    for rho in RHOS[1:]:
        line += f"{cov_tab[label][rho]-b:>11.3f}"
    print(line)

# ------------------------------------------------------- bootstrap coverage
NSIM_B, NREP_B = 1200, 800
print()
print("=" * 112)
print("PASS 3C :: coverage of the CLUSTER-BOOTSTRAP percentile interval, same DGP")
print(f"           ({NSIM_B} sims x {NREP_B} resamples) -- is the recommended fallback calibrated?")
print("=" * 112)
print(f"{'stratum':<26}" + "".join(f"{'rho='+str(r):>12}" for r in [0.0, 0.25, 0.38]))
for label in STRATA:
    sizes, p10 = disc_sizes(label)
    k = len(sizes)
    line = f"{label:<26}"
    for rho in [0.0, 0.25, 0.38]:
        ab = beta_ab(p10, rho)
        rng = random.Random(77000 + int(rho * 1000) + len(label))
        cov = 0
        for _ in range(NSIM_B):
            ys = sim_ys(sizes, p10, ab, rng)
            bp = []
            for _ in range(NREP_B):
                a = b = 0
                for _ in range(k):
                    i = rng.randrange(k)
                    a += ys[i]; b += sizes[i]
                if b: bp.append(a / b)
            bp.sort()
            lo = bp[int(0.025 * (len(bp) - 1))]
            hi = bp[int(math.ceil(0.975 * (len(bp) - 1)))]
            if lo <= p10 <= hi: cov += 1
        line += f"{cov/NSIM_B:>12.3f}"
    print(line)
print(f"\n  MC SE at 0.95 with {NSIM_B} sims = {math.sqrt(0.95*0.05/NSIM_B):.4f}")

json.dump({k: {str(kk): vv for kk, vv in v.items()} for k, v in cov_tab.items()},
          open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
               "experiment-31-07-26/analysis/stats_refute_exactci_side_03_out.json", "w"), indent=1)
print("\n[wrote stats_refute_exactci_side_03_out.json]")

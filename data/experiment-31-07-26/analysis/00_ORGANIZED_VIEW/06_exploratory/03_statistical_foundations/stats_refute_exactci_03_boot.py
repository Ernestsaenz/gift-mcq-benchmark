#!/usr/bin/env python3
"""
(1) Coverage of the CLUSTER BOOTSTRAP percentile interval -- the method the claim
    recommends -- at higher precision, and separated from clustering (rho=0 row).
(2) Monte-Carlo stability of the quoted bootstrap/exact width ratios across seeds.
"""
import json, math, random
from collections import defaultdict

PATH = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
        "experiment-31-07-26/analysis/paired_clean.json")
rows = [r for r in json.load(open(PATH)) if r["analysis_include"]]
MODELS = sorted(set(r["model"] for r in rows))

def _logpmf(i, n, p):
    if p <= 0.0:  return 0.0 if i == 0 else float("-inf")
    if p >= 1.0:  return 0.0 if i == n else float("-inf")
    return (math.lgamma(n+1)-math.lgamma(i+1)-math.lgamma(n-i+1)
            + i*math.log(p) + (n-i)*math.log1p(-p))
def _tail(p, k, n, upper):
    rng = range(k, n+1) if upper else range(0, k+1)
    t = [x for x in (_logpmf(i, n, p) for i in rng) if x != float("-inf")]
    if not t: return 0.0
    mx = max(t); return math.exp(mx)*sum(math.exp(x-mx) for x in t)
_C = {}
def cp(k, n, alpha=0.05):
    if (k, n) in _C: return _C[(k, n)]
    if k == 0: lo = 0.0
    else:
        a, b = 0.0, 1.0
        for _ in range(60):
            m = .5*(a+b)
            if _tail(m, k, n, True) < alpha/2: a = m
            else: b = m
        lo = .5*(a+b)
    if k == n: hi = 1.0
    else:
        a, b = 0.0, 1.0
        for _ in range(60):
            m = .5*(a+b)
            if _tail(m, k, n, False) < alpha/2: b = m
            else: a = m
        hi = .5*(a+b)
    _C[(k, n)] = (lo, hi); return lo, hi

def disc_pairs(model=None):
    g = defaultdict(lambda: [0, 0])
    for r in rows:
        if model is not None and r["model"] != model: continue
        a, b = r["A_correct"], r["B_correct"]
        if a == b: continue
        g[r["cluster"]][1] += 1
        if a == 0 and b == 1: g[r["cluster"]][0] += 1
    return [(v[0], v[1]) for v in g.values()]

def deff_dir(pairs):
    n10 = sum(x for x, _ in pairs); nd = sum(n for _, n in pairs)
    p = n10/nd
    return p, nd, sum((x-p*n)**2 for x, n in pairs)/nd**2/(p*(1-p)/nd)

def rho_from_deff(pairs, deff):
    nd = sum(n for _, n in pairs); s = sum(n*(n-1) for _, n in pairs)
    return 0.0 if s == 0 else max(0.0, (deff-1.0)*nd/s)

def pct(sv, q):
    n = len(sv); idx = q*(n-1)
    lo = int(math.floor(idx)); hi = int(math.ceil(idx))
    return sv[lo] if lo == hi else sv[lo]+(idx-lo)*(sv[hi]-sv[lo])

def beta_ab(mu, rho):
    if rho <= 1e-6: return None
    s = (1-rho)/rho; return (mu*s, (1-mu)*s)

def rbeta(rnd, ab):
    a, b = ab
    x = rnd.gammavariate(a, 1.0); y = rnd.gammavariate(b, 1.0); t = x+y
    return x/t if t > 0 else 0.5

def cov_both(pairs, mu, rho, nsim, breps, seed):
    rnd = random.Random(seed); ab = beta_ab(mu, rho)
    nd = sum(n for _, n in pairs); K = len(pairs)
    c_cp = c_bt = 0; w_cp = w_bt = 0.0
    miss_lo = miss_hi = 0
    for _ in range(nsim):
        sim = []; tot = 0
        for _, n in pairs:
            pc = rbeta(rnd, ab) if ab else mu
            k = sum(1 for _ in range(n) if rnd.random() < pc)
            sim.append((k, n)); tot += k
        lo, hi = cp(tot, nd)
        if lo <= mu <= hi: c_cp += 1
        w_cp += hi-lo
        dr = []
        for _ in range(breps):
            s10 = snd = 0
            for _ in range(K):
                x, n = sim[rnd.randrange(K)]
                s10 += x; snd += n
            dr.append(s10/snd)
        dr.sort()
        blo, bhi = pct(dr, .025), pct(dr, .975)
        if blo <= mu <= bhi: c_bt += 1
        else:
            if mu < blo: miss_lo += 1
            else: miss_hi += 1
        w_bt += bhi-blo
    return (c_cp/nsim, w_cp/nsim, c_bt/nsim, w_bt/nsim,
            miss_lo/nsim, miss_hi/nsim)

NSIM, BREPS = 2500, 600
print("="*116)
print(f"COVERAGE, {NSIM} sims x {BREPS} bootstrap reps.  rho_emp = calibrated to the MEASURED direction DEFF")
print("="*116)
print(f"{'stratum':<26}{'rho':>7}{'CP cov':>9}{'CP wid':>9}{'BOOT cov':>10}{'BOOT wid':>10}"
      f"{'miss lo':>9}{'miss hi':>9}")
for label in ["POOLED"] + MODELS:
    pairs = disc_pairs(None if label == "POOLED" else label)
    p, nd, dfe = deff_dir(pairs)
    for tag, rho in (("emp", rho_from_deff(pairs, dfe)), ("0", 0.0)):
        a, b, c, d, ml, mh = cov_both(pairs, p, rho, NSIM, BREPS, 4242)
        print(f"{label+' ['+tag+']':<26}{rho:>7.3f}{a:>9.3f}{b:>9.4f}{c:>10.3f}{d:>10.4f}"
              f"{ml:>9.3f}{mh:>9.3f}")
print(f"\nnominal 0.950;  MC SE at 0.95 with {NSIM} sims = {math.sqrt(.95*.05/NSIM):.4f}")

# ---------------------------------------------------------------- seed stability
print("\n" + "="*116)
print("MONTE-CARLO STABILITY of the quoted bootstrap/exact width ratios (10000 reps, 6 seeds)")
print("="*116)
def tab(cells):
    n10 = sum(1 for a, b in cells if a == 0 and b == 1)
    n01 = sum(1 for a, b in cells if a == 1 and b == 0)
    return n10, n01
def build(model=None):
    g = defaultdict(list)
    for r in rows:
        if model is not None and r["model"] != model: continue
        g[r["cluster"]].append((r["A_correct"], r["B_correct"]))
    return g
print(f"{'stratum':<26}{'OR ratio across seeds':>44}{'  quoted':>10}")
for label in ["POOLED"] + MODELS:
    byclu = build(None if label == "POOLED" else label)
    cells = [c for v in byclu.values() for c in v]
    n10, n01 = tab(cells); nd = n10+n01
    lo, hi = cp(n10, nd)
    ex_w = hi/(1-hi) - lo/(1-lo)
    exg_w = hi-lo
    pre = [tab(v) for v in byclu.values()]; K = len(pre)
    ors, gs = [], []
    for sd in (20260731, 1, 2, 3, 4, 5):
        rnd = random.Random(sd); O = []; G = []
        for _ in range(10000):
            s10 = s01 = 0
            for _ in range(K):
                t = pre[rnd.randrange(K)]
                s10 += t[0]; s01 += t[1]
            O.append((s10+.5)/(s01+.5)); G.append((s10+.5)/(s10+s01+1.0)-.5)
        O.sort(); G.sort()
        ors.append((pct(O, .975)-pct(O, .025))/ex_w)
        gs.append((pct(G, .975)-pct(G, .025))/exg_w)
    print(f"{label:<26}" + "".join(f"{x:>7.3f}" for x in ors)
          + f"    g:" + "".join(f"{x:>6.2f}" for x in gs))

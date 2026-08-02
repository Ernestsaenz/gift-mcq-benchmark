#!/usr/bin/env python3
"""
INDEPENDENT recomputation of the 'exact-binomial vs cluster-bootstrap' claim
on the p10 / OR / Cohen-g scale.  Stdlib only.

Checks
  1. the 2x2 tables
  2. Clopper-Pearson interval for p10 -> OR, g   (two independent implementations)
  3. the cluster bootstrap CIs, BOTH as the original script computed them
     (Haldane / +0.5 shrunk statistic inside replicates) and on the RAW statistic
  4. the observed width ratios quoted in the claim
  5. a model-free design-effect for the DIRECTION of discordance
     (cluster-robust SE of p10hat vs the binomial SE that CP assumes)
  6. homogeneity of p10 across the four models
"""
import json, math, random, statistics
from collections import defaultdict

PATH = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
        "experiment-31-07-26/analysis/paired_clean.json")
rows = [r for r in json.load(open(PATH)) if r["analysis_include"]]
MODELS = sorted(set(r["model"] for r in rows))
B_REPS = 10000
SEED = 20260731

# ------------------------------------------------------------------ CP method 1
# exact binomial tails, bisection (no beta functions)
def _logpmf(i, n, p):
    if p <= 0.0:  return 0.0 if i == 0 else float("-inf")
    if p >= 1.0:  return 0.0 if i == n else float("-inf")
    return (math.lgamma(n+1)-math.lgamma(i+1)-math.lgamma(n-i+1)
            + i*math.log(p) + (n-i)*math.log1p(-p))

def _tail(p, k, n, upper):
    rng = range(k, n+1) if upper else range(0, k+1)
    t = [_logpmf(i, n, p) for i in rng]
    t = [x for x in t if x != float("-inf")]
    if not t: return 0.0
    mx = max(t)
    return math.exp(mx)*sum(math.exp(x-mx) for x in t)

def cp_tailbisect(k, n, alpha=0.05):
    if n == 0: return (0.0, 1.0)
    if k == 0: lo = 0.0
    else:
        a, b = 0.0, 1.0
        for _ in range(300):
            m = 0.5*(a+b)
            if _tail(m, k, n, True) < alpha/2: a = m
            else: b = m
        lo = 0.5*(a+b)
    if k == n: hi = 1.0
    else:
        a, b = 0.0, 1.0
        for _ in range(300):
            m = 0.5*(a+b)
            if _tail(m, k, n, False) < alpha/2: b = m
            else: a = m
        hi = 0.5*(a+b)
    return lo, hi

# ------------------------------------------------------------------ CP method 2
# beta quantiles via regularised incomplete beta (continued fraction)
def betacf(a, b, x):
    MAXIT, EPS, FPMIN = 500, 3e-16, 1e-300
    qab, qap, qam = a+b, a+1.0, a-1.0
    c, d = 1.0, 1.0-qab*x/qap
    if abs(d) < FPMIN: d = FPMIN
    d = 1.0/d; h = d
    for m in range(1, MAXIT+1):
        m2 = 2*m
        aa = m*(b-m)*x/((qam+m2)*(a+m2))
        d = 1.0+aa*d; d = FPMIN if abs(d) < FPMIN else d; d = 1.0/d
        c = 1.0+aa/c; c = FPMIN if abs(c) < FPMIN else c
        h *= d*c
        aa = -(a+m)*(qab+m)*x/((a+m2)*(qap+m2))
        d = 1.0+aa*d; d = FPMIN if abs(d) < FPMIN else d; d = 1.0/d
        c = 1.0+aa/c; c = FPMIN if abs(c) < FPMIN else c
        de = d*c; h *= de
        if abs(de-1.0) < EPS: break
    return h

def betai(a, b, x):
    if x <= 0.0: return 0.0
    if x >= 1.0: return 1.0
    bt = math.exp(math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b)
                  + a*math.log(x) + b*math.log1p(-x))
    if x < (a+1.0)/(a+b+2.0): return bt*betacf(a, b, x)/a
    return 1.0-bt*betacf(b, a, 1.0-x)/b

def beta_q(p, a, b):
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5*(lo+hi)
        if betai(a, b, mid) < p: lo = mid
        else: hi = mid
    return 0.5*(lo+hi)

def cp_beta(k, n, alpha=0.05):
    lo = 0.0 if k == 0 else beta_q(alpha/2, k, n-k+1)
    hi = 1.0 if k == n else beta_q(1-alpha/2, k+1, n-k)
    return lo, hi

# textbook sanity check
a1 = cp_tailbisect(8, 10); a2 = cp_beta(8, 10)
print(f"CP sanity  8/10: tail-bisect [{a1[0]:.4f}, {a1[1]:.4f}]  "
      f"beta-quantile [{a2[0]:.4f}, {a2[1]:.4f}]   (textbook 0.4439, 0.9748)")

# ------------------------------------------------------------------ data build
def build(model=None, unit="cluster"):
    g = defaultdict(list)
    for r in rows:
        if model is not None and r["model"] != model: continue
        key = r["cluster"] if unit == "cluster" else r["question_id"]
        g[key].append((r["A_correct"], r["B_correct"]))
    return g

def tab(cells):
    n11 = sum(1 for a, b in cells if a == 1 and b == 1)
    n10 = sum(1 for a, b in cells if a == 0 and b == 1)
    n01 = sum(1 for a, b in cells if a == 1 and b == 0)
    n00 = sum(1 for a, b in cells if a == 0 and b == 0)
    return n11, n10, n01, n00

def pct(sv, q):
    n = len(sv); idx = q*(n-1)
    lo = int(math.floor(idx)); hi = int(math.ceil(idx))
    if lo == hi: return sv[lo]
    return sv[lo] + (idx-lo)*(sv[hi]-sv[lo])

# ------------------------------------------------------------------ bootstrap
def cluster_boot(byclu, reps, seed, shrunk):
    """shrunk=True reproduces the original script (Haldane OR, (n10+.5)/(nd+1) g).
       shrunk=False uses the RAW statistics the exact interval is built for."""
    rnd = random.Random(seed)
    keys = list(byclu.keys()); K = len(keys)
    pre = [tab(byclu[k]) for k in keys]          # (n11,n10,n01,n00) per cluster
    ORs, Gs = [], []
    for _ in range(reps):
        s10 = s01 = 0
        for _ in range(K):
            t = pre[rnd.randrange(K)]
            s10 += t[1]; s01 += t[2]
        nd = s10+s01
        if shrunk:
            ORs.append((s10+0.5)/(s01+0.5))
            Gs.append((s10+0.5)/(nd+1.0) - 0.5)
        else:
            if s01 == 0:  ORs.append(float("inf"))
            elif s10 == 0: ORs.append(0.0)
            else: ORs.append(s10/s01)
            Gs.append(s10/nd - 0.5 if nd else float("nan"))
    fo = sorted(x for x in ORs if x == x and x != float("inf"))
    fg = sorted(x for x in Gs if x == x)
    return (pct(fo, .025), pct(fo, .975)), (pct(fg, .025), pct(fg, .975))

# --------------------------------------------- model-free direction design eff
def direction_deff(byclu):
    """Cluster-robust (linearised ratio) SE of p10hat vs the binomial SE that the
    Clopper-Pearson interval assumes.  Purely empirical -- no simulation model."""
    n10 = n01 = 0
    per = []
    for k, v in byclu.items():
        a10 = sum(1 for a, b in v if a == 0 and b == 1)
        a01 = sum(1 for a, b in v if a == 1 and b == 0)
        n10 += a10; n01 += a01
        per.append((a10, a01))
    nd = n10+n01
    p = n10/nd
    var = sum((a10 - p*(a10+a01))**2 for a10, a01 in per)/nd**2
    se_cl = math.sqrt(var)
    se_bin = math.sqrt(p*(1-p)/nd)
    return p, nd, se_bin, se_cl, (se_cl/se_bin)**2

print("\n" + "="*104)
print("1. TABLES, EXACT CP INTERVAL, CLUSTER BOOTSTRAP (reps=%d seed=%d)" % (B_REPS, SEED))
print("="*104)
res = {}
for label in ["POOLED"] + MODELS:
    byclu = build(None if label == "POOLED" else label)
    cells = [c for v in byclu.values() for c in v]
    n11, n10, n01, n00 = tab(cells)
    nd = n10+n01; p10 = n10/nd
    lo1, hi1 = cp_tailbisect(n10, nd)
    lo2, hi2 = cp_beta(n10, nd)
    assert abs(lo1-lo2) < 1e-9 and abs(hi1-hi2) < 1e-9, (label, lo1, lo2, hi1, hi2)
    ex_or = (lo1/(1-lo1), hi1/(1-hi1)); ex_g = (lo1-0.5, hi1-0.5)
    b_or_s, b_g_s = cluster_boot(byclu, B_REPS, SEED, shrunk=True)
    b_or_r, b_g_r = cluster_boot(byclu, B_REPS, SEED, shrunk=False)
    res[label] = dict(n11=n11, n10=n10, n01=n01, n00=n00, nd=nd, p10=p10,
                      OR=n10/n01, g=p10-0.5, ex_or=ex_or, ex_g=ex_g,
                      b_or_s=b_or_s, b_g_s=b_g_s, b_or_r=b_or_r, b_g_r=b_g_r,
                      ncl=len(byclu), N=len(cells))
    w = lambda t: t[1]-t[0]
    print(f"\n{label}   N={len(cells)} clusters={len(byclu)}  "
          f"n11={n11} n10={n10} n01={n01} n00={n00}  nd={nd}  p10={p10:.4f}")
    print(f"   OR point {n10/n01:.4f} (Haldane {(n10+.5)/(n01+.5):.4f})   g point {p10-0.5:.4f}")
    print(f"   OR exact CP        [{ex_or[0]:.4f}, {ex_or[1]:.4f}]  width {w(ex_or):.4f}")
    print(f"   OR boot (shrunk)   [{b_or_s[0]:.4f}, {b_or_s[1]:.4f}]  width {w(b_or_s):.4f}"
          f"   ratio boot/exact = {w(b_or_s)/w(ex_or):.3f}")
    print(f"   OR boot (RAW)      [{b_or_r[0]:.4f}, {b_or_r[1]:.4f}]  width {w(b_or_r):.4f}"
          f"   ratio boot/exact = {w(b_or_r)/w(ex_or):.3f}")
    print(f"   g  exact CP        [{ex_g[0]:.4f}, {ex_g[1]:.4f}]  width {w(ex_g):.4f}")
    print(f"   g  boot (shrunk)   [{b_g_s[0]:.4f}, {b_g_s[1]:.4f}]  width {w(b_g_s):.4f}"
          f"   ratio boot/exact = {w(b_g_s)/w(ex_g):.3f}")
    print(f"   g  boot (RAW)      [{b_g_r[0]:.4f}, {b_g_r[1]:.4f}]  width {w(b_g_r):.4f}"
          f"   ratio boot/exact = {w(b_g_r)/w(ex_g):.3f}")

print("\n" + "="*104)
print("2. MODEL-FREE DESIGN EFFECT FOR THE DIRECTION OF DISCORDANCE")
print("   (cluster-robust SE of p10hat / binomial SE assumed by Clopper-Pearson)")
print("="*104)
print(f"{'stratum':<26}{'unit':>9}{'nd':>6}{'p10':>9}{'SE_bin':>9}{'SE_clu':>9}"
      f"{'DEFF':>8}{'SE ratio':>10}")
for label in ["POOLED"] + MODELS:
    for unit in ("cluster", "item"):
        byclu = build(None if label == "POOLED" else label, unit=unit)
        p, nd, sb, sc, deff = direction_deff(byclu)
        print(f"{label:<26}{unit:>9}{nd:>6}{p:>9.4f}{sb:>9.5f}{sc:>9.5f}"
              f"{deff:>8.3f}{math.sqrt(deff):>10.3f}")

print("\n" + "="*104)
print("3. HOMOGENEITY OF p10 ACROSS THE FOUR MODELS (is a pooled p10 a single target?)")
print("="*104)
ks, ns = [], []
for m in MODELS:
    cells = [c for v in build(m).values() for c in v]
    _, n10, n01, _ = tab(cells)
    ks.append(n10); ns.append(n10+n01)
pbar = sum(ks)/sum(ns)
chi = sum((k - n*pbar)**2/(n*pbar*(1-pbar)) for k, n in zip(ks, ns))
# chi-square upper tail, df=3, via series/continued fraction
def _gser(a, x):
    ap, s, dl = a, 1.0/a, 1.0/a
    for _ in range(2000):
        ap += 1.0; dl *= x/ap; s += dl
        if abs(dl) < abs(s)*3e-16: break
    return s*math.exp(-x + a*math.log(x) - math.lgamma(a))
def _gcf(a, x):
    fpmin = 1e-300
    b = x+1.0-a; c = 1.0/fpmin; d = 1.0/b; h = d
    for i in range(1, 2000):
        an = -i*(i-a); b += 2.0
        d = an*d+b; d = fpmin if abs(d) < fpmin else d
        c = b+an/c;  c = fpmin if abs(c) < fpmin else c
        d = 1.0/d; dl = d*c; h *= dl
        if abs(dl-1.0) < 3e-16: break
    return math.exp(-x + a*math.log(x) - math.lgamma(a))*h
def chi2_sf(x, df):
    if x <= 0: return 1.0
    a, z = df/2.0, x/2.0
    return 1.0-_gser(a, z) if z < a+1.0 else _gcf(a, z)
print(f"  per-model p10: " + "  ".join(f"{m.split('/')[-1]}={k}/{n}={k/n:.4f}"
                                       for m, k, n in zip(MODELS, ks, ns)))
print(f"  pooled p10 = {pbar:.4f}   Pearson chi2 (df=3) = {chi:.3f}   "
      f"p = {chi2_sf(chi, 3):.4f}   [chi-square asymptotic, own gamma-tail code]")

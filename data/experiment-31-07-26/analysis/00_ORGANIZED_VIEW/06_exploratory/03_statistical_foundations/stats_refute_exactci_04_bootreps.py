#!/usr/bin/env python3
"""Is the cluster-bootstrap under-coverage an artifact of the inner rep count?
Re-run the two headline strata with 600 / 2000 / 5000 inner bootstrap reps."""
import json, math, random
from collections import defaultdict

PATH = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
        "experiment-31-07-26/analysis/paired_clean.json")
rows = [r for r in json.load(open(PATH)) if r["analysis_include"]]

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
    n10 = sum(x for x, _ in pairs); nd = sum(n for _, n in pairs); p = n10/nd
    return p, nd, sum((x-p*n)**2 for x, n in pairs)/nd**2/(p*(1-p)/nd)

def rho_from_deff(pairs, d):
    nd = sum(n for _, n in pairs); s = sum(n*(n-1) for _, n in pairs)
    return 0.0 if s == 0 else max(0.0, (d-1.0)*nd/s)

def pct(sv, q):
    n = len(sv); idx = q*(n-1); lo = int(math.floor(idx)); hi = int(math.ceil(idx))
    return sv[lo] if lo == hi else sv[lo]+(idx-lo)*(sv[hi]-sv[lo])

def rbeta(rnd, ab):
    a, b = ab
    x = rnd.gammavariate(a, 1.0); y = rnd.gammavariate(b, 1.0); t = x+y
    return x/t if t > 0 else 0.5

def boot_cov(pairs, mu, rho, nsim, breps, seed):
    rnd = random.Random(seed)
    ab = None if rho <= 1e-6 else ((1-rho)/rho*mu, (1-rho)/rho*(1-mu))
    K = len(pairs); c = 0; w = 0.0
    for _ in range(nsim):
        sim = []
        for _, n in pairs:
            pc = rbeta(rnd, ab) if ab else mu
            sim.append((sum(1 for _ in range(n) if rnd.random() < pc), n))
        dr = []
        for _ in range(breps):
            s10 = snd = 0
            for _ in range(K):
                x, n = sim[rnd.randrange(K)]
                s10 += x; snd += n
            dr.append(s10/snd)
        dr.sort()
        lo, hi = pct(dr, .025), pct(dr, .975)
        if lo <= mu <= hi: c += 1
        w += hi-lo
    return c/nsim, w/nsim

for label, model in (("POOLED", None), ("gemini", "google/gemini-3.6-flash"),
                     ("glm", "z-ai/glm-5.2")):
    pairs = disc_pairs(model)
    p, nd, d = deff_dir(pairs)
    rho = rho_from_deff(pairs, d)
    line = f"{label:<8} nd={nd:<4} DEFF={d:.3f} rho={rho:.3f} | "
    for breps, nsim in ((600, 1500), (2000, 1500), (5000, 800)):
        c, w = boot_cov(pairs, p, rho, nsim, breps, 777)
        line += f"reps={breps}: cov={c:.3f} (n={nsim}, MCse={math.sqrt(.95*.05/nsim):.3f}) w={w:.4f}  "
    print(line)

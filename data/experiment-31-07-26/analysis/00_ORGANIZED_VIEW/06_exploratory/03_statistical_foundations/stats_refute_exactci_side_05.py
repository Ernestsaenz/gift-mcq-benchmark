#!/usr/bin/env python3
"""
REFUTATION PASS 5 -- pooled coverage under the REALISTIC dependence structure.

Pass 4 showed the pooled direction correlation is ITEM x MODEL (ICC 0.536),
with essentially nothing between different items of the same clinical cluster
(ICC -0.038). Pass 3 simulated the correlation at the CLUSTER level, which is
the wrong axis. This pass rebuilds the pooled DGP correctly:
    items nested in clinical clusters; direction correlated WITHIN item at the
    estimated rho_item; independent across items.
and re-measures (a) exact CP coverage and (b) cluster-bootstrap coverage.
Stdlib only.
"""
import json, math, random
from collections import defaultdict

PATH = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
        "experiment-31-07-26/analysis/paired_clean.json")

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

_C = {}
def cp(k, n, alpha=0.05):
    if (k, n) in _C: return _C[(k, n)]
    lo = 0.0 if k == 0 else beta_q(alpha / 2.0, k, n - k + 1)
    hi = 1.0 if k == n else beta_q(1.0 - alpha / 2.0, k + 1, n - k)
    _C[(k, n)] = (lo, hi)
    return lo, hi

rows = [r for r in json.load(open(PATH)) if r["analysis_include"]]
disc = [r for r in rows if r["A_correct"] != r["B_correct"]]

# item layout: how many discordant cells per item, and which cluster each item is in
item_n = defaultdict(int); item_clu = {}
for r in disc:
    item_n[r["question_id"]] += 1
    item_clu[r["question_id"]] = r["cluster"]
items = sorted(item_n)
sizes = [item_n[q] for q in items]
clu_of = [item_clu[q] for q in items]
clusters = sorted(set(clu_of))
cidx = {c: i for i, c in enumerate(clusters)}
by_cluster = defaultdict(list)
for j, q in enumerate(items):
    by_cluster[cidx[clu_of[q == q and q]]] if False else None
by_cluster = defaultdict(list)
for j in range(len(items)):
    by_cluster[cidx[clu_of[j]]].append(j)
clu_items = [by_cluster[i] for i in range(len(clusters))]

nd = sum(sizes)
p10 = sum(1 for r in disc if r["A_correct"] == 0) / nd
print("=" * 104)
print("PASS 5 :: POOLED coverage under the CORRECT (item x model) dependence axis")
print("=" * 104)
print(f"  discordant cells nd={nd}   items={len(items)}   clinical clusters={len(clusters)}")
print(f"  discordant-cells-per-item: " +
      str(sorted(((s, sizes.count(s)) for s in set(sizes)))))
print(f"  p10={p10:.4f}")

def beta_ab(mu, rho):
    if rho <= 1e-9: return None
    r = min(rho, 0.98); s = (1 - r) / r
    return (mu * s, (1 - mu) * s)

def draw(rho, rng):
    ab = beta_ab(p10, rho)
    ys = []
    for n in sizes:
        if ab:
            a, b = ab
            x = rng.gammavariate(a, 1.0); y = rng.gammavariate(b, 1.0)
            t = x + y; pc = x / t if t > 0 else 0.5
        else:
            pc = p10
        ys.append(sum(1 for _ in range(n) if rng.random() < pc))
    return ys

NSIM = 6000
print()
print(f"{'rho_item':>10}{'CP coverage':>14}{'mean CP width':>16}")
for rho in [0.0, 0.25, 0.40, 0.536, 0.70]:
    rng = random.Random(8080 + int(rho * 1000))
    cov = 0; w = 0.0
    for _ in range(NSIM):
        k = sum(draw(rho, rng))
        lo, hi = cp(k, nd)
        if lo <= p10 <= hi: cov += 1
        w += hi - lo
    tag = "  <- estimated" if abs(rho - 0.536) < 1e-9 else ""
    print(f"{rho:>10.3f}{cov/NSIM:>14.3f}{w/NSIM:>16.4f}{tag}")
print(f"\n  nominal 0.950;  MC SE = {math.sqrt(0.95*0.05/NSIM):.4f}")

NS, NR = 1500, 800
print()
print(f"  cluster-bootstrap percentile coverage, same DGP ({NS} sims x {NR} resamples):")
K = len(clu_items)
for rho in [0.0, 0.536]:
    rng = random.Random(9090 + int(rho * 1000))
    cov = 0
    for _ in range(NS):
        ys = draw(rho, rng)
        bp = []
        for _ in range(NR):
            a = b = 0
            for _ in range(K):
                for j in clu_items[rng.randrange(K)]:
                    a += ys[j]; b += sizes[j]
            if b: bp.append(a / b)
        bp.sort()
        lo = bp[int(0.025 * (len(bp) - 1))]
        hi = bp[int(math.ceil(0.975 * (len(bp) - 1)))]
        if lo <= p10 <= hi: cov += 1
    print(f"    rho_item={rho:.3f}  ->  {cov/NS:.3f}")
print(f"    MC SE = {math.sqrt(0.95*0.05/NS):.4f}")

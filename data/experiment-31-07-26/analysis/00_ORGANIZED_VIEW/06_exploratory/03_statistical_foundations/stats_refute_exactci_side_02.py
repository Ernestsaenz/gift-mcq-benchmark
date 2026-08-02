#!/usr/bin/env python3
"""
REFUTATION PASS 2 -- is the exact binomial's assumption (conditionally independent
DIRECTIONS among discordant pairs) actually satisfied, and is the evidence for
"it is satisfied" worth anything?

Clopper-Pearson for p10 is valid iff, conditional on the discordant set, the
directions are iid Bernoulli(p10). The claim's defence rests on a direction-ICC
CALIBRATED BY MATCHING A CLUSTER-ROBUST SE, which came out at EXACTLY 0.000 for
qwen and glm (boundary clamp). This pass replaces that with:

  (1) direct moment estimates of the direction-ICC + cluster-bootstrap CI;
  (2) a permutation test of the conditional-independence null itself;
  (3) the POWER of that test to detect a gemma-sized ICC.

Permutation nulls are cached by (stratum, total #ones) since the null law of the
concordance statistic depends only on the cluster-size layout and the total.
Stdlib only.
"""
import json, math, random
from collections import defaultdict

PATH = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
        "experiment-31-07-26/analysis/paired_clean.json")
rows = [r for r in json.load(open(PATH)) if r["analysis_include"]]
MODELS = sorted(set(r["model"] for r in rows))
STRATA = ["POOLED"] + MODELS


def disc_by_cluster(label):
    d = defaultdict(list)
    for r in rows:
        if label != "POOLED" and r["model"] != label: continue
        if r["A_correct"] == r["B_correct"]: continue
        d[r["cluster"]].append(1 if r["A_correct"] == 0 else 0)
    return d


# ------------------------------------------------------------- ICC estimators
def icc_anova(ns, ys):
    k = len(ns); N = sum(ns)
    if k < 2 or N == 0 or N == k: return None
    pbar = sum(ys) / N
    if pbar <= 0 or pbar >= 1: return None
    msb = sum(n * (y / n - pbar) ** 2 for n, y in zip(ns, ys)) / (k - 1)
    msw = sum(n * (y / n) * (1 - y / n) for n, y in zip(ns, ys)) / (N - k)
    n0 = (N - sum(n * n for n in ns) / N) / (k - 1)
    den = msb + (n0 - 1) * msw
    return None if den == 0 else (msb - msw) / den


def icc_pairwise(ns, ys):
    N = sum(ns)
    if N == 0: return None
    pbar = sum(ys) / N
    if pbar <= 0 or pbar >= 1: return None
    num = 0.0; dp = 0
    for n, y in zip(ns, ys):
        if n < 2: continue
        num += (y - n * pbar) ** 2 - (y * (1 - pbar) ** 2 + (n - y) * pbar ** 2)
        dp += n * (n - 1)
    return None if dp == 0 else (num / dp) / (pbar * (1 - pbar))


def concord(ns, ys):
    """ordered within-cluster same-direction pairs"""
    s = 0
    for n, y in zip(ns, ys):
        s += y * (y - 1) + (n - y) * (n - y - 1)
    return s


# ------------------------------- cached permutation null of the concordance stat
class PermNull:
    """null distribution of concord() given the cluster-size layout and total #ones"""
    def __init__(self, sizes, nperm=20000, seed=0):
        self.sizes = [n for n in sizes]
        self.big = [n for n in sizes if n >= 2]      # size-1 clusters contribute 0
        self.N = sum(sizes)
        self.nperm = nperm
        self.rng = random.Random(seed)
        self.cache = {}

    def draws(self, tot):
        if tot in self.cache: return self.cache[tot]
        vec = [1] * tot + [0] * (self.N - tot)
        rng = self.rng
        out = []
        for _ in range(self.nperm):
            rng.shuffle(vec)
            i = 0; s = 0
            for n in self.big:
                y = 0
                for j in range(i, i + n): y += vec[j]
                i += n
                s += y * (y - 1) + (n - y) * (n - y - 1)
            out.append(s)
        out.sort()
        self.cache[tot] = out
        return out

    def pvalue(self, tot, obs):
        d = self.draws(tot)
        # P(stat >= obs)
        lo, hi = 0, len(d)
        while lo < hi:
            m = (lo + hi) // 2
            if d[m] < obs: lo = m + 1
            else: hi = m
        return (len(d) - lo + 1) / (len(d) + 1)

    def crit95(self, tot):
        d = self.draws(tot)
        return d[min(len(d) - 1, int(math.ceil(0.95 * len(d))) - 1)]


# ------------------------------------------------------------------ beta-binom
def beta_ab(mu, rho):
    if rho <= 1e-9 or mu <= 1e-12 or mu >= 1 - 1e-12: return None
    r = min(rho, 0.98); s = (1 - r) / r
    return (mu * s, (1 - mu) * s)


def sim_ys(sizes, p, rho, rng):
    """per-cluster #ones, conditional on observed per-cluster discordant counts"""
    ab = beta_ab(p, rho)
    ys = []
    for n in sizes:
        if ab:
            a, b = ab
            x = rng.gammavariate(a, 1.0); yv = rng.gammavariate(b, 1.0)
            t = x + yv
            pc = x / t if t > 0 else 0.5
        else:
            pc = p
        ys.append(sum(1 for _ in range(n) if rng.random() < pc))
    return ys


print("=" * 108)
print("PASS 2 :: does conditional independence of DIRECTION hold?   (v2 dataset, 1271 cells)")
print("=" * 108)
print(f"{'stratum':<26}{'nd':>5}{'k_clu':>7}{'k>=2':>6}{'p10':>8}"
       f"{'ICC_anova':>11}{'ICC_pair':>10}{'   boot 95% CI (anova)':<26}{'perm p':>9}")

res = {}
for label in STRATA:
    d = disc_by_cluster(label)
    cl = list(d.values())
    ns = [len(v) for v in cl]; ys = [sum(v) for v in cl]
    nd = sum(ns); k = len(ns); k2 = sum(1 for n in ns if n >= 2)
    p10 = sum(ys) / nd
    ia = icc_anova(ns, ys); ip = icc_pairwise(ns, ys)

    rng = random.Random(4242 + len(label))
    bs = []
    for _ in range(4000):
        idx = [rng.randrange(k) for _ in range(k)]
        v = icc_anova([ns[i] for i in idx], [ys[i] for i in idx])
        if v is not None: bs.append(v)
    bs.sort()
    def pct(v, q):
        i = q * (len(v) - 1); f = math.floor(i); c = min(f + 1, len(v) - 1)
        return v[f] + (i - f) * (v[c] - v[f])
    lo, hi = pct(bs, 0.025), pct(bs, 0.975)

    pn = PermNull(ns, nperm=20000, seed=11 + len(label))
    pval = pn.pvalue(sum(ys), concord(ns, ys))

    res[label] = dict(sizes=ns, nd=nd, k=k, k2=k2, p10=p10, icc_anova=ia,
                      icc_pair=ip, icc_lo=lo, icc_hi=hi, perm_p=pval)
    print(f"{label:<26}{nd:>5}{k:>7}{k2:>6}{p10:>8.4f}"
          f"{ia:>11.4f}{ip:>10.4f}   [{lo:>7.4f}, {hi:>6.4f}]     {pval:>9.4f}")

print()
print("  perm p = P(within-cluster same-direction concordance >= observed) under the")
print("  EXACT-BINOMIAL NULL ITSELF (20,000 shuffles). Small p => the CP assumption fails.")

print()
print("=" * 108)
print("POWER of that permutation test to DETECT a direction-ICC of the size the claim")
print("concedes for gemma (0.38) or pooled (0.25).  Low power => 'no violation seen' is not evidence.")
print("=" * 108)
NSIM = 3000
print(f"{'stratum':<26}{'rho=0 (size)':>14}{'rho=0.15':>10}{'rho=0.25':>10}"
      f"{'rho=0.38':>10}{'rho=0.50':>10}")
power = {}
for label in STRATA:
    sizes = res[label]["sizes"]; p10 = res[label]["p10"]
    pn = PermNull(sizes, nperm=4000, seed=555 + len(label))
    line = f"{label:<26}"; power[label] = {}
    for rho in [0.0, 0.15, 0.25, 0.38, 0.50]:
        rng = random.Random(999 + int(rho * 1000) + len(label))
        rej = 0; used = 0
        for _ in range(NSIM):
            ys = sim_ys(sizes, p10, rho, rng)
            tot = sum(ys)
            if tot == 0 or tot == sum(sizes): continue
            used += 1
            if concord(sizes, ys) > pn.crit95(tot): rej += 1
        pw = rej / used if used else float('nan')
        power[label][rho] = pw
        line += f"{pw:>10.3f}" if rho > 0 else f"{pw:>14.3f}"
    print(line)

json.dump({k: {kk: vv for kk, vv in v.items() if kk != "sizes"} for k, v in res.items()},
          open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
               "experiment-31-07-26/analysis/stats_refute_exactci_side_02_out.json", "w"), indent=1)
print("\n[wrote stats_refute_exactci_side_02_out.json]")

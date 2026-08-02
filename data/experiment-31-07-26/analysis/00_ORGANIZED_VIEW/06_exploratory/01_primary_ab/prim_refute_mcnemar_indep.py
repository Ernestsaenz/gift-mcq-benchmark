#!/usr/bin/env python3
"""Independent recomputation of the exact McNemar claim.

Stdlib only. No scipy/numpy/pandas.
Everything exact-rational where possible (fractions.Fraction + math.comb).
"""
import json, math, os, random
from fractions import Fraction
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "paired_clean.json")

rows = json.load(open(DATA))
clean = [r for r in rows if r.get("analysis_include") is True]

print("=" * 78)
print("0. SHAPE CHECK")
print("=" * 78)
print("total rows in file  :", len(rows))
print("analysis_include    :", len(clean))
print("distinct question_id:", len({r["question_id"] for r in clean}))
print("distinct cluster    :", len({r["cluster"] for r in clean}))
print("distinct model      :", len({r["model"] for r in clean}))
# per-model cell counts
per_model_n = defaultdict(int)
for r in clean:
    per_model_n[r["model"]] += 1
for m in sorted(per_model_n):
    print(f"  n cells {m:28s} {per_model_n[m]}")

# ---------------------------------------------------------------- exact tests
def mcnemar_exact_doubled(b, c):
    """Two-sided exact McNemar, doubled-smaller-tail rule.
    p = min(1, 2 * sum_{k=0..min(b,c)} C(n,k) / 2^n), n=b+c. Exact Fraction."""
    n = b + c
    if n == 0:
        return Fraction(1, 1)
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1))
    p = Fraction(2 * tail, 2 ** n)
    return p if p < 1 else Fraction(1, 1)

def mcnemar_exact_minlike(b, c):
    """Two-sided exact McNemar, minimum-likelihood (point-probability) rule:
    sum of all P(X=k) with P(X=k) <= P(X=b). Exact Fraction."""
    n = b + c
    if n == 0:
        return Fraction(1, 1)
    pb = math.comb(n, b)
    tot = sum(math.comb(n, k) for k in range(n + 1) if math.comb(n, k) <= pb)
    p = Fraction(tot, 2 ** n)
    return p if p < 1 else Fraction(1, 1)

# ------------------------------------------------- Clopper-Pearson via bisect
def log_binom_tail_upper(n, b, logp, log1mp):
    """log P(X >= b) for X~Bin(n,p), computed stably via log-sum-exp."""
    terms = []
    for k in range(b, n + 1):
        terms.append(math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
                     + k * logp + (n - k) * log1mp)
    m = max(terms)
    return m + math.log(sum(math.exp(t - m) for t in terms))

def log_binom_tail_lower(n, b, logp, log1mp):
    """log P(X <= b)."""
    terms = []
    for k in range(0, b + 1):
        terms.append(math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
                     + k * logp + (n - k) * log1mp)
    m = max(terms)
    return m + math.log(sum(math.exp(t - m) for t in terms))

def clopper_pearson(b, n, alpha=0.05, iters=400):
    """Exact CI for pi. lo solves P(X>=b|lo)=alpha/2 ; hi solves P(X<=b|hi)=alpha/2."""
    target = math.log(alpha / 2.0)
    if b == 0:
        lo = 0.0
    else:
        a, z = 0.0, 1.0
        for _ in range(iters):
            mid = (a + z) / 2
            if mid <= 0: val = -math.inf
            elif mid >= 1: val = 0.0
            else: val = log_binom_tail_upper(n, b, math.log(mid), math.log1p(-mid))
            if val < target: a = mid
            else: z = mid
        lo = (a + z) / 2
    if b == n:
        hi = 1.0
    else:
        a, z = 0.0, 1.0
        for _ in range(iters):
            mid = (a + z) / 2
            if mid <= 0: val = 0.0
            elif mid >= 1: val = -math.inf
            else: val = log_binom_tail_lower(n, b, math.log(mid), math.log1p(-mid))
            if val > target: a = mid
            else: z = mid
        hi = (a + z) / 2
    return lo, hi

# ------------------------------------------------------------- build tables
def table(sub):
    a = b = c = d = 0
    for r in sub:
        A, B = r["A_correct"], r["B_correct"]
        if A == 1 and B == 1: a += 1
        elif A == 1 and B == 0: b += 1
        elif A == 0 and B == 1: c += 1
        else: d += 1
    return a, b, c, d

by_model = defaultdict(list)
for r in clean:
    by_model[r["model"]].append(r)

CLAIM = {
    "google/gemini-3.6-flash": dict(a=287, b=31, c=4, d=3, p=3.4655e-06, OR=7.7500, lo=2.7400, hi=30.2196),
    "z-ai/glm-5.2":            dict(a=235, b=67, c=8, d=14, p=1.0099e-12, OR=8.3750, lo=4.0150, hi=20.1910),
    "qwen/qwen3.6-35b-a3b":    dict(a=221, b=67, c=15, d=22, p=5.2573e-09, OR=4.4667, lo=2.5248, hi=8.4202),
    "google/gemma-4-26b-a4b-it": dict(a=176, b=82, c=18, d=49, p=6.1478e-11, OR=4.5556, lo=2.7109, hi=8.0653),
}

print()
print("=" * 78)
print("1. PER-MODEL 2x2 TABLES + EXACT McNEMAR")
print("=" * 78)
print("  b = A correct & B wrong  (item BROKEN by NOTA substitution)")
print("  c = A wrong  & B correct (item FIXED  by NOTA substitution)")
print()

results = {}
for m in sorted(by_model):
    sub = by_model[m]
    a, b, c, d = table(sub)
    n = a + b + c + d
    pA = (a + b) / n
    pB = (a + c) / n
    pd_ = mcnemar_exact_doubled(b, c)
    pm_ = mcnemar_exact_minlike(b, c)
    OR = b / c if c else float("inf")
    lo_pi, hi_pi = clopper_pearson(b, b + c)
    OR_lo = lo_pi / (1 - lo_pi)
    OR_hi = hi_pi / (1 - hi_pi) if hi_pi < 1 else float("inf")
    results[m] = dict(a=a, b=b, c=c, d=d, n=n, p=float(pd_), OR=OR, lo=OR_lo, hi=OR_hi)
    cl = CLAIM[m]
    print(f"{m}")
    print(f"   MINE   a={a:4d} b={b:3d} c={c:3d} d={d:3d}  n={n}  b+c={b+c}")
    print(f"   CLAIM  a={cl['a']:4d} b={cl['b']:3d} c={cl['c']:3d} d={cl['d']:3d}  "
          f"n={cl['a']+cl['b']+cl['c']+cl['d']}  b+c={cl['b']+cl['c']}")
    match = (a, b, c, d) == (cl['a'], cl['b'], cl['c'], cl['d'])
    print(f"   table match: {match}")
    print(f"   A acc={pA*100:.4f}%  B acc={pB*100:.4f}%  delta={(pB-pA)*100:+.4f} pp")
    print(f"   exact p (doubled tail) = {float(pd_):.6e}   [claim {cl['p']:.6e}]  "
          f"relerr={abs(float(pd_)-cl['p'])/cl['p']:.2e}")
    print(f"   exact p (min-likelihood)= {float(pm_):.6e}   identical rules: {pd_==pm_}")
    print(f"   exact p as Fraction     = {pd_.numerator}/{pd_.denominator}")
    print(f"   OR=b/c = {OR:.4f} [{OR_lo:.4f}, {OR_hi:.4f}]   "
          f"[claim {cl['OR']:.4f} [{cl['lo']:.4f}, {cl['hi']:.4f}]]")
    # verify CI endpoints solve the CP equations
    n_bc = b + c
    v_lo = math.exp(log_binom_tail_upper(n_bc, b, math.log(lo_pi), math.log1p(-lo_pi)))
    v_hi = math.exp(log_binom_tail_lower(n_bc, b, math.log(hi_pi), math.log1p(-hi_pi)))
    print(f"   CP check: P(X>=b|lo)={v_lo:.10f}  P(X<=b|hi)={v_hi:.10f}")
    print()

# ------------------------------------------------------------------ pooled
print("=" * 78)
print("2. POOLED (all 4 models stacked -- treats 1299 cells as independent)")
print("=" * 78)
a, b, c, d = table(clean)
n = a + b + c + d
pd_ = mcnemar_exact_doubled(b, c)
pm_ = mcnemar_exact_minlike(b, c)
OR = b / c
lo_pi, hi_pi = clopper_pearson(b, b + c)
print(f"   MINE   a={a} b={b} c={c} d={d}  n={n}  b+c={b+c}")
print(f"   CLAIM  a=919 b=247 c=45 d=88  n=1299 b+c=292")
print(f"   table match: {(a,b,c,d)==(919,247,45,88)}")
print(f"   exact p (doubled) = {float(pd_):.6e}  [claim 6.2745e-35]")
print(f"   exact p (minlike) = {float(pm_):.6e}  identical: {pd_==pm_}")
print(f"   OR = {OR:.4f} [{lo_pi/(1-lo_pi):.4f}, {hi_pi/(1-hi_pi):.4f}]  "
      f"[claim 5.4889 [3.9820, 7.7197]]")
print()

# ---------------------------------------- 3. verify the two-sided rule claim
print("=" * 78)
print("3. DOUBLED-TAIL vs MIN-LIKELIHOOD RULE, all (b,c) with b+c <= 120")
print("=" * 78)
mismatch = 0
for nn in range(1, 121):
    for bb in range(0, nn + 1):
        if mcnemar_exact_doubled(bb, nn - bb) != mcnemar_exact_minlike(bb, nn - bb):
            mismatch += 1
print(f"   mismatches over all b+c in 1..120: {mismatch}")
print("   (symmetric Bin(n,1/2) => the two two-sided rules coincide; claim's")
print("    'verified for b+c<=59' generalises)")
print()

# ------------------------------------- 4. does the exact test's iid assumption
#                                          survive item x model dependence?
print("=" * 78)
print("4. DEPENDENCE STRESS TEST -- the exact test's key assumption")
print("=" * 78)
print("   McNemar-exact conditions on n=b+c and assumes the b/c split is iid")
print("   Bin(n,1/2) under H0. Items are nested in 208 clusters and each item")
print("   is re-used across 4 models. Test whether that matters.")
print()

# 4a. cluster-level clumping of discordant pairs, per model.
#     Under iid, direction of each discordant pair is an independent coin flip.
#     Compare observed within-cluster variance of #broken to the iid expectation
#     via a cluster-permutation ("flip all discordant pairs in a cluster
#     together") reference distribution -- the maximally adverse dependence.
random.seed(20260731)

def cluster_flip_p(sub, nperm=200000):
    """Wild-cluster sign-flip: under H0 flip the SIGN of every discordant pair
    in a cluster jointly (perfect within-cluster correlation = worst case).
    Statistic = |b - c|."""
    disc = defaultdict(int)   # cluster -> net (broken - fixed)
    tot = defaultdict(int)
    for r in sub:
        A, B = r["A_correct"], r["B_correct"]
        if A == B:
            continue
        s = 1 if (A == 1 and B == 0) else -1
        disc[r["cluster"]] += s
        tot[r["cluster"]] += 1
    keys = list(disc)
    obs = abs(sum(disc[k] for k in keys))
    ge = 0
    for _ in range(nperm):
        s = 0
        for k in keys:
            s += disc[k] if random.getrandbits(1) else -disc[k]
        if abs(s) >= obs:
            ge += 1
    return obs, len(keys), (ge + 1) / (nperm + 1)

for m in sorted(by_model):
    obs, nclust, p = cluster_flip_p(by_model[m], nperm=200000)
    r = results[m]
    print(f"   {m:28s} |b-c|={obs:3d} over {nclust:3d} clusters "
          f"cluster-sign-flip p={p:.3e}  (exact-McNemar p={r['p']:.3e})")

obs, nclust, p = cluster_flip_p(clean, nperm=200000)
print(f"   {'POOLED (cluster-flip)':28s} |b-c|={obs:3d} over {nclust:3d} clusters "
      f"cluster-sign-flip p={p:.3e}  (exact-McNemar p={float(pd_):.3e})")

# 4b. pooled: flip by ITEM across models jointly (item x model dependence)
def item_flip_p(sub, nperm=200000):
    disc = defaultdict(int)
    for r in sub:
        A, B = r["A_correct"], r["B_correct"]
        if A == B: continue
        disc[r["question_id"]] += 1 if (A == 1 and B == 0) else -1
    keys = list(disc)
    obs = abs(sum(disc[k] for k in keys))
    ge = 0
    for _ in range(nperm):
        s = 0
        for k in keys:
            s += disc[k] if random.getrandbits(1) else -disc[k]
        if abs(s) >= obs: ge += 1
    return obs, len(keys), (ge + 1) / (nperm + 1)

obs, nit, p = item_flip_p(clean, nperm=200000)
print(f"   {'POOLED (item-flip)':28s} |b-c|={obs:3d} over {nit:3d} items "
      f"item-sign-flip p={p:.3e}")

# 4c. cluster-bootstrap of OR=b/c per model (resample clusters with replacement)
print()
print("   Cluster bootstrap of OR=b/c (resample the 208 clusters, B=20000):")
cl_index = defaultdict(list)
for r in clean:
    cl_index[r["cluster"]].append(r)
clusters = sorted(cl_index)
for m in sorted(by_model):
    ors = []
    sub_by_cl = defaultdict(list)
    for r in by_model[m]:
        sub_by_cl[r["cluster"]].append(r)
    for _ in range(20000):
        bb = cc = 0
        for _ in range(len(clusters)):
            k = clusters[random.randrange(len(clusters))]
            for r in sub_by_cl.get(k, ()):
                A, B = r["A_correct"], r["B_correct"]
                if A == 1 and B == 0: bb += 1
                elif A == 0 and B == 1: cc += 1
        if cc > 0:
            ors.append(bb / cc)
    ors.sort()
    lo = ors[int(0.025 * len(ors))]
    hi = ors[int(0.975 * len(ors)) - 1]
    frac_le1 = sum(1 for o in ors if o <= 1.0) / len(ors)
    r = results[m]
    print(f"   {m:28s} OR={r['OR']:.4f} exactCI[{r['lo']:.3f},{r['hi']:.3f}] "
          f"clusterboot[{lo:.3f},{hi:.3f}] P(OR<=1)={frac_le1:.4f}")

# ---------------------------------------------- 5. direction / ratio wording
print()
print("=" * 78)
print("5. WORDING CHECK: 'broken outnumber fixed 4.5-to-1 through 8.4-to-1'")
print("=" * 78)
ratios = {m: results[m]["OR"] for m in results}
for m in sorted(ratios, key=lambda k: ratios[k]):
    print(f"   {m:28s} b/c = {results[m]['b']}/{results[m]['c']} = {ratios[m]:.4f}")
print(f"   min b/c = {min(ratios.values()):.4f}   max b/c = {max(ratios.values()):.4f}")
print(f"   rounded to 1dp: [{min(ratios.values()):.1f}, {max(ratios.values()):.1f}]")

# 6. multiplicity: 4 tests
print()
print("=" * 78)
print("6. MULTIPLICITY (4 per-model tests)")
print("=" * 78)
ps = sorted((results[m]["p"], m) for m in results)
for i, (p, m) in enumerate(ps, 1):
    print(f"   {m:28s} p={p:.4e}  Bonferroni x4 = {min(1,p*4):.4e}  "
          f"Holm = {min(1, p*(4-i+1)):.4e}")

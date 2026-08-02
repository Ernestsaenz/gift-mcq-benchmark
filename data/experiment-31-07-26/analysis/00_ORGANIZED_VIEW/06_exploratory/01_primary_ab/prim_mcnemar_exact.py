"""
prim_mcnemar_exact.py -- exact McNemar analysis, standard library only.

METHODS (all hand-implemented, no numpy/scipy):
  * exact McNemar p : two-sided binomial tail on b ~ Bin(b+c, 0.5), computed as an
                      EXACT RATIONAL   2 * sum_{k=0}^{min(b,c)} C(n,k) / 2^n , capped at 1,
                      using math.comb + fractions.Fraction (no floating-point error).
                      Because the null density C(n,k)/2^n is symmetric about n/2, the
                      "doubled smaller tail" rule and the "sum of all k with density
                      <= density(b)" rule give the IDENTICAL set, so this is the
                      unambiguous two-sided exact p.
  * mid-p            : exact p minus the point mass at the observed value (reported as a
                       supplement only, never as the headline).
  * chi-square cc    : X2 = (|b-c| - 1)^2 / (b+c), p = P(chi2_1 > X2) = erfc(sqrt(X2/2)),
                       using math.erfc (this identity is exact for 1 df).
  * chi-square raw   : X2 = (b-c)^2 / (b+c), same tail function (shown to isolate how much
                       of the exact-vs-approx gap is the continuity correction itself).
  * OR CI            : conditional OR = b/c. Exact CI by inverting the two-sided binomial
                       test for pi = b/(b+c) (Clopper-Pearson), solved by 200-step bisection
                       on the exact binomial tail in log-gamma space; then OR = pi/(1-pi).
  * permutation      : cluster-level and item-level sign-flip permutation of the A/B labels,
                       Monte Carlo, seed fixed. Respects item x model and cluster dependence
                       that the pooled exact test ignores.
"""
import json, math, random, collections
from fractions import Fraction

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
SHORT = {"google/gemini-3.6-flash":"gemini-3.6-flash",
         "z-ai/glm-5.2":"glm-5.2",
         "qwen/qwen3.6-35b-a3b":"qwen3.6-35b-a3b",
         "google/gemma-4-26b-a4b-it":"gemma-4-26b-a4b-it"}
ORDER = ["gemini-3.6-flash","glm-5.2","qwen3.6-35b-a3b","gemma-4-26b-a4b-it"]

# ---------------------------------------------------------------- primitives
def mcnemar_exact_p(b, c):
    """Two-sided exact binomial p on b out of n=b+c with pi=0.5. Exact rational -> float."""
    n = b + c
    if n == 0:
        return 1.0, Fraction(1)
    lo = min(b, c)
    tail = sum(math.comb(n, k) for k in range(lo + 1))          # integer, exact
    p = Fraction(2 * tail, 1 << n)                               # 2 * tail / 2^n, exact
    if p > 1:
        p = Fraction(1)
    return float(p), p

def mcnemar_midp(b, c):
    """mid-p: exact two-sided p minus the point mass at the observed count."""
    n = b + c
    if n == 0:
        return 1.0
    lo = min(b, c)
    tail = sum(math.comb(n, k) for k in range(lo + 1))
    point = math.comb(n, lo)
    p = Fraction(2 * tail - point, 1 << n)
    if p > 1:
        p = Fraction(1)
    return float(p)

def chi2_1df_sf(x):
    """P(chi2_1 > x) = erfc(sqrt(x/2)). Exact identity for 1 df; math.erfc is stdlib."""
    if x <= 0:
        return 1.0
    return math.erfc(math.sqrt(x / 2.0))

def mcnemar_chi2_cc(b, c):
    n = b + c
    if n == 0:
        return float("nan"), 1.0
    x = (abs(b - c) - 1.0) ** 2 / n
    return x, chi2_1df_sf(x)

def mcnemar_chi2_raw(b, c):
    n = b + c
    if n == 0:
        return float("nan"), 1.0
    x = (b - c) ** 2 / n
    return x, chi2_1df_sf(x)

def _log_binom_pmf(n, k, p):
    if p <= 0.0:
        return 0.0 if k == 0 else -math.inf
    if p >= 1.0:
        return 0.0 if k == n else -math.inf
    lc = math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
    return lc + k * math.log(p) + (n - k) * math.log1p(-p)

def binom_sf_ge(n, k, p):
    """P(X >= k) for X~Bin(n,p), summed in log space."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return sum(math.exp(_log_binom_pmf(n, j, p)) for j in range(k, n + 1))

def binom_cdf_le(n, k, p):
    """P(X <= k) for X~Bin(n,p)."""
    if k >= n:
        return 1.0
    if k < 0:
        return 0.0
    return sum(math.exp(_log_binom_pmf(n, j, p)) for j in range(0, k + 1))

def clopper_pearson(b, n, alpha=0.05):
    """Exact (Clopper-Pearson) CI for pi=b/n by inverting the binomial test; bisection."""
    if n == 0:
        return (float("nan"), float("nan"))
    a = alpha / 2.0
    if b == 0:
        lo = 0.0
    else:
        x0, x1 = 0.0, 1.0
        for _ in range(200):                      # P(X>=b|p) is increasing in p
            mid = (x0 + x1) / 2.0
            if binom_sf_ge(n, b, mid) < a: x0 = mid
            else:                                x1 = mid
        lo = (x0 + x1) / 2.0
    if b == n:
        hi = 1.0
    else:
        x0, x1 = 0.0, 1.0
        for _ in range(200):                      # P(X<=b|p) is decreasing in p
            mid = (x0 + x1) / 2.0
            if binom_cdf_le(n, b, mid) > a: x0 = mid
            else:                                x1 = mid
        hi = (x0 + x1) / 2.0
    return lo, hi

def or_exact_ci(b, c, alpha=0.05):
    """Conditional McNemar OR = b/c with exact CI from the Clopper-Pearson CI on pi=b/(b+c)."""
    n = b + c
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    orh = float("inf") if c == 0 else (0.0 if b == 0 else b / c)
    lo, hi = clopper_pearson(b, n, alpha)
    lo_or = float("inf") if lo >= 1.0 else lo / (1.0 - lo)
    hi_or = float("inf") if hi >= 1.0 else hi / (1.0 - hi)
    return orh, lo_or, hi_or

def wilson_like_note(n):
    """Smallest attainable two-sided exact p for a table with n=b+c discordant pairs = 2/2^n."""
    return min(1.0, 2.0 / (1 << n)) if n > 0 else 1.0

def table(rows):
    a = sum(1 for r in rows if r["A_correct"] == 1 and r["B_correct"] == 1)
    b = sum(1 for r in rows if r["A_correct"] == 1 and r["B_correct"] == 0)
    c = sum(1 for r in rows if r["A_correct"] == 0 and r["B_correct"] == 1)
    d = sum(1 for r in rows if r["A_correct"] == 0 and r["B_correct"] == 0)
    return a, b, c, d

def fmt_p(p):
    if p >= 1e-4: return f"{p:.6f}"
    if p == 0.0:  return "0"
    return f"{p:.3e}"

# ---------------------------------------------------------------- load
raw = json.load(open(PATH))
D = [r for r in raw if r.get("analysis_include") is True]
for r in D:
    r["m"] = SHORT[r["model"]]
assert len(D) == 1299, len(D)

print("=" * 100)
print("0. RECOMPUTED MARGINALS  (clean subset, analysis_include==true)")
print("=" * 100)
print(f"{'model':22s} {'n':>5s} {'A_acc':>8s} {'B_acc':>8s} {'delta_pp':>9s}")
for m in ORDER:
    rr = [r for r in D if r["m"] == m]
    n = len(rr)
    A = sum(r["A_correct"] for r in rr) / n
    B = sum(r["B_correct"] for r in rr) / n
    print(f"{m:22s} {n:5d} {100*A:7.2f}% {100*B:7.2f}% {100*(B-A):+8.2f}")
nAll = len(D)
Aall = sum(r["A_correct"] for r in D) / nAll
Ball = sum(r["B_correct"] for r in D) / nAll
print(f"{'POOLED':22s} {nAll:5d} {100*Aall:7.2f}% {100*Ball:7.2f}% {100*(Ball-Aall):+8.2f}")

# ---------------------------------------------------------------- main tables
print()
print("=" * 100)
print("1. 2x2 DISCORDANCE TABLES + EXACT McNEMAR")
print("=" * 100)
results = {}
strata_all = []
for m in ORDER + ["POOLED"]:
    rr = D if m == "POOLED" else [r for r in D if r["m"] == m]
    a, b, c, d = table(rr)
    n = b + c
    pex, pex_frac = mcnemar_exact_p(b, c)
    pmid = mcnemar_midp(b, c)
    xcc, pcc = mcnemar_chi2_cc(b, c)
    xrw, prw = mcnemar_chi2_raw(b, c)
    orh, olo, ohi = or_exact_ci(b, c)
    results[m] = dict(a=a, b=b, c=c, d=d, n=n, pex=pex, pmid=pmid, xcc=xcc, pcc=pcc,
                      xrw=xrw, prw=prw, orh=orh, olo=olo, ohi=ohi, N=len(rr))
    print()
    print(f"--- {m}   (N pairs = {len(rr)})")
    print(f"                    B correct   B wrong")
    print(f"    A correct        a={a:5d}    b={b:5d}")
    print(f"    A wrong          c={c:5d}    d={d:5d}")
    print(f"    discordant n = b+c = {n}   |b-c| = {abs(b-c)}")
    print(f"    exact McNemar (binomial, two-sided, pi=0.5) : p = {fmt_p(pex)}")
    print(f"      exact rational                            : {pex_frac.numerator} / {pex_frac.denominator}"
          if pex_frac.denominator < 10**25 else
          f"      exact rational                            : (numer/denom with {len(str(pex_frac.denominator))} digits)")
    print(f"    mid-p (supplement)                          : p = {fmt_p(pmid)}")
    print(f"    chi2 w/ continuity correction  X2={xcc:10.4f} : p = {fmt_p(pcc)}")
    print(f"    chi2 w/o continuity correction X2={xrw:10.4f} : p = {fmt_p(prw)}")
    print(f"    OR = b/c = {orh:.4f}   exact 95% CI [{olo:.4f}, {ohi:.4f}]  (Clopper-Pearson on pi=b/(b+c))")
    print(f"    pi_hat = b/(b+c) = {b/n:.4f}" if n else "")
    print(f"    ratio  p_chi2cc / p_exact = {pcc/pex:.4f}" if pex > 0 else "")
    print(f"    abs diff p_chi2cc - p_exact = {pcc-pex:+.3e}")

# ---------------------------------------------------------------- strata
print()
print("=" * 100)
print("2. STRATIFIED TABLES -- where b+c gets small and the approximation breaks")
print("=" * 100)

def run_strata(keyname, keyfn, min_report=0):
    out = []
    keys = sorted({keyfn(r) for r in D}, key=lambda x: (str(type(x)), str(x)))
    for m in ORDER:
        for k in keys:
            rr = [r for r in D if r["m"] == m and keyfn(r) == k]
            if not rr: continue
            a, b, c, d = table(rr)
            n = b + c
            pex, _ = mcnemar_exact_p(b, c)
            xcc, pcc = mcnemar_chi2_cc(b, c)
            xrw, prw = mcnemar_chi2_raw(b, c)
            orh, olo, ohi = or_exact_ci(b, c)
            out.append(dict(strat=keyname, model=m, key=k, N=len(rr), b=b, c=c, n=n,
                            pex=pex, pcc=pcc, prw=prw, orh=orh, olo=olo, ohi=ohi))
    return out

strata = []
strata += run_strata("negated_stem", lambda r: r["negated_stem"])
strata += run_strata("has_context",  lambda r: r["has_context"])
strata += run_strata("exam_part",    lambda r: r["exam_part"])
strata += run_strata("region",       lambda r: r["region"])
strata += run_strata("correct_letter", lambda r: r["correct_letter"])

strata.sort(key=lambda s: (s["n"], s["strat"]))
print(f"{'stratum':16s} {'level':22s} {'model':20s} {'N':>4s} {'b':>4s} {'c':>4s} {'b+c':>4s} "
      f"{'p_exact':>11s} {'p_chi2cc':>11s} {'p_chi2raw':>11s} {'min possible p':>14s}")
for s in strata:
    print(f"{s['strat']:16s} {str(s['key'])[:22]:22s} {s['model']:20s} {s['N']:4d} {s['b']:4d} {s['c']:4d} {s['n']:4d} "
          f"{fmt_p(s['pex']):>11s} {fmt_p(s['pcc']):>11s} {fmt_p(s['prw']):>11s} {wilson_like_note(s['n']):14.4f}")

small = [s for s in strata if s["n"] < 25]
print()
print(f"strata with b+c < 25 (classic chi2 validity rule) : {len(small)} / {len(strata)}")
print(f"strata with b+c <  6 (exact p can NEVER reach .05): {len([s for s in strata if 0 < s['n'] < 6])}")
print(f"strata with b+c == 0 (test undefined)             : {len([s for s in strata if s['n']==0])}")
disc = [s for s in strata if s["n"] > 0 and ((s["pex"] < .05) != (s["pcc"] < .05))]
print(f"strata where exact and chi2cc DISAGREE at alpha=.05: {len(disc)}")
for s in disc:
    print(f"    {s['strat']}={s['key']} / {s['model']}: b={s['b']} c={s['c']} n={s['n']} "
          f"p_exact={fmt_p(s['pex'])} p_chi2cc={fmt_p(s['pcc'])} p_chi2raw={fmt_p(s['prw'])}")
disc2 = [s for s in strata if s["n"] > 0 and ((s["pex"] < .05) != (s["prw"] < .05))]
print(f"strata where exact and chi2 RAW disagree at alpha=.05: {len(disc2)}")
for s in disc2:
    print(f"    {s['strat']}={s['key']} / {s['model']}: b={s['b']} c={s['c']} n={s['n']} "
          f"p_exact={fmt_p(s['pex'])} p_chi2raw={fmt_p(s['prw'])}")

# max relative error among small strata
print()
print("worst p_chi2cc/p_exact ratios among strata with b+c<25:")
sm = sorted([s for s in small if s["n"] > 0 and s["pex"] > 0],
            key=lambda s: -abs(math.log(max(s["pcc"],1e-300)/s["pex"])))[:12]
for s in sm:
    print(f"    {s['strat']}={str(s['key'])[:18]:18s} {s['model']:20s} b={s['b']:3d} c={s['c']:3d} n={s['n']:3d} "
          f"p_exact={fmt_p(s['pex']):>11s} p_chi2cc={fmt_p(s['pcc']):>11s} ratio={s['pcc']/s['pex']:8.3f}")

# ---------------------------------------------------------------- calibration demo
print()
print("=" * 100)
print("3. WHY EXACT, NOT CHI2 -- null calibration of the chi2 approximation at small b+c")
print("=" * 100)
print("For each n=b+c, enumerate the FULL null distribution of b ~ Bin(n,0.5) (exact, by")
print("math.comb) and compute the true type-I error of each decision rule at alpha=0.05.")
print(f"{'n=b+c':>6s} {'true size chi2cc':>18s} {'true size chi2raw':>18s} {'true size exact':>16s} {'min p_exact':>13s}")
for n in list(range(1, 31)) + [40, 60, 100, 200]:
    sz_cc = sz_rw = sz_ex = Fraction(0)
    tot = Fraction(1, 1 << n)
    for b in range(n + 1):
        c = n - b
        w = Fraction(math.comb(n, b), 1 << n)
        if mcnemar_chi2_cc(b, c)[1]  < 0.05: sz_cc += w
        if mcnemar_chi2_raw(b, c)[1] < 0.05: sz_rw += w
        if mcnemar_exact_p(b, c)[0]  < 0.05: sz_ex += w
    print(f"{n:6d} {float(sz_cc):18.5f} {float(sz_rw):18.5f} {float(sz_ex):16.5f} {wilson_like_note(n):13.5f}")

# ---------------------------------------------------------------- dependence check
print()
print("=" * 100)
print("4. POOLED TABLE DEPENDENCE CHECK -- sign-flip permutation (Monte Carlo)")
print("=" * 100)
print("The pooled exact test treats all 1299 cells as independent Bernoulli discordances.")
print("They are not: each item contributes up to 4 cells (one per model) and items nest in")
print("208 clusters. Permutation swaps the A/B labels for a WHOLE item (or whole cluster) at")
print("once, preserving that dependence, and re-derives the null of the same statistic b-c.")

by_item = collections.defaultdict(list)
by_clus = collections.defaultdict(list)
for r in D:
    by_item[r["question_id"]].append(r)
    by_clus[r["cluster"]].append(r)

def obs_bc(rows):
    b = sum(1 for r in rows if r["A_correct"] == 1 and r["B_correct"] == 0)
    c = sum(1 for r in rows if r["A_correct"] == 0 and r["B_correct"] == 1)
    return b, c

def perm_p(groups, rows_subset, R=50000, seed=20260731):
    """Sign-flip permutation on statistic |b-c|; flips applied at group level."""
    rng = random.Random(seed)
    idx = set(id(r) for r in rows_subset)
    gs = []
    for g, rs in groups.items():
        sel = [r for r in rs if id(r) in idx]
        if not sel: continue
        gb = sum(1 for r in sel if r["A_correct"] == 1 and r["B_correct"] == 0)
        gc = sum(1 for r in sel if r["A_correct"] == 0 and r["B_correct"] == 1)
        gs.append((gb, gc))
    b0 = sum(g[0] for g in gs); c0 = sum(g[1] for g in gs)
    obs = abs(b0 - c0)
    ge = 0
    for _ in range(R):
        s = 0
        for gb, gc in gs:
            s += (gb - gc) if rng.getrandbits(1) else (gc - gb)
        if abs(s) >= obs: ge += 1
    return (ge + 1) / (R + 1), obs, len(gs)

for m in ORDER + ["POOLED"]:
    rr = D if m == "POOLED" else [r for r in D if r["m"] == m]
    pi_, obs, ng = perm_p(by_item, rr)
    pc_, _, ngc = perm_p(by_clus, rr)
    ex = results[m]["pex"]
    print(f"  {m:22s} |b-c|={obs:4d}  exact p={fmt_p(ex):>11s}  "
          f"perm(item, {ng:3d} grp) p={pi_:.5f}  perm(cluster, {ngc:3d} grp) p={pc_:.5f}")
print("  (permutation p is floored at 1/(R+1) = %.2e with R=50000)" % (1/50001))

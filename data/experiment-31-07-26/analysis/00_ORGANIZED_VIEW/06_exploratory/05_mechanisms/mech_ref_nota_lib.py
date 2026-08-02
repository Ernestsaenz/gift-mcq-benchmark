"""Independent stdlib stats + loaders for the nota-acceptance refutation.

Written from scratch (not importing mech_nota_lib) so the recount is independent.
Validated in __main__ against textbook values.
"""
import json, math, random
from collections import defaultdict, Counter

PAIRED = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"
LETTERS = ["a", "b", "c", "d"]


def cells(include_only=True):
    d = json.load(open(PAIRED))
    return [r for r in d if (r["analysis_include"] or not include_only)]


# ---------------- binomial ----------------
def lbinom(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def bpmf(k, n, p):
    if p <= 0:
        return 1.0 if k == 0 else 0.0
    if p >= 1:
        return 1.0 if k == n else 0.0
    return math.exp(lbinom(n, k) + k * math.log(p) + (n - k) * math.log1p(-p))


def bcdf_le(k, n, p):
    return sum(bpmf(i, n, p) for i in range(0, k + 1))


def bcdf_ge(k, n, p):
    return sum(bpmf(i, n, p) for i in range(k, n + 1))


def clopper_pearson(k, n, alpha=0.05):
    """Exact CI by root-finding on the binomial tails (bisection, 200 iters)."""
    if n == 0:
        return (0.0, 1.0)
    lo = 0.0
    if k > 0:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = 0.5 * (a + b)
            # P(X>=k|p) is increasing in p; want the p where it equals alpha/2
            if bcdf_ge(k, n, m) < alpha / 2:
                a = m
            else:
                b = m
        lo = 0.5 * (a + b)
    hi = 1.0
    if k < n:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = 0.5 * (a + b)
            # P(X<=k|p) is decreasing in p
            if bcdf_le(k, n, m) < alpha / 2:
                b = m
            else:
                a = m
        hi = 0.5 * (a + b)
    return (lo, hi)


def binom_exact_2sided(k, n, p0):
    """Exact two-sided binomial test, minimum-likelihood (Sterne / 'small p') method."""
    if n == 0:
        return 1.0
    obs = bpmf(k, n, p0)
    return min(1.0, sum(bpmf(i, n, p0) for i in range(n + 1)
                        if bpmf(i, n, p0) <= obs * (1 + 1e-9)))


def binom_exact_1sided_greater(k, n, p0):
    """Exact one-sided P(X >= k | Bin(n,p0))."""
    if n == 0:
        return 1.0
    return min(1.0, bcdf_ge(k, n, p0))


# ---------------- chi-square tail ----------------
def _gser(a, x):
    ap, s, dl = a, 1.0 / a, 1.0 / a
    for _ in range(2000):
        ap += 1.0
        dl *= x / ap
        s += dl
        if abs(dl) < abs(s) * 1e-16:
            break
    return s * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gcf(a, x):
    tiny = 1e-300
    b, c, d = x + 1.0 - a, 1e300, 1.0 / (x + 1.0 - a)
    h = d
    for i in range(1, 2000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-16:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def gammaq(a, x):
    if x < 0 or a <= 0:
        raise ValueError
    if x == 0:
        return 1.0
    return 1.0 - _gser(a, x) if x < a + 1.0 else _gcf(a, x)


def chi2_sf(x2, df):
    return 1.0 if x2 <= 0 else gammaq(df / 2.0, x2 / 2.0)


def norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2))


# ---------------- categorical tests ----------------
def chisq_table(rows):
    """Pearson chi-square on an r x c table of counts. Returns (X2, df, p)."""
    R, C = len(rows), len(rows[0])
    n = sum(sum(r) for r in rows)
    rt = [sum(r) for r in rows]
    ct = [sum(rows[i][j] for i in range(R)) for j in range(C)]
    x2 = 0.0
    for i in range(R):
        for j in range(C):
            e = rt[i] * ct[j] / n
            if e > 0:
                x2 += (rows[i][j] - e) ** 2 / e
    df = (R - 1) * (C - 1)
    return x2, df, chi2_sf(x2, df)


def gtest_table(rows):
    """Likelihood-ratio (G) test on an r x c table. Returns (G, df, p)."""
    R, C = len(rows), len(rows[0])
    n = sum(sum(r) for r in rows)
    rt = [sum(r) for r in rows]
    ct = [sum(rows[i][j] for i in range(R)) for j in range(C)]
    g = 0.0
    for i in range(R):
        for j in range(C):
            o = rows[i][j]
            e = rt[i] * ct[j] / n
            if o > 0 and e > 0:
                g += 2 * o * math.log(o / e)
    df = (R - 1) * (C - 1)
    return g, df, chi2_sf(g, df)


def fisher_2x2(a, b, c, d):
    n, r1, c1 = a + b + c + d, a + b, a + c

    def p(x):
        return math.exp(lbinom(r1, x) + lbinom(n - r1, c1 - x) - lbinom(n, c1))

    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    p0 = p(a)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= p0 * (1 + 1e-7)))


def holm(pairs):
    """pairs: list of (label, p). Returns list of (label, p, p_adj) in input order."""
    idx = sorted(range(len(pairs)), key=lambda i: pairs[i][1])
    m = len(pairs)
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(idx):
        v = (m - rank) * pairs[i][1]
        running = max(running, v)
        adj[i] = min(1.0, running)
    return [(pairs[i][0], pairs[i][1], adj[i]) for i in range(m)]


def multinom_exact_perm_p(counts_by_model, target_rate=None):
    """Placeholder hook (unused)."""
    raise NotImplementedError


# ---------------- cluster bootstrap ----------------
def cluster_bootstrap(units, stat, reps=20000, seed=12345, alpha=0.05):
    """units: dict cluster -> list of records. stat: list-of-records -> float or None."""
    keys = list(units.keys())
    rng = random.Random(seed)
    n = len(keys)
    out = []
    for _ in range(reps):
        samp = []
        for _ in range(n):
            samp.extend(units[keys[rng.randrange(n)]])
        v = stat(samp)
        if v is not None:
            out.append(v)
    out.sort()
    if not out:
        return (None, None, None)

    def q(p):
        if not out:
            return None
        i = p * (len(out) - 1)
        lo, hi = int(math.floor(i)), int(math.ceil(i))
        return out[lo] + (i - lo) * (out[hi] - out[lo])

    return (q(alpha / 2), q(1 - alpha / 2), out)


if __name__ == "__main__":
    print("CP95(8/10)   =", [round(v, 4) for v in clopper_pearson(8, 10)], "(txt 0.4439 0.9748)")
    print("CP95(45/133) =", [round(v, 4) for v in clopper_pearson(45, 133)])
    print("binom2(45,133,.25) =", round(binom_exact_2sided(45, 133, 0.25), 5))
    print("fisher(3,1,1,3) =", round(fisher_2x2(3, 1, 1, 3), 5), "(R 0.48571)")
    print("chi2_sf(3.96,3) =", round(chi2_sf(3.96, 3), 5), "(R 0.2657)")
    print("chi2_sf(3.841,1) =", round(chi2_sf(3.841, 1), 5), "(R 0.05000)")
    print("holm", holm([("a", .01), ("b", .04), ("c", .03)]))

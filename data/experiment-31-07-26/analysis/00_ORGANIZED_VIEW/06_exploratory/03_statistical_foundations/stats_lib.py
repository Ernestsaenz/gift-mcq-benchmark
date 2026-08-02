"""Shared pure-stdlib statistics helpers for the test-selection analysis.

No numpy/scipy available. Everything here is implemented from scratch.
Distribution tails:
  - chi-square upper tail via regularised incomplete gamma Q(a,x)
    (Numerical Recipes series + continued fraction, double precision).
  - normal tail via math.erfc (exact to machine precision).
  - binomial tail summed exactly with integer combinatorics (exact, no approximation).
"""
import math
from collections import defaultdict

# ---------------------------------------------------------------- gamma tails
def _gser(a, x, itmax=1000, eps=3e-16):
    """Series representation of the regularised lower incomplete gamma P(a,x)."""
    gln = math.lgamma(a)
    if x <= 0.0:
        return 0.0
    ap = a
    s = 1.0 / a
    dl = s
    for _ in range(itmax):
        ap += 1.0
        dl *= x / ap
        s += dl
        if abs(dl) < abs(s) * eps:
            break
    return s * math.exp(-x + a * math.log(x) - gln)


def _gcf(a, x, itmax=1000, eps=3e-16, fpmin=1e-300):
    """Continued fraction for the regularised upper incomplete gamma Q(a,x)."""
    gln = math.lgamma(a)
    b = x + 1.0 - a
    c = 1.0 / fpmin
    d = 1.0 / b
    h = d
    for i in range(1, itmax + 1):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < fpmin:
            d = fpmin
        c = b + an / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        dl = d * c
        h *= dl
        if abs(dl - 1.0) < eps:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def gammaq(a, x):
    """Regularised upper incomplete gamma Q(a,x) = 1 - P(a,x)."""
    if x < 0.0 or a <= 0.0:
        raise ValueError("bad args")
    if x == 0.0:
        return 1.0
    if x < a + 1.0:
        return 1.0 - _gser(a, x)
    return _gcf(a, x)


def chi2_sf(x, df):
    """Upper tail P(X > x) for chi-square with df degrees of freedom."""
    if x <= 0:
        return 1.0
    return gammaq(df / 2.0, x / 2.0)


def norm_sf(z):
    """Upper tail of the standard normal, via erfc (machine precision)."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def two_sided_z_p(z):
    return math.erfc(abs(z) / math.sqrt(2.0))


# ------------------------------------------------------------------- binomial
def binom_pmf(k, n, p=0.5):
    return math.comb(n, k) * (p ** k) * ((1.0 - p) ** (n - k))


def mcnemar_exact_p(b, c):
    """Exact two-sided McNemar p-value.

    Conditional on n = b + c discordant pairs, b ~ Binomial(n, 1/2) under H0.
    Two-sided p = 2 * min(tail, 0.5) capped at 1  -- the standard 'exact
    conditional' (Liddell) two-sided rule; identical to the sum of all
    outcomes with probability <= observed for the symmetric p=0.5 case.
    """
    n = b + c
    if n == 0:
        return 1.0
    lo = min(b, c)
    tail = sum(binom_pmf(k, n, 0.5) for k in range(0, lo + 1))
    return min(1.0, 2.0 * tail)


def _log_binom_pmf(i, n, p):
    """log P(X = i | n, p), computed with lgamma so large n does not overflow."""
    if p <= 0.0:
        return 0.0 if i == 0 else float("-inf")
    if p >= 1.0:
        return 0.0 if i == n else float("-inf")
    log_c = math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
    return log_c + i * math.log(p) + (n - i) * math.log1p(-p)


def _tail(p, k, n, upper):
    """upper=True  -> P(X >= k | p)   (INCREASING in p)
       upper=False -> P(X <= k | p)   (DECREASING in p)
    Summed in log space then exponentiated, so n in the thousands is safe."""
    rng = range(k, n + 1) if upper else range(0, k + 1)
    terms = [_log_binom_pmf(i, n, p) for i in rng]
    terms = [t for t in terms if t != float("-inf")]
    if not terms:
        return 0.0
    mx = max(terms)
    return math.exp(mx) * sum(math.exp(t - mx) for t in terms)


def binom_exact_ci(k, n, alpha=0.05, tol=1e-12):
    """Clopper-Pearson exact CI for a binomial proportion, by bisection on the
    exact binomial tail (no scipy beta functions used).

    FIXED 2026-07-31. The previous lower-limit bisection moved the bracket the
    wrong way: P(X >= k | p) is INCREASING in p, so when the tail falls below
    alpha/2 the root lies at LARGER p and the lower bracket must be raised
    (a = m), not the upper one lowered (b = m). The old code collapsed the lower
    limit to 0.0 or 1.0. Verified against the textbook value
    CP95(8/10) = [0.4439, 0.9748]. Tails are now summed in log space, so n in
    the thousands no longer overflows.
    """
    if n == 0:
        return (0.0, 1.0)
    k = int(k)
    n = int(n)

    if k == 0:
        lo = 0.0
    else:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = (a + b) / 2
            # P(X >= k | m) increases with m; we want it to equal alpha/2.
            if _tail(m, k, n, upper=True) < alpha / 2:
                a = m
            else:
                b = m
            if b - a < tol:
                break
        lo = (a + b) / 2

    if k == n:
        hi = 1.0
    else:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = (a + b) / 2
            # P(X <= k | m) decreases with m; we want it to equal alpha/2.
            if _tail(m, k, n, upper=False) < alpha / 2:
                b = m
            else:
                a = m
            if b - a < tol:
                break
        hi = (a + b) / 2
    return (lo, hi)


# ------------------------------------------------------------- linear algebra
def mat_inv2(m):
    """Invert a 2x2 matrix given as [[a,b],[c,d]]."""
    a, b = m[0]
    c, d = m[1]
    det = a * d - b * c
    if abs(det) < 1e-300:
        raise ZeroDivisionError("singular 2x2")
    return [[d / det, -b / det], [-c / det, a / det]]


def matmul(A, B):
    n, k, m = len(A), len(B), len(B[0])
    return [[sum(A[i][t] * B[t][j] for t in range(k)) for j in range(m)] for i in range(n)]


def transpose(A):
    return [list(r) for r in zip(*A)]


# ------------------------------------------------------------------- utilities
def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def quantile(sorted_xs, q):
    """Type-7 (Excel/R default) quantile of an already-sorted list."""
    n = len(sorted_xs)
    if n == 0:
        return float("nan")
    if n == 1:
        return sorted_xs[0]
    h = (n - 1) * q
    lo = int(math.floor(h))
    hi = min(lo + 1, n - 1)
    return sorted_xs[lo] + (h - lo) * (sorted_xs[hi] - sorted_xs[lo])


def load(include_only=True):
    import json
    p = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
         "experiment-31-07-26/analysis/paired_clean.json")
    rows = json.load(open(p))
    if include_only:
        rows = [r for r in rows if r.get("analysis_include") is True]
    return rows


def group(rows, key):
    g = defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    return g

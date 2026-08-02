"""Local helpers for the nota-acceptance analysis (pure stdlib).

NOTE: stats_lib.binom_exact_ci has an inverted bisection for the LOWER Clopper-Pearson
limit (it moves the bracket the wrong way because P(X>=k|p) is increasing in p), so it
returns ~0 or ~1 instead of the limit. Correct implementation below; verified against
the textbook value CP95(8/10) = [0.4439, 0.9748].
"""
import math


def log_binom_pmf(i, n, p):
    """log C(n,i) p^i (1-p)^(n-i), computed with lgamma so large n does not overflow."""
    if p <= 0.0:
        return 0.0 if i == 0 else float("-inf")
    if p >= 1.0:
        return 0.0 if i == n else float("-inf")
    return (math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
            + i * math.log(p) + (n - i) * math.log1p(-p))


def binom_pmf(i, n, p):
    lg = log_binom_pmf(i, n, p)
    return 0.0 if lg == float("-inf") else math.exp(lg)


def cp_ci(k, n, alpha=0.05):
    """Clopper-Pearson exact binomial CI by bisection on exact binomial tails."""
    if n == 0:
        return (0.0, 1.0)

    def upper_tail(p):          # P(X >= k | p), increasing in p
        return sum(binom_pmf(i, n, p) for i in range(k, n + 1))

    def lower_tail(p):          # P(X <= k | p), decreasing in p
        return sum(binom_pmf(i, n, p) for i in range(0, k + 1))

    if k == 0:
        lo = 0.0
    else:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = (a + b) / 2
            if upper_tail(m) < alpha / 2:
                a = m          # tail too small -> p must be larger
            else:
                b = m
        lo = (a + b) / 2
    if k == n:
        hi = 1.0
    else:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = (a + b) / 2
            if lower_tail(m) < alpha / 2:
                b = m          # tail too small -> p must be smaller
            else:
                a = m
        hi = (a + b) / 2
    return (lo, hi)


def fisher_2x2(a, b, c, d):
    """Two-sided Fisher exact test (sum of tables with prob <= observed)."""
    n = a + b + c + d
    r1, c1 = a + b, a + c

    def lc(nn, kk):
        return math.lgamma(nn + 1) - math.lgamma(kk + 1) - math.lgamma(nn - kk + 1)

    def p(x):
        return math.exp(lc(r1, x) + lc(n - r1, c1 - x) - lc(n, c1))

    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    p0 = p(a)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= p0 * (1 + 1e-7)))


def binom_test_exact(k, n, p0):
    """Exact two-sided binomial test (method of small p-values)."""
    if n == 0:
        return 1.0
    obs = binom_pmf(k, n, p0)
    tot = 0.0
    for i in range(n + 1):
        pi = binom_pmf(i, n, p0)
        if pi <= obs * (1 + 1e-9):
            tot += pi
    return min(1.0, tot)


def mcnemar_exact(b, c):
    """Exact two-sided McNemar: b ~ Bin(b+c, 1/2) under H0."""
    n = b + c
    if n == 0:
        return 1.0
    lo = min(b, c)
    tail = sum(binom_pmf(i, n, 0.5) for i in range(lo + 1))
    return min(1.0, 2 * tail)


if __name__ == "__main__":
    lo, hi = cp_ci(8, 10)
    print(f"CP95(8/10) = [{lo:.4f}, {hi:.4f}]  (textbook: [0.4439, 0.9748])")
    lo, hi = cp_ci(0, 20)
    print(f"CP95(0/20) = [{lo:.4f}, {hi:.4f}]  (textbook: [0.0000, 0.1684])")
    lo, hi = cp_ci(45, 133)
    print(f"CP95(45/133) = [{lo:.4f}, {hi:.4f}]")
    print("fisher 2x2 (3,1,1,3) =", round(fisher_2x2(3, 1, 1, 3), 5), "(R: 0.48571)")
    print("binom_test_exact(45,133,0.25) =", binom_test_exact(45, 133, 0.25))

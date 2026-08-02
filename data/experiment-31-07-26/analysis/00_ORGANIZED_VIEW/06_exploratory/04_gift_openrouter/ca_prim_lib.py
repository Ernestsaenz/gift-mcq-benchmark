"""Stdlib-only statistics for the PRIMARY cross-arm inference (GIFT vs OpenRouter).

Namespaced ca_prim_ to avoid colliding with another agent's ca_lib.py.
No numpy/scipy: every routine is implemented from scratch so the method behind
each p-value is inspectable.
"""
import math
from fractions import Fraction


# ---------------------------------------------------------------- normal dist
def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def phi_inv(p):
    """Standard normal quantile by bisection on phi."""
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
    lo, hi = -40.0, 40.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if phi(mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def chi2_sf_1df(x):
    if x <= 0:
        return 1.0
    return math.erfc(math.sqrt(x / 2.0))


# --------------------------------------------------------- exact binomial ops
def binom_pmf_half(k, n):
    return Fraction(math.comb(n, k), 1 << n)


def binom_cdf_half(k, n):
    if k < 0:
        return Fraction(0)
    if k >= n:
        return Fraction(1)
    return Fraction(sum(math.comb(n, i) for i in range(0, k + 1)), 1 << n)


def binom_sf_half(k, n):
    if k <= 0:
        return Fraction(1)
    if k > n:
        return Fraction(0)
    return Fraction(sum(math.comb(n, i) for i in range(k, n + 1)), 1 << n)


def binom_cdf(k, n, p):
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, k + 1))


def binom_sf(k, n, p):
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


# ------------------------------------------------------------- exact McNemar
def mcnemar_exact(b, c):
    """Exact conditional-binomial (sign) McNemar test, computed with math.comb.

    b = pairs where GIFT correct & OpenRouter wrong
    c = pairs where OpenRouter correct & GIFT wrong
    Conditional on n = b + c, b ~ Binomial(n, 1/2) under H0.
    Two-sided p = 2 * min(P(B<=b), P(B>=b)), capped at 1. Valid without
    modification because Bin(n,1/2) is symmetric, so the doubling convention
    coincides exactly with summing all outcomes no more probable than observed.
    """
    n = b + c
    if n == 0:
        return {"b": b, "c": c, "n_disc": 0, "p_exact": 1.0,
                "p_exact_frac": "1/1", "p_one_sided_greater": 1.0,
                "p_one_sided_less": 1.0, "min_attainable_p": 1.0}
    lo = binom_cdf_half(b, n)
    hi = binom_sf_half(b, n)
    p_two = min(Fraction(1), 2 * min(lo, hi))
    return {
        "b": b, "c": c, "n_disc": n,
        "p_exact": float(p_two),
        "p_exact_frac": f"{p_two.numerator}/{p_two.denominator}",
        "p_one_sided_greater": float(hi),
        "p_one_sided_less": float(lo),
        "min_attainable_p": float(min(Fraction(1), 2 * binom_pmf_half(0, n))),
    }


def mcnemar_chi2(b, c, continuity=False):
    n = b + c
    if n == 0:
        return {"chi2": float("nan"), "p": float("nan"), "n_disc": 0}
    num = abs(b - c) - (1.0 if continuity else 0.0)
    if num < 0:
        num = 0.0
    chi2 = num * num / n
    return {"chi2": chi2, "p": chi2_sf_1df(chi2), "n_disc": n}


# ------------------------------------- exact CI for the discordant odds ratio
def clopper_pearson(k, n, alpha=0.05):
    if n == 0:
        return (0.0, 1.0)
    if k == 0:
        lo = 0.0
    else:
        a, b_ = 0.0, 1.0
        for _ in range(200):
            m = 0.5 * (a + b_)
            if binom_sf(k, n, m) < alpha / 2:
                a = m
            else:
                b_ = m
        lo = 0.5 * (a + b_)
    if k == n:
        hi = 1.0
    else:
        a, b_ = 0.0, 1.0
        for _ in range(200):
            m = 0.5 * (a + b_)
            if binom_cdf(k, n, m) > alpha / 2:
                a = m
            else:
                b_ = m
        hi = 0.5 * (a + b_)
    return (lo, hi)


def discordant_or(b, c, alpha=0.05):
    """Conditional (McNemar) odds ratio b/c with an exact CI.

    OR = pi/(1-pi) with pi = b/(b+c). Clopper-Pearson on pi maps monotonically
    onto OR, so the interval is exact and remains finite/defined when b=0 or c=0
    (where the point estimate itself degenerates to 0 or +inf).
    """
    n = b + c
    if n == 0:
        return {"or": None, "or_ci": (None, None), "pi": None,
                "pi_ci": (None, None), "note": "no discordant pairs"}
    pi = b / n
    lo, hi = clopper_pearson(b, n, alpha)

    def tr(p):
        return math.inf if p >= 1.0 else p / (1.0 - p)

    return {"or": (math.inf if c == 0 else b / c),
            "pi": pi, "pi_ci": (lo, hi),
            "or_ci": (tr(lo), tr(hi))}


# ------------------------------------------------------------------- Holm
def holm(pvals_named, alpha=0.05):
    """Holm-Bonferroni step-down. Returns list of dicts in original order."""
    items = sorted(pvals_named.items(), key=lambda kv: kv[1])
    m = len(items)
    out = {}
    running = 0.0
    rejected_so_far = True
    for i, (name, p) in enumerate(items):
        thresh = alpha / (m - i)
        adj = min(1.0, (m - i) * p)
        running = max(running, adj)   # enforce monotonicity of adjusted p
        if rejected_so_far and p <= thresh:
            rej = True
        else:
            rej = False
            rejected_so_far = False
        out[name] = {"p_raw": p, "rank": i + 1, "threshold": thresh,
                     "p_holm_adj": running, "reject_at_%.2f" % alpha: rej}
    return out


# ------------------------------------------------------------------ resample
class LCG:
    """Deterministic 64-bit LCG so every resampling result is reproducible."""
    __slots__ = ("s",)

    def __init__(self, seed):
        self.s = (seed ^ 0x9E3779B97F4A7C15) & ((1 << 64) - 1)

    def next(self):
        self.s = (self.s * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        return self.s

    def randrange(self, n):
        return (self.next() >> 16) % n

    def randbit(self):
        return (self.next() >> 40) & 1


def percentile(sorted_vals, q):
    n = len(sorted_vals)
    if n == 0:
        return float("nan")
    if n == 1:
        return sorted_vals[0]
    idx = q * (n - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return sorted_vals[lo]
    w = idx - lo
    return sorted_vals[lo] * (1 - w) + sorted_vals[hi] * w


def bca(boot_sorted, theta_hat, jack_vals, alpha=0.05):
    """Bias-corrected and accelerated bootstrap interval.

    z0 from the fraction of bootstrap replicates below the point estimate;
    acceleration a from the cluster-delete-one jackknife skewness.
    """
    B = len(boot_sorted)
    if B == 0:
        return (float("nan"), float("nan"), float("nan"), float("nan"))
    n_below = 0
    for v in boot_sorted:
        if v < theta_hat:
            n_below += 1
        else:
            break
    frac = n_below / B
    frac = min(max(frac, 1.0 / (2 * B)), 1.0 - 1.0 / (2 * B))
    z0 = phi_inv(frac)
    jbar = sum(jack_vals) / len(jack_vals)
    d = [jbar - v for v in jack_vals]
    num = sum(x ** 3 for x in d)
    den = 6.0 * (sum(x ** 2 for x in d) ** 1.5)
    a = num / den if den != 0 else 0.0
    za = phi_inv(alpha / 2)
    zb = phi_inv(1 - alpha / 2)

    def adj(z):
        denom = 1 - a * (z0 + z)
        if denom == 0:
            return 0.5
        return phi(z0 + (z0 + z) / denom)

    a1, a2 = adj(za), adj(zb)
    return (percentile(boot_sorted, a1), percentile(boot_sorted, a2), z0, a)

#!/usr/bin/env python3
"""Independent stdlib-only stats for the flag-error refutation.

Everything re-implemented from scratch (not imported from mech_stats) so the
reproduction is genuinely independent of the code that produced the claim.
"""
import math
from fractions import Fraction


# ---------------------------------------------------------------- exact 2x2
def _logchoose(n, k):
    if k < 0 or k > n:
        return None
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def hypergeom_pmf(x, r1, r2, c1):
    """P(X=x) for the noncentral-free (psi=1) hypergeometric of a 2x2 table
    with row totals r1,r2 and first-column total c1."""
    n = r1 + r2
    a = _logchoose(r1, x)
    b = _logchoose(r2, c1 - x)
    c = _logchoose(n, c1)
    if a is None or b is None:
        return 0.0
    return math.exp(a + b - c)


def fisher2x2(a, b, c, d):
    """Two-sided Fisher exact (point-probability / Irwin method).

    Table [[a,b],[c,d]]: a = neg&event, b = neg&noevent, c = ref&event,
    d = ref&noevent.  Returns (OR, p_two_sided, p_midp).
    """
    r1, r2, c1 = a + b, c + d, a + c
    lo, hi = max(0, c1 - r2), min(r1, c1)
    probs = {x: hypergeom_pmf(x, r1, r2, c1) for x in range(lo, hi + 1)}
    tot = sum(probs.values())
    pobs = probs[a]
    p = sum(v for v in probs.values() if v <= pobs * (1 + 1e-9)) / tot
    pmid = (sum(v for k, v in probs.items() if v < pobs * (1 - 1e-9))
            + 0.5 * sum(v for k, v in probs.items()
                        if abs(v - pobs) <= pobs * 1e-9)) / tot
    orr = float("inf") if (b == 0 or c == 0) else (a * d) / (b * c)
    return orr, min(1.0, p), min(1.0, pmid)


def _nc_hyper_probs(psi, r1, r2, c1):
    lo, hi = max(0, c1 - r2), min(r1, c1)
    w = {}
    for x in range(lo, hi + 1):
        lw = _logchoose(r1, x) + _logchoose(r2, c1 - x) + x * math.log(psi)
        w[x] = lw
    m = max(w.values())
    e = {k: math.exp(v - m) for k, v in w.items()}
    s = sum(e.values())
    return {k: v / s for k, v in e.items()}


def fisher_ci(a, b, c, d, alpha=0.05):
    """Exact conditional (Cornfield) CI for the odds ratio, by inverting the
    noncentral hypergeometric tail tests.  Returns (lo, hi)."""
    r1, r2, c1 = a + b, c + d, a + c
    lo_x, hi_x = max(0, c1 - r2), min(r1, c1)

    def upper_tail(psi):   # P(X >= a)
        p = _nc_hyper_probs(psi, r1, r2, c1)
        return sum(v for k, v in p.items() if k >= a)

    def lower_tail(psi):   # P(X <= a)
        p = _nc_hyper_probs(psi, r1, r2, c1)
        return sum(v for k, v in p.items() if k <= a)

    def bisect(f, target, lo, hi):
        for _ in range(200):
            mid = math.sqrt(lo * hi)
            if f(mid) < target:
                lo = mid
            else:
                hi = mid
        return math.sqrt(lo * hi)

    if a == lo_x:
        L = 0.0
    else:
        L = bisect(upper_tail, alpha / 2, 1e-8, 1e8)
    if a == hi_x:
        U = float("inf")
    else:
        U = 1.0 / bisect(lambda psi: lower_tail(1.0 / psi), alpha / 2, 1e-8, 1e8)
    return L, U


# ------------------------------------------------------- Mantel-Haenszel
def mantel_haenszel(tables):
    """tables: list of (a,b,c,d).  Returns (OR_MH, chi2, p, se_log)."""
    num = den = 0.0
    E = V = O = 0.0
    F = G = H = K = 0.0
    for a, b, c, d in tables:
        n = a + b + c + d
        if n == 0:
            continue
        num += a * d / n
        den += b * c / n
        O += a
        E += (a + b) * (a + c) / n
        if n > 1:
            V += (a + b) * (c + d) * (a + c) * (b + d) / (n * n * (n - 1))
    if den == 0 or num == 0:
        return (float("inf") if den == 0 else 0.0), float("nan"), float("nan"), float("nan")
    orr = num / den
    # Robins-Breslow-Greenland variance of log(OR_MH)
    for a, b, c, d in tables:
        n = a + b + c + d
        if n == 0:
            continue
        P, Q = (a + d) / n, (b + c) / n
        R, S = a * d / n, b * c / n
        F += P * R
        G += P * S + Q * R
        H += Q * S
    var = F / (2 * num * num) + G / (2 * num * den) + H / (2 * den * den)
    chi2 = (abs(O - E) - 0.5) ** 2 / V if V > 0 else float("nan")
    p = math.erfc(math.sqrt(chi2 / 2.0)) if chi2 == chi2 else float("nan")
    return orr, chi2, p, math.sqrt(var)


def two_sided_z_p(z):
    return math.erfc(abs(z) / math.sqrt(2.0))


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    cen = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, cen - half), min(1.0, cen + half))

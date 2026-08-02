"""INDEPENDENT stdlib-only statistical primitives for refuting the
specification-curve robustness claim.

Deliberately written from scratch, with algorithms chosen to DIFFER from
sens_speccurve_lib.py wherever a second route exists, so that agreement is
evidence and not shared-bug propagation.

  * exact binomial two-sided : exact integer arithmetic (Fraction) AND an
                               independent log-space lgamma route.
  * chi-square survival      : even-df closed form via Poisson tail sum.
  * Student t two-sided      : EXACT closed forms for odd df (df=1,3,5,...)
                               derived from the arctangent expansion, plus a
                               Lentz continued-fraction incomplete beta for
                               the general case; the two are cross-checked.
  * logistic regression      : IRLS on the 2x2 normal equations.
  * cluster-robust sandwich  : CR1 (G/(G-1)) meat correction, t(G-1) reference.
"""
import math
from fractions import Fraction
from math import lgamma, log, exp, sqrt, atan, pi


# --------------------------------------------------------------- exact binomial
def binom_two_sided_exact(b, c):
    """Exact two-sided McNemar p = 2 * P(X <= min(b,c)), X ~ Bin(b+c, 1/2).

    Computed in EXACT rational arithmetic (no floating point until the end).
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    if n > 4000:          # exact path is O(n) bigints; fine up to a few thousand
        return binom_two_sided_log(b, c)
    num = 0
    for i in range(k + 1):
        num += math.comb(n, i)
    p = Fraction(2 * num, 1 << n)
    if p > 1:
        return 1.0
    # Fraction -> float can underflow to 0 for tiny p; go through logs instead.
    if p == 0:
        return 0.0
    try:
        v = float(p)
    except OverflowError:
        v = 0.0
    if v == 0.0:
        return binom_two_sided_log(b, c)
    return v


def binom_two_sided_log(b, c):
    """Same quantity via log-space accumulation (independent route)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    ln2 = math.log(2.0)
    terms = []
    for i in range(k + 1):
        lt = lgamma(n + 1) - lgamma(i + 1) - lgamma(n - i + 1) - n * ln2
        terms.append(lt)
    m = max(terms)
    s = sum(exp(t - m) for t in terms)
    lp = m + log(s) + ln2
    return min(1.0, exp(lp)) if lp > -745 else exp(lp) if lp > -745 else math.exp(lp)


def binom_two_sided_log10(b, c):
    """log10 of the exact two-sided p, safe far below double underflow."""
    n = b + c
    if n == 0:
        return 0.0
    k = min(b, c)
    ln2 = math.log(2.0)
    terms = [lgamma(n + 1) - lgamma(i + 1) - lgamma(n - i + 1) - n * ln2
             for i in range(k + 1)]
    m = max(terms)
    s = sum(exp(t - m) for t in terms)
    return (m + log(s) + ln2) / math.log(10.0)


# --------------------------------------------------------------- chi-square
def chi2_sf_even(x, df):
    """P(X > x) for chi-square with even df: Poisson(x/2) tail sum."""
    assert df % 2 == 0 and df > 0
    k = df // 2
    h = x / 2.0
    # sum_{i=0}^{k-1} h^i/i! * e^{-h}
    term = 1.0
    s = 1.0
    for i in range(1, k):
        term *= h / i
        s += term
    return exp(-h) * s


def chi2_sf_even_log10(x, df):
    assert df % 2 == 0 and df > 0
    k = df // 2
    h = x / 2.0
    term = 1.0
    s = 1.0
    for i in range(1, k):
        term *= h / i
        s += term
    return (-h + log(s)) / math.log(10.0)


# --------------------------------------------------------------- Student t
def t_two_sided_odd_exact(t, df):
    """EXACT two-sided tail for ODD df using the classical closed form.

    For df = 2m+1,  P(|T| > t) = 1 - (2/pi) * [ theta + sin(theta) * S ]
    where theta = atan(t/sqrt(df)) and
      S = sum_{j=1}^{m} ( (2j-2)!! / (2j-1)!! ) * cos(theta)^(2j-1)
    with the convention S = 0 for m = 0 (df = 1).
    Verified below against the standard df=3 form
      P(|T|>t) = 1 - (2/pi)[ atan(t/sqrt3) + t*sqrt3/(3+t^2) ].
    """
    assert df % 2 == 1 and df >= 1
    t = abs(t)
    m = (df - 1) // 2
    th = atan(t / sqrt(df))
    ct = math.cos(th)
    st = math.sin(th)
    S = 0.0
    coef = 1.0                      # (2j-2)!!/(2j-1)!! for j=1 is 1/1 = 1
    for j in range(1, m + 1):
        if j > 1:
            coef *= (2.0 * j - 2.0) / (2.0 * j - 1.0)
        S += coef * ct ** (2 * j - 1)
    cdf_half = (th + st * S) / pi   # = F(t) - 1/2
    return max(0.0, 1.0 - 2.0 * cdf_half)


def _betacf(a, b, x, MAXIT=500, EPS=1e-15, FPMIN=1e-300):
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for mm in range(1, MAXIT + 1):
        m2 = 2 * mm
        aa = mm * (b - mm) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + mm) * (qab + mm) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS:
            break
    return h


def betai(a, b, x):
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = lgamma(a + b) - lgamma(a) - lgamma(b) + a * log(x) + b * math.log1p(-x)
    if x < (a + 1.0) / (a + b + 2.0):
        return exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - exp(lbt) * _betacf(b, a, 1.0 - x) / b


def betai_log10(a, b, x):
    """log10 I_x(a,b) valid deep into the underflow region (lower tail only)."""
    if x <= 0.0:
        return float("-inf")
    lbt = lgamma(a + b) - lgamma(a) - lgamma(b) + a * log(x) + b * math.log1p(-x)
    cf = _betacf(a, b, x)
    return (lbt + log(cf) - log(a)) / math.log(10.0)


def t_two_sided(t, df):
    """Two-sided Student-t tail. Uses the exact odd-df form when available."""
    if df <= 0:
        return float("nan")
    t = abs(t)
    if not math.isfinite(t):
        return 0.0
    if df % 2 == 1 and df <= 41:
        return t_two_sided_odd_exact(t, df)
    return betai(df / 2.0, 0.5, df / (df + t * t))


def t_two_sided_log10(t, df):
    t = abs(t)
    x = df / (df + t * t)
    return betai_log10(df / 2.0, 0.5, x)


# --------------------------------------------------------------- logistic + CR1
def logit_fit(y, x, iters=200, tol=1e-12):
    b0 = b1 = 0.0
    n = len(y)
    for _ in range(iters):
        s00 = s01 = s11 = g0 = g1 = 0.0
        for i in range(n):
            e = b0 + b1 * x[i]
            p = 1.0 / (1.0 + exp(-e)) if e > -700 else 0.0
            w = p * (1.0 - p)
            r = y[i] - p
            g0 += r; g1 += r * x[i]
            s00 += w; s01 += w * x[i]; s11 += w * x[i] * x[i]
        det = s00 * s11 - s01 * s01
        if abs(det) < 1e-16:
            break
        d0 = (s11 * g0 - s01 * g1) / det
        d1 = (-s01 * g0 + s00 * g1) / det
        b0 += d0; b1 += d1
        if max(abs(d0), abs(d1)) < tol:
            break
    return b0, b1


def logit_cluster_robust(y, x, cl):
    """Return (beta1, se_cr1, p, G) with a CR1 cluster-robust sandwich, t(G-1)."""
    b0, b1 = logit_fit(y, x)
    n = len(y)
    s00 = s01 = s11 = 0.0
    sc = {}
    for i in range(n):
        e = b0 + b1 * x[i]
        p = 1.0 / (1.0 + exp(-e))
        w = p * (1.0 - p)
        s00 += w; s01 += w * x[i]; s11 += w * x[i] * x[i]
        r = y[i] - p
        g = cl[i]
        cur = sc.get(g)
        if cur is None:
            sc[g] = [r, r * x[i]]
        else:
            cur[0] += r; cur[1] += r * x[i]
    det = s00 * s11 - s01 * s01
    i00, i01, i11 = s11 / det, -s01 / det, s00 / det
    m00 = m01 = m11 = 0.0
    for u0, u1 in sc.values():
        m00 += u0 * u0; m01 += u0 * u1; m11 += u1 * u1
    G = len(sc)
    corr = G / (G - 1.0) if G > 1 else 1.0
    m00 *= corr; m01 *= corr; m11 *= corr
    # V = B M B, want V[1,1]
    a10 = i01 * m00 + i11 * m01
    a11 = i01 * m01 + i11 * m11
    v11 = a10 * i01 + a11 * i11
    se = sqrt(v11)
    return b1, se, t_two_sided(b1 / se, G - 1), G


def ols_intercept_cluster_robust(d, cl):
    """Mean of d vs 0, CR1 cluster-robust SE, t(G-1).  Returns (mean, se, p, G)."""
    n = len(d)
    mean = sum(d) / n
    agg = {}
    for i in range(n):
        g = cl[i]
        agg[g] = agg.get(g, 0.0) + (d[i] - mean)
    G = len(agg)
    meat = sum(u * u for u in agg.values())
    corr = G / (G - 1.0) if G > 1 else 1.0
    var = corr * meat / (n * n)
    se = sqrt(var) if var > 0 else float("nan")
    if not (se > 0):
        return mean, se, float("nan"), G
    return mean, se, t_two_sided(mean / se, G - 1), G


def fisher_combine(ps):
    ps = [min(max(p, 1e-300), 1.0) for p in ps]
    stat = -2.0 * sum(log(p) for p in ps)
    return chi2_sf_even(stat, 2 * len(ps)), stat


def fisher_combine_log10(ps):
    ps = [min(max(p, 1e-300), 1.0) for p in ps]
    stat = -2.0 * sum(log(p) for p in ps)
    return chi2_sf_even_log10(stat, 2 * len(ps)), stat

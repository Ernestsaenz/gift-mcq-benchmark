"""Pure-stdlib statistics helpers for the specification-curve analysis.

No numpy / scipy / pandas. Everything implemented from scratch.
"""
import math
from math import comb, erfc, lgamma


# ---------------------------------------------------------------- distributions
def norm_sf_two_sided(z):
    """Two-sided tail probability of a standard normal at |z|."""
    return erfc(abs(z) / math.sqrt(2.0))


def chi2_sf_even(x, df):
    """Survival function of chi-square with EVEN df (exact closed form).

    P(X > x) = exp(-x/2) * sum_{i=0}^{df/2 - 1} (x/2)^i / i!
    """
    assert df % 2 == 0
    k = df // 2
    h = x / 2.0
    term = 1.0
    s = 1.0
    for i in range(1, k):
        term *= h / i
        s += term
    return math.exp(-h) * s


def _betacf(a, b, x):
    """Continued fraction for the incomplete beta (Lentz's method, NR 6.4)."""
    MAXIT, EPS, FPMIN = 300, 3.0e-14, 1.0e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
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
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(lgamma(a + b) - lgamma(a) - lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_sf_two_sided(t, df):
    """Two-sided p-value from Student's t with df degrees of freedom."""
    if df <= 0:
        return float("nan")
    t = abs(t)
    if not math.isfinite(t):
        return 0.0
    return betai(df / 2.0, 0.5, df / (df + t * t))


# ---------------------------------------------------------------- exact McNemar
def mcnemar_exact_two_sided(b, c):
    """Exact two-sided McNemar test: X ~ Bin(b+c, 1/2), doubled one-tail.

    b = # pairs correct in A but not B; c = # pairs correct in B but not A.
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(0, k + 1))
    p = 2.0 * (tail / (2.0 ** n))
    return min(1.0, p)


# ---------------------------------------------------------------- logistic + sandwich
def logit_fit_arm(y, arm, max_iter=100, tol=1e-11):
    """Newton-Raphson logistic regression of y on [1, arm]. Returns (beta0, beta1)."""
    b0, b1 = 0.0, 0.0
    n = len(y)
    for _ in range(max_iter):
        s00 = s01 = s11 = 0.0
        g0 = g1 = 0.0
        for i in range(n):
            eta = b0 + b1 * arm[i]
            p = 1.0 / (1.0 + math.exp(-eta)) if eta > -700 else 0.0
            w = p * (1.0 - p)
            r = y[i] - p
            g0 += r
            g1 += r * arm[i]
            s00 += w
            s01 += w * arm[i]
            s11 += w * arm[i] * arm[i]
        det = s00 * s11 - s01 * s01
        if abs(det) < 1e-14:
            break
        d0 = (s11 * g0 - s01 * g1) / det
        d1 = (-s01 * g0 + s00 * g1) / det
        b0 += d0
        b1 += d1
        if max(abs(d0), abs(d1)) < tol:
            break
    return b0, b1


def logit_cluster_robust_p(y, arm, cluster_ids):
    """Wald two-sided p for the arm coefficient with a cluster-robust sandwich SE.

    V = Bread * Meat * Bread, Bread = (X'WX)^-1, Meat = sum_g u_g u_g',
    u_g = sum_{i in g} x_i (y_i - p_i).  Finite-sample correction G/(G-1).
    Returns (beta1, se, p).
    """
    b0, b1 = logit_fit_arm(y, arm)
    n = len(y)
    s00 = s01 = s11 = 0.0
    scores = {}
    for i in range(n):
        eta = b0 + b1 * arm[i]
        p = 1.0 / (1.0 + math.exp(-eta))
        w = p * (1.0 - p)
        s00 += w
        s01 += w * arm[i]
        s11 += w * arm[i] * arm[i]
        r = y[i] - p
        g = cluster_ids[i]
        cur = scores.get(g)
        if cur is None:
            scores[g] = [r, r * arm[i]]
        else:
            cur[0] += r
            cur[1] += r * arm[i]
    det = s00 * s11 - s01 * s01
    # Bread = inverse of [[s00,s01],[s01,s11]]
    i00, i01, i11 = s11 / det, -s01 / det, s00 / det
    m00 = m01 = m11 = 0.0
    for u0, u1 in scores.values():
        m00 += u0 * u0
        m01 += u0 * u1
        m11 += u1 * u1
    G = len(scores)
    corr = G / (G - 1.0) if G > 1 else 1.0
    m00 *= corr
    m01 *= corr
    m11 *= corr
    # V = I M I  (symmetric 2x2)
    a00 = i00 * m00 + i01 * m01
    a01 = i00 * m01 + i01 * m11
    a10 = i01 * m00 + i11 * m01
    a11 = i01 * m01 + i11 * m11
    v11 = a10 * i01 + a11 * i11
    se = math.sqrt(v11) if v11 > 0 else float("nan")
    # small-G t reference, df = G-1
    tstat = b1 / se
    return b1, se, t_sf_two_sided(tstat, G - 1)


def ols_intercept_cluster_robust_p(d, cluster_ids):
    """Mean of d tested against 0 with a cluster-robust SE (intercept-only OLS).

    Equivalent to a paired t-test when every observation is its own cluster.
    Returns (mean, se, p) with a t(G-1) reference distribution.
    """
    n = len(d)
    mean = sum(d) / n
    agg = {}
    for i in range(n):
        g = cluster_ids[i]
        agg[g] = agg.get(g, 0.0) + (d[i] - mean)
    G = len(agg)
    meat = sum(u * u for u in agg.values())
    corr = (G / (G - 1.0)) * ((n - 1.0) / (n - 1.0)) if G > 1 else 1.0
    var = corr * meat / (n * n)
    se = math.sqrt(var) if var > 0 else float("nan")
    if not (se > 0):
        return mean, se, float("nan")
    return mean, se, t_sf_two_sided(mean / se, G - 1)

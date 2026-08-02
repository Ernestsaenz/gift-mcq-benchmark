#!/usr/bin/env python
"""Stdlib-only statistics used by the mech_rneg_* refutation scripts.

Every routine is named where it is used so the p-value provenance is explicit.
"""
from __future__ import annotations
import math, random

# ---------------------------------------------------------------- combinatorics
def lchoose(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_exact_2x2(a, b, c, d):
    """Two-sided Fisher exact test, p<=p_obs point-probability rule.
    Table rows = exposure (a,b) / (c,d); cols = success / failure."""
    n = a + b + c + d
    r1, c1 = a + b, a + c
    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    def pr(x):
        return math.exp(lchoose(r1, x) + lchoose(n - r1, c1 - x) - lchoose(n, c1))
    po = pr(a)
    return sum(pr(x) for x in range(lo, hi + 1) if pr(x) <= po * (1 + 1e-9))


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    ctr = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return ctr - half, ctr + half


def OR(a, b, c, d, h=0.0):
    a, b, c, d = a + h, b + h, c + h, d + h
    return float("inf") if b * c == 0 else (a * d) / (b * c)


def logor_se(a, b, c, d, h=0.5):
    a, b, c, d = a + h, b + h, c + h, d + h
    return math.log((a * d) / (b * c)), math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)


def norm_sf2(z):
    """Two-sided standard-normal tail."""
    return math.erfc(abs(z) / math.sqrt(2))


def chi2_sf(x, k):
    """Upper tail of chi-square with k df (regularized incomplete gamma)."""
    if x <= 0:
        return 1.0
    a, xx = k / 2.0, x / 2.0
    if xx < a + 1:
        term = 1.0 / a
        s, n = term, 0
        while True:
            n += 1
            term *= xx / (a + n)
            s += term
            if abs(term) < abs(s) * 1e-15 or n > 20000:
                break
        return 1 - s * math.exp(-xx + a * math.log(xx) - math.lgamma(a))
    tiny = 1e-300
    b, c, d = xx + 1 - a, 1 / tiny, 1 / (xx + 1 - a)
    h = d
    for i in range(1, 20000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1 / d
        de = d * c
        h *= de
        if abs(de - 1) < 1e-15:
            break
    return h * math.exp(-xx + a * math.log(xx) - math.lgamma(a))


def student_sf2(t, df):
    """Two-sided Student-t tail via the incomplete beta / continued fraction."""
    x = df / (df + t * t)
    return betainc(df / 2.0, 0.5, x)


def betainc(a, b, x):
    """Regularized incomplete beta I_x(a,b), Lentz continued fraction."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1 - math.exp(lbeta + b * math.log(1 - x) + a * math.log(x)) * _betacf(b, a, 1 - x) / b


def _betacf(a, b, x):
    tiny, eps = 1e-300, 1e-15
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1 / d
        de = d * c
        h *= de
        if abs(de - 1) < eps:
            break
    return h


# ---------------------------------------------------------------- linear algebra
def matinv(M):
    n = len(M)
    A = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(M)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(A[r][col]))
        if abs(A[piv][col]) < 1e-12:
            A[piv][col] += 1e-10
        A[col], A[piv] = A[piv], A[col]
        pv = A[col][col]
        A[col] = [v / pv for v in A[col]]
        for r in range(n):
            if r == col:
                continue
            f = A[r][col]
            if f:
                A[r] = [vr - f * vc for vr, vc in zip(A[r], A[col])]
    return [row[n:] for row in A]


def logistic_fit(X, y, ridge=1e-8, iters=200):
    """IRLS / Newton-Raphson MLE with a whisper of ridge for separation safety."""
    k = len(X[0])
    beta = [0.0] * k
    for _ in range(iters):
        g = [0.0] * k
        H = [[0.0] * k for _ in range(k)]
        for xi, yi in zip(X, y):
            eta = sum(b * v for b, v in zip(beta, xi))
            eta = max(-30.0, min(30.0, eta))
            p = 1 / (1 + math.exp(-eta))
            w = max(p * (1 - p), 1e-9)
            r = yi - p
            for a in range(k):
                g[a] += xi[a] * r
                for b_ in range(k):
                    H[a][b_] += w * xi[a] * xi[b_]
        for a in range(k):
            H[a][a] += ridge
            g[a] -= ridge * beta[a]
        step = matinv(H)
        delta = [sum(step[a][b_] * g[b_] for b_ in range(k)) for a in range(k)]
        beta = [b + dl for b, dl in zip(beta, delta)]
        if max(abs(dl) for dl in delta) < 1e-10:
            break
    return beta


def _bread(X, beta, ridge=1e-8):
    k = len(X[0])
    H = [[0.0] * k for _ in range(k)]
    for xi in X:
        eta = max(-30.0, min(30.0, sum(b * v for b, v in zip(beta, xi))))
        p = 1 / (1 + math.exp(-eta))
        w = max(p * (1 - p), 1e-9)
        for a in range(k):
            for b_ in range(k):
                H[a][b_] += w * xi[a] * xi[b_]
    for a in range(k):
        H[a][a] += ridge
    return matinv(H)


def cluster_robust(X, y, beta, clusters, kind="CR0"):
    """Sandwich SE clustered on `clusters`.
    CR0 = raw meat.  CR1 = finite-sample scale G/(G-1) * (N-1)/(N-k).
    Returns (se list, G)."""
    k = len(X[0])
    Hinv = _bread(X, beta)
    byc = {}
    for xi, yi, ci in zip(X, y, clusters):
        eta = max(-30.0, min(30.0, sum(b * v for b, v in zip(beta, xi))))
        p = 1 / (1 + math.exp(-eta))
        r = yi - p
        s = byc.setdefault(ci, [0.0] * k)
        for a in range(k):
            s[a] += xi[a] * r
    meat = [[0.0] * k for _ in range(k)]
    for s in byc.values():
        for a in range(k):
            for b_ in range(k):
                meat[a][b_] += s[a] * s[b_]
    G, N = len(byc), len(X)
    scale = 1.0
    if kind == "CR1":
        scale = (G / (G - 1)) * ((N - 1) / (N - k))
    V = [[scale * sum(Hinv[a][m] * meat[m][n] for m in range(k)) for n in range(k)] for a in range(k)]
    V = [[sum(V[a][m] * Hinv[m][b_] for m in range(k)) for b_ in range(k)] for a in range(k)]
    return [math.sqrt(max(V[a][a], 0.0)) for a in range(k)], G

"""Extra pure-stdlib tests for the negated-interaction analysis."""
import math, random


def fisher_exact_2x2(a, b, c, d):
    """Two-sided Fisher exact test for [[a,b],[c,d]].

    Exact conditional (hypergeometric) null given both margins; two-sided
    p = sum of all tables with probability <= P(observed) * (1 + 1e-7).
    Returns (odds_ratio, p).
    """
    n = a + b + c + d
    r1, r2 = a + b, c + d
    c1 = a + c

    def prob(x):
        y = r1 - x
        z = c1 - x
        w = r2 - z
        if min(x, y, z, w) < 0:
            return 0.0
        return math.exp(
            math.lgamma(r1 + 1) + math.lgamma(r2 + 1) + math.lgamma(c1 + 1)
            + math.lgamma(n - c1 + 1) - math.lgamma(n + 1)
            - math.lgamma(x + 1) - math.lgamma(y + 1)
            - math.lgamma(z + 1) - math.lgamma(w + 1))

    p_obs = prob(a)
    lo = max(0, c1 - r2)
    hi = min(r1, c1)
    p = sum(prob(x) for x in range(lo, hi + 1) if prob(x) <= p_obs * (1 + 1e-7))
    orr = float("inf") if (b == 0 or c == 0) else (a * d) / (b * c)
    return orr, min(1.0, p)


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    cen = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, cen - half), min(1.0, cen + half))


# ------------------------------------------------------- logistic regression
def logistic_fit(X, y, w=None, iters=80, ridge=1e-8):
    """Newton-Raphson (IRLS) logistic regression. X includes intercept column."""
    n, k = len(X), len(X[0])
    beta = [0.0] * k
    for _ in range(iters):
        eta = [sum(X[i][j] * beta[j] for j in range(k)) for i in range(n)]
        mu = [1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, e)))) for e in eta]
        W = [max(mu[i] * (1 - mu[i]), 1e-10) for i in range(n)]
        g = [sum(X[i][j] * (y[i] - mu[i]) for i in range(n)) for j in range(k)]
        H = [[sum(X[i][a] * W[i] * X[i][b] for i in range(n)) + (ridge if a == b else 0.0)
              for b in range(k)] for a in range(k)]
        try:
            step = solve(H, g)
        except ZeroDivisionError:
            break
        beta = [beta[j] + step[j] for j in range(k)]
        if max(abs(s) for s in step) < 1e-10:
            break
    return beta


def solve(A, b):
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-300:
            raise ZeroDivisionError
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        M[c] = [v / pv for v in M[c]]
        for r in range(n):
            if r != c and M[r][c] != 0.0:
                f = M[r][c]
                M[r] = [M[r][j] - f * M[c][j] for j in range(n + 1)]
    return [M[i][n] for i in range(n)]


def inv(A):
    n = len(A)
    return [[solve(A, [1.0 if r == j else 0.0 for r in range(n)])[i] for j in range(n)]
            for i in range(n)]


def cluster_robust_se(X, y, beta, clusters):
    """CR0 sandwich: bread * meat * bread, clustering on `clusters`."""
    n, k = len(X), len(X[0])
    eta = [sum(X[i][j] * beta[j] for j in range(k)) for i in range(n)]
    mu = [1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, e)))) for e in eta]
    W = [max(mu[i] * (1 - mu[i]), 1e-10) for i in range(n)]
    B = [[sum(X[i][a] * W[i] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    Binv = inv(B)
    agg = {}
    for i in range(n):
        s = agg.setdefault(clusters[i], [0.0] * k)
        r = y[i] - mu[i]
        for j in range(k):
            s[j] += X[i][j] * r
    M = [[sum(v[a] * v[b] for v in agg.values()) for b in range(k)] for a in range(k)]
    G = len(agg)
    scale = G / max(G - 1, 1)
    V = [[scale * sum(Binv[a][x] * M[x][z] * Binv[z][b] for x in range(k) for z in range(k))
          for b in range(k)] for a in range(k)]
    return [math.sqrt(max(V[j][j], 0.0)) for j in range(k)], V


def two_sided_z_p(z):
    return math.erfc(abs(z) / math.sqrt(2.0))

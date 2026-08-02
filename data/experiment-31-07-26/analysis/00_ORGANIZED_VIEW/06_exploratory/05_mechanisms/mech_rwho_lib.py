"""Independent stdlib logistic regression + cluster-robust / bootstrap / permutation inference.

Written from scratch for the refutation pass; deliberately does NOT import mech_who_lib.
Newton-Raphson via Cholesky (mech_who_lib used Gauss-Jordan), so the linear algebra path
is different too.
"""
import math, random


# ---------- linear algebra: Cholesky (SPD) ----------
def chol(A):
    n = len(A)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                v = A[i][i] - s
                if v <= 1e-14:
                    raise ValueError("not positive definite (collinear design?)")
                L[i][j] = math.sqrt(v)
            else:
                L[i][j] = (A[i][j] - s) / L[j][j]
    return L


def chol_solve(L, b):
    n = len(L)
    y = [0.0] * n
    for i in range(n):
        y[i] = (b[i] - sum(L[i][k] * y[k] for k in range(i))) / L[i][i]
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (y[i] - sum(L[k][i] * x[k] for k in range(i + 1, n))) / L[i][i]
    return x


def chol_inv(A):
    L = chol(A)
    n = len(A)
    cols = []
    for j in range(n):
        e = [1.0 if i == j else 0.0 for i in range(n)]
        cols.append(chol_solve(L, e))
    return [[cols[j][i] for j in range(n)] for i in range(n)]


# ---------- logistic regression, Newton-Raphson ----------
def fit_logit(X, y, maxit=100, tol=1e-11):
    n, k = len(X), len(X[0])
    b = [0.0] * k
    for _ in range(maxit):
        eta = [sum(X[i][j] * b[j] for j in range(k)) for i in range(n)]
        p = [1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, e)))) for e in eta]
        w = [max(pi * (1 - pi), 1e-12) for pi in p]
        g = [sum(X[i][j] * (y[i] - p[i]) for i in range(n)) for j in range(k)]
        H = [[sum(X[i][a] * w[i] * X[i][c] for i in range(n)) for c in range(k)] for a in range(k)]
        L = chol(H)
        step = chol_solve(L, g)
        b = [b[j] + step[j] for j in range(k)]
        if max(abs(s) for s in step) < tol:
            break
    eta = [sum(X[i][j] * b[j] for j in range(k)) for i in range(n)]
    p = [1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, e)))) for e in eta]
    w = [max(pi * (1 - pi), 1e-12) for pi in p]
    H = [[sum(X[i][a] * w[i] * X[i][c] for i in range(n)) for c in range(k)] for a in range(k)]
    bread = chol_inv(H)
    ll = sum(y[i] * math.log(max(p[i], 1e-300)) + (1 - y[i]) * math.log(max(1 - p[i], 1e-300))
             for i in range(n))
    return b, bread, p, ll


def cr1(X, y, p, bread, cl):
    """CR1 cluster-robust sandwich."""
    n, k = len(X), len(X[0])
    r = [y[i] - p[i] for i in range(n)]
    byc = {}
    for i in range(n):
        byc.setdefault(cl[i], []).append(i)
    meat = [[0.0] * k for _ in range(k)]
    for _, idx in byc.items():
        u = [sum(X[i][j] * r[i] for i in idx) for j in range(k)]
        for a in range(k):
            for c in range(k):
                meat[a][c] += u[a] * u[c]
    G = len(byc)
    corr = (G / (G - 1.0)) * ((n - 1.0) / (n - k))
    V = [[corr * sum(bread[a][x] * meat[x][z] * bread[z][c] for x in range(k) for z in range(k))
          for c in range(k)] for a in range(k)]
    return V, G


def norm_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def chi2_sf(x, k):
    """upper tail of chi2_k, by series (exact for integer k)."""
    if x <= 0:
        return 1.0
    if k % 2 == 0:
        s, t = 0.0, math.exp(-x / 2)
        for i in range(k // 2):
            if i:
                t *= (x / 2) / i
            s += t
        return min(1.0, s)
    s = 2 * (1 - norm_cdf(math.sqrt(x)))
    t = math.sqrt(2 * x / math.pi) * math.exp(-x / 2)
    for i in range(1, (k - 1) // 2 + 1):
        s += t
        t *= x / (2 * i + 1)
    return min(1.0, max(0.0, s))


def wald(b, V, idx):
    sub = [[V[a][c] for c in idx] for a in idx]
    bb = [b[a] for a in idx]
    inv = chol_inv(sub)
    st = sum(bb[a] * inv[a][c] * bb[c] for a in range(len(idx)) for c in range(len(idx)))
    return st, len(idx), chi2_sf(st, len(idx))


# ---------- design helper ----------
def build(rows, terms):
    X = [[1.0] + [t[1](r) for t in terms] for r in rows]
    names = ["(intercept)"] + [t[0] for t in terms]
    return X, names


def run(rows, yf, terms, cluster_key="cluster", quiet=False, label=""):
    X, names = build(rows, terms)
    y = [float(yf(r)) for r in rows]
    cl = [r[cluster_key] for r in rows]
    b, bread, p, ll = fit_logit(X, y)
    V, G = cr1(X, y, p, bread, cl)
    if not quiet:
        se = [math.sqrt(max(V[j][j], 0)) for j in range(len(b))]
        print(f"\n{label}  n={len(rows)} events={int(sum(y))} clusters={G}")
        print(f"  {'term':<34}{'beta':>8}{'SE':>7}{'OR':>8}{'95%CI(OR)':>22}{'z':>7}{'p':>9}")
        for j in range(len(b)):
            z = b[j] / se[j] if se[j] > 0 else 0.0
            pv = 2 * (1 - norm_cdf(abs(z)))
            print(f"  {names[j]:<34}{b[j]:>8.3f}{se[j]:>7.3f}{math.exp(b[j]):>8.3f}"
                  f"{'[%.3f, %.3f]' % (math.exp(b[j]-1.96*se[j]), math.exp(b[j]+1.96*se[j])):>22}"
                  f"{z:>7.2f}{pv:>9.4f}")
    return b, V, names, ll, G


# ---------- cluster bootstrap ----------
def cluster_boot(rows, yf, terms, B=2000, seed=7, cluster_key="cluster"):
    """Percentile CIs from a nonparametric cluster (pairs) bootstrap."""
    rnd = random.Random(seed)
    byc = {}
    for r in rows:
        byc.setdefault(r[cluster_key], []).append(r)
    keys = list(byc)
    _, _, names = build(rows, terms)[0], None, build(rows, terms)[1]
    draws = []
    for _ in range(B):
        samp = []
        for _ in range(len(keys)):
            samp.extend(byc[keys[rnd.randrange(len(keys))]])
        try:
            X, _ = build(samp, terms)
            y = [float(yf(r)) for r in samp]
            b, _, _, _ = fit_logit(X, y)
        except Exception:
            continue
        if max(abs(v) for v in b) > 25:
            continue
        draws.append(b)
    return names, draws


def pct(v, q):
    v = sorted(v)
    i = q * (len(v) - 1)
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return v[lo] + (v[hi] - v[lo]) * (i - lo)

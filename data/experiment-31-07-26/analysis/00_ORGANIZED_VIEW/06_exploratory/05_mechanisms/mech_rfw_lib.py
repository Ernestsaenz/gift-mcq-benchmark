"""Independent stdlib logistic regression: Newton-Raphson IRLS + CR1 cluster-robust sandwich.

Written from scratch (does NOT import mech_who_lib) so the replication is genuinely independent.
Methods named at every use site:
  - point estimates: maximum-likelihood logistic regression via Newton-Raphson (IRLS)
  - SEs: Liang-Zeger cluster-robust sandwich with CR1 finite-cluster correction
  - single-coefficient p: Wald z, two-sided standard normal
  - multi-df: joint Wald chi2 on the cluster-robust covariance
  - sensitivity: t(G-1) reference distribution, and non-clustered likelihood-ratio test
"""
import math

# ---------------------------------------------------------------- linear algebra
def solve(A, b):
    n = len(A)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-13:
            raise ValueError("singular")
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        for r in range(n):
            if r == c:
                continue
            f = M[r][c] / pv
            if f != 0.0:
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]


def inv(A):
    n = len(A)
    cols = [solve(A, [1.0 if i == j else 0.0 for i in range(n)]) for j in range(n)]
    return [[cols[j][i] for j in range(n)] for i in range(n)]


# ---------------------------------------------------------------- distributions
def ncdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def chi2_sf(x, k):
    """upper tail of chi2_k via the regularized incomplete gamma Q(k/2, x/2)."""
    if x <= 0:
        return 1.0
    a, xx = k / 2.0, x / 2.0
    if xx < a + 1.0:                       # series for P
        term = 1.0 / a
        s = term
        n = 1
        while n < 10000:
            term *= xx / (a + n)
            s += term
            if abs(term) < abs(s) * 1e-16:
                break
            n += 1
        return max(0.0, min(1.0, 1.0 - s * math.exp(-xx + a * math.log(xx) - math.lgamma(a))))
    # continued fraction for Q (Lentz)
    tiny = 1e-300
    b = xx + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny: d = tiny
        c = b + an / c
        if abs(c) < tiny: c = tiny
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-16:
            break
    return max(0.0, min(1.0, h * math.exp(-xx + a * math.log(xx) - math.lgamma(a))))


def t_sf2(t, df):
    """two-sided tail of Student t via the regularized incomplete beta."""
    x = df / (df + t * t)
    return betainc(df / 2.0, 0.5, x)


def betainc(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(a * math.log(x) + b * math.log(1 - x) - lbeta)
    if x < (a + 1) / (a + b + 2):
        return front * _bcf(a, b, x) / a
    return 1.0 - math.exp(b * math.log(1 - x) + a * math.log(x) - lbeta) * _bcf(b, a, 1 - x) / b


def _bcf(a, b, x):
    tiny = 1e-300
    f, c, d = 1.0, 1.0, 0.0
    for i in range(0, 300):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        if abs(d) < tiny: d = tiny
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < tiny: c = tiny
        f *= c * d
        if abs(1.0 - c * d) < 1e-15:
            break
    return f - 1.0


# ---------------------------------------------------------------- model
def fit(X, y, maxit=300, tol=1e-12):
    n, k = len(X), len(X[0])
    beta = [0.0] * k
    for _ in range(maxit):
        eta = [sum(X[i][j] * beta[j] for j in range(k)) for i in range(n)]
        p = [1.0 / (1.0 + math.exp(-max(-500.0, min(500.0, e)))) for e in eta]
        w = [max(pi * (1 - pi), 1e-12) for pi in p]
        g = [sum(X[i][j] * (y[i] - p[i]) for i in range(n)) for j in range(k)]
        H = [[sum(X[i][a] * w[i] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
        st = solve(H, g)
        beta = [beta[j] + st[j] for j in range(k)]
        if max(abs(s) for s in st) < tol:
            break
    eta = [sum(X[i][j] * beta[j] for j in range(k)) for i in range(n)]
    p = [1.0 / (1.0 + math.exp(-max(-500.0, min(500.0, e)))) for e in eta]
    w = [max(pi * (1 - pi), 1e-12) for pi in p]
    H = [[sum(X[i][a] * w[i] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    bread = inv(H)
    ll = sum(y[i] * math.log(max(p[i], 1e-300)) + (1 - y[i]) * math.log(max(1 - p[i], 1e-300))
             for i in range(n))
    return beta, bread, p, ll, H


def crve(X, y, p, bread, clusters, correction="CR1"):
    n, k = len(X), len(X[0])
    r = [y[i] - p[i] for i in range(n)]
    byc = {}
    for i in range(n):
        byc.setdefault(clusters[i], []).append(i)
    meat = [[0.0] * k for _ in range(k)]
    for idx in byc.values():
        u = [sum(X[i][j] * r[i] for i in idx) for j in range(k)]
        for a in range(k):
            ua = u[a]
            for b in range(k):
                meat[a][b] += ua * u[b]
    G = len(byc)
    corr = (G / (G - 1.0)) * ((n - 1.0) / (n - k)) if correction == "CR1" else 1.0
    tmp = [[sum(bread[a][x] * meat[x][z] for x in range(k)) for z in range(k)] for a in range(k)]
    V = [[corr * sum(tmp[a][z] * bread[z][b] for z in range(k)) for b in range(k)] for a in range(k)]
    return V, G


def table(names, beta, V, G, title="", show=True):
    k = len(beta)
    se = [math.sqrt(max(V[j][j], 0.0)) for j in range(k)]
    rows = []
    if show and title:
        print("  " + title)
    if show:
        print(f"  {'term':<34}{'beta':>9}{'SE':>8}{'OR':>8}{'95% CI (OR)':>22}"
              f"{'z':>7}{'p_z':>10}{'p_t(G-1)':>11}")
    for j in range(k):
        z = beta[j] / se[j] if se[j] > 0 else 0.0
        pz = 2 * (1 - ncdf(abs(z)))
        pt = t_sf2(z, G - 1)
        lo, hi = beta[j] - 1.959963985 * se[j], beta[j] + 1.959963985 * se[j]
        if show:
            print(f"  {names[j]:<34}{beta[j]:>9.3f}{se[j]:>8.3f}{math.exp(beta[j]):>8.3f}"
                  f"{'[%.3f, %.3f]' % (math.exp(lo), math.exp(hi)):>22}{z:>7.2f}{pz:>10.4f}{pt:>11.4f}")
        rows.append(dict(name=names[j], beta=beta[j], se=se[j], z=z, p=pz, pt=pt,
                         lo=math.exp(lo), hi=math.exp(hi), orr=math.exp(beta[j])))
    return rows


def wald(beta, V, idx):
    sub = [[V[a][b] for b in idx] for a in idx]
    bb = [beta[a] for a in idx]
    Vi = inv(sub)
    stat = sum(bb[a] * Vi[a][b] * bb[b] for a in range(len(idx)) for b in range(len(idx)))
    return stat, len(idx), chi2_sf(stat, len(idx))


def run(rows, yf, terms, clusterf=lambda r: r["cluster"], title="", show=True):
    X = [[1.0] + [t[1](r) for t in terms] for r in rows]
    names = ["(intercept)"] + [t[0] for t in terms]
    y = [float(yf(r)) for r in rows]
    cl = [clusterf(r) for r in rows]
    beta, bread, p, ll, H = fit(X, y)
    V, G = crve(X, y, p, bread, cl)
    if show:
        print("=" * 108)
        print(f"{title}   n={len(rows)}  events={int(sum(y))}  clusters={G}")
    res = table(names, beta, V, G, show=show)
    return dict(beta=beta, V=V, names=names, ll=ll, G=G, rows=res, X=X, y=y, cl=cl, p=p)


def zfun(rows, f):
    v = [f(r) for r in rows]
    m = sum(v) / len(v)
    s = math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))
    return lambda r: (f(r) - m) / s

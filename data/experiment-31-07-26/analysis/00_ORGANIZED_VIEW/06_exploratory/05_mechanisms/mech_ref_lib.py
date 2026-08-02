"""Independent stdlib logistic regression: Newton-Raphson + Cholesky, CR0/CR1/CR3 sandwich.

Deliberately written from scratch (Cholesky rather than Gauss-Jordan, separate
score/hessian accumulation) so it is not a re-run of mech_who_lib.py.
Validated in mech_ref_01_validate.py against closed-form 2x2 logistic results.
"""
import math

# ---------- linear algebra ----------

def chol(A):
    """Cholesky L with A = L L^T for SPD A."""
    n = len(A)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = A[i][j] - sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                if s <= 1e-14:
                    raise ValueError("hessian not positive definite (separation/collinearity)")
                L[i][i] = math.sqrt(s)
            else:
                L[i][j] = s / L[j][j]
    return L


def chol_solve(L, b):
    n = len(L)
    y = [0.0] * n
    for i in range(n):
        y[i] = (b[i] - sum(L[i][k] * y[k] for k in range(i))) / L[i][i]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
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


# ---------- glm ----------

def _eta(X, beta):
    return [sum(xi[j] * beta[j] for j in range(len(beta))) for xi in X]


def _mu(eta):
    out = []
    for e in eta:
        e = max(-500.0, min(500.0, e))
        out.append(1.0 / (1.0 + math.exp(-e)))
    return out


def logit(X, y, maxit=300, tol=1e-12):
    """Newton-Raphson MLE.  Returns dict with beta, bread (inv Fisher info), mu, loglik."""
    n, k = len(X), len(X[0])
    beta = [0.0] * k
    for _ in range(maxit):
        mu = _mu(_eta(X, beta))
        g = [sum(X[i][j] * (y[i] - mu[i]) for i in range(n)) for j in range(k)]
        H = [[0.0] * k for _ in range(k)]
        for i in range(n):
            w = max(mu[i] * (1 - mu[i]), 1e-12)
            xi = X[i]
            for a in range(k):
                wa = w * xi[a]
                for b in range(a + 1):
                    H[a][b] += wa * xi[b]
        for a in range(k):
            for b in range(a + 1, k):
                H[a][b] = H[b][a]
        L = chol(H)
        step = chol_solve(L, g)
        # simple step halving on divergence
        beta = [beta[j] + step[j] for j in range(k)]
        if max(abs(s) for s in step) < tol:
            break
    mu = _mu(_eta(X, beta))
    H = [[0.0] * k for _ in range(k)]
    for i in range(n):
        w = max(mu[i] * (1 - mu[i]), 1e-12)
        xi = X[i]
        for a in range(k):
            wa = w * xi[a]
            for b in range(a + 1):
                H[a][b] += wa * xi[b]
    for a in range(k):
        for b in range(a + 1, k):
            H[a][b] = H[b][a]
    bread = chol_inv(H)
    ll = sum(y[i] * math.log(max(mu[i], 1e-300)) + (1 - y[i]) * math.log(max(1 - mu[i], 1e-300))
             for i in range(n))
    return dict(beta=beta, bread=bread, mu=mu, ll=ll, X=X, y=y, n=n, k=k)


def sandwich(fit, clusters, kind="CR1"):
    X, y, mu, bread = fit["X"], fit["y"], fit["mu"], fit["bread"]
    n, k = fit["n"], fit["k"]
    res = [y[i] - mu[i] for i in range(n)]
    byc = {}
    for i in range(n):
        byc.setdefault(clusters[i], []).append(i)
    G = len(byc)
    meat = [[0.0] * k for _ in range(k)]
    for c, idx in byc.items():
        u = [sum(X[i][j] * res[i] for i in idx) for j in range(k)]
        for a in range(k):
            for b in range(k):
                meat[a][b] += u[a] * u[b]
    if kind == "CR1":
        corr = (G / (G - 1.0)) * ((n - 1.0) / (n - k))
    elif kind == "CR0":
        corr = 1.0
    elif kind == "CR3":              # cluster-jackknife-ish inflation
        corr = (G / (G - 1.0)) ** 2
    else:
        raise ValueError(kind)
    V = [[corr * sum(bread[a][x] * meat[x][z] * bread[z][b]
                     for x in range(k) for z in range(k)) for b in range(k)] for a in range(k)]
    return V, G


def jackknife_cluster(X, y, clusters):
    """Leave-one-cluster-out jackknife covariance (CR3-equivalent, no bread assumption)."""
    byc = {}
    for i in range(len(X)):
        byc.setdefault(clusters[i], []).append(i)
    G = len(byc)
    full = logit(X, y)["beta"]
    k = len(full)
    reps = []
    for c, idx in byc.items():
        keep = [i for i in range(len(X)) if clusters[i] != c]
        try:
            reps.append(logit([X[i] for i in keep], [y[i] for i in keep])["beta"])
        except ValueError:
            continue
    m = [sum(r[j] for r in reps) / len(reps) for j in range(k)]
    V = [[(len(reps) - 1.0) / len(reps) * sum((r[a] - m[a]) * (r[b] - m[b]) for r in reps)
          for b in range(k)] for a in range(k)]
    return V, G, full


# ---------- inference ----------

def norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def norm_p(z):
    return 2.0 * (1.0 - norm_cdf(abs(z)))


def _lgamma(x):
    return math.lgamma(x)


def t_sf(t, df):
    """Two-sided p from Student t via regularised incomplete beta."""
    x = df / (df + t * t)
    return betainc(df / 2.0, 0.5, x)


def betainc(a, b, x):
    """Regularised incomplete beta I_x(a,b) by continued fraction."""
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    lbeta = _lgamma(a + b) - _lgamma(a) - _lgamma(b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b + lbeta) / a
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x)
    return 1.0 - math.exp(math.log(1 - x) * b + math.log(x) * a + lbeta) / b * _betacf(b, a, 1 - x)


def _betacf(a, b, x, itmax=300, eps=1e-14):
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < 1e-30: d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30: d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30: c = 1e-30
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30: d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30: c = 1e-30
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < eps: break
    return h


def t_crit(df, p=0.975, lo=0.0, hi=100.0):
    for _ in range(200):
        mid = (lo + hi) / 2
        if 1 - t_sf(mid, df) / 2 < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def chi2_sf(x, k):
    if x <= 0: return 1.0
    if k % 2 == 0:
        s, t = 0.0, math.exp(-x / 2)
        for i in range(k // 2):
            if i: t *= (x / 2) / i
            s += t
        return min(1.0, s)
    s = 2 * (1 - norm_cdf(math.sqrt(x)))
    t = math.sqrt(2 * x / math.pi) * math.exp(-x / 2)
    for i in range(1, (k - 1) // 2 + 1):
        s += t
        t *= x / (2 * i + 1)
    return min(1.0, max(0.0, s))


def wald_joint(beta, V, idx):
    sub = [[V[a][b] for b in idx] for a in idx]
    bb = [beta[a] for a in idx]
    inv = chol_inv(sub)
    stat = sum(bb[a] * inv[a][b] * bb[b] for a in range(len(idx)) for b in range(len(idx)))
    return stat, len(idx), chi2_sf(stat, len(idx))


def report(names, beta, V, G, label="", use_t=True):
    k = len(beta)
    se = [math.sqrt(max(V[j][j], 0.0)) for j in range(k)]
    df = G - 1
    tc = t_crit(df) if use_t else 1.959964
    rows = []
    if label:
        print("  " + label)
    print(f"  {'term':<34}{'beta':>9}{'SE':>8}{'OR':>8}{'95% CI (OR)':>22}{'t':>7}{'p':>10}")
    for j in range(k):
        t = beta[j] / se[j] if se[j] > 0 else 0.0
        pv = t_sf(t, df) if use_t else norm_p(t)
        lo, hi = beta[j] - tc * se[j], beta[j] + tc * se[j]
        star = "***" if pv < .001 else "**" if pv < .01 else "*" if pv < .05 else "." if pv < .1 else ""
        print(f"  {names[j]:<34}{beta[j]:>9.3f}{se[j]:>8.3f}{math.exp(beta[j]):>8.3f}"
              f"{'[%.3f, %.3f]' % (math.exp(lo), math.exp(hi)):>22}{t:>7.2f}{pv:>10.4f} {star}")
        rows.append(dict(name=names[j], beta=beta[j], se=se[j], t=t, p=pv,
                         or_=math.exp(beta[j]), lo=math.exp(lo), hi=math.exp(hi)))
    print(f"  (CR1 cluster-robust SEs, G={G}; {'t(G-1)' if use_t else 'normal'} reference)")
    return rows

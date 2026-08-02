"""Pure-stdlib logistic regression (IRLS) with cluster-robust sandwich SEs."""
import math

def _solve(A, b):
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-12: raise ValueError("singular design matrix")
        M[c], M[p] = M[p], M[c]
        pv = M[c][c]
        for r in range(n):
            if r == c: continue
            f = M[r][c] / pv
            if f:
                for k in range(c, n + 1): M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]

def _inv(A):
    n = len(A)
    cols = []
    for j in range(n):
        e = [1.0 if i == j else 0.0 for i in range(n)]
        cols.append(_solve(A, e))
    return [[cols[j][i] for j in range(n)] for i in range(n)]

def logit_fit(X, y, maxit=200, tol=1e-11, ridge=0.0):
    n, k = len(X), len(X[0])
    beta = [0.0] * k
    for _ in range(maxit):
        eta = [sum(X[i][j] * beta[j] for j in range(k)) for i in range(n)]
        p = [1 / (1 + math.exp(-max(-500, min(500, e)))) for e in eta]
        w = [max(pi * (1 - pi), 1e-10) for pi in p]
        g = [sum(X[i][j] * (y[i] - p[i]) for i in range(n)) - ridge * beta[j] for j in range(k)]
        H = [[sum(X[i][a] * w[i] * X[i][b] for i in range(n)) + (ridge if a == b else 0.0)
              for b in range(k)] for a in range(k)]
        step = _solve(H, g)
        beta = [beta[j] + step[j] for j in range(k)]
        if max(abs(s) for s in step) < tol: break
    eta = [sum(X[i][j] * beta[j] for j in range(k)) for i in range(n)]
    p = [1 / (1 + math.exp(-max(-500, min(500, e)))) for e in eta]
    w = [max(pi * (1 - pi), 1e-10) for pi in p]
    H = [[sum(X[i][a] * w[i] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    bread = _inv(H)
    ll = sum(y[i] * math.log(max(p[i], 1e-300)) + (1 - y[i]) * math.log(max(1 - p[i], 1e-300))
             for i in range(n))
    return beta, bread, p, ll

def cluster_robust(X, y, p, bread, clusters):
    n, k = len(X), len(X[0])
    res = [y[i] - p[i] for i in range(n)]
    byc = {}
    for i in range(n): byc.setdefault(clusters[i], []).append(i)
    meat = [[0.0] * k for _ in range(k)]
    for c, idx in byc.items():
        u = [sum(X[i][j] * res[i] for i in idx) for j in range(k)]
        for a in range(k):
            for b in range(k): meat[a][b] += u[a] * u[b]
    G = len(byc)
    corr = (G / (G - 1)) * ((n - 1) / (n - k))          # CR1 small-sample correction
    V = [[corr * sum(bread[a][x] * meat[x][z] * bread[z][b] for x in range(k) for z in range(k))
          for b in range(k)] for a in range(k)]
    return V, G

def _norm_cdf(z): return 0.5 * (1 + math.erf(z / math.sqrt(2)))

def report(names, beta, V, G, label=""):
    k = len(beta)
    se = [math.sqrt(max(V[j][j], 0)) for j in range(k)]
    # t(G-1) reference distribution for cluster-robust inference
    df = G - 1
    out = []
    print(f"\n  {label}")
    print(f"  {'term':<30}{'beta':>9}{'SE':>8}{'OR':>8}{'95% CI (OR)':>22}{'z':>7}{'p':>10}")
    for j in range(k):
        z = beta[j] / se[j] if se[j] > 0 else 0.0
        pv = 2 * (1 - _norm_cdf(abs(z)))
        lo, hi = beta[j] - 1.96 * se[j], beta[j] + 1.96 * se[j]
        star = "***" if pv < .001 else "**" if pv < .01 else "*" if pv < .05 else "." if pv < .1 else ""
        print(f"  {names[j]:<30}{beta[j]:>9.3f}{se[j]:>8.3f}{math.exp(beta[j]):>8.3f}"
              f"{'[%.3f, %.3f]' % (math.exp(lo), math.exp(hi)):>22}{z:>7.2f}{pv:>10.4f} {star}")
        out.append((names[j], beta[j], se[j], z, pv))
    print(f"  (cluster-robust CR1 SEs, G={G} clusters; Wald z, two-sided normal p)")
    return out

def wald_joint(beta, V, idx):
    """joint Wald chi2 test that the coefficients in idx are all zero"""
    sub = [[V[a][b] for b in idx] for a in idx]
    bb = [beta[a] for a in idx]
    inv = _inv(sub)
    stat = sum(bb[a] * inv[a][b] * bb[b] for a in range(len(idx)) for b in range(len(idx)))
    df = len(idx)
    return stat, df, _chi2_sf(stat, df)

def _chi2_sf(x, k):
    if x <= 0: return 1.0
    if k % 2 == 0:
        s, t = 0.0, math.exp(-x / 2)
        for i in range(k // 2):
            if i: t *= (x / 2) / i
            s += t
        return min(1.0, s)
    s = 2 * (1 - _norm_cdf(math.sqrt(x)))
    t = math.sqrt(2 * x / math.pi) * math.exp(-x / 2)
    for i in range(1, (k - 1) // 2 + 1):
        s += t
        t *= x / (2 * i + 1)
    return min(1.0, max(0.0, s))

def lrt(ll_full, ll_red, dfd):
    stat = 2 * (ll_full - ll_red)
    return stat, dfd, _chi2_sf(stat, dfd)

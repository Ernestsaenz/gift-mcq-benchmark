"""Pure-stdlib linear algebra + sparse IRLS logistic regression.

No numpy/scipy. Design matrices are stored as sparse rows: list of [(col, val), ...].
"""
import math


# ---------------------------------------------------------------- dense linalg
def chol(A):
    """Cholesky A = L L'. A is list of lists (symmetric positive definite)."""
    n = len(A)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = A[i][j]
            Li = L[i]
            Lj = L[j]
            for k in range(j):
                s -= Li[k] * Lj[k]
            if i == j:
                if s <= 0.0:
                    raise ValueError("not positive definite at %d (pivot %g)" % (i, s))
                L[i][j] = math.sqrt(s)
            else:
                L[i][j] = s / L[j][j]
    return L


def chol_solve(L, b):
    n = len(L)
    y = [0.0] * n
    for i in range(n):
        s = b[i]
        Li = L[i]
        for k in range(i):
            s -= Li[k] * y[k]
        y[i] = s / Li[i]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = y[i]
        for k in range(i + 1, n):
            s -= L[k][i] * x[k]
        x[i] = s / L[i][i]
    return x


def chol_inv(L):
    """Inverse of A given its Cholesky factor L."""
    n = len(L)
    cols = []
    for j in range(n):
        e = [0.0] * n
        e[j] = 1.0
        cols.append(chol_solve(L, e))
    # cols[j] is column j of A^{-1}
    return [[cols[j][i] for j in range(n)] for i in range(n)]


def matmul(A, B):
    n, m, p = len(A), len(B), len(B[0])
    C = [[0.0] * p for _ in range(n)]
    for i in range(n):
        Ai = A[i]
        Ci = C[i]
        for k in range(m):
            a = Ai[k]
            if a == 0.0:
                continue
            Bk = B[k]
            for j in range(p):
                Ci[j] += a * Bk[j]
    return C


def quad_form(v, M):
    """v' M v"""
    n = len(v)
    s = 0.0
    for i in range(n):
        if v[i] == 0.0:
            continue
        Mi = M[i]
        acc = 0.0
        for j in range(n):
            acc += Mi[j] * v[j]
        s += v[i] * acc
    return s


def solve_sym(M, b):
    """Solve M x = b for symmetric M (used for Wald chi-sq)."""
    return chol_solve(chol(M), b)


# ------------------------------------------------------------------ sparse GLM
def sparse_dot(row, beta):
    s = 0.0
    for c, v in row:
        s += beta[c] * v
    return s


def irls_logit(X, y, ncol, maxit=200, tol=1e-11, ridge=0.0):
    """Fisher-scoring / IRLS for binomial logit.

    X: sparse rows. y: 0/1 list. Returns dict with beta, converged flag,
    loglik, XtWX (dense ncol x ncol), fitted p.

    Update: (X'WX) delta = X'(y - p);  beta <- beta + delta,
    W = diag(p(1-p)). Equivalent to Newton-Raphson (canonical link => observed
    == expected information).
    """
    n = len(y)
    beta = [0.0] * ncol
    # sensible start: intercept at overall log-odds if col 0 is the intercept
    ybar = sum(y) / n
    ybar = min(max(ybar, 1e-6), 1 - 1e-6)
    beta[0] = math.log(ybar / (1 - ybar))

    converged = False
    for it in range(maxit):
        XtWX = [[0.0] * ncol for _ in range(ncol)]
        grad = [0.0] * ncol
        p = [0.0] * n
        for i in range(n):
            row = X[i]
            eta = sparse_dot(row, beta)
            if eta > 500:
                eta = 500.0
            elif eta < -500:
                eta = -500.0
            pi_ = 1.0 / (1.0 + math.exp(-eta))
            p[i] = pi_
            w = pi_ * (1.0 - pi_)
            if w < 1e-12:
                w = 1e-12
            r = y[i] - pi_
            for c, v in row:
                grad[c] += v * r
                wv = w * v
                Xc = XtWX[c]
                for c2, v2 in row:
                    Xc[c2] += wv * v2
        if ridge > 0.0:
            for c in range(ncol):
                XtWX[c][c] += ridge
        L = chol(XtWX)
        delta = chol_solve(L, grad)
        step = 1.0
        # simple step halving guard
        for _ in range(30):
            newbeta = [beta[c] + step * delta[c] for c in range(ncol)]
            if max(abs(b) for b in newbeta) < 1e4:
                break
            step *= 0.5
        beta = newbeta
        if max(abs(d) for d in delta) < tol:
            converged = True
            break

    # final quantities at converged beta
    XtWX = [[0.0] * ncol for _ in range(ncol)]
    p = [0.0] * n
    ll = 0.0
    for i in range(n):
        row = X[i]
        eta = sparse_dot(row, beta)
        eta = max(-500.0, min(500.0, eta))
        pi_ = 1.0 / (1.0 + math.exp(-eta))
        p[i] = pi_
        eps = 1e-15
        ll += y[i] * math.log(max(pi_, eps)) + (1 - y[i]) * math.log(max(1 - pi_, eps))
        w = max(pi_ * (1.0 - pi_), 1e-12)
        for c, v in row:
            wv = w * v
            Xc = XtWX[c]
            for c2, v2 in row:
                Xc[c2] += wv * v2
    if ridge > 0.0:
        for c in range(ncol):
            XtWX[c][c] += ridge
    return {
        "beta": beta, "converged": converged, "iters": it + 1,
        "loglik": ll, "XtWX": XtWX, "p": p, "n": n, "ncol": ncol,
    }


def model_based_vcov(fit):
    return chol_inv(chol(fit["XtWX"]))


def cluster_robust_vcov(fit, X, y, cluster_ids, correct=True):
    """CR1 sandwich: bread * meat * bread.

    bread = (X'WX)^{-1}
    meat  = sum_g (sum_{i in g} x_i (y_i - p_i)) (same)'
    finite-sample factor c = G/(G-1) * (N-1)/(N-k)
    """
    ncol = fit["ncol"]
    bread = chol_inv(chol(fit["XtWX"]))
    p = fit["p"]
    groups = {}
    for i, g in enumerate(cluster_ids):
        s = groups.get(g)
        if s is None:
            s = [0.0] * ncol
            groups[g] = s
        r = y[i] - p[i]
        for c, v in X[i]:
            s[c] += v * r
    meat = [[0.0] * ncol for _ in range(ncol)]
    for s in groups.values():
        for a in range(ncol):
            if s[a] == 0.0:
                continue
            Ma = meat[a]
            sa = s[a]
            for b in range(ncol):
                Ma[b] += sa * s[b]
    G = len(groups)
    N = fit["n"]
    if correct:
        c = (G / (G - 1.0)) * ((N - 1.0) / (N - ncol))
        for a in range(ncol):
            for b in range(ncol):
                meat[a][b] *= c
    V = matmul(matmul(bread, meat), bread)
    # symmetrise
    for a in range(ncol):
        for b in range(a + 1, ncol):
            m = 0.5 * (V[a][b] + V[b][a])
            V[a][b] = V[b][a] = m
    return V, G


# -------------------------------------------------------- normal / chi-sq tail
def norm_cdf(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def two_sided_z_p(z):
    return math.erfc(abs(z) / math.sqrt(2.0))


def chisq_sf(x, k):
    """Upper tail of chi-square with k df (k integer >= 1)."""
    if x <= 0:
        return 1.0
    return gammaincc(k / 2.0, x / 2.0)


def gammaincc(a, x):
    """Regularised upper incomplete gamma Q(a,x), Numerical-Recipes style."""
    if x < 0 or a <= 0:
        raise ValueError
    if x < a + 1.0:
        # series for P(a,x)
        ap = a
        s = 1.0 / a
        d = s
        for _ in range(10000):
            ap += 1.0
            d *= x / ap
            s += d
            if abs(d) < abs(s) * 1e-16:
                break
        return 1.0 - s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    # continued fraction for Q(a,x)
    FPMIN = 1e-300
    b = x + 1.0 - a
    c = 1.0 / FPMIN
    d = 1.0 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < FPMIN:
            d = FPMIN
        c = b + an / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-16:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


# ------------------------------------------------- Gauss-Hermite quadrature
def gauss_hermite(n):
    """Nodes/weights for int e^{-x^2} f(x) dx ~ sum w_i f(x_i).

    Newton iteration on the physicists' Hermite polynomial via the normalised
    three-term recurrence (Numerical Recipes `gauher`).
    """
    x = [0.0] * n
    w = [0.0] * n
    m = (n + 1) // 2
    PIM4 = 1.0 / math.pi ** 0.25
    z = 0.0
    pp = 0.0
    for i in range(1, m + 1):
        if i == 1:
            z = math.sqrt(2.0 * n + 1.0) - 1.85575 * (2.0 * n + 1.0) ** (-0.16667)
        elif i == 2:
            z -= 1.14 * n ** 0.426 / z
        elif i == 3:
            z = 1.86 * z - 0.86 * x[0]
        elif i == 4:
            z = 1.91 * z - 0.91 * x[1]
        else:
            z = 2.0 * z - x[i - 3]
        for _ in range(100):
            p1 = PIM4
            p2 = 0.0
            for j in range(1, n + 1):
                p3 = p2
                p2 = p1
                p1 = z * math.sqrt(2.0 / j) * p2 - math.sqrt((j - 1.0) / j) * p3
            pp = math.sqrt(2.0 * n) * p2
            z1 = z
            z = z1 - p1 / pp
            if abs(z - z1) <= 1e-14:
                break
        x[i - 1] = z
        x[n - i] = -z
        w[i - 1] = 2.0 / (pp * pp)
        w[n - i] = w[i - 1]
    return x, w

"""Pure-stdlib helpers for the NOTA-acceptance refutation. No numpy/scipy."""
import json, math, collections, random

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"


def load():
    return [r for r in json.load(open(PATH)) if r["analysis_include"]]


# ---------- Fisher exact, two-sided, point-probability (Irwin) method ----------
def _lchoose(n, k):
    if k < 0 or k > n:
        return float("-inf")
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def hypergeom_pmf(k, n1, n2, t):
    """P(X=k) for X ~ Hypergeom: n1 in group1, n2 in group2, t total successes."""
    return math.exp(_lchoose(n1, k) + _lchoose(n2, t - k) - _lchoose(n1 + n2, t))


def fisher_exact_two_sided(a, b, c, d):
    """2x2 = [[a,b],[c,d]]. Two-sided p by summing all tables with
    pmf <= pmf(observed)*(1+1e-9)  (point-probability / Irwin method)."""
    n1, n2 = a + b, c + d
    t = a + c
    lo, hi = max(0, t - n2), min(n1, t)
    p_obs = hypergeom_pmf(a, n1, n2, t)
    tol = p_obs * (1 + 1e-9)
    p = 0.0
    for k in range(lo, hi + 1):
        pk = hypergeom_pmf(k, n1, n2, t)
        if pk <= tol:
            p += pk
    return min(1.0, p)


def odds_ratio(a, b, c, d):
    if b == 0 or c == 0:
        return float("inf") if a * d > 0 else float("nan")
    return (a * d) / (b * c)


# ---------- Mantel-Haenszel with Robins-Breslow-Greenland variance ----------
def mantel_haenszel(tables):
    """tables: list of (a,b,c,d) per stratum, rows = exposure, cols = outcome.
    a = exposed & outcome+, b = exposed & outcome-, c = unexposed & outcome+, d = unexposed & outcome-
    Returns dict with OR_MH, log-OR, SE (RBG), CI, z, p, n informative strata."""
    R = S = 0.0
    PR = PS_QR = QS = 0.0
    n_inf = 0
    for (a, b, c, d) in tables:
        n = a + b + c + d
        if n == 0:
            continue
        Ri = a * d / n
        Si = b * c / n
        if Ri > 0 or Si > 0:
            n_inf += 1
        R += Ri
        S += Si
        P = (a + d) / n
        Q = (b + c) / n
        PR += P * Ri
        PS_QR += P * Si + Q * Ri
        QS += Q * Si
    if R == 0 or S == 0:
        return None
    or_mh = R / S
    var = PR / (2 * R * R) + PS_QR / (2 * R * S) + QS / (2 * S * S)
    se = math.sqrt(var)
    lo = math.exp(math.log(or_mh) - 1.959963985 * se)
    hi = math.exp(math.log(or_mh) + 1.959963985 * se)
    z = math.log(or_mh) / se
    p = 2 * (1 - norm_cdf(abs(z)))
    return dict(or_mh=or_mh, log_or=math.log(or_mh), se=se, ci=(lo, hi), z=z, p=p,
                n_informative=n_inf, R=R, S=S)


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# ---------- conditional logistic regression (exact, small strata) ----------
def _subsets_sum(xs, k):
    """yield sums of linear predictors over all size-k subsets of xs (list of floats)."""
    n = len(xs)
    idx = list(range(n))
    out = []

    def rec(start, chosen, acc):
        if len(chosen) == k:
            out.append(acc)
            return
        for i in range(start, n):
            if n - i < k - len(chosen):
                break
            rec(i + 1, chosen + [i], acc + xs[i])
    rec(0, [], 0.0)
    return out


def clogit(strata, maxit=200, tol=1e-10):
    """strata: list of (X, y) where X is list of covariate-vectors (list of float),
    y is list of 0/1. Conditional likelihood, exact enumeration (strata are tiny).
    Returns beta, se, z, p, loglik."""
    # keep informative strata only
    use = [(X, y) for (X, y) in strata if 0 < sum(y) < len(y)]
    if not use:
        return None
    p = len(use[0][0][0])
    beta = [0.0] * p

    def eval_ll(beta):
        ll = 0.0
        grad = [0.0] * p
        hess = [[0.0] * p for _ in range(p)]
        for (X, y) in use:
            k = sum(y)
            n = len(y)
            eta = [sum(b * x for b, x in zip(beta, xi)) for xi in X]
            # numerator
            num = sum(e for e, yy in zip(eta, y) if yy)
            xnum = [sum(xi[j] for xi, yy in zip(X, y) if yy) for j in range(p)]
            # denominator: enumerate subsets of size k
            idx = list(range(n))
            terms = []
            def rec(start, chosen):
                if len(chosen) == k:
                    terms.append(tuple(chosen))
                    return
                for i in range(start, n):
                    if n - i < k - len(chosen):
                        break
                    rec(i + 1, chosen + [i])
            rec(0, [])
            m = max(sum(eta[i] for i in t) for t in terms)
            ws = []
            for t in terms:
                ws.append(math.exp(sum(eta[i] for i in t) - m))
            W = sum(ws)
            ll += num - (m + math.log(W))
            # E[x] and E[xx']
            Ex = [0.0] * p
            Exx = [[0.0] * p for _ in range(p)]
            for t, w in zip(terms, ws):
                xt = [sum(X[i][j] for i in t) for j in range(p)]
                for j in range(p):
                    Ex[j] += w * xt[j]
                    for l in range(p):
                        Exx[j][l] += w * xt[j] * xt[l]
            for j in range(p):
                Ex[j] /= W
                for l in range(p):
                    Exx[j][l] /= W
            for j in range(p):
                grad[j] += xnum[j] - Ex[j]
                for l in range(p):
                    hess[j][l] -= (Exx[j][l] - Ex[j] * Ex[l])
        return ll, grad, hess

    for _ in range(maxit):
        ll, g, H = eval_ll(beta)
        # solve H delta = -g  -> delta = -H^-1 g
        Hi = invert(H)
        if Hi is None:
            return None
        delta = [-sum(Hi[j][l] * g[l] for l in range(p)) for j in range(p)]
        step = 1.0
        newbeta = [b + step * dl for b, dl in zip(beta, delta)]
        if max(abs(x) for x in delta) < tol:
            beta = newbeta
            break
        beta = newbeta
    ll, g, H = eval_ll(beta)
    Hi = invert([[-h for h in row] for row in H])  # observed information = -H
    se = [math.sqrt(Hi[j][j]) for j in range(p)]
    z = [b / s for b, s in zip(beta, se)]
    pv = [2 * (1 - norm_cdf(abs(zz))) for zz in z]
    return dict(beta=beta, se=se, z=z, p=pv, loglik=ll, n_strata=len(use))


def invert(M):
    n = len(M)
    A = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(M)]
    for i in range(n):
        piv = max(range(i, n), key=lambda r: abs(A[r][i]))
        if abs(A[piv][i]) < 1e-14:
            return None
        A[i], A[piv] = A[piv], A[i]
        pv = A[i][i]
        A[i] = [x / pv for x in A[i]]
        for r in range(n):
            if r != i and A[r][i] != 0:
                f = A[r][i]
                A[r] = [x - f * y for x, y in zip(A[r], A[i])]
    return [row[n:] for row in A]

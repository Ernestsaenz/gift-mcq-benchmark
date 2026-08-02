"""Extra pure-stdlib helpers for the effort-and-difficulty analysis.

Everything implemented from scratch (no numpy/scipy).  Methods are named
explicitly wherever a p-value or interval is produced.
"""
import json, math, random
from collections import defaultdict

P = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
     "experiment-31-07-26/analysis/paired_clean.json")

MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
SHORT = {"google/gemini-3.6-flash": "gemini-3.6-flash",
         "google/gemma-4-26b-a4b-it": "gemma-4-26b",
         "qwen/qwen3.6-35b-a3b": "qwen3.6-35b",
         "z-ai/glm-5.2": "glm-5.2"}


def load():
    return [r for r in json.load(open(P)) if r.get("analysis_include") is True]


# ------------------------------------------------------------- basic moments
def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return float("nan")
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def quantile(xs, q):
    """Type-7 (R/Excel default) quantile."""
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return float("nan")
    if n == 1:
        return s[0]
    h = (n - 1) * q
    lo = int(math.floor(h))
    hi = min(lo + 1, n - 1)
    return s[lo] + (h - lo) * (s[hi] - s[lo])


def sd(xs):
    n = len(xs)
    if n < 2:
        return float("nan")
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


# ---------------------------------------------------------------- normal tail
def norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def two_sided_z_p(z):
    return math.erfc(abs(z) / math.sqrt(2.0))


# --------------------------------------------------------- Student t two-tail
def _betacf(a, b, x, itmax=300, eps=3e-16, fpmin=1e-300):
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        dl = d * c
        h *= dl
        if abs(dl - 1.0) < eps:
            break
    return h


def betai(a, b, x):
    """Regularised incomplete beta I_x(a,b) (Numerical Recipes continued fraction)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                  + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_sf2(t, df):
    """Two-sided p-value for Student t: P(|T| > |t|) = I_{df/(df+t^2)}(df/2, 1/2)."""
    if df <= 0:
        return float("nan")
    return betai(df / 2.0, 0.5, df / (df + t * t))


# ------------------------------------------------------------- correlations
def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = mean(xs), mean(ys)
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    if sxx <= 0 or syy <= 0:
        return float("nan")
    return sxy / math.sqrt(sxx * syy)


def rank_avg(xs):
    """Average (midrank) ranks, 1-based."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = r
        i = j + 1
    return ranks


def spearman(xs, ys):
    return pearson(rank_avg(xs), rank_avg(ys))


# ------------------------------------------------- logistic regression (MLE)
def logistic_fit(X, y, ridge=1e-8, itmax=200, tol=1e-10):
    """Newton-Raphson / IRLS MLE for logistic regression.

    X: list of rows WITHOUT intercept (intercept is prepended here).
    Returns (beta, se) with se from the inverse observed Fisher information.
    A tiny ridge (1e-8) is added to the Hessian diagonal only for numerical
    stability; it does not materially move the estimates.
    """
    n = len(y)
    p = len(X[0]) + 1
    Xd = [[1.0] + list(row) for row in X]
    beta = [0.0] * p
    for _ in range(itmax):
        # gradient and Hessian
        g = [0.0] * p
        H = [[0.0] * p for _ in range(p)]
        for i in range(n):
            eta = sum(beta[k] * Xd[i][k] for k in range(p))
            eta = max(-30.0, min(30.0, eta))
            mu = 1.0 / (1.0 + math.exp(-eta))
            w = mu * (1.0 - mu)
            r = y[i] - mu
            for k in range(p):
                g[k] += Xd[i][k] * r
                for l in range(k, p):
                    H[k][l] += w * Xd[i][k] * Xd[i][l]
        for k in range(p):
            H[k][k] += ridge
            for l in range(k):
                H[k][l] = H[l][k]
        try:
            Hi = mat_inv(H)
        except ZeroDivisionError:
            return None, None
        step = [sum(Hi[k][l] * g[l] for l in range(p)) for k in range(p)]
        beta = [beta[k] + step[k] for k in range(p)]
        if max(abs(s) for s in step) < tol:
            break
    se = [math.sqrt(max(Hi[k][k], 0.0)) for k in range(p)]
    return beta, se


def mat_inv(M):
    """Gauss-Jordan inversion with partial pivoting."""
    n = len(M)
    A = [list(M[i]) + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(A[r][c]))
        if abs(A[piv][c]) < 1e-300:
            raise ZeroDivisionError("singular")
        A[c], A[piv] = A[piv], A[c]
        pv = A[c][c]
        A[c] = [v / pv for v in A[c]]
        for r in range(n):
            if r != c and A[r][c] != 0.0:
                f = A[r][c]
                A[r] = [a - f * b for a, b in zip(A[r], A[c])]
    return [row[n:] for row in A]


# ------------------------------------------------------- cluster bootstrap
def cluster_bootstrap(rows, stat_fn, B=4000, seed=20260731, cluster_key="cluster"):
    """Nonparametric cluster bootstrap: resample CLUSTERS with replacement
    (whole clusters, keeping all their cells) and recompute stat_fn.

    Returns (point_estimate, lo2.5, hi97.5, list_of_replicates).
    Percentile interval.
    """
    rng = random.Random(seed)
    by = defaultdict(list)
    for r in rows:
        by[r[cluster_key]].append(r)
    keys = list(by.keys())
    K = len(keys)
    point = stat_fn(rows)
    reps = []
    for _ in range(B):
        samp = []
        for _ in range(K):
            samp.extend(by[keys[rng.randrange(K)]])
        v = stat_fn(samp)
        if v is not None and v == v:
            reps.append(v)
    reps.sort()
    return point, quantile(reps, 0.025), quantile(reps, 0.975), reps


def boot_p_two_sided(reps, null=0.0):
    """Two-sided bootstrap p: 2*min(frac(reps<=null), frac(reps>=null)),
    with the usual +1/(B+1) continuity correction, capped at 1."""
    B = len(reps)
    lo = (sum(1 for v in reps if v <= null) + 1) / (B + 1)
    hi = (sum(1 for v in reps if v >= null) + 1) / (B + 1)
    return min(1.0, 2.0 * min(lo, hi))


# --------------------------------------------- Clopper-Pearson (vendored)
def cp_ci(k, n, alpha=0.05):
    """Exact Clopper-Pearson binomial CI by bisection on the exact binomial
    tails (own implementation -- stats_lib.py is being edited concurrently by
    other agents in this session, so it is not depended on here).

    lower = p solving P(X >= k | p) = alpha/2   (increasing in p)
    upper = p solving P(X <= k | p) = alpha/2   (decreasing in p)

    NOTE: descriptive only.  With cells nested in 208 clusters these exact
    intervals undercover; the cluster bootstrap is the inferential instrument.
    """
    if n == 0:
        return (0.0, 1.0)

    def upper_tail(p):   # P(X >= k)
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))

    def lower_tail(p):   # P(X <= k)
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, k + 1))

    if k == 0:
        lo = 0.0
    else:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = (a + b) / 2
            if upper_tail(m) < alpha / 2:
                a = m           # tail too small -> need LARGER p
            else:
                b = m
        lo = (a + b) / 2
    if k == n:
        hi = 1.0
    else:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = (a + b) / 2
            if lower_tail(m) < alpha / 2:
                b = m           # tail too small -> need SMALLER p
            else:
                a = m
        hi = (a + b) / 2
    return (lo, hi)

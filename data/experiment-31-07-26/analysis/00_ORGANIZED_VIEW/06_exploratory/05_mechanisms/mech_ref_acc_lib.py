"""Independent stdlib stats for refuting the nota-acceptance claim.

Clopper-Pearson implemented from the Beta-quantile identity (NOT bisection on
binomial tails), so it is a genuinely independent check of mech_nota_lib.cp_ci:
    lo = BetaInv(alpha/2; k, n-k+1),  hi = BetaInv(1-alpha/2; k+1, n-k)
Regularised incomplete beta via the Lentz continued fraction.
"""
import json, math, random, sqlite3

DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"
PAIRED = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
LETTERS = ["a", "b", "c", "d"]


# ---------------- incomplete beta ----------------
def _betacf(a, b, x):
    TINY, EPS = 1e-30, 3e-16
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < TINY:
        d = TINY
    d = 1.0 / d
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < TINY:
            d = TINY
        c = 1.0 + aa / c
        if abs(c) < TINY:
            c = TINY
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < TINY:
            d = TINY
        c = 1.0 + aa / c
        if abs(c) < TINY:
            c = TINY
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS:
            break
    return h


def betainc(a, b, x):
    """Regularised incomplete beta I_x(a,b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
             + a * math.log(x) + b * math.log1p(-x))
    front = math.exp(lbeta)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                          + b * math.log1p(-x) + a * math.log(x)) * _betacf(b, a, 1.0 - x) / b


def betainv(p, a, b):
    """Inverse of I_x(a,b) by bisection on a monotone increasing function."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if betainc(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def cp_ci(k, n, alpha=0.05):
    """Clopper-Pearson exact CI via Beta quantiles (independent of tail bisection)."""
    if n == 0:
        return (0.0, 1.0)
    lo = 0.0 if k == 0 else betainv(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else betainv(1 - alpha / 2, k + 1, n - k)
    return (lo, hi)


# ---------------- exact binomial helpers ----------------
def log_binom_pmf(i, n, p):
    if p <= 0.0:
        return 0.0 if i == 0 else float("-inf")
    if p >= 1.0:
        return 0.0 if i == n else float("-inf")
    return (math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
            + i * math.log(p) + (n - i) * math.log1p(-p))


def binom_pmf(i, n, p):
    lg = log_binom_pmf(i, n, p)
    return 0.0 if lg == float("-inf") else math.exp(lg)


def mcnemar_exact(b, c):
    """Exact two-sided McNemar (binomial sign test on discordant pairs)."""
    n = b + c
    if n == 0:
        return 1.0
    lo = min(b, c)
    return min(1.0, 2 * sum(binom_pmf(i, n, 0.5) for i in range(lo + 1)))


def binom_test_exact(k, n, p0):
    """Exact two-sided binomial test, method of small p-values."""
    if n == 0:
        return 1.0
    obs = binom_pmf(k, n, p0)
    return min(1.0, sum(binom_pmf(i, n, p0) for i in range(n + 1)
                        if binom_pmf(i, n, p0) <= obs * (1 + 1e-9)))


def fisher_2x2(a, b, c, d):
    n = a + b + c + d
    r1, c1 = a + b, a + c

    def lc(nn, kk):
        return math.lgamma(nn + 1) - math.lgamma(kk + 1) - math.lgamma(nn - kk + 1)

    def p(x):
        return math.exp(lc(r1, x) + lc(n - r1, c1 - x) - lc(n, c1))

    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    p0 = p(a)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= p0 * (1 + 1e-7)))


def chisq_sf(x2, df):
    if x2 <= 0:
        return 1.0
    if df == 1:
        return math.erfc(math.sqrt(x2 / 2.0))
    if df % 2 == 0:
        s = term = math.exp(-x2 / 2.0)
        for i in range(1, df // 2):
            term *= (x2 / 2.0) / i
            s += term
        return min(1.0, s)
    s = math.erfc(math.sqrt(x2 / 2.0))
    term = math.sqrt(2.0 * x2 / math.pi) * math.exp(-x2 / 2.0)
    s += term
    for i in range(1, (df - 1) // 2):
        term *= x2 / (2.0 * i + 1.0)
        s += term
    return min(1.0, s)


def cochran_armitage(rows):
    """Cochran-Armitage trend test. rows = [(score, n_success, n_total), ...].
    Returns (z, two-sided p) using the normal approximation."""
    N = sum(t for _, _, t in rows)
    S = sum(s for _, s, _ in rows)
    if N == 0 or S in (0, N):
        return 0.0, 1.0
    pbar = S / N
    xbar = sum(x * t for x, _, t in rows) / N
    num = sum((x - xbar) * (s - pbar * t) for x, s, t in rows)
    den = pbar * (1 - pbar) * sum(t * (x - xbar) ** 2 for x, _, t in rows)
    if den <= 0:
        return 0.0, 1.0
    z = num / math.sqrt(den)
    return z, math.erfc(abs(z) / math.sqrt(2))


def cluster_boot_ci(units, stat, B=8000, seed=11, alpha=0.05):
    """Percentile cluster bootstrap. units = list of lists of records."""
    rng = random.Random(seed)
    n = len(units)
    out = []
    for _ in range(B):
        samp = []
        for _ in range(n):
            samp.extend(units[rng.randrange(n)])
        v = stat(samp)
        if v is not None:
            out.append(v)
    out.sort()
    if not out:
        return (float("nan"), float("nan"))
    return (out[int(alpha / 2 * len(out))], out[min(len(out) - 1, int((1 - alpha / 2) * len(out)))])


# ---------------- data ----------------
def load_cells():
    return [r for r in json.load(open(PAIRED)) if r["analysis_include"]]


def load_questions():
    idx = {"a": 2, "b": 3, "c": 4, "d": 5}
    con = sqlite3.connect(DB, uri=True)
    q = {}
    for ds, key in (("balanced_a_310726", "A"), ("balanced_b_310726", "B")):
        for r in con.execute(
                "select q.question_id,q.correct_letter,q.option_a,q.option_b,q.option_c,"
                "q.option_d,q.question_text from questions q join datasets d "
                "on d.id=q.dataset_id where d.name=?", (ds,)):
            q.setdefault(r[0], {})[key] = {
                "correct_letter": r[1],
                "opts": {L: r[idx[L]] for L in LETTERS},
                "qtext": r[6],
            }
    con.close()
    return q


if __name__ == "__main__":
    print("CP95(8/10)   =", [round(v, 4) for v in cp_ci(8, 10)], " textbook [0.4439, 0.9748]")
    print("CP95(0/20)   =", [round(v, 4) for v in cp_ci(0, 20)], " textbook [0.0000, 0.1684]")
    print("CP95(20/20)  =", [round(v, 4) for v in cp_ci(20, 20)], " textbook [0.8316, 1.0000]")
    print("CP95(919/1166)=", [round(v, 4) for v in cp_ci(919, 1166)])
    print("CP95(287/318)=", [round(v, 4) for v in cp_ci(287, 318)])
    print("fisher(3,1,1,3) =", round(fisher_2x2(3, 1, 1, 3), 5), " R: 0.48571")
    print("mcnemar_exact(31,4) =", mcnemar_exact(31, 4))
    print("chisq_sf(3.841,1) =", round(chisq_sf(3.841, 1), 4), " expect 0.05")
    print("chisq_sf(7.815,3) =", round(chisq_sf(7.815, 3), 4), " expect 0.05")

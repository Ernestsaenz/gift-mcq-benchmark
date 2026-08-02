"""Shared helpers for the retrieval-harm analysis (ca_ prefix). Stdlib only."""
import json, math, random, os

BASE = os.path.dirname(os.path.abspath(__file__))
CROSS = os.path.join(BASE, 'cross_arm_A.json')
DB = os.path.join(os.path.dirname(BASE), 'experiment.sqlite')


def load(include_only=True):
    rows = json.load(open(CROSS))
    if include_only:
        rows = [r for r in rows if r.get('analysis_include')]
    return rows


# ---------- exact / closed-form tests ----------

def binom_pmf(k, n, p=0.5):
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def mcnemar_exact(b, c):
    """Two-sided exact binomial (sign) test on the discordant pairs.
    b = GIFT right / OR wrong ; c = OR right / GIFT wrong."""
    n = b + c
    if n == 0:
        return 1.0
    obs = binom_pmf(b, n)
    p = 0.0
    for k in range(n + 1):
        pk = binom_pmf(k, n)
        if pk <= obs * (1 + 1e-9):
            p += pk
    return min(1.0, p)


def mcnemar_chi2(b, c, cc=False):
    if b + c == 0:
        return 0.0, 1.0
    num = abs(b - c) - (1.0 if cc else 0.0)
    if num < 0:
        num = 0.0
    x2 = num * num / (b + c)
    return x2, chi2_sf_1df(x2)


def chi2_sf_1df(x):
    if x <= 0:
        return 1.0
    return math.erfc(math.sqrt(x / 2.0))


def norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def fisher_exact_2x2(a, b, c, d):
    """Two-sided Fisher exact p (point-probability method)."""
    n = a + b + c + d
    r1, r2 = a + b, c + d
    c1 = a + c

    def prob(x):
        y = r1 - x
        z = c1 - x
        w = r2 - z
        if y < 0 or z < 0 or w < 0:
            return 0.0
        return (math.comb(r1, x) * math.comb(r2, z)) / math.comb(n, c1)

    obs = prob(a)
    lo = max(0, c1 - r2)
    hi = min(r1, c1)
    p = sum(prob(x) for x in range(lo, hi + 1) if prob(x) <= obs * (1 + 1e-9))
    return min(1.0, p)


# ---------- resampling ----------

def cluster_bootstrap(rows, stat_fn, keyf=lambda r: r['cluster'], B=20000, seed=20260731):
    rng = random.Random(seed)
    groups = {}
    for r in rows:
        groups.setdefault(keyf(r), []).append(r)
    keys = list(groups.keys())
    K = len(keys)
    out = []
    for _ in range(B):
        samp = []
        for _ in range(K):
            samp.extend(groups[keys[rng.randrange(K)]])
        v = stat_fn(samp)
        if v is not None:
            out.append(v)
    out.sort()
    return out


def pctile(sorted_vals, q):
    if not sorted_vals:
        return float('nan')
    i = q * (len(sorted_vals) - 1)
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (i - lo)


def ci(sorted_vals, alpha=0.05):
    return pctile(sorted_vals, alpha / 2), pctile(sorted_vals, 1 - alpha / 2)


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c - h, c + h)

"""who-benefits (ca_wb_*) shared helpers. Stdlib only, no numpy/scipy.

Every statistical routine here is named explicitly at the call site.
"""
import json, math, os, random

BASE = os.path.dirname(os.path.abspath(__file__))
CROSS = os.path.join(BASE, "cross_arm_A.json")
ORFULL = os.path.join(BASE, "ca_or_full.json")

MODELS = ["google/gemma-4-26b-a4b-it", "z-ai/glm-5.2",
          "qwen/qwen3.6-35b-a3b", "google/gemini-3.6-flash"]
SHORT = {"google/gemma-4-26b-a4b-it": "gemma-4-26b",
         "z-ai/glm-5.2": "glm-5.2",
         "qwen/qwen3.6-35b-a3b": "qwen3.6-35b",
         "google/gemini-3.6-flash": "gemini-3.6-fl"}


def load(include_only=True):
    rows = json.load(open(CROSS))
    if include_only:
        rows = [r for r in rows if r.get("analysis_include")]
    return rows


# ---------------------------------------------------------------- 2x2 tables
def table(cells):
    """(a,b,c,d) = (G1O1, G1O0, G0O1, G0O0)."""
    a = b = c = d = 0
    for r in cells:
        g, o = r["gift_correct"], r["or_correct"]
        if g and o:
            a += 1
        elif g and not o:
            b += 1
        elif (not g) and o:
            c += 1
        else:
            d += 1
    return a, b, c, d


# ---------------------------------------------------------------- exact tests
def binom_pmf(k, n, p=0.5):
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def mcnemar_exact(b, c):
    """Exact conditional binomial (sign) test on the b+c discordant pairs;
    two-sided by the method of small p-values."""
    n = b + c
    if n == 0:
        return 1.0
    obs = binom_pmf(b, n)
    return min(1.0, sum(binom_pmf(k, n) for k in range(n + 1)
                        if binom_pmf(k, n) <= obs * (1 + 1e-9)))


def mcnemar_chi2(b, c, cc=False):
    if b + c == 0:
        return 0.0, 1.0
    num = abs(b - c) - (1.0 if cc else 0.0)
    num = max(num, 0.0)
    x2 = num * num / (b + c)
    return x2, chi2_sf_1df(x2)


def chi2_sf_1df(x):
    return 1.0 if x <= 0 else math.erfc(math.sqrt(x / 2.0))


def norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def fisher_exact_2x2(a, b, c, d):
    n = a + b + c + d
    r1, r2, c1 = a + b, c + d, a + c

    def prob(x):
        y, z = r1 - x, c1 - x
        w = r2 - z
        if y < 0 or z < 0 or w < 0:
            return 0.0
        return math.comb(r1, x) * math.comb(r2, z) / math.comb(n, c1)

    obs = prob(a)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    return min(1.0, sum(prob(x) for x in range(lo, hi + 1)
                        if prob(x) <= obs * (1 + 1e-9)))


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    den = 1 + z * z / n
    ctr = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, ctr - h), min(1.0, ctr + h)


# ---------------------------------------------------------------- resampling
def cluster_boot(rows, stat_fn, B=20000, seed=20260731, keyf=None):
    """Nonparametric cluster bootstrap over question clusters; percentile CI."""
    keyf = keyf or (lambda r: r["cluster"])
    rng = random.Random(seed)
    g = {}
    for r in rows:
        g.setdefault(keyf(r), []).append(r)
    keys = list(g)
    K = len(keys)
    out = []
    for _ in range(B):
        s = []
        for _ in range(K):
            s.extend(g[keys[rng.randrange(K)]])
        v = stat_fn(s)
        if v is not None and v == v:
            out.append(v)
    out.sort()
    return out


def pctile(v, q):
    if not v:
        return float("nan")
    i = q * (len(v) - 1)
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return v[lo] if lo == hi else v[lo] + (v[hi] - v[lo]) * (i - lo)


def ci(v, alpha=0.05):
    return pctile(v, alpha / 2), pctile(v, 1 - alpha / 2)


def boot_p(reps, null=0.0):
    """Two-sided bootstrap p by inversion: 2*min(share<=null, share>=null)."""
    if not reps:
        return float("nan")
    n = len(reps)
    lo = sum(1 for v in reps if v <= null) / n
    hi = sum(1 for v in reps if v >= null) / n
    return min(1.0, 2 * min(lo, hi))


def cluster_armflip(rows, stat_fn, B=20000, seed=515):
    """Cluster-level randomization test of H0: arm labels exchangeable.
    All cells inside a cluster get their (gift, or) outcomes swapped together,
    preserving the within-cluster / within-item dependence structure."""
    rng = random.Random(seed)
    g = {}
    for r in rows:
        g.setdefault(r["cluster"], []).append(r)
    keys = list(g)
    obs = stat_fn(rows)
    ge, reps = 0, []
    for _ in range(B):
        perm = []
        for k in keys:
            if rng.random() < 0.5:
                for r in g[k]:
                    q = dict(r)
                    q["gift_correct"], q["or_correct"] = r["or_correct"], r["gift_correct"]
                    perm.append(q)
            else:
                perm.extend(g[k])
        v = stat_fn(perm)
        reps.append(v)
        if abs(v) >= abs(obs) - 1e-12:
            ge += 1
    reps.sort()
    return obs, (ge + 1) / (B + 1), reps


def pct(x, nd=1):
    return "  nan " if x != x else ("%." + str(nd) + "f") % (100 * x)

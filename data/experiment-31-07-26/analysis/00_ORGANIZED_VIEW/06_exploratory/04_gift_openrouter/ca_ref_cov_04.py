"""ca_ref_cov_04: CI reproduction on the stale basis + clustered inference on both bases."""
import json, math, os, random
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
rows_all = json.load(open(os.path.join(BASE, "cross_arm_A.json")))
OLD = set(json.load(open(os.path.join(BASE, "ca_cov_grid.json")))["defect"])
BASES = {"stale 1244": [r for r in rows_all if r["question_id"] not in OLD],
         "shipped 1224": [r for r in rows_all if r.get("analysis_include") is True]}


def delta(rs):
    return 100.0 * sum(r["gift_correct"] - r["or_correct"] for r in rs) / len(rs)


def boot(rs, B=20000, seed=707070):
    rng = random.Random(seed)
    g = defaultdict(list)
    for r in rs:
        g[r["cluster"]].append(r)
    keys = list(g)
    K = len(keys)
    v = []
    for _ in range(B):
        s = []
        for _ in range(K):
            s.extend(g[keys[rng.randrange(K)]])
        v.append(delta(s))
    v.sort()
    return v


def pct(v, q):
    i = q * (len(v) - 1)
    lo, hi = math.floor(i), math.ceil(i)
    return v[int(lo)] if lo == hi else v[int(lo)] + (v[int(hi)] - v[int(lo)]) * (i - lo)


def perm(rs, B=200000, seed=4242):
    g = defaultdict(int)
    for r in rs:
        g[r["cluster"]] += r["gift_correct"] - r["or_correct"]
    d = list(g.values())
    obs = abs(sum(d))
    rng = random.Random(seed)
    hits = sum(1 for _ in range(B)
               if abs(sum(x if rng.random() < .5 else -x for x in d)) >= obs - 1e-9)
    return (hits + 1) / (B + 1)


def lch(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def sign_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    f = lambda k: math.exp(lch(n, k) - n * math.log(2.0))
    o = f(b)
    return min(1.0, sum(f(k) for k in range(n + 1) if f(k) <= o * (1 + 1e-9)))


for nm, rs in BASES.items():
    b = sum(1 for r in rs if r["gift_correct"] and not r["or_correct"])
    c = sum(1 for r in rs if r["or_correct"] and not r["gift_correct"])
    nk = len(set(r["cluster"] for r in rs))
    print(f"\n### {nm}: cells={len(rs)} clusters={nk} b={b} c={c} delta={delta(rs):+.3f}pp")
    for seed in (707070, 12345, 60606):
        v = boot(rs, seed=seed)
        print(f"   cluster-bootstrap B=20000 seed={seed:6d}  95% CI "
              f"[{pct(v,.025):+.3f}, {pct(v,.975):+.3f}]pp")
    print(f"   unclustered exact McNemar (sign test) p = {sign_exact(b,c):.4f}")
    print(f"   CLUSTER sign-flip permutation      p = {perm(rs):.4f}   "
          f"<-- honest pooled p; ratio {perm(rs)/sign_exact(b,c):.1f}x")

"""ca_ref_cov_02: same recount on BOTH exclusion bases (stale 14-item vs shipped 22-item),
plus clustered inference and heterogeneity. Stdlib only, nothing imported from ca_lib.
"""
import json, math, os, random
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
rows_all = json.load(open(os.path.join(BASE, "cross_arm_A.json")))
meta = json.load(open(os.path.join(BASE, "dataset_meta.json")))["exclusions"]
NEW_DEFECT = set(meta["out_of_domain_law"]) | set(meta["adjudicated_key_defect"])
OLD_DEFECT = set(json.load(open(os.path.join(BASE, "ca_cov_grid.json")))["defect"])

MODELS = ["google/gemma-4-26b-a4b-it", "z-ai/glm-5.2",
          "qwen/qwen3.6-35b-a3b", "google/gemini-3.6-flash"]
SHORT = {"google/gemini-3.6-flash": "gemini-3.6-flash",
         "google/gemma-4-26b-a4b-it": "gemma-4-26b-a4b-it",
         "qwen/qwen3.6-35b-a3b": "qwen3.6-35b-a3b", "z-ai/glm-5.2": "glm-5.2"}


def lchoose(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def bpmf(k, n):
    return math.exp(lchoose(n, k) - n * math.log(2.0))


def sign_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    obs = bpmf(b, n)
    return min(1.0, sum(bpmf(k, n) for k in range(n + 1) if bpmf(k, n) <= obs * (1 + 1e-9)))


def chi2sf(x):
    return 1.0 if x <= 0 else math.erfc(math.sqrt(x / 2.0))


def report(rows, label):
    print(f"\n===== {label}: cells={len(rows)} items={len(set(r['question_id'] for r in rows))} "
          f"clusters={len(set(r['cluster'] for r in rows))} =====")
    print(f"{'model':20s} {'n':>4s} {'GIFT%':>7s} {'OR%':>7s} {'d_pp':>7s} {'b':>3s} {'c':>3s} "
          f"{'x2unc':>6s} {'x2cc':>6s} {'p_ex':>7s}")
    out = {}
    for m in MODELS + ["POOLED"]:
        sub = rows if m == "POOLED" else [r for r in rows if r["model"] == m]
        n = len(sub)
        gk = sum(r["gift_correct"] for r in sub)
        ok = sum(r["or_correct"] for r in sub)
        b = sum(1 for r in sub if r["gift_correct"] and not r["or_correct"])
        c = sum(1 for r in sub if r["or_correct"] and not r["gift_correct"])
        xu = (b - c) ** 2 / (b + c) if b + c else 0.0
        xc = max(0, abs(b - c) - 1) ** 2 / (b + c) if b + c else 0.0
        pe = sign_exact(b, c)
        out[m] = dict(n=n, gk=gk, ok=ok, b=b, c=c, d=100 * (gk - ok) / n,
                      xu=xu, xc=xc, pe=pe)
        print(f"{SHORT.get(m,m):20s} {n:4d} {100*gk/n:6.2f}% {100*ok/n:6.2f}% "
              f"{100*(gk-ok)/n:+7.3f} {b:3d} {c:3d} {xu:6.3f} {xc:6.3f} {pe:7.4f}")
    P = out["POOLED"]
    print(f"    POOLED p(chi2 unc)={chi2sf(P['xu']):.4f}  p(chi2 cc)={chi2sf(P['xc']):.4f}")
    return out


old = report([r for r in rows_all if r["question_id"] not in OLD_DEFECT],
             "STALE 14-item defect basis (what the claim used)")
new = report([r for r in rows_all if r.get("analysis_include") is True],
             "SHIPPED analysis_include basis (22-item defect list)")

print("\n=== WHICH ITEMS MOVED, AND WHAT THEY CONTRIBUTED ===")
moved = sorted(set(r["question_id"] for r in rows_all
                   if r["question_id"] in NEW_DEFECT and r["question_id"] not in OLD_DEFECT))
print("covered items newly excluded:", moved)
for q in moved:
    sub = [r for r in rows_all if r["question_id"] == q]
    b = sum(1 for r in sub if r["gift_correct"] and not r["or_correct"])
    c = sum(1 for r in sub if r["or_correct"] and not r["gift_correct"])
    who = [SHORT[r["model"]] for r in sub if r["gift_correct"] != r["or_correct"]]
    print(f"  {q:6s} region={sub[0]['region']:20s} cluster={sub[0]['cluster']:4d} "
          f"b={b} c={c} discordant_models={who}")

# ---------------------------------------------------------------- clustered inference
rows = [r for r in rows_all if r.get("analysis_include") is True]


def delta_pp(rs):
    if not rs:
        return None
    return 100.0 * sum(r["gift_correct"] - r["or_correct"] for r in rs) / len(rs)


def cluster_boot(rs, B=20000, seed=707070, key="cluster"):
    rng = random.Random(seed)
    g = defaultdict(list)
    for r in rs:
        g[r[key]].append(r)
    keys = list(g)
    K = len(keys)
    vals = []
    for _ in range(B):
        s = []
        for _ in range(K):
            s.extend(g[keys[rng.randrange(K)]])
        vals.append(delta_pp(s))
    vals.sort()
    return vals


def pct(v, q):
    i = q * (len(v) - 1)
    lo, hi = math.floor(i), math.ceil(i)
    return v[int(lo)] if lo == hi else v[int(lo)] + (v[int(hi)] - v[int(lo)]) * (i - lo)


print("\n=== POOLED delta_pp, resampling unit sensitivity (B=20000) ===")
for key, nm in [("cluster", "cluster (183/178)"), ("question_id", "item")]:
    for seed in (707070, 11, 999):
        v = cluster_boot(rows, seed=seed, key=key)
        print(f"  unit={nm:20s} seed={seed:6d}  point={delta_pp(rows):+.3f}pp  "
              f"95% CI [{pct(v,.025):+.3f}, {pct(v,.975):+.3f}]  P(<=0)={sum(1 for x in v if x<=0)/len(v):.4f}")

# cluster-level sign-flip permutation: the honest pooled test
print("\n=== CLUSTER SIGN-FLIP PERMUTATION (pooled) ===")
g = defaultdict(int)
for r in rows:
    g[r["cluster"]] += r["gift_correct"] - r["or_correct"]
d = list(g.values())
obs = abs(sum(d))
rng = random.Random(4242)
B = 200000
hits = sum(1 for _ in range(B)
           if abs(sum(x if rng.random() < .5 else -x for x in d)) >= obs - 1e-9)
print(f"  observed net discordance = {sum(d)} over {len(d)} clusters")
print(f"  two-sided cluster-permutation p = {(hits+1)/(B+1):.4f}   (unclustered exact p = {new['POOLED']['pe']:.4f})")

# design effect: variance of clustered vs binomial
print("\n=== BETWEEN-MODEL HETEROGENEITY (are the 4 models exchangeable?) ===")
# 2x4 chi-square on (b,c) across models
bs = [new[m]["b"] for m in MODELS]
cs = [new[m]["c"] for m in MODELS]
N = sum(bs) + sum(cs)
pb = sum(bs) / N
chi = 0.0
for b, c in zip(bs, cs):
    n = b + c
    if n == 0:
        continue
    chi += (b - n * pb) ** 2 / (n * pb) + (c - n * (1 - pb)) ** 2 / (n * (1 - pb))
print(f"  b per model {bs}  c per model {cs}")


def chi2sf_df(x, df):
    # regularised upper incomplete gamma via series/continued fraction
    a = df / 2.0
    xx = x / 2.0
    if xx <= 0:
        return 1.0
    if xx < a + 1:
        s, term, n = 1.0 / a, 1.0 / a, 0
        while abs(term) > 1e-14 * abs(s):
            n += 1
            term *= xx / (a + n)
            s += term
        return 1.0 - s * math.exp(-xx + a * math.log(xx) - math.lgamma(a))
    b0, c0, dd, h = xx + 1 - a, 1e300, 1.0 / (xx + 1 - a), 1.0 / (xx + 1 - a)
    for i in range(1, 400):
        an = -i * (i - a)
        b0 += 2
        dd = an * dd + b0
        if abs(dd) < 1e-300:
            dd = 1e-300
        c0 = b0 + an / c0
        if abs(c0) < 1e-300:
            c0 = 1e-300
        dd = 1.0 / dd
        de = dd * c0
        h *= de
        if abs(de - 1) < 1e-14:
            break
    return math.exp(-xx + a * math.log(xx) - math.lgamma(a)) * h


print(f"  heterogeneity chi2 = {chi:.3f} on 3 df, p = {chi2sf_df(chi,3):.4f}")

"""ca_wb_03: two gradient tests.

(1) ACROSS MODELS (n=4, acknowledged as near-meaningless): Spearman rho between
    the OpenRouter baseline and the GIFT delta, with the EXACT permutation null
    over all 4! = 24 rank orderings, plus a cluster bootstrap showing how
    unstable the rho is.

(2) WITHIN THE DATA (the real test): among cells the base model got WRONG on
    OpenRouter, does the recovery probability depend on item difficulty
    (leave-one-out k = how many of the OTHER 3 models got it right on
    OpenRouter)?  Cochran-Armitage linear trend, with a cluster bootstrap of
    the slope and a cluster-level label permutation p.
"""
import json, math, itertools, random
from ca_wb_lib import (load, table, MODELS, SHORT, wilson, cluster_boot, ci,
                       boot_p, fisher_exact_2x2, chi2_sf_1df, pct)

rows = load()
by_item = {}
for r in rows:
    by_item.setdefault(r["question_id"], {})[r["model"]] = r
k_all = {q: sum(v["or_correct"] for v in d.values()) for q, d in by_item.items()}
for r in rows:
    r["k_loo"] = k_all[r["question_id"]] - r["or_correct"]


def spearman(x, y):
    def rk(v):
        s = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and v[s[j + 1]] == v[s[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for t in range(i, j + 1):
                r[s[t]] = avg
            i = j + 1
        return r
    rx, ry = rk(x), rk(y)
    n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = math.sqrt(sum((rx[i] - mx) ** 2 for i in range(n)))
    dy = math.sqrt(sum((ry[i] - my) ** 2 for i in range(n)))
    return num / (dx * dy) if dx and dy else float("nan")


# ------------------------------------------------------ (1) across-model rho
stats = {}
for m in MODELS:
    a, b, c, d = table([r for r in rows if r["model"] == m])
    n = a + b + c + d
    stats[m] = dict(orr=(a + c) / n, delta=(b - c) / n, headroom=(b + d) / n,
                    rec=b / (b + d) if b + d else float("nan"),
                    brk=c / (a + c) if a + c else float("nan"), a=a, b=b, c=c, d=d, n=n)

base = [stats[m]["orr"] for m in MODELS]
delt = [stats[m]["delta"] for m in MODELS]
head = [stats[m]["headroom"] for m in MODELS]
recs = [stats[m]["rec"] for m in MODELS]

print("ACROSS-MODEL GRADIENT (n = 4 models)")
print("%-14s %9s %9s %9s %9s" % ("model", "OR base", "delta", "headroom", "recovery"))
for i, m in enumerate(MODELS):
    print("%-14s %9s %+9s %9s %9s" % (SHORT[m], pct(base[i]), pct(delt[i]),
                                      pct(head[i]), pct(recs[i])))


def exact_perm_p(x, y):
    """Exact two-sided permutation p for Spearman rho over all n! orderings."""
    obs = spearman(x, y)
    cnt = tot = 0
    for perm in itertools.permutations(range(len(y))):
        r = spearman(x, [y[i] for i in perm])
        tot += 1
        if abs(r) >= abs(obs) - 1e-12:
            cnt += 1
    return obs, cnt / tot, tot


for lab, yv in (("delta", delt), ("recovery", recs)):
    r, p, tot = exact_perm_p(base, yv)
    print("  Spearman rho(OR baseline, %s) = %+.3f ; exact permutation p = %.4f over %d orderings"
          % (lab, r, p, tot))
r, p, tot = exact_perm_p(head, delt)
print("  Spearman rho(headroom, delta)   = %+.3f ; exact permutation p = %.4f over %d orderings"
      % (r, p, tot))

# how stable is that rho? recompute it inside a cluster bootstrap
def rho_stat(s):
    b_, d_ = [], []
    for m in MODELS:
        A, B_, C, D = table([r for r in s if r["model"] == m])
        n = A + B_ + C + D
        if n == 0:
            return None
        b_.append((A + C) / n)
        d_.append((B_ - C) / n)
    return spearman(b_, d_)


reps = cluster_boot(rows, rho_stat, B=5000, seed=7)
lo, hi = ci(reps)
frac_neg = sum(1 for v in reps if v < 0) / len(reps)
print("  cluster bootstrap of rho(OR baseline, delta): 95%% CI [%.2f, %.2f]; "
      "P(rho<0)=%.3f  (B=5000)" % (lo, hi, frac_neg))
print("  -> with 4 models the rank correlation cannot be distinguished from noise;")
print("     it is reported only to show that it is uninformative.")

# ------------------------------------------- (2) within-data difficulty trend
print()
print("=" * 96)
print("WITHIN-DATA TEST: recovery P(GIFT correct | OR wrong) by leave-one-out difficulty")
print("k_loo = number of the OTHER 3 models correct on OpenRouter (0 = hardest)")
wrong = [r for r in rows if r["or_correct"] == 0]
right = [r for r in rows if r["or_correct"] == 1]
print("  OR-wrong cells: %d of %d (%.1f%%);  OR-correct cells: %d"
      % (len(wrong), len(rows), 100 * len(wrong) / len(rows), len(right)))
print()
print("%5s %8s %8s %26s | %8s %8s %24s" % (
    "k_loo", "n wrong", "recov", "recovery 95% Wilson",
    "n right", "break", "breakage 95% Wilson"))
print("-" * 96)
tr = {}
for k in range(4):
    w = [r for r in wrong if r["k_loo"] == k]
    g = [r for r in right if r["k_loo"] == k]
    kb = sum(r["gift_correct"] for r in w)
    kc = sum(1 - r["gift_correct"] for r in g)
    pr, pl, ph = wilson(kb, len(w))
    br, bl, bh = wilson(kc, len(g))
    print("%5d %8d %8s   [%5s, %5s]  (%2d/%2d) | %8d %8s [%5s, %5s] (%2d/%3d)" % (
        k, len(w), pct(pr), pct(pl), pct(ph), kb, len(w),
        len(g), pct(br), pct(bl), pct(bh), kc, len(g)))
    tr[k] = dict(n_wrong=len(w), rec_k=kb, n_right=len(g), brk_k=kc)

# Cochran-Armitage linear trend on recovery, scores = k_loo
def ca_trend(cells):
    """Cochran-Armitage trend statistic z for P(gift_correct) vs k_loo among
    OR-wrong cells; returns the slope of the linear probability fit."""
    xs = [r["k_loo"] for r in cells]
    ys = [r["gift_correct"] for r in cells]
    n = len(xs)
    if n < 5:
        return None
    mx = sum(xs) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    my = sum(ys) / n
    return sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / sxx


slope = ca_trend(wrong)
sreps = cluster_boot(wrong, ca_trend, B=20000, seed=99)
slo, shi = ci(sreps)
print()
print("Cochran-Armitage / linear-probability slope of recovery on k_loo:")
print("  slope = %+.4f per difficulty step  (i.e. %+.1f pp per step)" % (slope, 100 * slope))
print("  cluster bootstrap 95%% CI [%+.4f, %+.4f]  two-sided bootstrap p = %.4f (B=20000)"
      % (slo, shi, boot_p(sreps)))

# cluster-level label permutation: shuffle the item->k_loo map across items
def perm_p_labels(cells, B=20000, seed=11):
    rng = random.Random(seed)
    obs = ca_trend(cells)
    # permute k_loo labels at CLUSTER level: reassign whole clusters' label
    # vectors to other clusters of the same length, so within-cluster label
    # dependence is preserved.
    byc = {}
    for r in cells:
        byc.setdefault(r["cluster"], []).append(r)
    keys = list(byc)
    pools = {}
    for k in keys:
        pools.setdefault(len(byc[k]), []).append([r["k_loo"] for r in byc[k]])
    ge = 0
    for _ in range(B):
        newp = {sz: [v[:] for v in vs] for sz, vs in pools.items()}
        for sz in newp:
            rng.shuffle(newp[sz])
        idx = {sz: 0 for sz in newp}
        out = []
        for k in keys:
            sz = len(byc[k])
            lab = newp[sz][idx[sz]]
            idx[sz] += 1
            for r, L in zip(byc[k], lab):
                q = dict(r)
                q["k_loo"] = L
                out.append(q)
        v = ca_trend(out)
        if v is not None and abs(v) >= abs(obs) - 1e-12:
            ge += 1
    return obs, (ge + 1) / (B + 1)


o, pl_ = perm_p_labels(wrong, B=20000)
print("  cluster-level difficulty-label permutation p = %.4f (B=20000)" % pl_)

# hardest stratum vs the rest: Fisher exact
k0b = tr[0]["rec_k"]; k0n = tr[0]["n_wrong"]
restb = sum(tr[k]["rec_k"] for k in (1, 2, 3))
restn = sum(tr[k]["n_wrong"] for k in (1, 2, 3))
pf = fisher_exact_2x2(k0b, k0n - k0b, restb, restn - restb)
print()
print("HARDEST stratum (k_loo=0: no other model solved it) vs k_loo>=1:")
print("  recovery %d/%d = %s   vs   %d/%d = %s ; Fisher exact two-sided p = %.4f"
      % (k0b, k0n, pct(k0b / k0n if k0n else float('nan')),
         restb, restn, pct(restb / restn), pf))

json.dump({"per_model": stats, "trend": tr, "slope": slope,
           "slope_ci": [slo, shi], "slope_boot_p": boot_p(sreps),
           "slope_perm_p": pl_, "fisher_k0_vs_rest": pf},
          open("ca_wb_03_gradient.json", "w"), indent=1)
print("\nwritten ca_wb_03_gradient.json")

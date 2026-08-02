#!/usr/bin/env python3
"""Part 3: is the cluster structure real signal or an artifact of variance
heterogeneity? Permutation test on ICC + variance decomposition."""
import json, math, random
from collections import defaultdict, Counter

P = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
inc = [r for r in json.load(open(P)) if r["analysis_include"] is True]

it = defaultdict(list)
itcl = {}
for r in inc:
    it[r["question_id"]].append(r["B_correct"] - r["A_correct"])
    itcl[r["question_id"]] = r["cluster"]
d_item = {i: sum(v) / len(v) for i, v in it.items()}
items = sorted(d_item)
cl_items = defaultdict(list)
for i in items:
    cl_items[itcl[i]].append(i)
sizes_profile = sorted((len(v) for v in cl_items.values()), reverse=True)


def var(v):
    m = sum(v) / len(v)
    return sum((x - m) ** 2 for x in v) / (len(v) - 1)


multi_cl = [c for c, v in cl_items.items() if len(v) > 1]
multi_items = [i for c in multi_cl for i in cl_items[c]]
sing_items = [i for c, v in cl_items.items() if len(v) == 1 for i in v]

print("=== VARIANCE HETEROGENEITY (per-item delta d_i = mean_m(B-A)) ===")
print("  all items      n=%3d var=%.6f" % (len(items), var([d_item[i] for i in items])))
print("  multi-cluster  n=%3d var=%.6f mean=%+.6f"
      % (len(multi_items), var([d_item[i] for i in multi_items]),
         sum(d_item[i] for i in multi_items) / len(multi_items)))
print("  singleton      n=%3d var=%.6f mean=%+.6f"
      % (len(sing_items), var([d_item[i] for i in sing_items]),
         sum(d_item[i] for i in sing_items) / len(sing_items)))
print("  var ratio singleton/multi = %.4f"
      % (var([d_item[i] for i in sing_items]) / var([d_item[i] for i in multi_items])))
print("  d_i == 0 share: multi=%.4f  singleton=%.4f"
      % (sum(1 for i in multi_items if d_item[i] == 0) / len(multi_items),
         sum(1 for i in sing_items if d_item[i] == 0) / len(sing_items)))


def anova_icc(assign):
    """assign: dict item->cluster label. Returns (MSB, MSW, m0, ICC, F)."""
    g = defaultdict(list)
    for i, c in assign.items():
        g[c].append(d_item[i])
    k = len(g)
    N = sum(len(x) for x in g.values())
    gm = sum(sum(x) for x in g.values()) / N
    MSB = sum(len(x) * (sum(x) / len(x) - gm) ** 2 for x in g.values()) / (k - 1)
    ssw = sum(sum((y - sum(x) / len(x)) ** 2 for y in x) for x in g.values())
    dfw = N - k
    MSW = ssw / dfw
    sz = [len(x) for x in g.values()]
    m0 = (N - sum(s * s for s in sz) / N) / (k - 1)
    icc = (MSB - MSW) / (MSB + (m0 - 1) * MSW)
    return MSB, MSW, m0, icc, MSB / MSW


obs = anova_icc(itcl)
print("\n=== OBSERVED ===")
print("  MSB=%.6f MSW=%.6f m0=%.4f ICC=%.6f F=MSB/MSW=%.4f (df 207,117)"
      % obs)

# ---- permutation null: shuffle item->cluster assignment, keep size profile ----
random.seed(20260731)
R = 20000
labels = []
for idx, s in enumerate(sizes_profile):
    labels += [idx] * s
assert len(labels) == len(items)
null_icc = []
null_F = []
pool = list(items)
for _ in range(R):
    random.shuffle(pool)
    assign = {pool[j]: labels[j] for j in range(len(pool))}
    _, _, _, ic, F = anova_icc(assign)
    null_icc.append(ic)
    null_F.append(F)


def pct(v, q):
    v = sorted(v)
    h = (len(v) - 1) * q
    lo = math.floor(h)
    hi = math.ceil(h)
    return v[lo] + (h - lo) * (v[hi] - v[lo])


p_icc = (1 + sum(1 for x in null_icc if x >= obs[3])) / (R + 1)
p_F = (1 + sum(1 for x in null_F if x >= obs[4])) / (R + 1)
print("\n=== PERMUTATION NULL (R=%d, item->cluster reshuffled, sizes fixed, seed=20260731) ===" % R)
print("  null ICC: mean=%.6f sd=%.6f  95%% range [%.4f, %.4f]  99th pct=%.4f"
      % (sum(null_icc) / R, math.sqrt(var(null_icc)), pct(null_icc, .025), pct(null_icc, .975),
         pct(null_icc, .99)))
print("  observed ICC=%.6f   one-sided p = %.5f" % (obs[3], p_icc))
print("  observed F  =%.6f   one-sided p = %.5f" % (obs[4], p_F))

# ---- cluster bootstrap SE ratio under the permutation null, for calibration ----
print("\n=== IS THE CLUSTER-BOOTSTRAP SE RATIO (1.034) UNUSUAL? ===")
B = 4000


def se_ratio(assign):
    ci = defaultdict(list)
    for i, c in assign.items():
        ci[c].append(i)
    cl = list(ci)
    n = len(cl)
    bc = []
    for _ in range(B):
        s = 0.0
        c2 = 0
        for _ in range(n):
            for i in ci[cl[random.randrange(n)]]:
                s += d_item[i]
                c2 += 1
        bc.append(s / c2)
    m = sum(bc) / len(bc)
    sdc = math.sqrt(sum((x - m) ** 2 for x in bc) / (len(bc) - 1))
    ni = len(assign)
    bi = []
    for _ in range(B):
        s = 0.0
        for _ in range(ni):
            s += d_item[items[random.randrange(ni)]]
        bi.append(s / ni)
    m = sum(bi) / len(bi)
    sdi = math.sqrt(sum((x - m) ** 2 for x in bi) / (len(bi) - 1))
    return sdc / sdi


obs_ratio = se_ratio(itcl)
print("  observed SE ratio (B=%d) = %.4f" % (B, obs_ratio))
nullr = []
for _ in range(40):
    random.shuffle(pool)
    nullr.append(se_ratio({pool[j]: labels[j] for j in range(len(pool))}))
nullr.sort()
print("  null SE ratios (40 reshuffles): min=%.4f median=%.4f max=%.4f mean=%.4f"
      % (nullr[0], nullr[len(nullr) // 2], nullr[-1], sum(nullr) / len(nullr)))
print("  -> null ratio is ABOVE 1 even with no real clustering, because unequal")
print("     cluster sizes alone make the cluster bootstrap noisier.")
print("  excess of observed over null median = %.4f" % (obs_ratio - nullr[len(nullr) // 2]))

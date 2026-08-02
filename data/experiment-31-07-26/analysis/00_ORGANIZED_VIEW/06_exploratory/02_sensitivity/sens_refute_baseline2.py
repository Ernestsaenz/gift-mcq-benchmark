#!/usr/bin/env python3
"""
Part 2: (a) Monte-Carlo noise envelope on the bootstrap percentile endpoints,
        (b) robustness of the sign-flip p to statistic choice,
        (c) audit of the exclusion bookkeeping (does 1691 -> 1299 add up?),
        (d) does the baseline survive alternative inference routes?
"""
import json, random, math, statistics
from collections import defaultdict, Counter

BASE = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
rows = json.load(open(f"{BASE}/paired_clean.json"))
inc = [r for r in rows if r["analysis_include"]]
n = len(inc)
pooled = sum(r["B_correct"] - r["A_correct"] for r in inc) / n

by_cluster = defaultdict(list)
for r in inc:
    by_cluster[r["cluster"]].append(r["B_correct"] - r["A_correct"])
clusters = sorted(by_cluster)
K = len(clusters)
sums = [sum(by_cluster[c]) for c in clusters]
ns = [len(by_cluster[c]) for c in clusters]

# ---------------- (a) MC envelope on the percentile endpoints ----------------
def boot_ci(seed, reps=20000):
    rng = random.Random(seed); rr = rng.randrange
    out = []
    for _ in range(reps):
        s = 0; m = 0
        for _ in range(K):
            j = rr(K); s += sums[j]; m += ns[j]
        out.append(s / m)
    out.sort()
    return out[int(0.025 * reps)] * 100, out[int(0.975 * reps)] * 100

los, his = [], []
for sd in range(40):
    lo, hi = boot_ci(1000 + sd)
    los.append(lo); his.append(hi)
print("MC envelope over 40 independent bootstrap runs (20000 reps each):")
print(f"  lower endpoint: mean {statistics.mean(los):.4f}  sd {statistics.stdev(los):.4f}  "
      f"range [{min(los):.4f}, {max(los):.4f}]")
print(f"  upper endpoint: mean {statistics.mean(his):.4f}  sd {statistics.stdev(his):.4f}  "
      f"range [{min(his):.4f}, {max(his):.4f}]")
print(f"  width:          mean {statistics.mean(h-l for l,h in zip(los,his)):.4f}  "
      f"range [{min(h-l for l,h in zip(los,his)):.4f}, {max(h-l for l,h in zip(los,his)):.4f}]")
print(f"  CLAIMED [-18.81, -12.48] width 6.33 inside envelope? "
      f"lo:{min(los) <= -18.81 <= max(los)}  hi:{min(his) <= -12.48 <= max(his)}")

# a bigger single bootstrap for a stable reference
big = 200000
lo, hi = boot_ci(777, big)
print(f"  reference bootstrap B={big}: [{lo:.4f}, {hi:.4f}] width {hi-lo:.4f}")

# ---------------- (b) sign-flip p under 3 statistic choices ----------------
def signflip(stat, seed, reps=20000):
    rng = random.Random(seed)
    obs = abs(stat(sums))
    ge = 0
    maxabs = 0.0
    for _ in range(reps):
        f = [s if rng.getrandbits(1) else -s for s in sums]
        v = abs(stat(f))
        maxabs = max(maxabs, v)
        if v >= obs - 1e-15:
            ge += 1
    return (1 + ge) / (1 + reps), ge, obs, maxabs

# S1: pooled mean over cells (the claimed statistic)
S1 = lambda f: sum(f) / n
# S2: unweighted mean of cluster means
S2 = lambda f: sum(v / m for v, m in zip(f, ns)) / K
# S3: studentised (cluster-robust t)
def S3(f):
    tot = sum(f) / n
    num = sum((v - tot * m) ** 2 for v, m in zip(f, ns))
    se = math.sqrt(num) / n
    return tot / se if se > 0 else 0.0

print("\nsign-flip permutation, 20000 reps, p=(1+#ge)/(1+B):")
for nm, st in (("S1 pooled cell mean", S1),
               ("S2 mean of cluster means", S2),
               ("S3 cluster-robust t", S3)):
    p, ge, obs, mx = signflip(st, 424242)
    print(f"  {nm:26s} |t_obs|={obs:.5f}  max|t*|={mx:.5f}  #ge={ge}  p={p:.6f}")

# how extreme is t_obs relative to the null sd?
rng = random.Random(99)
null = []
for _ in range(20000):
    null.append(sum(s if rng.getrandbits(1) else -s for s in sums) / n)
sd0 = statistics.pstdev(null)
print(f"  null sd (S1) = {sd0*100:.4f} pp ; |t_obs|/sd0 = {abs(pooled)/sd0:.2f} sigma")
print(f"  normal-approx two-sided p = {math.erfc(abs(pooled)/sd0/math.sqrt(2)):.3e}")

# ---------------- (c) exclusion bookkeeping audit ----------------
print("\n--- exclusion bookkeeping ---")
allq = {r["question_id"] for r in rows}
print(f"distinct items in paired_clean (all)   : {len(allq)}")
def_items = {r["question_id"] for r in rows if r["excl_item_defect"]}
posa_items = {r["question_id"] for r in rows if r["excl_nota_position_a"]}
print(f"items flagged excl_item_defect         : {len(def_items)}  {sorted(def_items)}")
print(f"items flagged excl_nota_position_a     : {len(posa_items)}")
print(f"overlap (defect AND position-a)        : {len(def_items & posa_items)}  {sorted(def_items & posa_items)}")
print(f"union excluded items                   : {len(def_items | posa_items)}")
print(f"items remaining                        : {len(allq - (def_items | posa_items))}")
cells_def = sum(1 for r in rows if r["excl_item_defect"])
cells_posa = sum(1 for r in rows if r["excl_nota_position_a"])
cells_both = sum(1 for r in rows if r["excl_item_defect"] and r["excl_nota_position_a"])
print(f"cells: defect={cells_def} posA={cells_posa} both={cells_both} "
      f"union={cells_def+cells_posa-cells_both}  1691-union={1691-(cells_def+cells_posa-cells_both)}")
print(f"correct_letter distribution (all cells): {Counter(r['correct_letter'] for r in rows)}")

# ---------------- (d) alternative inference routes ----------------
print("\n--- alternative routes to the same effect ---")
# exact-ish McNemar on discordant pairs (cell level, ignores clustering) via binomial
b10 = sum(1 for r in inc if r["A_correct"] == 1 and r["B_correct"] == 0)
b01 = sum(1 for r in inc if r["A_correct"] == 0 and r["B_correct"] == 1)
m = b10 + b01
# two-sided exact binomial p, P(X<=min)*2 style
def logC(n_, k):
    return (math.lgamma(n_+1) - math.lgamma(k+1) - math.lgamma(n_-k+1))
tail = sum(math.exp(logC(m, k) - m * math.log(2)) for k in range(0, min(b10, b01) + 1))
print(f"McNemar exact (cell-level, anti-conservative here): b10={b10} b01={b01} "
      f"two-sided p={2*tail:.3e}")

# cluster-level Wilcoxon-ish sign test on cluster mean diffs
cm = [sum(by_cluster[c]) / len(by_cluster[c]) for c in clusters]
neg = sum(1 for v in cm if v < 0); pos = sum(1 for v in cm if v > 0); zero = sum(1 for v in cm if v == 0)
mm = neg + pos
tail2 = sum(math.exp(logC(mm, k) - mm * math.log(2)) for k in range(0, min(neg, pos) + 1))
print(f"cluster sign test: clusters with mean diff <0: {neg}, >0: {pos}, ==0: {zero} "
      f"-> two-sided p={2*tail2:.3e}")

# t on cluster means (unweighted)
mbar = statistics.mean(cm); sdm = statistics.stdev(cm)
se = sdm / math.sqrt(K)
print(f"unweighted cluster-mean delta = {mbar*100:.4f} pp, SE={se*100:.4f}, "
      f"95% CI [{(mbar-1.96*se)*100:.4f}, {(mbar+1.96*se)*100:.4f}], t={mbar/se:.2f}")

# item-level clustering instead of clinical-context clustering (finer -> narrower)
by_item = defaultdict(list)
for r in inc:
    by_item[r["question_id"]].append(r["B_correct"] - r["A_correct"])
items = sorted(by_item)
isums = [sum(by_item[i]) for i in items]; ins = [len(by_item[i]) for i in items]
num = sum((v - pooled * mq) ** 2 for v, mq in zip(isums, ins))
se_i = math.sqrt(num) / n
print(f"item-clustered CR0 SE = {se_i*100:.4f} pp -> 95% CI "
      f"[{(pooled-1.96*se_i)*100:.4f}, {(pooled+1.96*se_i)*100:.4f}]")

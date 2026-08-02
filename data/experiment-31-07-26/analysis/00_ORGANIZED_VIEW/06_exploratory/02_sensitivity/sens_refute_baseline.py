#!/usr/bin/env python3
"""
Independent recomputation of the LOO BASELINE claim.

CLAIM under test (analysis set, n=1299 cells):
  pooled delta = -15.5504 pp  (A 89.76% -> B 74.21%)
  247 cells 1->0, 45 cells 0->1, 1007 tie, net -202
  cluster bootstrap 95% CI [-18.81, -12.48] pp, width 6.33
  cluster sign-flip permutation p = 0.00005

Methods implemented from scratch (stdlib only):
  * pooled delta = mean over cells of (B_correct - A_correct)
  * nonparametric CLUSTER bootstrap: resample the 208 clusters with replacement,
    20000 reps, percentile 2.5/97.5 interval
  * cluster-level SIGN-FLIP permutation: each cluster's mean diff contribution
    gets multiplied by +-1, 20000 reps, two-sided,
    p = (1 + #{|t*| >= |t_obs|}) / (1 + B)
"""
import json, random, statistics, sys
from collections import defaultdict, Counter

BASE = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
rows = json.load(open(f"{BASE}/paired_clean.json"))

print(f"TOTAL records loaded: {len(rows)}")

# ---------- integrity of the exclusion bookkeeping ----------
meta = json.load(open(f"{BASE}/dataset_meta.json"))
defect_ids = set(meta["exclusions"]["administrative_legal_out_of_domain"]) | set(
    meta["exclusions"]["adjudicated_key_defect"])

bad_flag = 0
for r in rows:
    want_defect = r["question_id"] in defect_ids
    want_posa = (r["correct_letter"] == "a")
    if r["excl_item_defect"] != want_defect: bad_flag += 1
    if r["excl_nota_position_a"] != want_posa: bad_flag += 1
    if r["analysis_include"] != (not (want_defect or want_posa)): bad_flag += 1
print(f"flag-consistency violations: {bad_flag}")

inc = [r for r in rows if r["analysis_include"]]
print(f"analysis_include==True cells: {len(inc)}")
print(f"distinct items in analysis set: {len({r['question_id'] for r in inc})}")
print(f"distinct clusters in analysis set: {len({r['cluster'] for r in inc})}")
print(f"models: {sorted({r['model'] for r in inc})}")

# every cell must have 0/1 outcomes
vals = Counter((r["A_correct"], r["B_correct"]) for r in inc)
print("2x2 (A,B) table:", dict(vals))

# ---------- point estimate ----------
nA = sum(r["A_correct"] for r in inc)
nB = sum(r["B_correct"] for r in inc)
n = len(inc)
accA = nA / n
accB = nB / n
diffs = [r["B_correct"] - r["A_correct"] for r in inc]
pooled = sum(diffs) / n

b10 = vals[(1, 0)]   # A right, B wrong  -> 1->0
b01 = vals[(0, 1)]   # A wrong, B right  -> 0->1
tie = vals[(1, 1)] + vals[(0, 0)]

print()
print(f"A correct = {nA}  acc = {accA*100:.4f}%")
print(f"B correct = {nB}  acc = {accB*100:.4f}%")
print(f"pooled delta = {pooled*100:.4f} pp")
print(f"flips 1->0 = {b10}   flips 0->1 = {b01}   ties = {tie}   sum={b10+b01+tie}")
print(f"net discordant = {b01 - b10}")

# ---------- cluster structure ----------
by_cluster = defaultdict(list)
for r in inc:
    by_cluster[r["cluster"]].append(r["B_correct"] - r["A_correct"])
clusters = sorted(by_cluster)
K = len(clusters)
csum = {c: sum(v) for c, v in by_cluster.items()}
cn = {c: len(v) for c, v in by_cluster.items()}
print(f"\nclusters K = {K}; cells/cluster min={min(cn.values())} max={max(cn.values())} "
      f"median={statistics.median(cn.values())}")

# ---------- cluster bootstrap, 20000 reps, percentile ----------
B_REP = 20000
SEEDS = [12345, 20260731, 987654321]
sums = [csum[c] for c in clusters]
ns = [cn[c] for c in clusters]

def cluster_boot(seed, reps=B_REP):
    rng = random.Random(seed)
    out = []
    K_ = K
    rr = rng.randrange
    for _ in range(reps):
        s = 0; m = 0
        for _ in range(K_):
            j = rr(K_)
            s += sums[j]; m += ns[j]
        out.append(s / m)
    out.sort()
    lo = out[int(0.025 * reps)]
    hi = out[int(0.975 * reps) - 1] if int(0.975*reps) >= reps else out[int(0.975 * reps)]
    return lo, hi, out

print()
for sd in SEEDS:
    lo, hi, dist = cluster_boot(sd)
    print(f"cluster bootstrap seed={sd}: 95% CI [{lo*100:.4f}, {hi*100:.4f}] pp  "
          f"width={(hi-lo)*100:.4f}  mean*={statistics.mean(dist)*100:.4f}")

# ---------- cluster sign-flip permutation ----------
# t_obs = pooled delta. Under H0 the sign of each cluster's total diff is exchangeable.
def signflip(seed, reps=B_REP):
    rng = random.Random(seed)
    t_obs = pooled
    ge = 0
    tot_n = n
    for _ in range(reps):
        s = 0
        for v in sums:
            s += v if rng.getrandbits(1) else -v
        if abs(s / tot_n) >= abs(t_obs) - 1e-15:
            ge += 1
    return (1 + ge) / (1 + reps), ge

print()
for sd in SEEDS:
    p, ge = signflip(sd)
    print(f"sign-flip permutation seed={sd}: #{{|t*|>=|t_obs|}}={ge}  p={p:.6f}")
print(f"min attainable p with B={B_REP}: {1/(1+B_REP):.6f}")

# ---------- cross-checks on the CI: alternative variance routes ----------
# (a) naive cell-level (ignores clustering) normal CI on McNemar-style difference
import math
var_cell = sum((d - pooled) ** 2 for d in diffs) / (n - 1)
se_naive = math.sqrt(var_cell / n)
print(f"\nnaive (cell iid) SE = {se_naive*100:.4f} pp -> 95% CI "
      f"[{(pooled-1.96*se_naive)*100:.4f}, {(pooled+1.96*se_naive)*100:.4f}]")

# (b) cluster-robust (sandwich / CR0) SE for the mean
nbar = n / K
num = sum((csum[c] - pooled * cn[c]) ** 2 for c in clusters)
se_cr = math.sqrt(num) / n
print(f"cluster-robust (CR0) SE = {se_cr*100:.4f} pp -> 95% CI "
      f"[{(pooled-1.96*se_cr)*100:.4f}, {(pooled+1.96*se_cr)*100:.4f}]")

# (c) design effect
print(f"design effect (var ratio) = {(se_cr/se_naive)**2:.3f}")

# ---------- per-model decomposition ----------
print("\nper-model:")
for m in sorted({r["model"] for r in inc}):
    sub = [r for r in inc if r["model"] == m]
    a = sum(x["A_correct"] for x in sub); b = sum(x["B_correct"] for x in sub)
    print(f"  {m:32s} n={len(sub):4d} A={a/len(sub)*100:6.2f}% B={b/len(sub)*100:6.2f}% "
          f"d={(b-a)/len(sub)*100:8.4f} pp")

# ---------- sanity: is 'cluster' really nested above model? ----------
mult = Counter()
for r in inc:
    mult[(r["cluster"], r["question_id"], r["model"])] += 1
print(f"\nmax cells per (cluster,item,model) = {max(mult.values())} (runs_per_cell=1 expected)")
q2c = defaultdict(set)
for r in rows:
    q2c[r["question_id"]].add(r["cluster"])
print(f"items mapping to >1 cluster: {sum(1 for k,v in q2c.items() if len(v)>1)}")

"""Validation + de-confounding.

1. Cell-level permutation must reproduce the exact McNemar p (same null); confirms
   both implementations.
2. The difficulty gradient in ca_prim_03 stratifies on the OpenRouter arm itself,
   which can manufacture a gradient by regression-to-the-mean. Re-derive it with a
   LEAVE-ONE-MODEL-OUT stratifier: for model m, difficulty is the number of the
   OTHER three models OpenRouter got right. The model's own OR outcome then never
   enters its own stratum assignment.
3. Bootstrap-of-the-exact-test: cluster-resample and recompute the exact McNemar
   p to see how fragile the per-model verdicts are to which cases were sampled.
"""
import json, os, sys, math, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_prim_lib import mcnemar_exact, LCG, percentile

BASE = os.path.dirname(os.path.abspath(__file__))
rows = [r for r in json.load(open(os.path.join(BASE, 'cross_arm_A.json')))
        if r.get('analysis_include')]
MODELS = sorted({r['model'] for r in rows})
SEED = 20260731
out = {}

# ------------------------------------------------ 1. permutation == exact test
print("validation: cell-level permutation vs exact McNemar")
val = {}
for k in MODELS + ['POOLED']:
    sub = rows if k == 'POOLED' else [r for r in rows if r['model'] == k]
    b = sum(1 for r in sub if r['gift_correct'] and not r['or_correct'])
    c = sum(1 for r in sub if r['or_correct'] and not r['gift_correct'])
    ex = mcnemar_exact(b, c)['p_exact']
    rr = LCG(SEED + 11)
    R, ge, base = 200000, 0, abs(b - c)
    d = [1] * b + [-1] * c
    for _ in range(R):
        s = 0
        for x in d:
            s += -x if rr.randbit() else x
        if abs(s) >= base:
            ge += 1
    pm = (ge + 1) / (R + 1)
    val[k] = {"p_exact": ex, "p_permutation_cell": pm, "abs_diff": abs(ex - pm),
              "mc_se": math.sqrt(max(ex * (1 - ex), 1e-12) / R)}
    print(f"  {k:28s} exact={ex:.5f}  perm={pm:.5f}  diff={abs(ex-pm):.5f} "
          f"(MC SE={val[k]['mc_se']:.5f})")
out['permutation_vs_exact'] = val

# ------------------------------- 2. leave-one-model-out difficulty stratifier
or_by_item = collections.defaultdict(dict)
for r in rows:
    or_by_item[r['question_id']][r['model']] = r['or_correct']

print("\nleave-one-model-out difficulty (other 3 models' OpenRouter correctness):")
loo = {}
for k in range(0, 4):
    sub = [r for r in rows
           if sum(v for m2, v in or_by_item[r['question_id']].items() if m2 != r['model']) == k]
    if not sub:
        continue
    g = sum(r['gift_correct'] for r in sub) / len(sub)
    o = sum(r['or_correct'] for r in sub) / len(sub)
    b = sum(1 for r in sub if r['gift_correct'] and not r['or_correct'])
    c = sum(1 for r in sub if r['or_correct'] and not r['gift_correct'])
    ex = mcnemar_exact(b, c)
    loo[f"{k}/3 others correct"] = {
        "n_cells": len(sub), "gift_pct": 100 * g, "or_pct": 100 * o,
        "rd_pp": 100 * (g - o), "b": b, "c": c, "p_exact": ex['p_exact']}
    print(f"  {k}/3 others right: cells={len(sub):5d} GIFT={100*g:6.2f}% OR={100*o:6.2f}% "
          f"RD={100*(g-o):+6.2f}pp  b={b:3d} c={c:3d}  exact p={ex['p_exact']:.5f}")
out['loo_difficulty_gradient'] = loo

# trend test: does RD decline monotonically with difficulty? Permutation on the
# Spearman-style linear trend of the per-cell (gift-or) contrast against stratum.
pairs = []
for r in rows:
    kk = sum(v for m2, v in or_by_item[r['question_id']].items() if m2 != r['model'])
    pairs.append((kk, r['gift_correct'] - r['or_correct']))
kbar = sum(p[0] for p in pairs) / len(pairs)
T_obs = sum((kk - kbar) * d for kk, d in pairs)
rr = LCG(SEED + 12)
R, ge = 100000, 0
nz = [(kk - kbar, d) for kk, d in pairs if d != 0]
for _ in range(R):
    s = 0.0
    for w, d in nz:
        s += w * (-d if rr.randbit() else d)
    if abs(s) >= abs(T_obs) - 1e-9:
        ge += 1
out['difficulty_trend_test'] = {
    "statistic": T_obs, "p_permutation_arm_swap": (ge + 1) / (R + 1), "R": R,
    "note": "arm label swapped within cell; tests whether the GIFT-minus-OR "
            "contrast covaries with leave-one-model-out item difficulty"}
print(f"  trend of RD vs difficulty: T={T_obs:.1f}  perm p={(ge+1)/(R+1):.6f}")

# ------------------------------------ 3. cluster-bootstrap of the exact verdict
by_cluster = collections.defaultdict(list)
for r in rows:
    by_cluster[r['cluster']].append(r)
CL = sorted(by_cluster)
clus = [by_cluster[c] for c in CL]
K = len(clus)
rng = LCG(SEED + 13)
B = 5000
frag = {m: {"p_le_05": 0, "sign_pos": 0, "ps": []} for m in MODELS + ['POOLED']}
for _ in range(B):
    samp = []
    for _ in range(K):
        samp.extend(clus[rng.randrange(K)])
    for m in MODELS + ['POOLED']:
        sub = samp if m == 'POOLED' else [r for r in samp if r['model'] == m]
        b = sum(1 for r in sub if r['gift_correct'] and not r['or_correct'])
        c = sum(1 for r in sub if r['or_correct'] and not r['gift_correct'])
        p = mcnemar_exact(b, c)['p_exact']
        frag[m]['ps'].append(p)
        frag[m]['p_le_05'] += (p <= 0.05)
        frag[m]['sign_pos'] += (b > c)
res = {}
for m in MODELS + ['POOLED']:
    ps = sorted(frag[m]['ps'])
    res[m] = {"pct_replicates_p<=0.05": 100 * frag[m]['p_le_05'] / B,
              "pct_replicates_gift_ahead": 100 * frag[m]['sign_pos'] / B,
              "median_p": percentile(ps, 0.5),
              "p_95th": percentile(ps, 0.95)}
    print(f"  {m:28s} replicates with exact p<=.05: {res[m]['pct_replicates_p<=0.05']:5.1f}%  "
          f"GIFT ahead in {res[m]['pct_replicates_gift_ahead']:5.1f}%  median p={res[m]['median_p']:.4f}")
out['bootstrap_stability_of_exact_verdict'] = {"B": B, "per_model": res}

json.dump(out, open(os.path.join(BASE, 'ca_prim_04_validate.json'), 'w'), indent=1, default=str)
print("\nwrote ca_prim_04_validate.json")

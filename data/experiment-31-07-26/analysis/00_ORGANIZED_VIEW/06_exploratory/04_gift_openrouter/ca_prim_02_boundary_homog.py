"""(a) Correct boundary handling of the bootstrap p-value (gemini b=0).
(b) Homogeneity of the GIFT effect across the four models.
(c) Exact power floor at each model's observed discordant count.
"""
import json, os, sys, math, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_prim_lib import (mcnemar_exact, LCG, percentile, binom_pmf_half,
                         binom_cdf_half, chi2_sf_1df)

BASE = os.path.dirname(os.path.abspath(__file__))
rows = [r for r in json.load(open(os.path.join(BASE, 'cross_arm_A.json')))
        if r.get('analysis_include')]
MODELS = sorted({r['model'] for r in rows})
CLUSTERS = sorted({r['cluster'] for r in rows})
SEED, B = 20260731, 20000
out = {}

subsets = {m: [r for r in rows if r['model'] == m] for m in MODELS}
subsets['POOLED'] = rows
KEYS = MODELS + ['POOLED']

by_cluster = collections.defaultdict(list)
for r in rows:
    by_cluster[r['cluster']].append(r)
clus = [by_cluster[c] for c in CLUSTERS]
pre = {k: [((sum(x['gift_correct'] for x in (cl if k == 'POOLED' else [y for y in cl if y['model'] == k])),
             sum(x['or_correct'] for x in (cl if k == 'POOLED' else [y for y in cl if y['model'] == k])),
             len(cl if k == 'POOLED' else [y for y in cl if y['model'] == k])))[0:3]
           for cl in clus] for k in KEYS}

K = len(clus)
rng = LCG(SEED)
draws = [[rng.randrange(K) for _ in range(K)] for _ in range(B)]
boot = {k: [] for k in KEYS}
for idxs in draws:
    for k in KEYS:
        arr = pre[k]
        gs = os_ = ns = 0
        for i in idxs:
            g, o, n = arr[i]
            gs += g; os_ += o; ns += n
        boot[k].append((gs - os_) / ns if ns else 0.0)

# ------------------------------------------------- (a) boundary diagnostics
bd = {}
for k in KEYS:
    bs = boot[k]
    n_lt = sum(1 for v in bs if v < 0)
    n_eq = sum(1 for v in bs if v == 0)
    n_gt = sum(1 for v in bs if v > 0)
    # correct interval-inversion p: both tails must INCLUDE the atom at 0
    p_correct = min(1.0, 2 * min(n_lt + n_eq, n_gt + n_eq) / len(bs))
    # the naive version that excludes the atom from the upper tail
    p_naive = min(1.0, 2 * min(n_lt + n_eq, n_gt) / len(bs))
    bd[k] = {"frac_below_0": n_lt / len(bs), "atom_at_exactly_0": n_eq / len(bs),
             "frac_above_0": n_gt / len(bs),
             "p_boot_inverted_correct": p_correct,
             "p_boot_inverted_naive_wrong": p_naive}
    print(f"{k:28s} boot mass  <0={n_lt/len(bs):.4f}  ==0={n_eq/len(bs):.4f}  "
          f">0={n_gt/len(bs):.4f}   p_correct={p_correct:.4f} (naive={p_naive:.4f})")
out['bootstrap_boundary'] = bd

# ------------------------------------------- (c) exact attainable p-value floor
floors = {}
for k in KEYS:
    b = sum(1 for r in subsets[k] if r['gift_correct'] and not r['or_correct'])
    c = sum(1 for r in subsets[k] if r['or_correct'] and not r['gift_correct'])
    n = b + c
    ex = mcnemar_exact(b, c)
    floors[k] = {"b": b, "c": c, "n_disc": n,
                 "min_attainable_two_sided_p": ex['min_attainable_p'],
                 "can_ever_reach_0.05": ex['min_attainable_p'] <= 0.05,
                 "min_n_disc_for_p_le_0.05": 6,   # 2*(1/2)^n <= .05  =>  n >= 6
                 "p_exact": ex['p_exact']}
    print(f"{k:28s} n_disc={n:3d}  floor p={ex['min_attainable_p']:.4f}  "
          f"can reach .05: {ex['min_attainable_p']<=0.05}")
out['exact_power_floor'] = floors

# ------------------------------------------------ (b) homogeneity across models
# Conditional on each model's discordant count n_i, test H0: common pi.
bs_ = [sum(1 for r in subsets[m] if r['gift_correct'] and not r['or_correct']) for m in MODELS]
ns_ = [sum(1 for r in subsets[m] if r['gift_correct'] != r['or_correct']) for m in MODELS]
pi_hat = sum(bs_) / sum(ns_)
stat_obs = sum((b - n * pi_hat) ** 2 / (n * pi_hat * (1 - pi_hat)) for b, n in zip(bs_, ns_) if n)
# parametric bootstrap under the common-pi null (exact conditional reference)
rr = LCG(SEED + 77)
R = 200000
ge = 0
for _ in range(R):
    s = 0.0
    for n in ns_:
        b = sum(1 for _ in range(n) if (rr.next() >> 11) / float(1 << 53) < pi_hat)
        s += (b - n * pi_hat) ** 2 / (n * pi_hat * (1 - pi_hat))
    if s >= stat_obs - 1e-12:
        ge += 1
p_homog = (ge + 1) / (R + 1)
out['homogeneity_of_discordant_pi'] = {
    "b_per_model": dict(zip(MODELS, bs_)), "n_disc_per_model": dict(zip(MODELS, ns_)),
    "pi_hat_common": pi_hat, "statistic": stat_obs,
    "p_parametric_bootstrap": p_homog, "R": R,
    "p_asymptotic_chi2_3df": chi2_sf_1df(stat_obs) if False else None}
# proper 3-df chi-square survival via series (stdlib)
def chi2_sf_3df(x):
    # 1 - P(3df <= x) = erfc(sqrt(x/2)) + sqrt(2x/pi)*exp(-x/2)
    return math.erfc(math.sqrt(x / 2.0)) + math.sqrt(2 * x / math.pi) * math.exp(-x / 2.0)
out['homogeneity_of_discordant_pi']['p_asymptotic_chi2_3df'] = chi2_sf_3df(stat_obs)
print(f"\nhomogeneity of discordant pi across 4 models: Q={stat_obs:.3f} "
      f"p_paramboot={p_homog:.5f}  p_chi2_3df={chi2_sf_3df(stat_obs):.5f}  pi_common={pi_hat:.4f}")

# also: permutation test of heterogeneity in the RISK DIFFERENCE across models,
# resampling clusters (does the sign reversal survive clustering?)
rds = {m: (sum(r['gift_correct'] for r in subsets[m]) - sum(r['or_correct'] for r in subsets[m])) / len(subsets[m])
       for m in MODELS}
spread_obs = max(rds.values()) - min(rds.values())
bootspread = []
for idxs in draws:
    vals = []
    for m in MODELS:
        arr = pre[m]
        gs = os_ = ns = 0
        for i in idxs:
            g, o, n = arr[i]
            gs += g; os_ += o; ns += n
        vals.append((gs - os_) / ns)
    bootspread.append(max(vals) - min(vals))
bootspread.sort()
out['rd_spread_across_models'] = {
    "rd_pp": {m: 100 * v for m, v in rds.items()},
    "observed_spread_pp": 100 * spread_obs,
    "cluster_boot_ci_pp": (100 * percentile(bootspread, 0.025),
                           100 * percentile(bootspread, 0.975))}
print(f"RD spread across models = {100*spread_obs:.2f}pp  "
      f"cluster-boot 95% CI ({100*percentile(bootspread,0.025):.2f}, "
      f"{100*percentile(bootspread,0.975):.2f})")

# gemma-vs-qwen contrast (largest gap), cluster bootstrap on the difference
diffs = []
for idxs in draws:
    v = []
    for m in ['google/gemma-4-26b-a4b-it', 'qwen/qwen3.6-35b-a3b']:
        arr = pre[m]
        gs = os_ = ns = 0
        for i in idxs:
            g, o, n = arr[i]
            gs += g; os_ += o; ns += n
        v.append((gs - os_) / ns)
    diffs.append(v[0] - v[1])
diffs.sort()
n_le = sum(1 for v in diffs if v <= 0)
out['contrast_gemma_minus_qwen'] = {
    "point_pp": 100 * (rds['google/gemma-4-26b-a4b-it'] - rds['qwen/qwen3.6-35b-a3b']),
    "cluster_boot_ci_pp": (100 * percentile(diffs, 0.025), 100 * percentile(diffs, 0.975)),
    "p_boot": min(1.0, 2 * min(n_le, len(diffs) - n_le) / len(diffs))}
print("gemma - qwen RD contrast:", out['contrast_gemma_minus_qwen'])

json.dump(out, open(os.path.join(BASE, 'ca_prim_02_boundary_homog.json'), 'w'), indent=1, default=str)
print("\nwrote ca_prim_02_boundary_homog.json")

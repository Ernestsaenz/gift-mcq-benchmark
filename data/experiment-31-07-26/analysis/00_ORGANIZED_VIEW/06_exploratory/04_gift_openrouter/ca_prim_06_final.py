"""Final robustness: model-as-unit test, leave-one-cluster-out influence,
and a consolidated summary table."""
import json, os, sys, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_prim_lib import mcnemar_exact, binom_cdf_half, binom_sf_half

BASE = os.path.dirname(os.path.abspath(__file__))
rows = [r for r in json.load(open(os.path.join(BASE, 'cross_arm_A.json')))
        if r.get('analysis_include')]
MODELS = sorted({r['model'] for r in rows})
out = {}

# ------------------------------------------------------- model as the unit
rds = {}
for m in MODELS:
    s = [r for r in rows if r['model'] == m]
    rds[m] = (sum(r['gift_correct'] for r in s) - sum(r['or_correct'] for r in s)) / len(s)
pos = sum(1 for v in rds.values() if v > 0)
neg = sum(1 for v in rds.values() if v < 0)
sign_p = mcnemar_exact(pos, neg)['p_exact']
out['model_as_unit_sign_test'] = {
    "rd_pp": {m: 100 * v for m, v in rds.items()},
    "models_favouring_gift": pos, "models_favouring_openrouter": neg,
    "exact_sign_test_p": sign_p,
    "note": "treats each model as one exchangeable unit; 4 units cannot reach "
            "p<=0.05 (floor = 2*(1/2)^4 = 0.125) even if all four agreed"}
print(f"model-as-unit: {pos} models favour GIFT, {neg} favour OpenRouter -> exact sign p={sign_p:.4f}")
print(f"  (with only 4 models the smallest attainable two-sided p is "
      f"{mcnemar_exact(4,0)['p_exact']:.4f}, so this test is unpowered by design)")

# ---------------------------------------------- leave-one-cluster-out influence
by_cluster = collections.defaultdict(list)
for r in rows:
    by_cluster[r['cluster']].append(r)
CL = sorted(by_cluster)
infl = {}
for k in ['POOLED'] + MODELS:
    base_sub = rows if k == 'POOLED' else [r for r in rows if r['model'] == k]
    b0 = sum(1 for r in base_sub if r['gift_correct'] and not r['or_correct'])
    c0 = sum(1 for r in base_sub if r['or_correct'] and not r['gift_correct'])
    p0 = mcnemar_exact(b0, c0)['p_exact']
    worst_p, worst_c, worst_rd, best_rd = p0, None, None, None
    rd0 = (sum(r['gift_correct'] for r in base_sub) - sum(r['or_correct'] for r in base_sub)) / len(base_sub)
    rmin, rmax = rd0, rd0
    for cl in CL:
        sub = [r for r in base_sub if r['cluster'] != cl]
        if not sub:
            continue
        b = sum(1 for r in sub if r['gift_correct'] and not r['or_correct'])
        c = sum(1 for r in sub if r['or_correct'] and not r['gift_correct'])
        p = mcnemar_exact(b, c)['p_exact']
        rd = (sum(r['gift_correct'] for r in sub) - sum(r['or_correct'] for r in sub)) / len(sub)
        if p > worst_p:
            worst_p, worst_c = p, cl
        rmin = min(rmin, rd); rmax = max(rmax, rd)
    infl[k] = {"p_full": p0, "worst_case_p_after_dropping_one_cluster": worst_p,
               "cluster_dropped": worst_c,
               "rd_range_pp": (100 * rmin, 100 * rmax),
               "still_p<=0.05_after_any_single_cluster_drop": worst_p <= 0.05}
    print(f"{k:28s} p_full={p0:.5f}  worst p after dropping any 1 of 183 clusters="
          f"{worst_p:.5f} (cluster {worst_c})  RD range=({100*rmin:+.2f},{100*rmax:+.2f})pp")
out['leave_one_cluster_out'] = infl

json.dump(out, open(os.path.join(BASE, 'ca_prim_06_final.json'), 'w'), indent=1, default=str)
print("\nwrote ca_prim_06_final.json")

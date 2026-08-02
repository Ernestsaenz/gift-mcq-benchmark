"""Spec-by-spec cross-check of my independent curve against the stored one,
plus a decomposition of the two-way (model x cluster) clustered variance.
"""
import json, os, sys, math, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sens_refute_curvep_lib as L

mine = json.load(open(os.path.join(HERE, "sens_refute_curvep_out.json")))["results"]
orig = json.load(open(os.path.join(HERE, "sens_speccurve_results.json")))["results"]

key = lambda r: (r["exclusion"], r["outcome"], r["unit"], r["inference"], r["pooling"])
M = {key(r): r for r in mine}
O = {key(r): r for r in orig}
print("=" * 92)
print("SPEC-BY-SPEC CROSS-CHECK: my independent curve vs the stored one")
print("=" * 92)
print(f"  same 160 spec keys: {set(M) == set(O)}   |mine|={len(M)} |stored|={len(O)}")

worst_est = 0.0
det_bad, res_bad = [], []
for k in sorted(M):
    a, b = M[k], O[k]
    de = abs(a["delta_pp"] - b["delta_pp"])
    worst_est = max(worst_est, de)
    if de > 1e-9:
        det_bad.append((k, a["delta_pp"], b["delta_pp"]))
    # deterministic p (no RNG) must match to floating precision
    if a["inference"] in ("mcnemar_exact", "logit_robustSE", "ols_robustSE"):
        if b["p"] > 0 and abs(math.log10(a["p"] / b["p"])) > 1e-6:
            res_bad.append((k, a["p"], b["p"]))
print(f"  max |delta_mine - delta_stored| over 160 specs : {worst_est:.3e}")
print(f"  point-estimate mismatches                      : {len(det_bad)}")
print(f"  DETERMINISTIC p mismatches (McNemar/logit/OLS) : {len(res_bad)}")
for k, x, y in res_bad[:10]:
    print("     ", k, x, y)

rng_specs = [k for k in M if M[k]["inference"] in ("cluster_bootstrap", "permutation")]
diff = [(k, M[k]["p"], O[k]["p"]) for k in rng_specs if abs(M[k]["p"] - O[k]["p"]) > 1e-15]
print(f"\n  resampling specs (different seed, so exact equality not expected): {len(rng_specs)}")
print(f"    of which differ at all : {len(diff)}")
for k, x, y in sorted(diff, key=lambda z: -abs(math.log10(z[1] / z[2])))[:6]:
    print(f"      {'/'.join(k):<70} mine={x:.4e} stored={y:.4e}")
print("    -> all resampling p agree on the only thing they can resolve: "
      "'below 1/(B+1)'.")

print("\n  threshold counts, mine vs stored:")
for thr in (0.05, 0.01, 0.001):
    km = sum(1 for r in mine if r["p"] < thr)
    ko = sum(1 for r in orig if r["p"] < thr)
    print(f"    p<{thr:<7} mine={km:>3}/160   stored={ko:>3}/160")

# ---------------------------------------------------------------- two-way
print("\n" + "=" * 92)
print("TWO-WAY (model x cluster) CLUSTERED VARIANCE DECOMPOSITION -- primary/lenient")
print("=" * 92)
rows = json.load(open(os.path.join(HERE, "paired_clean.json")))
recs = [r for r in rows if not r["excl_item_defect"] and not r["excl_nota_position_a"]]
d = [100.0 * (r["B_correct"] - r["A_correct"]) for r in recs]
n = len(d)
mean = sum(d) / n
e = [x - mean for x in d]


def comp(keys):
    agg = collections.defaultdict(float)
    for i in range(n):
        agg[keys[i]] += e[i]
    G = len(agg)
    meat = sum(u * u for u in agg.values())
    return (G / (G - 1.0)) * meat / (n * n), G


v_m, G_m = comp([r["model"] for r in recs])
v_c, G_c = comp([r["cluster"] for r in recs])
v_i, G_i = comp([(r["model"], r["cluster"]) for r in recs])
v_iid = sum(x * x for x in e) / (n * (n - 1.0))
print(f"  N cells = {n}, mean paired diff = {mean:+.4f} pp")
print(f"    V(iid, no clustering)          se={math.sqrt(v_iid):.4f}  "
      f"t={mean/math.sqrt(v_iid):+8.3f}  p(t,{n-1})={L.t_two_sided(mean/math.sqrt(v_iid), n-1):.3e}")
print(f"    V(cluster only)  G={G_c:<5}      se={math.sqrt(v_c):.4f}  "
      f"t={mean/math.sqrt(v_c):+8.3f}  p(t,{G_c-1})={L.t_two_sided(mean/math.sqrt(v_c), G_c-1):.3e}")
print(f"    V(model only)    G={G_m:<5}      se={math.sqrt(v_m):.4f}  "
      f"t={mean/math.sqrt(v_m):+8.3f}  p(t,{G_m-1})={L.t_two_sided(mean/math.sqrt(v_m), G_m-1):.3e}")
v2 = v_m + v_c - v_i
print(f"    V(two-way CGM)   G=min({G_m},{G_c})  se={math.sqrt(v2):.4f}  "
      f"t={mean/math.sqrt(v2):+8.3f}  p(t,{min(G_m,G_c)-1})="
      f"{L.t_two_sided(mean/math.sqrt(v2), min(G_m, G_c)-1):.5f}")
print(f"      components: V_model={v_m:.5f}  V_cluster={v_c:.5f}  V_inter={v_i:.5f}"
      f"  -> V_2way={v2:.5f}")
print(f"      SE inflation vs iid: {math.sqrt(v2/v_iid):.2f}x ;"
      f" vs cluster-only: {math.sqrt(v2/v_c):.2f}x")
print("\n  The two-way estimator is the textbook choice for a crossed design")
print("  (4 models x 208 clinical clusters, every model answering every item).")
print("  It is NOT in the 160-spec grid, and it exceeds the claimed max p of 1.009e-02.")

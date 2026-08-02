"""INDEPENDENT recomputation of the specification curve point estimates.

Nothing is imported from sens_speccurve.py / sens_speccurve_lib.py.  Every
aggregation is re-derived from paired_clean.json directly.

Estimand (as claimed): delta = acc(B) - acc(A) in percentage points, aggregated
at the chosen unit.

Units re-implemented from the verbal definition, not from the original code:
  cell     : pooled over all paired cells,  100*(sum B - sum A)/N
  item     : mean over items of the item-level mean difference
  cluster  : mean over clusters of the cluster-level cell-weighted difference
  model    : unweighted mean of the 4 per-model cell-level deltas
  sepclust : unweighted mean of the 4 per-model cluster-averaged deltas
"""
import json, os, statistics, collections

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "paired_clean.json")))
MODELS = sorted({r["model"] for r in rows})

# ---- the strict-outcome extra cell, rebuilt independently -------------------
_b320 = [r for r in rows if r["question_id"] == "b320"][0]
STRICT_EXTRA = dict(question_id="b320", model="z-ai/glm-5.2", cluster=_b320["cluster"],
                    correct_letter=_b320["correct_letter"], A_correct=0, B_correct=1,
                    excl_item_defect=False, excl_nota_position_a=False)

KEEP = {
    "primary":     lambda r: (not r["excl_item_defect"]) and (not r["excl_nota_position_a"]),
    "defect_only": lambda r: not r["excl_item_defect"],
    "notaA_only":  lambda r: not r["excl_nota_position_a"],
    "none":        lambda r: True,
}


def subset(exclusion, outcome):
    base = rows + ([STRICT_EXTRA] if outcome == "strict" else [])
    return [r for r in base if KEEP[exclusion](r)]


def mean(xs):
    return sum(xs) / len(xs)


def estimates(recs):
    """Return the five distinct point estimates, computed from first principles."""
    out = {}
    # --- cell
    out["cell"] = 100.0 * (sum(r["B_correct"] for r in recs)
                           - sum(r["A_correct"] for r in recs)) / len(recs)
    # --- item
    byit = collections.defaultdict(list)
    for r in recs:
        byit[r["question_id"]].append(r)
    item_d = [100.0 * mean([x["B_correct"] - x["A_correct"] for x in v]) for v in byit.values()]
    out["item"] = mean(item_d)
    # --- cluster
    bycl = collections.defaultdict(list)
    for r in recs:
        bycl[r["cluster"]].append(r)
    clu_d = [100.0 * mean([x["B_correct"] - x["A_correct"] for x in v]) for v in bycl.values()]
    out["cluster"] = mean(clu_d)
    # --- model (unweighted mean of per-model cell deltas)
    pm_cell = []
    pm_clu = []
    for m in MODELS:
        mr = [r for r in recs if r["model"] == m]
        pm_cell.append(100.0 * mean([x["B_correct"] - x["A_correct"] for x in mr]))
        g = collections.defaultdict(list)
        for r in mr:
            g[r["cluster"]].append(r)
        pm_clu.append(mean([100.0 * mean([x["B_correct"] - x["A_correct"] for x in v])
                            for v in g.values()]))
    out["model"] = mean(pm_cell)
    out["sepclust"] = mean(pm_clu)
    out["_pm_cell"] = pm_cell
    out["_pm_clu"] = pm_clu
    out["n_cells"] = len(recs)
    out["n_items"] = len(byit)
    out["n_clusters"] = len(bycl)
    out["accA"] = 100.0 * mean([r["A_correct"] for r in recs])
    out["accB"] = 100.0 * mean([r["B_correct"] for r in recs])
    return out


mine = {}
print(f"{'exclusion':<12} {'outcome':<8} {'N':>5} {'items':>5} {'clus':>5} "
      f"{'accA':>7} {'accB':>7} {'cell':>9} {'item':>9} {'cluster':>9} {'model':>9} {'sepclu':>9}")
for ex in ("primary", "defect_only", "notaA_only", "none"):
    for oc in ("lenient", "strict"):
        e = estimates(subset(ex, oc))
        mine[(ex, oc)] = e
        print(f"{ex:<12} {oc:<8} {e['n_cells']:>5} {e['n_items']:>5} {e['n_clusters']:>5} "
              f"{e['accA']:>7.3f} {e['accB']:>7.3f} {e['cell']:>9.4f} {e['item']:>9.4f} "
              f"{e['cluster']:>9.4f} {e['model']:>9.4f} {e['sepclust']:>9.4f}")

# ---------------------------------------------------------------------------
# Cross-check against the stored spec-curve output, spec by spec.
# ---------------------------------------------------------------------------
stored = json.load(open(os.path.join(HERE, "sens_speccurve_results.json")))
res = stored["results"]
print("\nstored n_specs =", stored["n_specs"], " len(results) =", len(res))

UNITMAP = {("cell", "pooled"): "cell", ("item", "pooled"): "item",
           ("cluster", "pooled"): "cluster", ("model", "pooled"): "model",
           ("cell", "separate"): "model", ("cluster", "separate"): "sepclust"}

worst = 0.0
mismatch = []
for r in res:
    key = UNITMAP[(r["unit"], r["pooling"])]
    ref = mine[(r["exclusion"], r["outcome"])][key]
    d = abs(ref - r["delta_pp"])
    worst = max(worst, d)
    if d > 1e-9:
        mismatch.append((r["exclusion"], r["outcome"], r["unit"], r["pooling"], r["delta_pp"], ref))
print("max |stored - independent| over all 160 specs:", worst)
print("mismatched specs:", len(mismatch))
for m in mismatch[:20]:
    print("   ", m)

ests = [r["delta_pp"] for r in res]
ests_sorted = sorted(ests)


def pctl(v, q):
    # linear interpolation, same convention as a standard quartile
    n = len(v)
    h = (n - 1) * q
    lo = int(h)
    hi = min(lo + 1, n - 1)
    return v[lo] + (h - lo) * (v[hi] - v[lo])


print("\n--- distribution of the 160 stored point estimates ---")
print("n negative      :", sum(1 for e in ests if e < 0))
print("n zero/positive :", sum(1 for e in ests if e >= 0))
print("min             :", min(ests))
print("max             :", max(ests))
print("span            :", max(ests) - min(ests))
print("median          :", statistics.median(ests))
print("mean            :", statistics.mean(ests))
print("Q1 / Q3 (linear):", pctl(ests_sorted, 0.25), pctl(ests_sorted, 0.75))
print("distinct (1e-9) :", len({round(e, 9) for e in ests}))

# recount distinct from MY estimates, replicated at the stored multiplicities
mult = collections.Counter((r["exclusion"], r["outcome"], UNITMAP[(r["unit"], r["pooling"])])
                           for r in res)
myests = []
for (ex, oc, k), c in mult.items():
    myests.extend([mine[(ex, oc)][k]] * c)
print("\nindependent curve: n =", len(myests),
      " neg =", sum(1 for e in myests if e < 0),
      " min =", min(myests), " max =", max(myests),
      " span =", max(myests) - min(myests),
      " distinct =", len({round(e, 9) for e in myests}))

# --- p-values --------------------------------------------------------------
ps = [r["p"] for r in res]
print("\n--- p-values across the 160 specs ---")
print("max p:", max(ps), " n p>=0.05:", sum(1 for p in ps if p >= 0.05),
      " n p>=0.01:", sum(1 for p in ps if p >= 0.01))
for r in sorted(res, key=lambda x: -x["p"])[:6]:
    print(f"   p={r['p']:.4g}  {r['exclusion']}/{r['outcome']} {r['unit']}/{r['inference']}/{r['pooling']} delta={r['delta_pp']:.3f}")

# --- grid completeness -----------------------------------------------------
combos = collections.Counter((r["unit"], r["inference"], r["pooling"]) for r in res)
print("\n--- distinct unit x inference x pooling combos ---")
for k, v in sorted(combos.items()):
    print("   ", k, v)
print("n pooled combos  :", len({k for k in combos if k[2] == 'pooled'}))
print("n separate combos:", len({k for k in combos if k[2] == 'separate'}))

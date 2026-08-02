#!/usr/bin/env python3
"""Independent recomputation of the 'cluster variable is degenerate' claim.
Stdlib only. Writes nothing but stdout."""
import json, math, statistics as st
from collections import Counter, defaultdict

P = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
rows = json.load(open(P))
inc = [r for r in rows if r["analysis_include"] is True]

print("=== 0. SHAPE ===")
print("all records          :", len(rows))
print("analysis_include=True:", len(inc))
items = {r["question_id"] for r in inc}
clusters = {r["cluster"] for r in inc}
models = {r["model"] for r in inc}
print("items   :", len(items))
print("clusters:", len(clusters))
print("models  :", len(models))

# --- cluster field sanity: type, sentinel values, null handling ---
print("\n=== 1. CLUSTER FIELD SANITY ===")
types = Counter(type(r["cluster"]).__name__ for r in inc)
print("cluster value types:", dict(types))
cl_sorted = sorted(clusters, key=lambda x: (x is None, x))
print("min cluster id:", cl_sorted[0], " max cluster id:", cl_sorted[-1])
print("n distinct ids:", len(cl_sorted))
print("ids 0..30 present:", [c for c in cl_sorted if isinstance(c, int) and c <= 30])
print("contiguous 0..N-1?:", cl_sorted == list(range(len(cl_sorted))))
missing = [c for c in range(max(c for c in cl_sorted if isinstance(c, int)) + 1) if c not in clusters]
print("gaps in integer range:", missing[:20], "...(n=%d)" % len(missing))
# is cluster unique per item, i.e. does one item ever span two clusters?
it2cl = defaultdict(set)
for r in inc:
    it2cl[r["question_id"]].add(r["cluster"])
bad = {k: v for k, v in it2cl.items() if len(v) > 1}
print("items mapping to >1 cluster:", len(bad))

# --- items per cluster ---
print("\n=== 2. ITEMS PER CLUSTER ===")
cl2items = defaultdict(set)
for r in inc:
    cl2items[r["cluster"]].add(r["question_id"])
sizes = sorted((len(v) for v in cl2items.values()))
n = len(sizes)
print("n clusters:", n, " total items:", sum(sizes))


def quantile_type7(x, q):
    """R type-7 / numpy default linear interpolation."""
    x = sorted(x)
    if len(x) == 1:
        return float(x[0])
    h = (len(x) - 1) * q
    lo = math.floor(h)
    hi = math.ceil(h)
    return x[lo] + (h - lo) * (x[hi] - x[lo])


print("min=%d q1=%g median=%g q3=%g max=%d"
      % (sizes[0], quantile_type7(sizes, .25), quantile_type7(sizes, .5),
         quantile_type7(sizes, .75), sizes[-1]))
mean = sum(sizes) / n
print("mean=%.6f" % mean)
print("sd(sample,n-1)=%.6f   sd(pop,n)=%.6f"
      % (st.stdev(sizes), st.pstdev(sizes)))
hist = Counter(sizes)
print("histogram:", dict(sorted(hist.items())))
print("hist sums -> clusters=%d items=%d" % (sum(hist.values()), sum(k * v for k, v in hist.items())))

singletons = [c for c, v in cl2items.items() if len(v) == 1]
multis = [c for c, v in cl2items.items() if len(v) > 1]
n_multi_items = sum(len(cl2items[c]) for c in multis)
print("\nsingleton clusters : %d  (%.4f%% of clusters, %.4f%% of items)"
      % (len(singletons), 100 * len(singletons) / n, 100 * len(singletons) / sum(sizes)))
print("multi-item clusters: %d  holding %d items (%.4f%% of items)"
      % (len(multis), n_multi_items, 100 * n_multi_items / sum(sizes)))
print("multi cluster (id,n_items) desc:",
      sorted(((c, len(cl2items[c])) for c in multis), key=lambda t: (-t[1], t[0])))

# --- cells per cluster ---
print("\n=== 3. CELLS PER CLUSTER ===")
cl2cells = Counter(r["cluster"] for r in inc)
cs = sorted(cl2cells.values())
print("min=%d q1=%g median=%g q3=%g max=%d mean=%.6f sd(n-1)=%.6f sd(n)=%.6f"
      % (cs[0], quantile_type7(cs, .25), quantile_type7(cs, .5), quantile_type7(cs, .75),
         cs[-1], sum(cs) / len(cs), st.stdev(cs), st.pstdev(cs)))
print("cells-per-cluster histogram:", dict(sorted(Counter(cs).items())))

multi_cells = [r for r in inc if r["cluster"] in set(multis)]
sing_cells = [r for r in inc if r["cluster"] in set(singletons)]
print("cells in multi-item clusters :", len(multi_cells))
print("cells in singleton clusters  :", len(sing_cells))

# --- the "exactly the clinical vignettes" claim, BOTH directions ---
print("\n=== 4. 'EXACTLY THE CLINICAL VIGNETTES' (both directions) ===")
print("-- multi-item cluster cells --")
print("  has_context counts:", dict(Counter(r["has_context"] for r in multi_cells)))
print("  exam_part counts  :", dict(Counter(r["exam_part"] for r in multi_cells)))
print("-- singleton cluster cells --")
print("  has_context counts:", dict(Counter(r["has_context"] for r in sing_cells)))
sing_ctx = [r for r in sing_cells if r["has_context"]]
print("  singleton cells WITH has_context=True:", len(sing_ctx))
print("  their exam_part counts:", dict(Counter(r["exam_part"] for r in sing_ctx)))
sing_ctx_items = {r["question_id"] for r in sing_ctx}
print("  singleton ITEMS with has_context=True:", len(sing_ctx_items))
sing_ctx_cl = {r["cluster"] for r in sing_ctx}
print("  singleton CLUSTERS with has_context=True:", len(sing_ctx_cl), sorted(sing_ctx_cl)[:30])

# caso-* family across the whole pool
print("\n-- exam_part 'caso' family across whole analysis pool --")
ep = Counter(r["exam_part"] for r in inc)
print("  all exam_part values:", dict(sorted(ep.items(), key=lambda t: -t[1])))
caso_cells = [r for r in inc if isinstance(r["exam_part"], str) and r["exam_part"].startswith("caso")]
caso_items = {r["question_id"] for r in caso_cells}
caso_cl = {r["cluster"] for r in caso_cells}
print("  caso-* cells:", len(caso_cells), " items:", len(caso_items), " clusters:", len(caso_cl))
caso_cl_sizes = Counter(len(cl2items[c]) for c in caso_cl)
print("  size distribution of caso-* clusters:", dict(sorted(caso_cl_sizes.items())))
caso_singleton_cl = [c for c in caso_cl if len(cl2items[c]) == 1]
print("  caso-* clusters that are SINGLETONS:", len(caso_singleton_cl), sorted(caso_singleton_cl))

# has_context across whole pool
ctx_items = {r["question_id"] for r in inc if r["has_context"]}
ctx_cl = {r["cluster"] for r in inc if r["has_context"]}
print("\n  has_context=True: cells=%d items=%d clusters=%d"
      % (sum(1 for r in inc if r["has_context"]), len(ctx_items), len(ctx_cl)))
print("  of those clusters, singletons:", sum(1 for c in ctx_cl if len(cl2items[c]) == 1))

# --- qlen ---
print("\n=== 5. STEM LENGTH (qlen) ===")


def summ(label, vals):
    vals = sorted(vals)
    print("  %-34s n=%4d mean=%9.3f median=%8.1f min=%d max=%d"
          % (label, len(vals), sum(vals) / len(vals), quantile_type7(vals, .5), vals[0], vals[-1]))


summ("multi-item clusters, per CELL", [r["qlen"] for r in multi_cells])
summ("singleton clusters, per CELL", [r["qlen"] for r in sing_cells])
# per-item (de-duplicated across the 4 models)
it_qlen = {}
it_cl = {}
for r in inc:
    it_qlen[r["question_id"]] = r["qlen"]
    it_cl[r["question_id"]] = r["cluster"]
ms = set(multis)
summ("multi-item clusters, per ITEM", [q for i, q in it_qlen.items() if it_cl[i] in ms])
summ("singleton clusters, per ITEM", [q for i, q in it_qlen.items() if it_cl[i] not in ms])
# qlen constant within item across models?
iq = defaultdict(set)
for r in inc:
    iq[r["question_id"]].add(r["qlen"])
print("  items with non-constant qlen across models:", sum(1 for v in iq.values() if len(v) > 1))

# --- accuracy ---
print("\n=== 6. ACCURACY BY CLUSTER TYPE ===")
for lab, cells in (("multi-item", multi_cells), ("singleton", sing_cells)):
    a = sum(r["A_correct"] for r in cells) / len(cells)
    b = sum(r["B_correct"] for r in cells) / len(cells)
    print("  %-11s n=%4d A=%.6f B=%.6f delta=%+.6f" % (lab, len(cells), a, b, b - a))

# --- df arithmetic sanity ---
print("\n=== 7. DF ARITHMETIC ===")
print("items - clusters            = %d - %d = %d" % (len(items), n, len(items) - n))
print("cells - clusters            = %d - %d = %d" % (len(inc), n, len(inc) - n))
print("cells - items               = %d - %d = %d" % (len(inc), len(items), len(inc) - len(items)))
print("clusters contributing WITHIN-cluster item contrasts (n_items>1):", len(multis))
print("clusters contributing WITHIN-cluster CELL contrasts (n_cells>1):",
      sum(1 for c, k in cl2cells.items() if k > 1))

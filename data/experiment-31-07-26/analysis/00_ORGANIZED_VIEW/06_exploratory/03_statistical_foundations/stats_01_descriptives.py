"""Step 1: structure + descriptives. Establishes the facts every test-selection
argument below has to respect."""
import sys, math
from collections import defaultdict, Counter
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from stats_lib import *

rows = load()
print("=== STRUCTURE ===")
print("cells (analysis_include):", len(rows))
items = sorted({r["question_id"] for r in rows})
clusters = sorted({r["cluster"] for r in rows})
models = sorted({r["model"] for r in rows})
print("items:", len(items), "clusters:", len(clusters), "models:", len(models))
print("models:", models)

# cells per item
cpi = Counter(len(v) for v in group(rows, lambda r: r["question_id"]).values())
print("cells per item distribution:", dict(sorted(cpi.items())))
# items per cluster
ipc = Counter(len({r['question_id'] for r in v})
              for v in group(rows, lambda r: r["cluster"]).values())
print("items per cluster distribution:", dict(sorted(ipc.items())))
# cells per cluster
cpc = [len(v) for v in group(rows, lambda r: r["cluster"]).values()]
print("cells per cluster: min %d max %d mean %.2f" % (min(cpc), max(cpc), mean(cpc)))
# is item -> cluster a function (nesting)?
i2c = defaultdict(set)
for r in rows:
    i2c[r["question_id"]].add(r["cluster"])
print("items mapping to >1 cluster:", sum(1 for v in i2c.values() if len(v) > 1))

# per-model cell counts
print("\ncells per model:", {m: len(v) for m, v in sorted(group(rows, lambda r: r["model"]).items())})

print("\n=== PAIRED 2x2 TABLES (a=both correct, b=A only, c=B only, d=neither) ===")
def table(rs):
    a = sum(1 for r in rs if r["A_correct"] == 1 and r["B_correct"] == 1)
    b = sum(1 for r in rs if r["A_correct"] == 1 and r["B_correct"] == 0)
    c = sum(1 for r in rs if r["A_correct"] == 0 and r["B_correct"] == 1)
    d = sum(1 for r in rs if r["A_correct"] == 0 and r["B_correct"] == 0)
    return a, b, c, d

hdr = "%-28s %5s %5s %5s %5s | %7s %7s %8s" % ("stratum", "a", "b", "c", "d", "accA", "accB", "delta")
print(hdr)
def line(name, rs):
    a, b, c, d = table(rs)
    n = a + b + c + d
    pA = (a + b) / n
    pB = (a + c) / n
    print("%-28s %5d %5d %5d %5d | %7.4f %7.4f %+8.4f" % (name, a, b, c, d, pA, pB, pB - pA))
    return (a, b, c, d)

per_model = {}
for m, rs in sorted(group(rows, lambda r: r["model"]).items()):
    per_model[m] = line(m.split("/")[-1], rs)
POOLED = line("POOLED", rows)
print("\npooled a,b,c,d =", POOLED, " discordant n =", POOLED[1] + POOLED[2])
print("per-model b,c:", {k: (v[1], v[2]) for k, v in per_model.items()})

print("\n=== DEPENDENCE DIAGNOSTICS ===")
# 1. item-level: correlation of the paired difference across models sharing an item
# difference d_ijk = B_correct - A_correct in {-1,0,1}
D = {}
for r in rows:
    D[(r["question_id"], r["model"])] = r["B_correct"] - r["A_correct"]
alld = list(D.values())
gm = mean(alld)
print("cell-level difference d = B-A: mean %+.4f  sd %.4f" % (gm, math.sqrt(sum((x-gm)**2 for x in alld)/(len(alld)-1))))
print("distribution of d:", dict(sorted(Counter(alld).items())))

def icc_oneway(groups):
    """One-way random-effects ICC(1) from group means (ANOVA estimator).
    groups: list of lists of values."""
    gs = [g for g in groups if len(g) >= 1]
    k = len(gs)
    N = sum(len(g) for g in gs)
    grand = sum(sum(g) for g in gs) / N
    ssb = sum(len(g) * (mean(g) - grand) ** 2 for g in gs)
    ssw = sum(sum((x - mean(g)) ** 2 for x in g) for g in gs)
    dfb, dfw = k - 1, N - k
    if dfw <= 0 or dfb <= 0:
        return float("nan"), float("nan")
    msb, msw = ssb / dfb, ssw / dfw
    # average group size correction
    n0 = (N - sum(len(g) ** 2 for g in gs) / N) / (k - 1)
    icc = (msb - msw) / (msb + (n0 - 1) * msw)
    return icc, n0

# ICC of d across models within item
by_item = defaultdict(list)
for (q, m), v in D.items():
    by_item[q].append(v)
icc_item, n0_item = icc_oneway(list(by_item.values()))
print("ICC of d within ITEM (across models): %.4f  (avg group size %.2f)" % (icc_item, n0_item))

# ICC of d across all cells within cluster
by_clu = defaultdict(list)
q2c = {r["question_id"]: r["cluster"] for r in rows}
for (q, m), v in D.items():
    by_clu[q2c[q]].append(v)
icc_clu, n0_clu = icc_oneway(list(by_clu.values()))
print("ICC of d within CLUSTER (all cells): %.4f  (avg group size %.2f)" % (icc_clu, n0_clu))

# ICC of item-mean d within cluster (item as unit, removes model layer)
item_mean_d = {q: mean(v) for q, v in by_item.items()}
by_clu_item = defaultdict(list)
for q, v in item_mean_d.items():
    by_clu_item[q2c[q]].append(v)
icc_clu2, n0_clu2 = icc_oneway(list(by_clu_item.values()))
print("ICC of item-mean d within CLUSTER: %.4f  (avg group size %.2f)" % (icc_clu2, n0_clu2))

# ICC of A_correct and B_correct within item across models (baseline difficulty sharing)
for fld in ("A_correct", "B_correct"):
    bi = defaultdict(list)
    for r in rows:
        bi[r["question_id"]].append(r[fld])
    ic, n0 = icc_oneway(list(bi.values()))
    print("ICC of %s within ITEM (across models): %.4f" % (fld, ic))

# design effects
print("\ndesign effect for cluster-of-cells on d: 1+(n0-1)*ICC = %.3f" % (1 + (n0_clu - 1) * icc_clu))
print("design effect for item-of-models on d:   1+(n0-1)*ICC = %.3f" % (1 + (n0_item - 1) * icc_item))

#!/usr/bin/env python3
"""Part 2: (a) are singletons manufactured by the exclusions?
(b) exam_part composition per multi-item cluster (test the 'all caso-*' claim)
(c) does clustering actually matter -- ICC + design effect + cluster bootstrap."""
import json, math, random
from collections import Counter, defaultdict

P = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
rows = json.load(open(P))
inc = [r for r in rows if r["analysis_include"] is True]

# ---------------------------------------------------------------- (a)
print("=== A. SINGLETONS BEFORE vs AFTER EXCLUSIONS ===")


def cluster_profile(cells, label):
    cl2items = defaultdict(set)
    for r in cells:
        cl2items[r["cluster"]].add(r["question_id"])
    sizes = Counter(len(v) for v in cl2items.values())
    nsing = sizes.get(1, 0)
    ncl = len(cl2items)
    nit = sum(len(v) for v in cl2items.values())
    nmultiit = sum(len(v) for v in cl2items.values() if len(v) > 1)
    print("  %-26s cells=%4d items=%3d clusters=%3d singletons=%3d (%.1f%% of clusters)"
          % (label, len(cells), nit, ncl, nsing, 100 * nsing / ncl))
    print("  %-26s items in multi-item clusters=%d (%.1f%%)   size hist=%s"
          % ("", nmultiit, 100 * nmultiit / nit, dict(sorted(sizes.items()))))
    return cl2items


full = cluster_profile(rows, "ALL records (pre-exclusion)")
ana = cluster_profile(inc, "analysis_include=True")

# which clusters shrank, and why
print("\n  clusters that LOST items to exclusions (top 20 by loss):")
loss = []
for c, its in full.items():
    a = len(ana.get(c, set()))
    f = len(its)
    if f != a:
        loss.append((f - a, c, f, a))
loss.sort(reverse=True)
for d, c, f, a in loss[:20]:
    print("    cluster %3d: %2d -> %2d items  (lost %d)" % (c, f, a, d))
print("  n clusters that shrank:", len(loss))
print("  n clusters wiped out entirely:", sum(1 for d, c, f, a in loss if a == 0))

# singletons in analysis that were NOT singletons pre-exclusion
ana_sing = {c for c, v in ana.items() if len(v) == 1}
made_sing = [c for c in ana_sing if len(full[c]) > 1]
print("\n  analysis singleton clusters that were MULTI-item pre-exclusion: %d" % len(made_sing))
print("   ", sorted((c, len(full[c])) for c in made_sing))

# exclusion reason breakdown for dropped cells
dropped = [r for r in rows if not r["analysis_include"]]
print("\n  dropped cells=%d ; reason flags:" % len(dropped))
print("    excl_item_defect      :", sum(1 for r in dropped if r["excl_item_defect"]))
print("    excl_nota_position_a  :", sum(1 for r in dropped if r["excl_nota_position_a"]))
print("    neither flag (unparsed):", sum(1 for r in dropped
                                          if not r["excl_item_defect"] and not r["excl_nota_position_a"]))

# ---------------------------------------------------------------- (b)
print("\n=== B. exam_part COMPOSITION OF THE 11 MULTI-ITEM CLUSTERS ===")
multis = sorted((c for c, v in ana.items() if len(v) > 1), key=lambda c: -len(ana[c]))
n_noncaso_cells = 0
n_mixed = 0
for c in multis:
    cells = [r for r in inc if r["cluster"] == c]
    eps = Counter(r["exam_part"] for r in cells)
    caso = all(str(r["exam_part"]).startswith("caso-") for r in cells)
    anycaso = any(str(r["exam_part"]).startswith("caso-") for r in cells)
    n_noncaso_cells += sum(1 for r in cells if not str(r["exam_part"]).startswith("caso-"))
    if anycaso and not caso:
        n_mixed += 1
    print("  cluster %2d: items=%2d cells=%2d all_caso*=%-5s %s"
          % (c, len(ana[c]), len(cells), caso, dict(eps)))
print("  --> multi-item cells whose exam_part is NOT caso-*: %d / %d" % (n_noncaso_cells, 512))
print("  --> multi-item clusters that MIX caso-* with non-caso exam_part:", n_mixed)

# ---------------------------------------------------------------- (c)
print("\n=== C. DOES CLUSTERING ACTUALLY MATTER? ===")
# per-item paired delta averaged over the models that scored it
it = defaultdict(list)
itcl = {}
for r in inc:
    it[r["question_id"]].append(r["B_correct"] - r["A_correct"])
    itcl[r["question_id"]] = r["cluster"]
d_item = {i: sum(v) / len(v) for i, v in it.items()}
grand = sum(sum(v) for v in it.values()) / sum(len(v) for v in it.values())
print("  cell-level mean delta (B-A) = %.6f  over %d cells" % (grand, len(inc)))

# one-way ANOVA ICC on the per-item delta, grouping = cluster
groups = defaultdict(list)
for i, d in d_item.items():
    groups[itcl[i]].append(d)
k = len(groups)
N = sum(len(g) for g in groups.values())
gm = sum(sum(g) for g in groups.values()) / N
MSB = sum(len(g) * (sum(g) / len(g) - gm) ** 2 for g in groups.values()) / (k - 1)
ssw = sum(sum((x - sum(g) / len(g)) ** 2 for x in g) for g in groups.values())
dfw = N - k
MSW = ssw / dfw if dfw else float("nan")
sizes = [len(g) for g in groups.values()]
m0 = (N - sum(s * s for s in sizes) / N) / (k - 1)
icc = (MSB - MSW) / (MSB + (m0 - 1) * MSW) if dfw else float("nan")
print("  ANOVA on per-item delta: k=%d N=%d dfw=%d  MSB=%.6f MSW=%.6f m0=%.4f"
      % (k, N, dfw, MSB, MSW, m0))
print("  ICC(cluster) = %.6f" % icc)
sbar = sum(s * s for s in sizes) / N  # size-weighted mean cluster size
print("  size-weighted mean cluster size (sum n^2 / sum n) = %.4f" % sbar)
print("  design effect 1+(sbar-1)*ICC = %.4f  -> effective n = %.1f of %d items"
      % (1 + (sbar - 1) * icc, N / (1 + (sbar - 1) * icc), N))

# bootstrap: resample CLUSTERS vs resample ITEMS (independence assumption)
random.seed(20260731)
B = 20000
items_all = list(d_item)
cl_list = list(groups)
cl_items = defaultdict(list)
for i in items_all:
    cl_items[itcl[i]].append(i)


def boot(units, expand, reps=B):
    out = []
    n = len(units)
    for _ in range(reps):
        s = 0.0
        c = 0
        for _ in range(n):
            u = units[random.randrange(n)]
            for i in expand(u):
                s += d_item[i]
                c += 1
        out.append(s / c)
    return out


bi = boot(items_all, lambda i: (i,))
bc = boot(cl_list, lambda c: cl_items[c])


def sd(v):
    m = sum(v) / len(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))


def pct(v, q):
    v = sorted(v)
    h = (len(v) - 1) * q
    lo = math.floor(h)
    hi = math.ceil(h)
    return v[lo] + (h - lo) * (v[hi] - v[lo])


print("\n  item-level (independence) bootstrap: SE=%.6f  95%% CI [%.4f, %.4f]"
      % (sd(bi), pct(bi, .025), pct(bi, .975)))
print("  CLUSTER  bootstrap                 : SE=%.6f  95%% CI [%.4f, %.4f]"
      % (sd(bc), pct(bc, .025), pct(bc, .975)))
print("  SE ratio (cluster / item) = %.4f   -> variance inflation = %.4f"
      % (sd(bc) / sd(bi), (sd(bc) / sd(bi)) ** 2))
print("  B = %d resamples, seed=20260731" % B)

# how much of the total item weight sits in the 11 big clusters
big = [c for c in cl_list if len(cl_items[c]) > 1]
print("\n  items in the 11 multi-item clusters: %d / %d = %.2f%%"
      % (sum(len(cl_items[c]) for c in big), N, 100 * sum(len(cl_items[c]) for c in big) / N))
print("  largest cluster = %.2f%% of all items; top-3 = %.2f%%"
      % (100 * max(len(cl_items[c]) for c in big) / N,
         100 * sum(sorted((len(cl_items[c]) for c in big), reverse=True)[:3]) / N))

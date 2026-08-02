"""ca_wb_05: the interpretation checks that decide what the two conditional
rates actually mean.

 A. Ceiling arithmetic: the maximum attainable delta is the headroom.
 B. Multiplicity: Holm over the four per-model McNemar tests.
 C. Independence check: among cells BOTH arms got wrong, do they pick the SAME
    wrong option? High agreement => GIFT is largely the same model reasoning
    the same way, so 'recovery' is a targeted change, not a re-roll.
 D. The k_loo=0 result is 8 cells but only 2 ITEMS. Item-level restatement.
 E. Regional homogeneity of the recovery rate (transport check for ca_wb_04).
"""
import json, math, os, random
from ca_wb_lib import (load, table, MODELS, SHORT, wilson, cluster_boot, ci,
                       boot_p, fisher_exact_2x2, mcnemar_exact, chi2_sf_1df,
                       pct, BASE)

rows = load()
by_item = {}
for r in rows:
    by_item.setdefault(r["question_id"], {})[r["model"]] = r
k_all = {q: sum(v["or_correct"] for v in d.values()) for q, d in by_item.items()}
for r in rows:
    r["k_all"] = k_all[r["question_id"]]
    r["k_loo"] = k_all[r["question_id"]] - r["or_correct"]

out = {}

# ------------------------------------------------------------ A. ceiling
print("A. CEILING ARITHMETIC -- the largest delta a model could possibly show")
print("%-14s %9s %14s %12s %14s" % ("model", "OR acc", "max delta (=h)",
                                    "obs delta", "share of max"))
print("-" * 80)
for m in MODELS:
    a, b, c, d = table([r for r in rows if r["model"] == m])
    n = a + b + c + d
    h = (b + d) / n
    dobs = (b - c) / n
    print("%-14s %9s %14s %+12s %13s%%" % (SHORT[m], pct((a + c) / n), pct(h),
                                           pct(dobs), "%.0f" % (100 * dobs / h)))
    out.setdefault("ceiling", {})[m] = dict(headroom=h, delta=dobs, share=dobs / h)

# ------------------------------------------------------------ B. multiplicity
print()
print("B. MULTIPLICITY -- Holm-Bonferroni over the 4 per-model exact McNemar tests")
ps = []
for m in MODELS:
    a, b, c, d = table([r for r in rows if r["model"] == m])
    ps.append((m, mcnemar_exact(b, c), b, c))
order = sorted(range(4), key=lambda i: ps[i][1])
holm = {}
run = 0.0
for rank, i in enumerate(order):
    adj = min(1.0, max(run, (4 - rank) * ps[i][1]))
    run = adj
    holm[ps[i][0]] = adj
print("%-14s %6s %6s %12s %12s %8s" % ("model", "b", "c", "raw p", "Holm p", "sig .05"))
print("-" * 80)
for m in MODELS:
    _, p, b, c = [x for x in ps if x[0] == m][0]
    print("%-14s %6d %6d %12.4f %12.4f %8s" % (SHORT[m], b, c, p, holm[m],
                                               "yes" if holm[m] < 0.05 else "no"))
out["holm"] = holm

# ------------------------------------------- C. both-wrong option agreement
print()
print("C. WHEN BOTH ARMS ARE WRONG, DO THEY PICK THE SAME WRONG OPTION?")
print("(if GIFT were an independent re-roll of the model, agreement on the")
print(" specific wrong distractor should be near 1/3)")
print("%-14s %8s %10s %26s" % ("model", "n both", "same opt", "agreement 95% Wilson"))
print("-" * 80)
for m in MODELS + ["POOLED"]:
    cells = rows if m == "POOLED" else [r for r in rows if r["model"] == m]
    bw = [r for r in cells if not r["gift_correct"] and not r["or_correct"]]
    same = sum(1 for r in bw if r["gift_selected"] == r["or_selected"])
    p, lo, hi = wilson(same, len(bw))
    print("%-14s %8d %10d %10s [%5s, %5s]" % (SHORT.get(m, m), len(bw), same,
                                              pct(p), pct(lo), pct(hi)))
    out.setdefault("bothwrong", {})[m] = dict(n=len(bw), same=same)
bw = [r for r in rows if not r["gift_correct"] and not r["or_correct"]]
same = sum(1 for r in bw if r["gift_selected"] == r["or_selected"])
# exact binomial vs the 1/3 independent-re-roll benchmark
n = len(bw)
pv = sum(math.comb(n, k) * (1 / 3) ** k * (2 / 3) ** (n - k) for k in range(same, n + 1))
print("  pooled %d/%d ; exact one-sided binomial vs p0=1/3 : p = %.2e" % (same, n, pv))
out["bothwrong_binom_p"] = pv

# also: overall option-level agreement, as context
agr = sum(1 for r in rows if r["gift_selected"] == r["or_selected"]) / len(rows)
print("  (for context: the two arms select the identical option on %s of all 1244 cells)"
      % pct(agr))

# ------------------------------------------------- D. k_loo=0 at item level
print()
print("D. THE 'HARDEST ITEMS' RESULT AT ITEM LEVEL")
k0 = [r for r in rows if r["k_loo"] == 0]
k0items = sorted({r["question_id"] for r in k0})
print("  k_loo=0 covers %d cells but only %d distinct items: %s"
      % (len(k0), len(k0items), k0items))
for q in k0items:
    d = by_item[q]
    ks = k_all[q]
    g = sum(v["gift_correct"] for v in d.values())
    print("    %-6s k_all=%d  OR correct %d/4  GIFT correct %d/4  cluster=%s"
          % (q, ks, ks, g, d[MODELS[0]]["cluster"]))
kall0 = [q for q in k_all if k_all[q] == 0]
cells0 = [r for r in rows if r["k_all"] == 0]
wrong = [r for r in rows if r["or_correct"] == 0]
k0w = [r for r in wrong if r["k_loo"] == 0]
print("  the 8 OR-WRONG cells at k_loo=0 are exactly the %d items ALL FOUR models"
      % len(kall0))
print("  failed on OpenRouter (%s), x 4 models. GIFT rescued %d of them."
      % (", ".join(kall0), sum(r["gift_correct"] for r in cells0)))
print("  => effective n is 2 ITEMS, not 8 cells. The Fisher p=0.0080 computed on")
print("     cells is INVALID here: it treats 4 correlated cells per item as")
print("     independent. A cluster bootstrap is also degenerate -- whenever either")
print("     item is drawn the stratum rate is exactly 0, so the CI can never")
print("     cover 0. NO p-value is reported for this contrast.")
print("  Item-level restatement: of %d items on which every model failed on"
      % len(kall0))
print("  OpenRouter, GIFT rescued 0 for 0 of 4 models. That is the whole result.")

# item-level recovery: unit = item, value = share of its OR-wrong cells rescued
print()
print("  ITEM-LEVEL recovery (unit = item; value = share of that item's OR-wrong")
print("  cells that GIFT got right), stratified by k_all:")
print("%7s %8s %14s %10s" % ("k_all", "n items", "mean item recov", "cells"))
iw = {}
for r in wrong:
    iw.setdefault(r["question_id"], []).append(r)
for k in range(4):
    qs = [q for q in iw if k_all[q] == k]
    if not qs:
        continue
    vals = [sum(x["gift_correct"] for x in iw[q]) / len(iw[q]) for q in qs]
    print("%7d %8d %14s %10d" % (k, len(qs), pct(sum(vals) / len(vals)),
                                 sum(len(iw[q]) for q in qs)))
out["k0_items"] = dict(n_items_all_fail=len(kall0),
                       rescued_cells=sum(r["gift_correct"] for r in cells0),
                       n_cells=len(cells0))

# ------------------------------------------------ E. regional heterogeneity
print()
print("E. REGIONAL HOMOGENEITY OF THE RECOVERY RATE (transport check)")
regs = {}
for r in rows:
    regs.setdefault(r["region"], []).append(r)
counts = []
for reg, s in regs.items():
    a, b, c, d = table(s)
    if b + d:
        counts.append((reg, b, b + d))
S = sum(x[1] for x in counts)
T = sum(x[2] for x in counts)
p0 = S / T
x2 = sum((k - t * p0) ** 2 / (t * p0) + ((t - k) - t * (1 - p0)) ** 2 / (t * (1 - p0))
         for _, k, t in counts)
df = len(counts) - 1
print("  Pearson chi2 = %.2f on df=%d (%d regions with >=1 OR-wrong cell)"
      % (x2, df, len(counts)))
print("  expected cell counts are tiny -> asymptotic p is unreliable; using a")
print("  Monte-Carlo permutation of region labels across CLUSTERS instead")


def x2_stat(cells):
    g = {}
    for r in cells:
        g.setdefault(r["region"], []).append(r)
    cs = []
    for reg, s in g.items():
        a, b, c, d = table(s)
        if b + d:
            cs.append((b, b + d))
    S_ = sum(x[0] for x in cs)
    T_ = sum(x[1] for x in cs)
    if T_ == 0 or S_ == 0 or S_ == T_:
        return 0.0
    p_ = S_ / T_
    return sum((k - t * p_) ** 2 / (t * p_) + ((t - k) - t * (1 - p_)) ** 2 / (t * (1 - p_))
               for k, t in cs)


rng = random.Random(2026)
byc = {}
for r in wrong:
    byc.setdefault(r["cluster"], []).append(r)
keys = list(byc)
labels = [byc[k][0]["region"] for k in keys]
obs = x2_stat(wrong)
ge = 0
B = 20000
for _ in range(B):
    L = labels[:]
    rng.shuffle(L)
    perm = []
    for k, lab in zip(keys, L):
        for r in byc[k]:
            q = dict(r)
            q["region"] = lab
            perm.append(q)
    if x2_stat(perm) >= obs - 1e-9:
        ge += 1
print("  observed chi2 among the 103 OR-wrong cells = %.2f ; cluster-label"
      % obs)
print("  permutation p = %.4f (B=%d)" % ((ge + 1) / (B + 1), B))
out["region_perm_p"] = (ge + 1) / (B + 1)

json.dump(out, open(os.path.join(BASE, "ca_wb_05_checks.json"), "w"), indent=1)
print("\nwritten ca_wb_05_checks.json")

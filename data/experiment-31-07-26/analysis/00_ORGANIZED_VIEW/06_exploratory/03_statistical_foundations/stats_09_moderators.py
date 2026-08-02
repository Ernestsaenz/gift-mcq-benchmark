"""Step 9: where the test choice actually CHANGES a conclusion.

The main effect is so large that every candidate rejects. The decision matters for
(a) the width of the interval on delta and (b) the secondary/moderator contrasts,
which is where most of the paper's claims will live. Each moderator contrast is
computed with an iid-cell SE and with a cluster-robust SE, and the two verdicts at
alpha = .05 are compared.
"""
import sys, math
from collections import defaultdict
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from stats_lib import *

rows = load()
for r in rows:
    r["d"] = r["B_correct"] - r["A_correct"]
n = len(rows)
qlens = sorted(r["qlen"] for r in rows)
qmed = quantile(qlens, 0.5)
years = sorted({r["year"] for r in rows})
ymed = quantile(sorted(r["year"] for r in rows), 0.5)

def contrast(sel1, sel0, label):
    """delta(group1) - delta(group0) with iid vs cluster-robust vs item-robust SE."""
    g1 = [r for r in rows if sel1(r)]
    g0 = [r for r in rows if sel0(r)]
    n1, n0 = len(g1), len(g0)
    if n1 < 20 or n0 < 20:
        return None
    d1 = sum(r["d"] for r in g1) / n1
    d0 = sum(r["d"] for r in g0) / n0
    est = d1 - d0
    # influence contributions
    psi = {}
    for r in g1:
        psi[id(r)] = (r["d"] - d1) / n1
    for r in g0:
        psi[id(r)] = -(r["d"] - d0) / n0
    v_iid = sum(p * p for p in psi.values())
    def robust(key):
        acc = defaultdict(float)
        for r in g1 + g0:
            acc[key(r)] += psi[id(r)]
        return sum(v * v for v in acc.values())
    v_clu = robust(lambda r: r["cluster"])
    v_itm = robust(lambda r: r["question_id"])
    se_i, se_c, se_t = math.sqrt(v_iid), math.sqrt(v_clu), math.sqrt(v_itm)
    p_i = two_sided_z_p(est / se_i) if se_i > 0 else 1
    p_c = two_sided_z_p(est / se_c) if se_c > 0 else 1
    p_t = two_sided_z_p(est / se_t) if se_t > 0 else 1
    return dict(label=label, n1=n1, n0=n0, d1=d1, d0=d0, est=est,
                se_i=se_i, se_c=se_c, se_t=se_t, p_i=p_i, p_c=p_c, p_t=p_t,
                ratio=se_c / se_i)

tests = [
    (lambda r: r["negated_stem"], lambda r: not r["negated_stem"], "negated stem vs not"),
    (lambda r: r["has_context"], lambda r: not r["has_context"], "has context vs not"),
    (lambda r: r["correct_letter"] == "d", lambda r: r["correct_letter"] != "d", "correct letter d vs b/c"),
    (lambda r: r["correct_letter"] == "b", lambda r: r["correct_letter"] != "b", "correct letter b vs c/d"),
    (lambda r: r["qlen"] > qmed, lambda r: r["qlen"] <= qmed, "qlen above vs below median"),
    (lambda r: r["year"] >= ymed, lambda r: r["year"] < ymed, "year >= median vs <"),
    (lambda r: r["exam_part"].startswith("caso"), lambda r: not r["exam_part"].startswith("caso"), "case-based vs standalone"),
]
print("=== moderator contrasts on delta: iid-cell vs cluster-robust ===")
print("%-30s %6s %6s %+9s %9s %9s %11s %11s  %s"
      % ("contrast", "n1", "n0", "est", "SE_iid", "SE_clu", "p_iid", "p_clu", "verdict flip?"))
flips = 0
outs = []
for s1, s0, lab in tests:
    o = contrast(s1, s0, lab)
    if not o:
        continue
    outs.append(o)
    flip = (o["p_i"] < 0.05) != (o["p_c"] < 0.05)
    flips += flip
    print("%-30s %6d %6d %+9.4f %9.5f %9.5f %11.4f %11.4f  %s"
          % (lab, o["n1"], o["n0"], o["est"], o["se_i"], o["se_c"], o["p_i"], o["p_c"],
             "*** FLIP ***" if flip else ""))
print("\nmoderator contrasts whose 0.05 verdict flips between iid and cluster-robust: %d of %d"
      % (flips, len(outs)))
print("median SE inflation (cluster/iid) across these contrasts: %.3f"
      % quantile(sorted(o["ratio"] for o in outs), 0.5))
print("max SE inflation: %.3f (%s)" % (max(o["ratio"] for o in outs),
                                       max(outs, key=lambda o: o["ratio"])["label"]))

print("\n=== per-region delta (the contrast most exposed to clustering) ===")
byreg = group(rows, lambda r: r["region"])
print("%-28s %6s %9s %9s %9s" % ("region", "cells", "delta", "SE_iid", "SE_clu"))
for reg, rs in sorted(byreg.items(), key=lambda kv: -len(kv[1]))[:10]:
    nn = len(rs)
    dd = sum(r["d"] for r in rs) / nn
    vi = sum((r["d"] - dd) ** 2 for r in rs) / nn / nn
    acc = defaultdict(float)
    for r in rs:
        acc[r["cluster"]] += (r["d"] - dd) / nn
    vc = sum(v * v for v in acc.values())
    print("%-28s %6d %+9.4f %9.5f %9.5f" % (reg, nn, dd, math.sqrt(vi), math.sqrt(vc)))

print("\n=== the main effect: every candidate, one table, same estimand (delta) ===")
dbar = sum(r["d"] for r in rows) / n
b = sum(1 for r in rows if r["d"] == -1); c = sum(1 for r in rows if r["d"] == 1)
def cr(key):
    acc = defaultdict(float)
    for r in rows:
        acc[key(r)] += (r["d"] - dbar)
    return math.sqrt(sum(v * v for v in acc.values())) / n
se_cell = math.sqrt(sum((r["d"] - dbar) ** 2 for r in rows)) / n
se_item = cr(lambda r: r["question_id"])
se_clu = cr(lambda r: r["cluster"])
print("delta = %+.4f" % dbar)
for nm, se in [("iid cells (McNemar-equivalent)", se_cell), ("item-robust", se_item), ("cluster-robust", se_clu)]:
    print("  %-32s SE %.5f  95%% CI [%+.4f, %+.4f]  half-width %.4f"
          % (nm, se, dbar - 1.96 * se, dbar + 1.96 * se, 1.96 * se))
print("  CI half-width is understated by %.1f%% if clustering is ignored"
      % (100 * (1 - se_cell / se_clu)))

# exact CI on the discordance ratio (Clopper-Pearson), the McNemar-native interval
lo, hi = binom_exact_ci(b, b + c)
print("\nexact (Clopper-Pearson) CI on P(d=-1 | discordant) = %d/%d = %.4f: [%.4f, %.4f]"
      % (b, b + c, b / (b + c), lo, hi))
print("  -> implied OR interval [%.3f, %.3f] (conditional estimand, ASSUMES independent discordant cells)"
      % (lo / (1 - lo), hi / (1 - hi)))

"""ca_wb_01: confirm the observed cross-arm numbers and compute the two
substantive conditional rates per model:

    RECOVERY  P(GIFT correct | OpenRouter wrong)   = b / (b + d)
    BREAKAGE  P(GIFT wrong   | OpenRouter correct) = c / (a + c)

Also: the symmetric-noise benchmark. If GIFT were merely a noisy re-draw of the
same model (same accuracy, flips independent of correctness), the flip rate
would be equal in both directions and, because correct cells vastly outnumber
wrong ones, breakage COUNTS would swamp recovery counts. Asymmetry is the
evidence for retrieval doing something directional.
"""
import json
from ca_wb_lib import (load, table, MODELS, SHORT, mcnemar_exact, mcnemar_chi2,
                       wilson, cluster_boot, ci, boot_p, cluster_armflip, pct)

rows = load()
print("cells=%d items=%d clusters=%d models=%d" % (
    len(rows), len({r["question_id"] for r in rows}),
    len({r["cluster"] for r in rows}), len({r["model"] for r in rows})))

out = {}
print()
print("%-14s %5s %6s %6s %7s | %4s %4s %4s %4s | %8s %8s" % (
    "model", "n", "GIFT", "OR", "delta", "a", "b", "c", "d", "McN exact", "chi2"))
print("-" * 100)

for m in MODELS + ["POOLED"]:
    cells = rows if m == "POOLED" else [r for r in rows if r["model"] == m]
    a, b, c, d = table(cells)
    n = a + b + c + d
    g = (a + b) / n
    o = (a + c) / n
    pex = mcnemar_exact(b, c)
    x2, px2 = mcnemar_chi2(b, c)
    print("%-14s %5d %6s %6s %+7s | %4d %4d %4d %4d | %8.4f %5.2f/%.4f" % (
        SHORT.get(m, m), n, pct(g, 1), pct(o, 1), pct(g - o, 1), a, b, c, d,
        pex, x2, px2))
    out[m] = dict(n=n, a=a, b=b, c=c, d=d, gift=g, orr=o, delta=g - o,
                  mcnemar_exact=pex, mcnemar_chi2=x2, mcnemar_chi2_p=px2)

# --------------------------------------------------------------- conditionals
print()
print("CONDITIONAL RATES  (Wilson 95% CI, then cluster-bootstrap 95% CI, B=20000)")
print("%-14s %-28s %-28s %8s" % ("model", "RECOVERY P(G ok | OR wrong)",
                                 "BREAKAGE P(G bad | OR ok)", "rec-brk"))
print("-" * 100)

for m in MODELS + ["POOLED"]:
    cells = rows if m == "POOLED" else [r for r in rows if r["model"] == m]
    a, b, c, d = table(cells)
    rec, rlo, rhi = wilson(b, b + d)
    brk, blo, bhi = wilson(c, a + c)

    def f_rec(s):
        A, B_, C, D = table(s)
        return B_ / (B_ + D) if (B_ + D) else None

    def f_brk(s):
        A, B_, C, D = table(s)
        return C / (A + C) if (A + C) else None

    def f_diff(s):
        A, B_, C, D = table(s)
        if (B_ + D) == 0 or (A + C) == 0:
            return None
        return B_ / (B_ + D) - C / (A + C)

    rb = cluster_boot(cells, f_rec)
    bb = cluster_boot(cells, f_brk)
    db = cluster_boot(cells, f_diff)
    rlo2, rhi2 = ci(rb)
    blo2, bhi2 = ci(bb)
    dlo, dhi = ci(db)
    print("%-14s %5s [%4s,%5s]/[%4s,%5s] %5s [%4s,%4s]/[%4s,%4s] %6s [%5s,%5s] bootp=%.4f" % (
        SHORT.get(m, m), pct(rec), pct(rlo), pct(rhi), pct(rlo2), pct(rhi2),
        pct(brk), pct(blo), pct(bhi), pct(blo2), pct(bhi2),
        pct(rec - brk), pct(dlo), pct(dhi), boot_p(db)))
    out[m].update(recovery=rec, rec_wilson=[rlo, rhi], rec_boot=[rlo2, rhi2],
                  rec_n=b + d, brk_n=a + c,
                  breakage=brk, brk_wilson=[blo, bhi], brk_boot=[blo2, bhi2],
                  rec_minus_brk=rec - brk, rmb_boot=[dlo, dhi],
                  rmb_boot_p=boot_p(db))

# ------------------------------------------------- symmetric-noise benchmark
print()
print("SYMMETRIC-NOISE BENCHMARK: if GIFT were the same model re-drawn with an")
print("outcome-independent flip probability f, then E[b]=f*(b+d), E[c]=f*(a+c),")
print("so E[c]/E[b] = (a+c)/(b+d).  Observed c/b vs that expectation:")
print("%-14s %6s %6s %10s %10s %12s" % ("model", "b", "c", "obs c/b",
                                        "exp c/b", "brk/rec odds"))
print("-" * 100)
for m in MODELS + ["POOLED"]:
    cells = rows if m == "POOLED" else [r for r in rows if r["model"] == m]
    a, b, c, d = table(cells)
    exp_ratio = (a + c) / (b + d) if (b + d) else float("nan")
    obs_ratio = c / b if b else float("inf")
    print("%-14s %6d %6d %10.3f %10.3f %12s" % (
        SHORT.get(m, m), b, c, obs_ratio, exp_ratio,
        "%.3f" % (obs_ratio / exp_ratio) if b and exp_ratio == exp_ratio else "n/a"))
    out[m]["exp_c_over_b_if_symmetric"] = exp_ratio
    out[m]["obs_c_over_b"] = obs_ratio

# ------------------------------------------------ cluster randomization test
print()
print("CLUSTER-LEVEL ARM-FLIP RANDOMIZATION TEST on the pooled accuracy delta")
print("(swap GIFT/OR outcomes for whole clusters; B=20000)")


def delta_stat(s):
    A, B_, C, D = table(s)
    n = A + B_ + C + D
    return (B_ - C) / n


obs, p, reps = cluster_armflip(rows, delta_stat, B=20000, seed=515)
print("  observed pooled delta = %+.4f pp=%.2f   cluster-perm p = %.4f" % (
    obs, 100 * obs, p))
out["POOLED"]["cluster_perm_p"] = p
out["POOLED"]["cluster_perm_obs"] = obs

json.dump(out, open("ca_wb_01_core.json", "w"), indent=1)
print("\nwritten ca_wb_01_core.json")

"""ca_wb_04: engage with the 83%-completion caveat.

GIFT stopped at 83%; coverage is a sequential prefix, so the 311 analysed items
are systematically easier than the full 474-item dataset. For a who-benefits
claim this matters twice over:

  (a) HEADROOM. The delta is headroom*recovery - (1-headroom)*breakage. If the
      analysed subset is easier, every model's headroom is understated, and the
      whole 'weak models gain more' arithmetic is evaluated at the wrong point.
  (b) DIFFICULTY MIX. The stratum weights are wrong: the hard strata that would
      test the mechanism are under-represented.

OpenRouter ran the FULL 474 items on both covered and uncovered questions, so
the counterfactual difficulty mix is directly observable. We use it to reweight.

Transport assumption named explicitly: stratum-specific recovery and breakage
rates estimated on the covered items are assumed to carry to the uncovered
items. That is an assumption, not a measurement -- GIFT never saw those items.
"""
import json, math, os
from ca_wb_lib import (load, table, MODELS, SHORT, wilson, cluster_boot, ci,
                       boot_p, fisher_exact_2x2, pct, BASE)

rows = load()
full = json.load(open(os.path.join(BASE, "ca_wb_or_full.json")))
items_meta = full["items"]

DEFECT = set(["b205", "b238", "b331", "b341", "b343", "b378", "b385", "b391",
              "b401", "b420", "b430", "b178", "b197", "b496"])

or_full = {}
gift_seen = {}
for c in full["cells"]:
    if c["parse_status"] != "ok":
        continue
    if c["exp"] == "expA_or_310726":
        or_full.setdefault(c["qid"], {})[c["model"]] = c["strict_correct"]
    elif c["exp"] == "expA_gift_310726":
        gift_seen.setdefault(c["qid"], {})[c["model"]] = c["strict_correct"]

analysed = {r["question_id"] for r in rows}
eligible = [q for q in items_meta if q not in DEFECT]
print("dataset A items %d ; minus 14 defects -> %d eligible ; analysed (GIFT complete on 4) %d"
      % (len(items_meta), len(eligible), len(analysed)))

or4 = [q for q in eligible if len(or_full.get(q, {})) == 4]
print("items with all 4 OpenRouter cells parsed: %d  (the %d-item gap is the known"
      % (len(or4), len(eligible) - len(or4)))
print(" b320 x glm-5.2 runaway documented in RUN_STATUS.md)")
missing = [q for q in or4 if q not in analysed]
print("covered by GIFT: %d ; NOT covered: %d" % (len(or4) - len(missing), len(missing)))

# ------------------------------------------------- OR accuracy covered vs not
print()
print("OPENROUTER ACCURACY AND HEADROOM, COVERED vs UNCOVERED  (per model)")
print("%-14s %20s %20s %10s" % ("model", "covered (n items)", "uncovered (n items)",
                                "headroom x"))
print("-" * 90)
cov_stats = {}
for m in MODELS:
    cv = [or_full[q][m] for q in or4 if q in analysed]
    uv = [or_full[q][m] for q in or4 if q not in analysed]
    ac, au = sum(cv) / len(cv), sum(uv) / len(uv)
    hc, hu = 1 - ac, 1 - au
    print("%-14s %13s (%3d) %14s (%3d) %10.2f" % (
        SHORT[m], pct(ac), len(cv), pct(au), len(uv), (hu / hc) if hc else float("nan")))
    cov_stats[m] = dict(acc_cov=ac, acc_unc=au, head_cov=hc, head_unc=hu,
                        n_cov=len(cv), n_unc=len(uv))
allc = [or_full[q][m] for q in or4 if q in analysed for m in MODELS]
allu = [or_full[q][m] for q in or4 if q not in analysed for m in MODELS]
print("%-14s %13s (%3d) %14s (%3d)" % ("POOLED", pct(sum(allc) / len(allc)), len(allc),
                                       pct(sum(allu) / len(allu)), len(allu)))
print("  -> the analysed subset is %.1f pp easier at cell level"
      % (100 * (sum(allc) / len(allc) - sum(allu) / len(allu))))

# ------------------------------------------------------ difficulty mix shift
print()
print("ITEM DIFFICULTY MIX (k = #of 4 models correct on OpenRouter)")
print("%5s %18s %18s" % ("k", "covered", "uncovered"))
kc = {k: 0 for k in range(5)}
ku = {k: 0 for k in range(5)}
for q in or4:
    k = sum(or_full[q][m] for m in MODELS)
    (kc if q in analysed else ku)[k] += 1
nc, nu = sum(kc.values()), sum(ku.values())
for k in range(5):
    print("%5d %8d (%5.1f%%) %8d (%5.1f%%)" % (k, kc[k], 100 * kc[k] / nc,
                                               ku[k], 100 * ku[k] / nu))
print("  mean k covered %.3f   uncovered %.3f" % (
    sum(k * kc[k] for k in kc) / nc, sum(k * ku[k] for k in ku) / nu))

# ------------------------------------------------------------- reweighting
# Per model, apply the covered-subset recovery/breakage rates to the FULL
# eligible dataset's headroom for that model.
print()
print("PROJECTION 1 -- headroom reweighting.")
print("Hold each model's measured recovery and breakage constant; substitute the")
print("full-dataset (%d eligible items) headroom for the covered-subset headroom." % len(or4))
print("%-14s %9s %9s %9s %11s %11s %9s" % (
    "model", "rec", "brk", "h covered", "delta obs", "h full", "delta proj"))
print("-" * 90)
proj = {}
for m in MODELS:
    a, b, c, d = table([r for r in rows if r["model"] == m])
    n = a + b + c + d
    rec = b / (b + d) if b + d else 0.0
    brk = c / (a + c) if a + c else 0.0
    hcov = (b + d) / n
    hfull = 1 - (sum(or_full[q][m] for q in or4) / len(or4))
    dobs = (b - c) / n
    dproj = hfull * rec - (1 - hfull) * brk
    print("%-14s %9s %9s %9s %+11s %11s %+9s" % (
        SHORT[m], pct(rec), pct(brk), pct(hcov), pct(dobs), pct(hfull), pct(dproj)))
    proj[m] = dict(rec=rec, brk=brk, h_cov=hcov, h_full=hfull,
                   delta_obs=dobs, delta_proj=dproj)
pooled_obs = sum(proj[m]["delta_obs"] for m in MODELS) / 4
pooled_proj = sum(proj[m]["delta_proj"] for m in MODELS) / 4
print("%-14s %9s %9s %9s %+11s %11s %+9s" % (
    "MEAN OF 4", "", "", "", pct(pooled_obs), "", pct(pooled_proj)))

# --------------------------------------------------- stratum reweighting
print()
print("PROJECTION 2 -- difficulty-stratum reweighting (post-stratification).")
print("Per model, take the covered-subset GIFT-minus-OR delta INSIDE each")
print("leave-one-out difficulty stratum and reweight by the full dataset's")
print("stratum shares. Strata with no covered data contribute their own")
print("covered-arm delta of 0 (flagged).")
by_item = {}
for r in rows:
    by_item.setdefault(r["question_id"], {})[r["model"]] = r
k_all_cov = {q: sum(v["or_correct"] for v in d.values()) for q, d in by_item.items()}
for r in rows:
    r["k_loo"] = k_all_cov[r["question_id"]] - r["or_correct"]

print("%-14s %8s %8s %10s %10s" % ("model", "obs", "proj", "shift", "n empty strata"))
print("-" * 90)
for m in MODELS:
    cells = [r for r in rows if r["model"] == m]
    # covered stratum deltas
    sd, sn = {}, {}
    for k in range(4):
        s = [r for r in cells if r["k_loo"] == k]
        if s:
            a, b, c, d = table(s)
            sd[k] = (b - c) / len(s)
            sn[k] = len(s)
    # full-dataset stratum shares for this model
    w = {k: 0 for k in range(4)}
    for q in or4:
        kl = sum(or_full[q][mm] for mm in MODELS if mm != m)
        w[kl] += 1
    tot = sum(w.values())
    empty = sum(1 for k in range(4) if k not in sd and w[k] > 0)
    dproj = sum((w[k] / tot) * sd.get(k, 0.0) for k in range(4))
    dobs = sum((sn.get(k, 0) / len(cells)) * sd.get(k, 0.0) for k in range(4))
    print("%-14s %+8s %+8s %+10s %10d" % (SHORT[m], pct(dobs), pct(dproj),
                                          pct(dproj - dobs), empty))
    proj[m]["delta_strat_proj"] = dproj

# --------------------------------- does recovery/breakage travel across region?
print()
print("TRANSPORT CHECK -- the region mix is skewed (Illes Balears over-covered).")
print("If recovery/breakage differ by region, neither projection transports.")
print("%-26s %6s %18s %18s" % ("region", "cells", "recovery", "breakage"))
print("-" * 90)
regs = {}
for r in rows:
    regs.setdefault(r["region"], []).append(r)
for reg, s in sorted(regs.items(), key=lambda kv: -len(kv[1])):
    a, b, c, d = table(s)
    rr, rl, rh = wilson(b, b + d)
    br, bl, bh = wilson(c, a + c)
    print("%-26s %6d %6s [%5s,%5s] (%2d) %6s [%4s,%4s] (%3d)" % (
        reg, len(s), pct(rr), pct(rl), pct(rh), b + d, pct(br), pct(bl), pct(bh), a + c))
    regs[reg] = dict(n=len(s), a=a, b=b, c=c, d=d)

json.dump({"cov_stats": cov_stats, "proj": proj, "k_cov": kc, "k_unc": ku,
           "regions": regs}, open(os.path.join(BASE,"ca_wb_04_coverage.json"), "w"), indent=1)
print("\nwritten ca_wb_04_coverage.json")

"""REFUTATION pass 2.

Three things the claim asserts or implies, tested:

 (A) "64 of 160 ... (all bootstrap and permutation specs)".  Count how many specs
     actually use resampling, and how many are FLOOR-LIMITED (i.e. their reported
     value is a deterministic function of the floor and carries no resolution),
     as opposed to merely SITTING ON the floor.

 (B) "'p<0.001' is a floor statement for those, not a resolved value."  Every one
     of the four pooled permutation statistics is LINEAR in the cluster sign
     vector, so the sign-flip null tail is analytically resolvable.  Compute
       - a rigorous Hoeffding upper bound  P(|S| >= s) <= 2 exp(-s^2 / (2 sum w^2))
       - the normal (CLT) sign-flip approximation z = s / sqrt(sum w^2)
     for each of the 32 pooled permutation specs.  If those land at 1e-15 .. 1e-40,
     the floor is a reporting limit, not a lack of evidence, and DELETING the
     specs is the wrong repair.

 (C) "Restricting to the 64 exact/analytic specs removes the artefact."  24 of
     those 64 are Fisher combinations across the 4 models, which share clusters
     and items.  The pipeline's own docstring flags this as an independence
     violation.  Replace Fisher with combinations that are valid under arbitrary
     dependence (Bonferroni min-p, and Ruger/Hommel), and re-summarise.
     Also report the raw per-model p-values with no combination at all.
"""
import json, os, math
from fractions import Fraction
import sens_refute_mcfloor_01 as R   # reuse the independent estimators

HERE = os.path.dirname(os.path.abspath(__file__))
pub = json.load(open(os.path.join(HERE, "sens_speccurve_results.json")))
res = pub["results"]
B = pub["B_perm"]
FLOOR = 1.0 / (B + 1.0)
MODELS = R.MODELS
NM = R.NM

print("=" * 100)
print("(A) how many specs are actually floor-limited?")
print("=" * 100)
resamp = [x for x in res if x["inference"] in ("cluster_bootstrap", "permutation")]
exact_floor = [x for x in res if abs(x["p"] - FLOOR) < 1e-15]
sep = [x for x in resamp if x["pooling"] == "separate"]
sep_allfloor = [x for x in sep if all(abs(p - FLOOR) < 1e-15 for p in x["per_model_p"])]
sep_anyfloor = [x for x in sep if any(abs(p - FLOOR) < 1e-15 for p in x["per_model_p"])]
print(f"total specs                                : {len(res)}")
print(f"specs using resampling                     : {len(resamp)}   <-- claim says 'all ... 64'")
print(f"specs sitting EXACTLY on the floor          : {len(exact_floor)}  (all pooling=pooled)")
print(f"Fisher-'separate' resampling specs          : {len(sep)}")
print(f"   ... with ALL 4 per-model p at the floor  : {len(sep_allfloor)}")
print(f"   ... with >=1 per-model p at the floor    : {len(sep_anyfloor)}")
print(f"FLOOR-LIMITED specs (no resolution at all)  : {len(exact_floor) + len(sep_allfloor)} / {len(res)}")
# show that the 'impressive' Fisher values are pure arithmetic on the floor
L = R.fisher_log10([math.log10(FLOOR)] * 4)
print(f"\nFisher(4 x floor) = 1e{L:.4f} = {10**L:.4e}")
obs = sorted(set(round(x['p'], 20) for x in sep_allfloor))
print(f"observed distinct p among the {len(sep_allfloor)} all-floor Fisher specs: {obs}")
print("-> those p ~ 9.0e-13 are NOT evidence; they are chi2_sf(-8*ln(1/10001), 8).")
print("   They are the MOST extreme-looking resampling p in the whole curve and")
print("   contain strictly zero information beyond 'each per-model p <= 1e-4'.")

print("\n" + "=" * 100)
print("(B) resolving the floored permutation p-values analytically")
print("=" * 100)
print("Method: the cluster sign-flip statistic is  T(s) = (1/D) * sum_g s_g w_g")
print("        with D invariant under flipping, so the null tail of the OBSERVED")
print("        statistic equals P(|sum_g s_g w_g| >= |sum_g w_g|), s_g iid Rademacher.")
print("        Hoeffding bound (rigorous, no distributional assumption):")
print("            p_exact <= 2 exp(-S^2 / (2 * sum_g w_g^2))")
print("        CLT approximation:  z = S / sqrt(sum_g w_g^2),  p ~= erfc(|z|/sqrt2).")
print()


def weights(recs, unit):
    """Per-cluster weights w_g such that the permutation statistic is
    (100/D) * sum_g s_g w_g with D invariant under sign flips."""
    bycl = {}
    for r in recs:
        bycl.setdefault(r["cluster"], []).append(r)
    W, D = [], 0.0
    if unit == "cell":
        for g in sorted(bycl):
            rs = bycl[g]
            W.append(sum(r["B_correct"] - r["A_correct"] for r in rs))
        D = len(recs)
    elif unit == "item":
        nit = len(set(r["question_id"] for r in recs))
        for g in sorted(bycl):
            rs = bycl[g]
            byit = {}
            for r in rs:
                byit.setdefault(r["question_id"], []).append(r)
            W.append(sum((sum(x["B_correct"] for x in qr) - sum(x["A_correct"] for x in qr)) / len(qr)
                         for qr in byit.values()))
        D = nit
    elif unit == "cluster":
        for g in sorted(bycl):
            rs = bycl[g]
            W.append((sum(r["B_correct"] for r in rs) - sum(r["A_correct"] for r in rs)) / len(rs))
        D = len(bycl)
    elif unit == "model":
        mn = {m: sum(1 for r in recs if r["model"] == m) for m in MODELS}
        for g in sorted(bycl):
            rs = bycl[g]
            W.append(sum((sum(r["B_correct"] - r["A_correct"] for r in rs if r["model"] == m)) / mn[m]
                         for m in MODELS))
        D = NM
    return W, D


def erfc_p(z):
    return math.erfc(abs(z) / math.sqrt(2.0))


rowsout = []
print(f"{'exclusion':<12}{'outcome':<9}{'unit':<9}{'delta_pp':>9}  {'reported p':>11}  "
      f"{'Hoeffding UB':>13}  {'CLT p':>11}")
for exclusion in ("primary", "defect_only", "notaA_only", "none"):
    for outcome in ("lenient", "strict"):
        recs = R.get_rows(exclusion, outcome)
        for unit in ("cell", "item", "cluster", "model"):
            W, D = weights(recs, unit)
            S = sum(W)
            SS = sum(w * w for w in W)
            hoeff = min(1.0, 2.0 * math.exp(-S * S / (2.0 * SS)))
            z = S / math.sqrt(SS)
            pn = erfc_p(z)
            est = 100.0 * S / D
            rep = [x for x in res if x["exclusion"] == exclusion and x["outcome"] == outcome
                   and x["unit"] == unit and x["inference"] == "permutation"
                   and x["pooling"] == "pooled"][0]
            assert abs(rep["delta_pp"] - est) < 1e-9, (rep["delta_pp"], est)
            print(f"{exclusion:<12}{outcome:<9}{unit:<9}{est:9.3f}  {rep['p']:11.3e}  "
                  f"{hoeff:13.3e}  {pn:11.3e}")
            rowsout.append(dict(exclusion=exclusion, outcome=outcome, unit=unit,
                                delta_pp=est, reported_p=rep["p"],
                                hoeffding_ub=hoeff, clt_p=pn, z=z, K=len(W)))
hs = [r["hoeffding_ub"] for r in rowsout]
print(f"\nRIGOROUS Hoeffding upper bounds over the 32 floored permutation specs:")
print(f"   max = {max(hs):.3e}   median = {sorted(hs)[16]:.3e}   min = {min(hs):.3e}")
print("-> every floored permutation p is provably below ~1e-8 WITHOUT any resampling.")
print("   The floor is a reporting artefact of B=10000, not an unresolved p-value.")

print("\n" + "=" * 100)
print("(C) the analytic subset is NOT artefact-free: 24/64 use an invalid Fisher")
print("=" * 100)
analytic = json.load(open(os.path.join(HERE, "sens_refute_mcfloor_01_out.json")))
pooled = [x for x in analytic if x["pooling"] == "pooled"]
separate = [x for x in analytic if x["pooling"] == "separate"]
print(f"analytic specs: {len(analytic)}  = {len(pooled)} pooled + {len(separate)} Fisher-separate")


def summ(tag, specs):
    lps = sorted(x["log10p"] for x in specs)
    ps = sorted(x["p"] for x in specs)
    n = len(ps)
    medp = (ps[n // 2 - 1] + ps[n // 2]) / 2 if n % 2 == 0 else ps[n // 2]
    medl = (lps[n // 2 - 1] + lps[n // 2]) / 2 if n % 2 == 0 else lps[n // 2]
    print(f"{tag:<52} n={n:<4} median p={medp:.3g} (1e{medl:.2f})  max p={ps[-1]:.4g}  "
          f"<0.05={sum(1 for p in ps if p<0.05)/n:.3f}  <0.001={sum(1 for p in ps if p<0.001)/n:.3f}")


summ("claim's 'analytic-only' subset", analytic)
summ("  ... its POOLED half (honest, no Fisher)", pooled)
summ("  ... its FISHER half (independence violated)", separate)

# now recompute the 24 separate specs with dependence-valid combinations
print("\nreplacing Fisher with combinations valid under ARBITRARY dependence:")
print("  Bonferroni/min-p : p = min(4 * min_j p_j, 1)   (valid, any dependence)")
print("  Ruger k=2        : p = min((4/2) * p_(2), 1)   (valid, any dependence)")
print("  max-p (all 4)    : p = max_j p_j              (worst single model)")
fixed = []
for exclusion in ("primary", "defect_only", "notaA_only", "none"):
    for outcome in ("lenient", "strict"):
        recs = R.get_rows(exclusion, outcome)
        per = {"mcnemar_exact": [], "logit_robustSE": [], "ols_robustSE": []}
        pmd = []
        for m in MODELS:
            mr = [r for r in recs if r["model"] == m]
            bb = sum(1 for r in mr if r["A_correct"] == 1 and r["B_correct"] == 0)
            cc = sum(1 for r in mr if r["A_correct"] == 0 and r["B_correct"] == 1)
            per["mcnemar_exact"].append(R.log10_from_fraction(R.mcnemar_exact_frac(bb, cc)))
            per["logit_robustSE"].append(R.logit_cluster_robust(mr)[3])
            bycl = {}
            for r in mr:
                bycl.setdefault(r["cluster"], []).append(r)
            dd, gg = [], []
            for g in sorted(bycl):
                rs = bycl[g]
                dd.append(100.0 * (sum(x["B_correct"] for x in rs) - sum(x["A_correct"] for x in rs)) / len(rs))
                gg.append(g)
            per["ols_robustSE"].append(R.ols_cluster_robust(dd, gg)[3])
            pmd.append(100.0 * (sum(x["B_correct"] for x in mr) - sum(x["A_correct"] for x in mr)) / len(mr))
        for inf, lps in per.items():
            s = sorted(lps)
            bonf = min(0.0, s[0] + math.log10(4))
            rug2 = min(0.0, s[1] + math.log10(2))
            mx = s[-1]
            fi = R.fisher_log10(lps)
            fixed.append(dict(exclusion=exclusion, outcome=outcome, inference=inf,
                              fisher=fi, bonf=bonf, rug2=rug2, maxp=mx,
                              per_model=lps, per_model_delta=pmd))

print(f"\n{'exclusion':<12}{'outcome':<9}{'inference':<16}{'log10 Fisher':>13}{'log10 Bonf':>12}"
      f"{'log10 Ruger2':>13}{'log10 max-p':>12}")
for f in fixed:
    print(f"{f['exclusion']:<12}{f['outcome']:<9}{f['inference']:<16}{f['fisher']:13.2f}"
          f"{f['bonf']:12.2f}{f['rug2']:13.2f}{f['maxp']:12.2f}")

# rebuild the analytic subset with Bonferroni instead of Fisher
rebuilt = [dict(x) for x in pooled]
for f in fixed:
    unit = "cluster" if f["inference"] == "ols_robustSE" else "cell"
    rebuilt.append(dict(exclusion=f["exclusion"], outcome=f["outcome"], unit=unit,
                        inference=f["inference"], pooling="separate",
                        p=10 ** f["bonf"], log10p=f["bonf"]))
print()
summ("analytic subset, Fisher -> Bonferroni min-p", rebuilt)
rebuilt2 = [dict(x) for x in pooled]
for f in fixed:
    unit = "cluster" if f["inference"] == "ols_robustSE" else "cell"
    rebuilt2.append(dict(exclusion=f["exclusion"], outcome=f["outcome"], unit=unit,
                         inference=f["inference"], pooling="separate",
                         p=10 ** f["maxp"], log10p=f["maxp"]))
summ("analytic subset, Fisher -> worst-model max-p", rebuilt2)

print("\n" + "=" * 100)
print("(D) per-model disaggregation -- what the 64-spec count hides")
print("=" * 100)
recs = R.get_rows("primary", "lenient")
print(f"{'model':<28}{'accA%':>8}{'accB%':>8}{'delta_pp':>10}{'b':>6}{'c':>6}"
      f"{'log10 McNemar':>15}{'log10 cl-OLS':>14}")
for m in MODELS:
    mr = [r for r in recs if r["model"] == m]
    bb = sum(1 for r in mr if r["A_correct"] == 1 and r["B_correct"] == 0)
    cc = sum(1 for r in mr if r["A_correct"] == 0 and r["B_correct"] == 1)
    accA = 100.0 * sum(r["A_correct"] for r in mr) / len(mr)
    accB = 100.0 * sum(r["B_correct"] for r in mr) / len(mr)
    lp = R.log10_from_fraction(R.mcnemar_exact_frac(bb, cc))
    bycl = {}
    for r in mr:
        bycl.setdefault(r["cluster"], []).append(r)
    dd, gg = [], []
    for g in sorted(bycl):
        rs = bycl[g]
        dd.append(100.0 * (sum(x["B_correct"] for x in rs) - sum(x["A_correct"] for x in rs)) / len(rs))
        gg.append(g)
    lo = R.ols_cluster_robust(dd, gg)[3]
    print(f"{m:<28}{accA:8.2f}{accB:8.2f}{accB-accA:10.2f}{bb:6d}{cc:6d}{lp:15.2f}{lo:14.2f}")

json.dump(dict(perm_resolution=rowsout, fisher_fix=fixed),
          open(os.path.join(HERE, "sens_refute_mcfloor_02_out.json"), "w"), indent=1)

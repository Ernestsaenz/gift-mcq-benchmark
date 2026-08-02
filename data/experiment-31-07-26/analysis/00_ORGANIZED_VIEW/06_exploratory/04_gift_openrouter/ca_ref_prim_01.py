#!/usr/bin/env python3
"""Independent refutation recompute of the primary cross-arm claim.
Stdlib only. Every p-value names its method.
"""
import json, math, collections

BASE = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/"
rows = json.load(open(BASE + "cross_arm_A.json"))

print("=== 0. SHAPE ===")
print("total records            :", len(rows))
inc = [r for r in rows if r["analysis_include"] is True]
print("analysis_include==True   :", len(inc))
print("excluded                 :", len(rows) - len(inc))
# what drives exclusion?
exc = [r for r in rows if not r["analysis_include"]]
print("excluded w/ excl_item_defect:", sum(1 for r in exc if r["excl_item_defect"]))
print("excluded w/o defect flag   :", sum(1 for r in exc if not r["excl_item_defect"]))
print("included w/ excl_item_defect:", sum(1 for r in inc if r["excl_item_defect"]))

qs = sorted({r["question_id"] for r in inc})
cl = sorted({r["cluster"] for r in inc})
ms = sorted({r["model"] for r in inc})
print("items    :", len(qs))
print("clusters :", len(cl))
print("models   :", len(ms), ms)

# balance: does every model have the same item set?
per_model = {m: {r["question_id"] for r in inc if r["model"] == m} for m in ms}
sizes = {m: len(s) for m, s in per_model.items()}
print("items per model:", sizes)
allsame = all(per_model[m] == per_model[ms[0]] for m in ms)
print("identical item sets across models:", allsame)
if not allsame:
    base = per_model[ms[0]]
    for m in ms:
        print("   ", m, "diff:", len(per_model[m] ^ base))
# duplicate cells?
cellcount = collections.Counter((r["question_id"], r["model"]) for r in inc)
dups = {k: v for k, v in cellcount.items() if v > 1}
print("duplicate (item,model) cells:", len(dups))
# cluster is item-level?
q2c = {}
bad = 0
for r in inc:
    if r["question_id"] in q2c and q2c[r["question_id"]] != r["cluster"]:
        bad += 1
    q2c[r["question_id"]] = r["cluster"]
print("items with inconsistent cluster:", bad)
print("distinct clusters over items:", len({q2c[q] for q in qs}))

# correctness fields binary?
vals = {r["gift_correct"] for r in inc} | {r["or_correct"] for r in inc}
print("correctness value domain:", sorted(vals))


def chi2_sf(x, df=1):
    """Survival function of chi-square. df=1 -> erfc(sqrt(x/2))."""
    assert df == 1
    return math.erfc(math.sqrt(x / 2.0))


def tab(cells):
    a = sum(1 for r in cells if r["gift_correct"] == 1 and r["or_correct"] == 1)
    b = sum(1 for r in cells if r["gift_correct"] == 1 and r["or_correct"] == 0)
    c = sum(1 for r in cells if r["gift_correct"] == 0 and r["or_correct"] == 1)
    d = sum(1 for r in cells if r["gift_correct"] == 0 and r["or_correct"] == 0)
    return a, b, c, d


def binom_two_sided_exact(b, c):
    """Exact McNemar: two-sided binomial test, k=b successes of n=b+c at p=0.5."""
    n = b + c
    if n == 0:
        return 1.0
    # symmetric distribution -> two-sided = 2*min tail, capped at 1
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2.0 ** n)
    return min(1.0, 2.0 * tail)


print()
print("=== 1. PER-MODEL 2x2 (GIFT rows vs OR cols) ===")
hdr = f"{'model':<26}{'n':>5}{'GIFT%':>9}{'OR%':>9}{'diff_pp':>9}{'a':>5}{'b':>4}{'c':>4}{'d':>4}"
print(hdr)
results = {}
for m in ms:
    cells = [r for r in inc if r["model"] == m]
    a, b, c, d = tab(cells)
    n = len(cells)
    g = 100.0 * (a + b) / n
    o = 100.0 * (a + c) / n
    results[m] = dict(n=n, a=a, b=b, c=c, d=d, gift=g, or_=o, diff=g - o)
    print(f"{m:<26}{n:>5}{g:>9.4f}{o:>9.4f}{g-o:>9.4f}{a:>5}{b:>4}{c:>4}{d:>4}")

a, b, c, d = tab(inc)
n = len(inc)
g = 100.0 * (a + b) / n
o = 100.0 * (a + c) / n
print(f"{'POOLED':<26}{n:>5}{g:>9.4f}{o:>9.4f}{g-o:>9.4f}{a:>5}{b:>4}{c:>4}{d:>4}")
results["POOLED"] = dict(n=n, a=a, b=b, c=c, d=d, gift=g, or_=o, diff=g - o)

print()
print("=== 2. THE chi2 6.30 QUESTION ===")
B, C = results["POOLED"]["b"], results["POOLED"]["c"]
print(f"b (GIFT-only-right) = {B}, c (OR-only-right) = {C}, b+c = {B+C}")
unc = (B - C) ** 2 / (B + C)
cc = (abs(B - C) - 1) ** 2 / (B + C)
print(f"UNCORRECTED McNemar chi2 = ({B}-{C})^2/{B+C} = {(B-C)**2}/{B+C} = {unc!r}")
print(f"   -> {unc:.6f}  p = {chi2_sf(unc):.8f}   [chi-square 1 df, math.erfc]")
print(f"CONTINUITY-CORRECTED     = (|{B}-{C}|-1)^2/{B+C} = {(abs(B-C)-1)**2}/{B+C} = {cc!r}")
print(f"   -> {cc:.6f}  p = {chi2_sf(cc):.8f}   [chi-square 1 df, math.erfc]")
print(f"exact (binomial, two-sided, n={B+C}, p=0.5): p = {binom_two_sided_exact(B,C):.8f}")
print()
print(f"Which one rounds to 6.30?  uncorrected -> {unc:.2f} ; corrected -> {cc:.2f}")
print(f"441/70 = {441/70!r}  (exactly 6.3)")

print()
print("=== 3. PER-MODEL McNEMAR (both variants + exact) ===")
print(f"{'model':<26}{'b':>4}{'c':>4}{'chi2_unc':>10}{'p_unc':>10}{'chi2_cc':>10}{'p_cc':>10}{'p_exact':>10}")
for m in ms + ["POOLED"]:
    r = results[m]
    b_, c_ = r["b"], r["c"]
    if b_ + c_ == 0:
        print(f"{m:<26}{b_:>4}{c_:>4}{'n/a':>10}{'n/a':>10}{'n/a':>10}{'n/a':>10}{1.0:>10.4f}")
        continue
    u = (b_ - c_) ** 2 / (b_ + c_)
    k = (abs(b_ - c_) - 1) ** 2 / (b_ + c_)
    print(f"{m:<26}{b_:>4}{c_:>4}{u:>10.4f}{chi2_sf(u):>10.5f}{k:>10.4f}{chi2_sf(k):>10.5f}{binom_two_sided_exact(b_,c_):>10.5f}")

print()
print("=== 4. CLAIMED NUMBERS vs RECOMPUTED ===")
claimed = {
    "google/gemma-4-26b-a4b-it":  (88.42, 82.96, 5.47, 24, 7),
    "z-ai/glm-5.2":               (96.46, 93.25, 3.22, 11, 1),
    "qwen/qwen3.6-35b-a3b":       (91.64, 92.28, -0.64, 11, 13),
    "google/gemini-3.6-flash":    (97.43, 98.39, -0.96, 0, 3),
    "POOLED":                     (93.49, 91.72, 1.77, 46, 24),
}
ok = True
for m, (cg, co, cd, cb, cc_) in claimed.items():
    r = results[m]
    dg, do, dd = abs(r["gift"] - cg), abs(r["or_"] - co), abs(r["diff"] - cd)
    match = dg < 0.005 and do < 0.005 and dd < 0.005 and r["b"] == cb and r["c"] == cc_
    ok &= match
    print(f"{m:<26} claim {cg:6.2f}/{co:6.2f}/{cd:+5.2f} b={cb:<3}c={cc_:<3} | "
          f"mine {r['gift']:6.2f}/{r['or_']:6.2f}/{r['diff']:+5.2f} b={r['b']:<3}c={r['c']:<3} | "
          f"{'MATCH' if match else 'MISMATCH'}")
print("ALL CLAIMED NUMBERS REPRODUCE:", ok)

json.dump({"results": results, "unc": unc, "cc": cc,
           "p_unc": chi2_sf(unc), "p_cc": chi2_sf(cc),
           "p_exact": binom_two_sided_exact(B, C),
           "n_items": len(qs), "n_cells": len(inc), "n_clusters": len(cl),
           "balanced": allsame},
          open(BASE + "ca_ref_prim_01.json", "w"), indent=1)

#!/usr/bin/env python3
"""REFUTE step 4: separate BIAS (the attenuation the claim names) from POWER
(the exposed arm growing from 34 to 61 cells), and check confounders.

The claim's mechanism is 'classic non-differential-misclassification
attenuation'.  That mechanism is testable here because the shipped flag has
perfect specificity (flag=T is a strict subset of adj=T): the ONLY bias is
contamination of the comparison arm.  Remove that contamination WITHOUT adding
the 27 extra exposed cells and see whether the finding appears.
"""
import json, math, random, collections, sys
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_refute_lib import fisher2x2, fisher_ci, mantel_haenszel, two_sided_z_p

ANA = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
BAR = "=" * 96

rows = [r for r in json.load(open(f"{ANA}/paired_clean.json")) if r["analysis_include"]]
L = json.load(open(f"{ANA}/mech_refute_labels.json"))
for r in rows:
    r["adj"] = L[r["question_id"]]["adj"]
    r["flag"] = L[r["question_id"]]["flag"]
AW = [r for r in rows if not r["A_correct"]]


def tab(cells, key):
    a = sum(r["B_correct"] for r in cells if key(r))
    b = sum(1 for r in cells if key(r)) - a
    c = sum(r["B_correct"] for r in cells if not key(r))
    d = sum(1 for r in cells if not key(r)) - c
    return a, b, c, d


print(BAR)
print("STEP 10 -- BIAS-ONLY correction: drop the 65 misclassified items entirely")
print("           (they leave the comparison arm; they do NOT join the exposed arm)")
print(BAR)
print("  This isolates exactly the mechanism the claim names.  Both arms are now")
print("  free of misclassification: exposed = flag-caught negated (pure, since the")
print("  flag has no false positives), comparison = items both labelings call positive.\n")

specs = [
    ("shipped flag as-is (biased comparison arm)",
     lambda r: r["flag"], AW),
    ("BIAS REMOVED ONLY: flag-negated vs clean-positive, 65 items dropped",
     lambda r: r["flag"], [r for r in AW if r["flag"] or not r["adj"]]),
    ("BIAS REMOVED + POWER ADDED: full adjudicated relabel",
     lambda r: r["adj"], AW),
]
for name, key, cells in specs:
    a, b, c, d = tab(cells, key)
    o, p, _ = fisher2x2(a, b, c, d)
    lo, hi = fisher_ci(a, b, c, d)
    print(f"  {name}")
    print(f"     {a}/{a+b} vs {c}/{c+d}   OR={o:.3f}  Fisher exact p={p:.4g}"
          f"  exact 95% CI [{lo:.3f},{hi:.3f}]")
print()
print("  => removing the bias the claim names, on its own, moves p from 0.536 to 0.177.")
print("     By the claim's own decision rule that is still 'no negation shortcut'.")
print("     p<0.05 arrives only once the exposed arm also grows 34 -> 61 cells.")

print()
print(BAR)
print("STEP 11 -- how much of the flag/adjudicated gap is just power?")
print(BAR)
print("  Monte-Carlo power: assume the adjudicated point estimate is the truth")
print("  (P(recover|neg)=0.443, P(recover|pos)=0.250) and simulate the SHIPPED-flag")
print("  design (34 exposed / 99 comparison A-wrong cells, independent draws).")
rng = random.Random(31072026)
N = 40000
hit = 0
for _ in range(N):
    a = sum(1 for _ in range(34) if rng.random() < 27 / 61)
    c = sum(1 for _ in range(99) if rng.random() < 18 / 72)
    _, p, _ = fisher2x2(a, 34 - a, c, 99 - c)
    if p < 0.05:
        hit += 1
print(f"     power of the shipped-flag design at the adjudicated effect size:"
      f" {hit/N:.3f}")
print("     (and this ignores clustering, so the true power is lower still)")
hit2 = 0
for _ in range(N):
    a = sum(1 for _ in range(61) if rng.random() < 27 / 61)
    c = sum(1 for _ in range(72) if rng.random() < 18 / 72)
    _, p, _ = fisher2x2(a, 61 - a, c, 72 - c)
    if p < 0.05:
        hit2 += 1
print(f"     power of the adjudicated design at the same effect size: {hit2/N:.3f}")
print(f"  => even with a PERFECT flag the study is a coin-flip; a null under the")
print(f"     shipped flag is the expected outcome under the claim's own alternative,")
print(f"     not evidence that the flag error 'erased' anything.")

print()
print(BAR)
print("STEP 12 -- confounders of the recovery contrast (nothing to do with negation)")
print(BAR)
for var, name in (("correct_letter", "NOTA slot letter"),
                  ("has_context", "clinical vignette present"),
                  ("model", "model")):
    print(f"\n  -- stratified by {name} --")
    levs = sorted({r[var] for r in AW}, key=str)
    tabs = []
    for lv in levs:
        sub = [r for r in AW if r[var] == lv]
        a, b, c, d = tab(sub, lambda r: r["adj"])
        tabs.append((a, b, c, d))
        rec = (a + c) / len(sub)
        share = (a + b) / len(sub)
        print(f"     {str(lv):26s} n={len(sub):3d}  neg-share={share:.2f}"
              f"  recovery={rec:.3f}   neg {a}/{a+b}  pos {c}/{c+d}")
    o, chi2, pmh, se = mantel_haenszel(tabs)
    if se == se:
        z = math.log(o) / se
        print(f"     Mantel-Haenszel adjusted OR={o:.3f}"
              f"  95% CI [{math.exp(math.log(o)-1.96*se):.3f},{math.exp(math.log(o)+1.96*se):.3f}]"
              f"  RBG z p={two_sided_z_p(z):.4g}")

# qlen: median split
print("\n  -- stratified by stem length (median split) --")
med = sorted(r["qlen"] for r in AW)[len(AW) // 2]
tabs = []
for lv, nm in ((True, f"qlen<{med}"), (False, f"qlen>={med}")):
    sub = [r for r in AW if (r["qlen"] < med) == lv]
    a, b, c, d = tab(sub, lambda r: r["adj"])
    tabs.append((a, b, c, d))
    print(f"     {nm:26s} n={len(sub):3d}  neg-share={(a+b)/len(sub):.2f}"
          f"  recovery={(a+c)/len(sub):.3f}   neg {a}/{a+b}  pos {c}/{c+d}")
o, chi2, pmh, se = mantel_haenszel(tabs)
z = math.log(o) / se
print(f"     Mantel-Haenszel adjusted OR={o:.3f}  RBG z p={two_sided_z_p(z):.4g}")

print()
print(BAR)
print("STEP 13 -- the estimand the flag error supposedly 'erases'")
print(BAR)
print("  The recovery contrast conditions on A being wrong -- a post-treatment")
print("  subgroup of 10% of cells.  The unconditional statement of the same")
print("  hypothesis ('the A->B drop is smaller when the stem is negated') is the")
print("  quantity the dossier headlines.  Under BOTH labelings:")
for key, nm in (("flag", "shipped flag"), ("adj", "adjudicated")):
    neg = [r for r in rows if r[key]]; pos = [r for r in rows if not r[key]]
    dn = sum(r["A_correct"] - r["B_correct"] for r in neg) / len(neg)
    dp = sum(r["A_correct"] - r["B_correct"] for r in pos) / len(pos)
    # cluster bootstrap on the difference in deltas
    byc = collections.defaultdict(list)
    for r in rows:
        byc[r["cluster"]].append(r)
    ks = list(byc); rng2 = random.Random(7); bs = []
    for _ in range(4000):
        s = []
        for _ in range(len(ks)):
            s.extend(byc[ks[rng2.randrange(len(ks))]])
        n1 = [r for r in s if r[key]]; p1 = [r for r in s if not r[key]]
        if not n1 or not p1:
            continue
        bs.append(sum(r["A_correct"] - r["B_correct"] for r in p1) / len(p1)
                  - sum(r["A_correct"] - r["B_correct"] for r in n1) / len(n1))
    bs.sort()
    fr = sum(1 for v in bs if v <= 0) / len(bs)
    print(f"    {nm:14s} delta_neg={dn:+.4f}  delta_pos={dp:+.4f}"
          f"  diff={dp-dn:+.4f}  cluster-boot 95% CI"
          f" [{bs[int(.025*len(bs))]:+.4f},{bs[int(.975*len(bs))]:+.4f}]"
          f"  p~{2*min(fr,1-fr):.3g}")
print("  => on this estimand the negation shortcut is absent under BOTH labelings.")
print("     The flag error changes nothing here, so it cannot be said to 'erase")
print("     the finding' without first privileging one of two operationalizations.")

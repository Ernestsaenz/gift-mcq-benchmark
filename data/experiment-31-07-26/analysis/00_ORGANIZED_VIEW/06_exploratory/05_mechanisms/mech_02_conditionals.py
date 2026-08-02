"""nota-acceptance: decompose B performance into knowledge vs willingness-to-pick-NOTA.

Per model:
  P(B correct | A correct)  -- knew it, saw the key text removed: does it endorse NOTA?
  P(B correct | A wrong)    -- did NOT know it, yet lands on the NOTA slot: odd-one-out?

Methods (all pure stdlib, implemented here or in mech_nota_lib / stats_lib):
  - Clopper-Pearson exact binomial CIs (mech_nota_lib.cp_ci; stats_lib's version is buggy).
  - Fisher exact 2x2 (two-sided, point-probability method) for within-model and pairwise.
  - Pearson chi-square on the 4x2 model x outcome table for the across-model contrast.
  - Exact two-sided binomial test vs the 25% random-guess floor.
  - Mantel-Haenszel common odds ratio stratified by ITEM (difficulty-controlled),
    with Robins-Breslow-Greenland variance -> normal-approx p-value.
"""
import json
import math
from collections import defaultdict

import stats_lib as S
from mech_nota_lib import binom_test_exact, cp_ci, fisher_2x2

ROWS = [r for r in json.load(open(
    "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
    "experiment-31-07-26/analysis/paired_clean.json")) if r["analysis_include"]]

MODELS = sorted(set(r["model"] for r in ROWS))
SHORT = {m: m.split("/")[-1] for m in MODELS}


def pct(k, n):
    return 100.0 * k / n if n else float("nan")


def cistr(k, n):
    lo, hi = cp_ci(k, n)
    return f"[{100*lo:4.1f},{100*hi:5.1f}]"


print("=" * 104)
print("1. CONDITIONAL DECOMPOSITION OF B  (1299 cells | 325 items | 208 clusters | key letter in {b,c,d})")
print("=" * 104)
hdr = f"{'model':<22}{'A acc':>8}{'B acc':>8}{'drop':>8}   {'P(B ok | A ok)':<30}{'P(B ok | A wrong)':<30}"
print(hdr)
cond = {}
for m in MODELS:
    rs = [r for r in ROWS if r["model"] == m]
    n = len(rs)
    Aok = [r for r in rs if r["A_correct"] == 1]
    Abad = [r for r in rs if r["A_correct"] == 0]
    kA, kB = len(Aok), sum(r["B_correct"] for r in rs)
    k1 = sum(r["B_correct"] for r in Aok)
    k0 = sum(r["B_correct"] for r in Abad)
    cond[m] = dict(n=n, kA=kA, kB=kB, n1=len(Aok), k1=k1, n0=len(Abad), k0=k0)
    print(f"{SHORT[m]:<22}{pct(kA,n):>7.1f}%{pct(kB,n):>7.1f}%{pct(kA,n)-pct(kB,n):>7.1f}   "
          f"{pct(k1,len(Aok)):>5.1f}% {cistr(k1,len(Aok))} {k1:>3}/{len(Aok):<4}   "
          f"{pct(k0,len(Abad)):>5.1f}% {cistr(k0,len(Abad))} {k0:>3}/{len(Abad):<4}")

pk1 = sum(cond[m]["k1"] for m in MODELS); pn1 = sum(cond[m]["n1"] for m in MODELS)
pk0 = sum(cond[m]["k0"] for m in MODELS); pn0 = sum(cond[m]["n0"] for m in MODELS)
print(f"{'POOLED (4 models)':<22}{'':>7} {'':>7} {'':>7}    "
      f"{pct(pk1,pn1):>5.1f}% {cistr(pk1,pn1)} {pk1:>3}/{pn1:<4}   "
      f"{pct(pk0,pn0):>5.1f}% {cistr(pk0,pn0)} {pk0:>3}/{pn0:<4}")

print()
print("   within-model: P(B|A ok) vs P(B|A wrong)   [Fisher exact 2x2, two-sided]")
for m in MODELS + ["POOLED"]:
    if m == "POOLED":
        k1, n1, k0, n0 = pk1, pn1, pk0, pn0
        lab = "POOLED"
    else:
        c = cond[m]; k1, n1, k0, n0 = c["k1"], c["n1"], c["k0"], c["n0"]
        lab = SHORT[m]
    p = fisher_2x2(k1, n1 - k1, k0, n0 - k0)
    orr = ((k1 + .5) * (n0 - k0 + .5)) / ((n1 - k1 + .5) * (k0 + .5))
    print(f"   {lab:<22} diff={pct(k1,n1)-pct(k0,n0):+6.1f} pp   OR(Haldane-corrected)={orr:5.2f}   p={p:.3g}")

print()
print("   P(B correct | A wrong) vs the 25% random-guess floor  [exact two-sided binomial test]")
for m in MODELS:
    c = cond[m]
    print(f"   {SHORT[m]:<22} {c['k0']:>3}/{c['n0']:<4} = {pct(c['k0'],c['n0']):5.1f}%   p={binom_test_exact(c['k0'],c['n0'],0.25):.3g}")
print(f"   {'POOLED':<22} {pk0:>3}/{pn0:<4} = {pct(pk0,pn0):5.1f}%   p={binom_test_exact(pk0,pn0,0.25):.3g}")

# ------------------------------------------------- 2. across-model comparisons
print()
print("=" * 104)
print("2. ACROSS-MODEL COMPARISON")
print("=" * 104)


def chi2_kx2(succ, tot):
    N, Sm = sum(tot), sum(succ)
    ps = Sm / N
    x2 = 0.0
    for s, t in zip(succ, tot):
        for obs, e in ((s, t * ps), (t - s, t * (1 - ps))):
            if e > 0:
                x2 += (obs - e) ** 2 / e
    return x2, len(succ) - 1, S.chi2_sf(x2, len(succ) - 1)


for label, kk, nn in (
    ("P(B ok | A wrong)  KEY", [cond[m]["k0"] for m in MODELS], [cond[m]["n0"] for m in MODELS]),
    ("P(B ok | A correct)", [cond[m]["k1"] for m in MODELS], [cond[m]["n1"] for m in MODELS]),
    ("A accuracy", [cond[m]["kA"] for m in MODELS], [cond[m]["n"] for m in MODELS]),
    ("B accuracy", [cond[m]["kB"] for m in MODELS], [cond[m]["n"] for m in MODELS]),
):
    x2, df, p = chi2_kx2(kk, nn)
    rates = "  ".join(f"{SHORT[m][:10]}={pct(k,n):.1f}%({k}/{n})" for m, k, n in zip(MODELS, kk, nn))
    print(f"  {label:<24} chi2({df})={x2:7.2f}  p={p:<10.3g} {rates}")

print()
print("  pairwise P(B correct | A wrong)  [Fisher exact, two-sided; Holm step-down]")
pairs = []
for i in range(len(MODELS)):
    for j in range(i + 1, len(MODELS)):
        a, b = MODELS[i], MODELS[j]
        ca, cb = cond[a], cond[b]
        pairs.append((fisher_2x2(ca["k0"], ca["n0"] - ca["k0"], cb["k0"], cb["n0"] - cb["k0"]),
                      a, b, pct(ca["k0"], ca["n0"]), pct(cb["k0"], cb["n0"])))
pairs.sort()
prev = 0.0
for idx, (p, a, b, ra, rb) in enumerate(pairs):
    adj = min(1.0, max(prev, (len(pairs) - idx) * p)); prev = adj
    print(f"    {SHORT[a][:20]:<20} {ra:5.1f}%  vs  {SHORT[b][:20]:<20} {rb:5.1f}%   p={p:.3g}  p_holm={adj:.3g}")

# ------------------------------- 3. item-stratified (difficulty-controlled) MH
print()
print("=" * 104)
print("3. IS THE A-ok / A-wrong GAP JUST ITEM DIFFICULTY?")
print("   Mantel-Haenszel odds ratio for (A correct -> B correct), STRATIFIED BY ITEM.")
print("   Only the 4 model-cells of the same item are compared, so item difficulty,")
print("   stem wording, distractor quality and NOTA position are all held fixed.")
print("=" * 104)
by_item = defaultdict(list)
for r in ROWS:
    by_item[r["question_id"]].append(r)

num = den = 0.0
R_ = Sx = P_R = P_S = Q_R = Q_S = 0.0
informative = 0
for qid, rs in by_item.items():
    a = sum(1 for r in rs if r["A_correct"] == 1 and r["B_correct"] == 1)
    b = sum(1 for r in rs if r["A_correct"] == 1 and r["B_correct"] == 0)
    c = sum(1 for r in rs if r["A_correct"] == 0 and r["B_correct"] == 1)
    d = sum(1 for r in rs if r["A_correct"] == 0 and r["B_correct"] == 0)
    n = a + b + c + d
    if (a + b) == 0 or (c + d) == 0 or (a + c) == 0 or (b + d) == 0:
        continue                      # non-informative stratum
    informative += 1
    R_ += a * d / n
    Sx += b * c / n
    P_R += ((a + d) / n) * (a * d / n)
    P_S += ((a + d) / n) * (b * c / n) + ((b + c) / n) * (a * d / n)
    Q_S += ((b + c) / n) * (b * c / n)
OR_mh = R_ / Sx if Sx else float("inf")
var = P_R / (2 * R_ ** 2) + P_S / (2 * R_ * Sx) + Q_S / (2 * Sx ** 2)
z = abs(math.log(OR_mh)) / var ** 0.5
p = S.two_sided_z_p(z)
print(f"   informative strata (items where models split on A and on B): {informative}")
print(f"   OR_MH = {OR_mh:.2f}   95% CI = [{OR_mh*math.exp(-1.96*var**0.5):.2f}, "
      f"{OR_mh*math.exp(1.96*var**0.5):.2f}]   z={z:.2f}   p={p:.3g}   [Robins-Breslow-Greenland SE]")

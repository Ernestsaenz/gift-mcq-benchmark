"""Step 2: where does B land, conditional on A being wrong?

The claim benchmarks P(B correct | A wrong) against a 25% "four-option guess floor".
That floor is the behaviour of a model that re-guesses uniformly over the 4 slots.
But in B, three of the four options are the SAME TEXT as in A -- including the exact
distractor the model chose in A. So the within-cell control is: among the three slots
the model did NOT choose in A, is the NOTA slot picked more often than the two
ordinary unchosen distractors? Under any "no NOTA-directed process" model
(sticky OR uniform re-guessing) the three unchosen slots are exchangeable.
"""
from collections import defaultdict, Counter
import mech_ref_nota_lib as L

rows = L.cells()
MODELS = sorted({r["model"] for r in rows})
short = {m: m.split("/")[-1] for m in MODELS}

print("=== overall A/B accuracy (context for the conditioning) ===")
for m in MODELS + ["POOLED"]:
    sub = rows if m == "POOLED" else [r for r in rows if r["model"] == m]
    a = sum(r["A_correct"] for r in sub); b = sum(r["B_correct"] for r in sub)
    print(f"  {short.get(m,m):>22s} n={len(sub):4d}  A={a/len(sub)*100:5.1f}%  B={b/len(sub)*100:5.1f}%"
          f"   A-wrong n={len(sub)-a:3d}")

print("\n=== destination of B, conditional on A wrong ===")
print(f"{'model':>22s} {'n':>4s} {'stay(=A_sel)':>13s} {'NOTA(=corr)':>12s} {'other distr':>12s}")
agg = Counter()
per = {}
for m in MODELS:
    sub = [r for r in rows if r["model"] == m and r["A_correct"] == 0]
    stay = sum(1 for r in sub if r["B_selected"] == r["A_selected"])
    nota = sum(1 for r in sub if r["B_selected"] == r["correct_letter"])
    other = len(sub) - stay - nota
    per[m] = (stay, nota, other)
    agg["stay"] += stay; agg["nota"] += nota; agg["other"] += other; agg["n"] += len(sub)
    print(f"{short[m]:>22s} {len(sub):4d} {stay:6d} ({stay/len(sub)*100:4.1f}%) "
          f"{nota:5d} ({nota/len(sub)*100:4.1f}%) {other:5d} ({other/len(sub)*100:4.1f}%)")
n = agg["n"]
print(f"{'POOLED':>22s} {n:4d} {agg['stay']:6d} ({agg['stay']/n*100:4.1f}%) "
      f"{agg['nota']:5d} ({agg['nota']/n*100:4.1f}%) {agg['other']:5d} ({agg['other']/n*100:4.1f}%)")

print("\n--- Test 1: among the 3 slots NOT chosen in A, is NOTA picked more than an "
      "ordinary unchosen distractor?  (H0: 1/3 of switches; exact binomial) ---")
for m in MODELS + ["POOLED"]:
    if m == "POOLED":
        stay, nota, other = agg["stay"], agg["nota"], agg["other"]
    else:
        stay, nota, other = per[m]
    sw = nota + other
    if sw == 0:
        print(f"  {short.get(m,m):>22s} no switches"); continue
    lo, hi = L.clopper_pearson(nota, sw)
    p2 = L.binom_exact_2sided(nota, sw, 1 / 3)
    p1 = L.binom_exact_1sided_greater(nota, sw, 1 / 3)
    print(f"  {short.get(m,m):>22s} NOTA share of switches {nota:3d}/{sw:3d} = {nota/sw*100:5.1f}% "
          f"CP95[{lo*100:.1f},{hi*100:.1f}]  vs 1/3: p2={p2:.2e} p1={p1:.2e}")

print("\n--- Test 2: NOTA slot vs a matched unchosen distractor slot (rate per slot) ---")
for m in MODELS + ["POOLED"]:
    if m == "POOLED":
        stay, nota, other, nn = agg["stay"], agg["nota"], agg["other"], n
    else:
        stay, nota, other = per[m]; nn = sum(per[m])
    per_slot_other = other / 2 / nn
    print(f"  {short.get(m,m):>22s} P(NOTA slot)={nota/nn*100:5.1f}%   "
          f"P(a given unchosen ordinary distractor)={per_slot_other*100:5.1f}%   "
          f"ratio={(nota/nn)/per_slot_other if per_slot_other else float('inf'):.2f}x")

print("\n--- Test 3: same decomposition when A was CORRECT (model knew the answer) ---")
print(f"{'model':>22s} {'n':>4s} {'NOTA(=corr)':>12s} {'other':>10s}")
for m in MODELS + ["POOLED"]:
    sub = [r for r in rows if r["A_correct"] == 1 and (m == "POOLED" or r["model"] == m)]
    nota = sum(1 for r in sub if r["B_selected"] == r["correct_letter"])
    print(f"  {short.get(m,m):>22s} {len(sub):4d} {nota:5d} ({nota/len(sub)*100:5.1f}%)")

print("\n--- Test 4: 3x2 sanity, is the destination split heterogeneous across models? ---")
tbl = [[per[m][0], per[m][1], per[m][2]] for m in MODELS]
x2, df, p = L.chisq_table(tbl)
print("  stay/nota/other by model chi2=%.2f df=%d p=%.3f" % (x2, df, p))
for m, r in zip(MODELS, tbl):
    print("   ", short[m], r)

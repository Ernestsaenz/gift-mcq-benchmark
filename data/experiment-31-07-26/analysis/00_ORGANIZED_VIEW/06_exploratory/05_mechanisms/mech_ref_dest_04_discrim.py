"""REFUTATION pass 4: does 'every B error is a positive distractor pick' actually
discriminate re-routing from the alternatives?  Build the A->B flow table, the
conditional P(B wrong | A right), and check whether the observable the claim
rests on is predicted equally by NOTA-aversion.  Stdlib only."""
import json, collections, math, random

BASE = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26"
inc = [r for r in json.load(open(f"{BASE}/analysis/paired_clean.json"))
       if r["analysis_include"]]
LET = ["a", "b", "c", "d"]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


print("=" * 78)
print("1. A->B FLOW")
print("=" * 78)
t = collections.Counter((c["A_correct"], c["B_correct"]) for c in inc)
print(f"  A right & B right : {t[(1,1)]}")
print(f"  A right & B WRONG : {t[(1,0)]}")
print(f"  A wrong & B right : {t[(0,1)]}")
print(f"  A wrong & B wrong : {t[(0,0)]}")
p, lo, hi = wilson(t[(1, 0)], t[(1, 0)] + t[(1, 1)])
print(f"\n  P(B wrong | A right) = {t[(1,0)]}/{t[(1,0)]+t[(1,1)]} = {p:.3%} "
      f"[95% Wilson {lo:.1%},{hi:.1%}]")
p2, lo2, hi2 = wilson(t[(0, 1)], t[(0, 1)] + t[(0, 0)])
print(f"  P(B right | A wrong) = {t[(0,1)]}/{t[(0,1)]+t[(0,0)]} = {p2:.3%} "
      f"[95% Wilson {lo2:.1%},{hi2:.1%}]")
print(f"\n  -> the {t[(1,0)]} cells in 'A right & B wrong' are items where the model "
      "demonstrably reproduced the key text in A and still declined the NOTA slot in B.")
print("     A pure loss-of-recognition-shortcut account has to explain why knowing "
      "the key did not translate into detecting its absence.")

print()
print("=" * 78)
print("2. IS 'ALL B ERRORS ARE DISTRACTOR PICKS' DIAGNOSTIC?")
print("=" * 78)
print("  Under the response schema the reply must satisfy "
      "selected_letter in enum[a,b,c,d] (strict json_schema, required).")
print("  Therefore, for EVERY hypothesis in the open question --")
print("    H1 recognition-shortcut loss, H2 NOTA-aversion, H3 cannot reject all "
      "three, H4 plain added difficulty --")
print("  the predicted observable is identical: a letter from {a,b,c,d}, hence a")
print("  'positive selection of a surviving distractor' whenever it is not the NOTA slot.")
print("  P(observation | H) = 1 for all four -> likelihood ratio 1 -> zero evidential value.")

print()
print("=" * 78)
print("3. WHERE THE NOTA SLOT SITS, AND WHETHER B ACCURACY TRACKS IT")
print("=" * 78)
byL = collections.defaultdict(lambda: [0, 0])
for c in inc:
    byL[c["correct_letter"]][0] += c["B_correct"]
    byL[c["correct_letter"]][1] += 1
for L in LET:
    k, n = byL[L]
    if n:
        p, lo, hi = wilson(k, n)
        print(f"  NOTA at slot {L}: B accuracy {k}/{n} = {p:.1%} [{lo:.1%},{hi:.1%}]")
byLA = collections.defaultdict(lambda: [0, 0])
for c in inc:
    byLA[c["correct_letter"]][0] += c["A_correct"]
    byLA[c["correct_letter"]][1] += 1
print("  (same slots, condition A for reference)")
for L in LET:
    k, n = byLA[L]
    if n:
        print(f"    key at slot {L}: A accuracy {k}/{n} = {k/n:.1%}")

print()
print("=" * 78)
print("4. DESTINATION OF B ERRORS -- LAST-SLOT BIAS AS AN INDEPENDENT CHECK")
print("=" * 78)
for lbl, key, ok in (("A", "A_selected", "A_correct"), ("B", "B_selected", "B_correct")):
    r = collections.Counter()
    for c in inc:
        if c[ok]:
            continue
        surv = [L for L in LET if L != c["correct_letter"]]
        r[surv.index(c[key])] += 1
    n = sum(r.values())
    print(f"  cond {lbl}: survivor-rank counts {[r[i] for i in range(3)]} (n={n}) "
          f"fracs {[round(r[i]/n,3) for i in range(3)]}")

print()
print("=" * 78)
print("5. WHAT THE CLAIM'S OWN CHECKS COULD HAVE DETECTED")
print("=" * 78)
print("  'null B_selected' scans a column whose alphabet is {a,b,c,d} by construction:")
print("   ", sorted(set(c["B_selected"] for c in inc)))
print("  'B errors that selected the NOTA letter' is  sum(B_correct==0 and "
      "B_selected==correct_letter),")
print("   but B_correct == (B_selected==correct_letter) holds in all 1299 rows, so the "
      "predicate is unsatisfiable.")
bad = sum(1 for c in inc if c["B_correct"] != int(c["B_selected"] == c["correct_letter"]))
print(f"   rows violating that identity: {bad}  -> the test can only ever return 0.")

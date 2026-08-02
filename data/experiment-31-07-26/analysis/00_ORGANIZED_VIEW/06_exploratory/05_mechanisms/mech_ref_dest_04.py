"""Part 4: final sensitivity checks + two-proportion comparisons."""
import math, collections, sys
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_ref_dest_01 import chi2sf, gof, cells, surv, L, Aerr, Berr

print("\n" + "#" * 76); print("PART 4"); print("#" * 76)
drop = [c for c in cells if c["A_correct"] and not c["B_correct"]]
both = [c for c in cells if not c["A_correct"] and not c["B_correct"]]
copyf = [c for c in both if c["A_selected"] == c["B_selected"]]

def two_prop(k1, n1, k2, n2, lab):
    p1, p2 = k1/n1, k2/n2
    p = (k1+k2)/(n1+n2)
    se = math.sqrt(p*(1-p)*(1/n1+1/n2))
    z = (p1-p2)/se
    print(f"   {lab}: {p1:.4f} (n={n1}) vs {p2:.4f} (n={n2})  z={z:+.2f} "
          f"p={math.erfc(abs(z)/math.sqrt(2)):.4f}  [two-proportion z-test, pooled SE]")

print("=" * 76)
print("S1. Is the item-level concentration NEW in B, or already in A?")
print("=" * 76)
two_prop(158, 216, 45, 67, "within-item destination agreement  B-all vs A ")
two_prop(90, 128, 45, 67, "within-item destination agreement  B-DROP vs A")

print("\n" + "=" * 76)
print("S2. Sensitivity of the 2x4 'flat null' to the copy-forward cells")
print("=" * 76)
print(f"   BOTH-wrong cells whose B choice == their A choice: {len(copyf)}/{len(both)} "
      f"({len(copyf)/len(Berr):.1%} of the 335-cell B row)")
def lp(rows, key):
    o = collections.Counter()
    for c in rows: o[c[key]] += 1
    return [o[x] for x in L]
def indep(r0, r1):
    k = len(r0); t = sum(r0)+sum(r1)
    ct = [r0[j]+r1[j] for j in range(k)]; rt = [sum(r0), sum(r1)]
    s = sum((r[j]-rt[i]*ct[j]/t)**2/(rt[i]*ct[j]/t)
            for i, r in enumerate([r0, r1]) for j in range(k) if ct[j] > 0)
    return s, k-1
oA = lp(Aerr, "A_selected")
for lab, rows in [("full B pool (335, as claimed)", Berr),
                  ("B minus copy-forward (257)   ", [c for c in Berr if c not in copyf]),
                  ("B DROP only (247)            ", drop)]:
    o = lp(rows, "B_selected"); x, df = indep(oA, o)
    print(f"   2x4 vs A errors, {lab}: obs={o}  X2={x:.2f} df={df} p={chi2sf(x,df):.4f}")

print("\n" + "=" * 76)
print("S3. What the 2x4 could NOT have detected (equivalence framing)")
print("=" * 76)
# 95% CI on the A-vs-B difference in each letter's share (unpooled, normal approx)
nA, nB = sum(oA), len(Berr)
oB = lp(Berr, "B_selected")
for j, x in enumerate(L):
    p1, p2 = oA[j]/nA, oB[j]/nB
    se = math.sqrt(p1*(1-p1)/nA + p2*(1-p2)/nB)
    d = p2-p1
    print(f"   letter {x}: B-A share diff = {d:+.4f}  95% CI [{d-1.96*se:+.4f}, {d+1.96*se:+.4f}]"
          f"   [Wald CI on a difference of proportions]")
print("   -> the data are consistent with per-letter shifts of up to ~+/-9-10 percentage")
print("      points; 'no new positional signature AT ALL' is not what these CIs support.")

print("\n" + "=" * 76)
print("S4. Design caveat on letter 'a'")
print("=" * 76)
allc = __import__("json").load(open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
                                    "data/experiment-31-07-26/analysis/paired_clean.json"))
exA = [r for r in allc if r["excl_nota_position_a"]]
print(f"   rows with excl_nota_position_a=True: {len(exA)} "
      f"(items: {len(set(r['question_id'] for r in exA))})")
print(f"   -> letter 'a' is a distractor in 100% of RETAINED items by construction, so the")
print(f"      a-obs/exp=0.81 is measured on a positionally selected subsample.")

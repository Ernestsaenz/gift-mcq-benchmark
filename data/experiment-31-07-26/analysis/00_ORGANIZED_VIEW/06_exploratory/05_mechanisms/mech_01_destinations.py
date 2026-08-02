"""(a) Where do B errors go? Uniformity across the three surviving distractors."""
import sys, collections
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_lib import *

Q = load_questions()
cells = load_cells()
models = sorted(set(c["model"] for c in cells))

print("=" * 78)
print("0. ERROR VOLUME")
print("=" * 78)
nA = sum(1 - c["A_correct"] for c in cells)
nB = sum(1 - c["B_correct"] for c in cells)
print(f"cells={len(cells)}  A errors={nA} ({nA/len(cells):.3%})  B errors={nB} ({nB/len(cells):.3%})")
for m in models:
    r = [c for c in cells if c["model"] == m]
    a = sum(1 - c["A_correct"] for c in r); b = sum(1 - c["B_correct"] for c in r)
    print(f"  {m:28s} n={len(r)}  A_err={a:3d}  B_err={b:3d}  delta={b-a:+d}")

# no refusals / nulls?
print("null A_selected:", sum(1 for c in cells if not c["A_selected"]),
      " null B_selected:", sum(1 for c in cells if not c["B_selected"]))
print("B errors that selected the NOTA letter but were scored wrong:",
      sum(1 for c in cells if c["B_correct"] == 0 and c["B_selected"] == c["correct_letter"]))

print()
print("=" * 78)
print("1. DESTINATION BY ABSOLUTE LETTER (expected from availability)")
print("=" * 78)
# in B, correct_letter is the NOTA slot; survivors = other 3 letters.
# 'a' is never correct in the included set -> always available.
obs = collections.Counter()
avail = collections.Counter()
for c in cells:
    if c["B_correct"]:
        continue
    obs[c["B_selected"]] += 1
    for L in LETTERS:
        if L != c["correct_letter"]:
            avail[L] += 1.0 / 3.0
letters = [L for L in LETTERS]
o = [obs[L] for L in letters]
e = [avail[L] for L in letters]
x2, df = chisq_gof(o, e)
p = chisq_sf(x2, df)
print(f"{'letter':8s} {'obs':>6s} {'exp':>8s} {'obs/exp':>8s}")
for L, oo, ee in zip(letters, o, e):
    print(f"{L:8s} {oo:6d} {ee:8.1f} {oo/ee:8.2f}")
print(f"chi2 GOF vs availability-weighted uniform: X2={x2:.2f} df={df} p={p:.3e}")

# same for A errors, as the baseline attractor map
obsA = collections.Counter()
availA = collections.Counter()
for c in cells:
    if c["A_correct"]:
        continue
    obsA[c["A_selected"]] += 1
    for L in LETTERS:
        if L != c["correct_letter"]:
            availA[L] += 1.0 / 3.0
oA = [obsA[L] for L in letters]; eA = [availA[L] for L in letters]
x2A, dfA = chisq_gof(oA, eA); pA = chisq_sf(x2A, dfA)
print("\nA-condition errors (same availability structure):")
for L, oo, ee in zip(letters, oA, eA):
    print(f"{L:8s} {oo:6d} {ee:8.1f} {oo/ee:8.2f}")
print(f"chi2 GOF: X2={x2A:.2f} df={dfA} p={pA:.3e}")

# A vs B destination distribution: 4x2 contingency (letter x condition), errors only
print("\nA-error vs B-error destination distribution (2x4 chi-square of independence):")
rows = [oA, o]
tot = sum(oA) + sum(o)
colt = [oA[i] + o[i] for i in range(4)]
rowt = [sum(oA), sum(o)]
x2c = 0.0
for i in range(2):
    for j in range(4):
        ex = rowt[i] * colt[j] / tot
        if ex > 0:
            x2c += (rows[i][j] - ex) ** 2 / ex
pc = chisq_sf(x2c, 3)
print(f"  X2={x2c:.2f} df=3 p={pc:.3e}   (A n={sum(oA)}, B n={sum(o)})")

print()
print("=" * 78)
print("2. DESTINATION BY RANK-POSITION AMONG THE THREE SURVIVORS")
print("=" * 78)
rank = collections.Counter()
for c in cells:
    if c["B_correct"]:
        continue
    surv = [L for L in LETTERS if L != c["correct_letter"]]
    rank[surv.index(c["B_selected"])] += 1
n = sum(rank.values())
o2 = [rank[i] for i in range(3)]
e2 = [n / 3.0] * 3
x22, df2 = chisq_gof(o2, e2); p2 = chisq_sf(x22, df2)
print(f"1st surviving slot: {o2[0]:4d}   2nd: {o2[1]:4d}   3rd: {o2[2]:4d}   (n={n})")
print(f"chi2 GOF vs uniform(1/3): X2={x22:.2f} df={df2} p={p2:.3e}")

rankA = collections.Counter()
for c in cells:
    if c["A_correct"]:
        continue
    surv = [L for L in LETTERS if L != c["correct_letter"]]
    rankA[surv.index(c["A_selected"])] += 1
nA2 = sum(rankA.values()); o2A = [rankA[i] for i in range(3)]
x22A, _ = chisq_gof(o2A, [nA2 / 3.0] * 3)
print(f"A errors  1st:{o2A[0]:4d}  2nd:{o2A[1]:4d}  3rd:{o2A[2]:4d}  (n={nA2}) "
      f"X2={x22A:.2f} p={chisq_sf(x22A,2):.3e}")

print()
print("=" * 78)
print("3. PER-MODEL DESTINATION PROFILE (rank among survivors)")
print("=" * 78)
for m in models:
    rk = collections.Counter()
    for c in cells:
        if c["model"] != m or c["B_correct"]:
            continue
        surv = [L for L in LETTERS if L != c["correct_letter"]]
        rk[surv.index(c["B_selected"])] += 1
    nn = sum(rk.values())
    oo = [rk[i] for i in range(3)]
    xx, _ = chisq_gof(oo, [nn / 3.0] * 3)
    print(f"{m:28s} n={nn:4d}  [{oo[0]:3d} {oo[1]:3d} {oo[2]:3d}]  "
          f"frac=[{oo[0]/nn:.3f} {oo[1]/nn:.3f} {oo[2]/nn:.3f}]  X2={xx:.2f} p={chisq_sf(xx,2):.4f}")

print()
print("=" * 78)
print("4. ITEM-LEVEL CONCENTRATION (do the 4 models pile onto one distractor?)")
print("=" * 78)
# For each item, tally errors over the 3 survivors; compare concentration to
# multinomial-uniform expectation via the pairwise-agreement statistic.
items = collections.defaultdict(list)
for c in cells:
    if not c["B_correct"]:
        items[c["question_id"]].append(c["B_selected"])
pairs_same = pairs_tot = 0
dist_k = collections.Counter()
for q, sel in items.items():
    k = len(sel)
    dist_k[k] += 1
    cnt = collections.Counter(sel)
    pairs_same += sum(v * (v - 1) // 2 for v in cnt.values())
    pairs_tot += k * (k - 1) // 2
print("items with >=1 B error:", len(items), " distribution of #erring models:",
      dict(sorted(dist_k.items())))
print(f"within-item pairwise agreement on destination: {pairs_same}/{pairs_tot} = "
      f"{pairs_same/pairs_tot:.4f}  (chance if independent-uniform over 3 = 0.3333)")

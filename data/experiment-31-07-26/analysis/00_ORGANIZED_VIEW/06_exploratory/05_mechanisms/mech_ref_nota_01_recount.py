"""Step 1: independent recount of P(B correct | A wrong) and the claim's tests."""
from collections import defaultdict, Counter
import mech_ref_nota_lib as L

rows = L.cells()
print("cells:", len(rows), "items:", len({r["question_id"] for r in rows}),
      "clusters:", len({r["cluster"] for r in rows}), "models:", len({r["model"] for r in rows}))

# --- integrity: does A_correct == (A_selected == correct_letter)? any nulls?
bad = [r for r in rows if r["A_correct"] != int(r["A_selected"] == r["correct_letter"])]
badB = [r for r in rows if r["B_correct"] != int(r["B_selected"] == r["correct_letter"])]
nullA = [r for r in rows if r["A_selected"] not in L.LETTERS]
nullB = [r for r in rows if r["B_selected"] not in L.LETTERS]
print("A_correct mismatch:", len(bad), " B_correct mismatch:", len(badB),
      " non-letter A_selected:", len(nullA), Counter(r["A_selected"] for r in nullA),
      " non-letter B_selected:", len(nullB), Counter(r["B_selected"] for r in nullB))

MODELS = sorted({r["model"] for r in rows})
short = {m: m.split("/")[-1] for m in MODELS}
print("models:", [short[m] for m in MODELS])

# --- the claim's headline conditional
print("\n=== P(B correct | A wrong) ===")
tab = {}
for m in MODELS:
    sub = [r for r in rows if r["model"] == m and r["A_correct"] == 0]
    k = sum(r["B_correct"] for r in sub)
    n = len(sub)
    lo, hi = L.clopper_pearson(k, n)
    p2 = L.binom_exact_2sided(k, n, 0.25)
    p1 = L.binom_exact_1sided_greater(k, n, 0.25)
    tab[m] = (k, n)
    print(f"  {short[m]:>22s} {k:3d}/{n:3d} = {k/n*100 if n else float('nan'):5.1f}%"
          f"  CP95[{lo*100:.1f},{hi*100:.1f}]  binom2 vs .25 p={p2:.3f}  1-sided p={p1:.3f}")
K = sum(v[0] for v in tab.values()); N = sum(v[1] for v in tab.values())
lo, hi = L.clopper_pearson(K, N)
print(f"  {'POOLED':>22s} {K:3d}/{N:3d} = {K/N*100:5.1f}%  CP95[{lo*100:.1f},{hi*100:.1f}]"
      f"  binom2 p={L.binom_exact_2sided(K,N,0.25):.4f}  1-sided p={L.binom_exact_1sided_greater(K,N,0.25):.4f}")

# --- homogeneity across models
tbl = [[tab[m][0], tab[m][1] - tab[m][0]] for m in MODELS]
x2, df, p = L.chisq_table(tbl)
g, gdf, gp = L.gtest_table(tbl)
print(f"\nPearson chi2({df}) = {x2:.3f}  p={p:.4f}   |  G({gdf}) = {g:.3f} p={gp:.4f}")
mine = [c for r in tbl for c in r]
n_ = sum(mine)
rts = [sum(r) for r in tbl]; cts = [sum(t[j] for t in tbl) for j in (0, 1)]
print("expected cells:", [round(rts[i]*cts[j]/n_, 2) for i in range(4) for j in (0, 1)])

pairs = []
for i in range(len(MODELS)):
    for j in range(i + 1, len(MODELS)):
        a, b = tab[MODELS[i]]; c, d = tab[MODELS[j]]
        pf = L.fisher_2x2(a, b - a, c, d - c)
        pairs.append((f"{short[MODELS[i]]} vs {short[MODELS[j]]}", pf))
for lab, praw, padj in L.holm(pairs):
    print(f"  {lab:<48s} fisher p={praw:.3f}  holm={padj:.3f}")

# --- cluster bootstrap of the pooled conditional
units = defaultdict(list)
for r in rows:
    if r["A_correct"] == 0:
        units[r["cluster"]].append(r)
# include all clusters (even those contributing 0 A-wrong cells) so the resample
# reflects the real cluster population
allc = defaultdict(list)
for r in rows:
    allc[r["cluster"]].append(r)
for c in allc:
    units.setdefault(c, [])


def stat(rs):
    rs = [r for r in rs if r["A_correct"] == 0]
    return sum(r["B_correct"] for r in rs) / len(rs) if rs else None


lo_b, hi_b, dist = L.cluster_bootstrap(units, stat, reps=20000, seed=20260731)
print(f"\ncluster bootstrap (208 clusters, 20000 reps): 95% CI [{lo_b*100:.1f}, {hi_b*100:.1f}]"
      f"   frac of reps <= 0.25: {sum(1 for v in dist if v <= 0.25)/len(dist):.4f}")

import sys, json, math, collections
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_ref_nota2_lib import *

d = load()
print("N =", len(d))

# ---- within-model 2x2 ----
print("\n=== WITHIN-MODEL: P(B ok | A ok) vs P(B ok | A wrong) ===")
print(f"{'model':28s} {'nAok':>5s} {'B|Aok':>7s} {'nAwr':>5s} {'B|Awr':>7s} {'gap pp':>7s} {'OR':>7s} {'Fisher p':>10s}")
rows = {}
for m in sorted({r["model"] for r in d}):
    sub = [r for r in d if r["model"] == m]
    a = sum(1 for r in sub if r["A_correct"] and r["B_correct"])
    b = sum(1 for r in sub if r["A_correct"] and not r["B_correct"])
    c = sum(1 for r in sub if not r["A_correct"] and r["B_correct"])
    e = sum(1 for r in sub if not r["A_correct"] and not r["B_correct"])
    p1, p0 = a / (a + b), c / (c + e) if (c + e) else float("nan")
    pv = fisher_exact_two_sided(a, b, c, e)
    rows[m] = (a, b, c, e)
    print(f"{m:28s} {a+b:5d} {p1:7.3f} {c+e:5d} {p0:7.3f} {100*(p1-p0):7.1f} "
          f"{odds_ratio(a,b,c,e):7.2f} {pv:10.3g}")

# ---- pooled ----
A = sum(1 for r in d if r["A_correct"] and r["B_correct"])
B = sum(1 for r in d if r["A_correct"] and not r["B_correct"])
C = sum(1 for r in d if not r["A_correct"] and r["B_correct"])
E = sum(1 for r in d if not r["A_correct"] and not r["B_correct"])
p1, p0 = A / (A + B), C / (C + E)
print(f"\nPOOLED  a={A} b={B} c={C} d={E}")
print(f"  P(B|Aok)={p1:.4f}  P(B|Awr)={p0:.4f}  gap={100*(p1-p0):.1f}pp  OR={odds_ratio(A,B,C,E):.3f}  "
      f"Fisher p={fisher_exact_two_sided(A,B,C,E):.3g}")
print(f"  share of B-correct arriving via A-wrong route: {C}/{A+C} = {C/(A+C):.4f}")
print(f"  BASE-RATE BENCHMARK: under INDEPENDENCE this share would be P(A wrong) = {(C+E)/len(d):.4f}")
print(f"  recomposition: {(A+B)/len(d):.3f}*{p1:.3f} + {(C+E)/len(d):.3f}*{p0:.3f} = "
      f"{(A+B)/len(d)*p1+(C+E)/len(d)*p0:.4f}  vs B acc {(A+C)/len(d):.4f}  (identity, not evidence)")

print("\n!! pooled gap 45.0pp EXCEEDS every within-model gap -> aggregation across models inflates it")

# ---- MH stratified by question_id ----
by_item = collections.defaultdict(list)
for r in d:
    by_item[r["question_id"]].append(r)
tables = []
for q, rs in by_item.items():
    a = sum(1 for r in rs if r["A_correct"] and r["B_correct"])
    b = sum(1 for r in rs if r["A_correct"] and not r["B_correct"])
    c = sum(1 for r in rs if not r["A_correct"] and r["B_correct"])
    e = sum(1 for r in rs if not r["A_correct"] and not r["B_correct"])
    tables.append((a, b, c, e))
mh = mantel_haenszel(tables)
print("\n=== MANTEL-HAENSZEL stratified by question_id (RBG variance) ===")
print(f"  OR_MH = {mh['or_mh']:.3f}  95% CI [{mh['ci'][0]:.3f}, {mh['ci'][1]:.3f}]  "
      f"z = {mh['z']:.3f}  p = {mh['p']:.3g}")
print(f"  informative strata (R_i>0 or S_i>0) = {mh['n_informative']}")
n_disc = sum(1 for (a, b, c, e) in tables if (a + b) > 0 and (c + e) > 0 and (a + c) > 0 and (b + e) > 0)
print(f"  strata contributing to BOTH R and S (fully discordant) = "
      f"{sum(1 for (a,b,c,e) in tables if a*e>0 and b*c>0)}")
print(f"  strata with both exposure and outcome variation = {n_disc}")
print(f"  -> {325-mh['n_informative']} of 325 items contribute NOTHING to the MH estimate")

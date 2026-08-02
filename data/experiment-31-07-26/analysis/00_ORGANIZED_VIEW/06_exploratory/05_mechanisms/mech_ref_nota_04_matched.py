"""Step 4: is the cross-model comparison of P(B|A wrong) even a like-for-like comparison?

Conditioning on A_correct==0 selects a different item population for every model
(gemini: 7/325 items; gemma: 67/325). Stratify by item hardness and compare models
only within strata / within shared items.
"""
from collections import defaultdict, Counter
import mech_ref_nota_lib as L

rows = L.cells()
MODELS = sorted({r["model"] for r in rows})
short = {m: m.split("/")[-1] for m in MODELS}

# how many models got each item wrong in A
awrong_by_item = defaultdict(set)
seen = defaultdict(set)
for r in rows:
    seen[r["question_id"]].add(r["model"])
    if r["A_correct"] == 0:
        awrong_by_item[r["question_id"]].add(r["model"])

aw = [r for r in rows if r["A_correct"] == 0]
print("=== overlap of the A-wrong sets across models ===")
for m in MODELS:
    s = {q for q, v in awrong_by_item.items() if m in v}
    print(f"  {short[m]:>22s} A-wrong on {len(s):3d} items")
print("  items A-wrong for >=1 model:", len(awrong_by_item),
      " >=2:", sum(1 for v in awrong_by_item.values() if len(v) >= 2),
      " >=3:", sum(1 for v in awrong_by_item.values() if len(v) >= 3),
      " all 4:", sum(1 for v in awrong_by_item.values() if len(v) == 4))
pairs = [(short[a], short[b],
          len({q for q, v in awrong_by_item.items() if a in v and b in v}))
         for i, a in enumerate(MODELS) for b in MODELS[i + 1:]]
print("  pairwise shared A-wrong items:", pairs)

print("\n=== P(B correct | A wrong) stratified by item hardness (#models A-wrong) ===")
for h in (1, 2, 3, 4):
    sub = [r for r in aw if len(awrong_by_item[r["question_id"]]) == h]
    if not sub:
        continue
    k = sum(r["B_correct"] for r in sub)
    lo, hi = L.clopper_pearson(k, len(sub))
    comp = Counter(short[r["model"]] for r in sub)
    print(f"  hardness={h}: {k:3d}/{len(sub):3d} = {k/len(sub)*100:5.1f}% CP95[{lo*100:.0f},{hi*100:.0f}]"
          f"  composition={dict(comp)}")
tbl = []
for h in (1, 2, 3, 4):
    sub = [r for r in aw if len(awrong_by_item[r["question_id"]]) == h]
    if sub:
        tbl.append([sum(r["B_correct"] for r in sub), len(sub) - sum(r["B_correct"] for r in sub)])
x2, df, p = L.chisq_table(tbl)
print(f"  hardness gradient chi2({df})={x2:.2f} p={p:.3f}")

print("\n=== the same, for the NOTA-share-of-switches ===")
for h in (1, 2, 3, 4):
    sub = [r for r in aw if len(awrong_by_item[r["question_id"]]) == h]
    sw = [r for r in sub if r["B_selected"] != r["A_selected"]]
    if not sw:
        continue
    k = sum(1 for r in sw if r["B_selected"] == r["correct_letter"])
    lo, hi = L.clopper_pearson(k, len(sw))
    print(f"  hardness={h}: {k:3d}/{len(sw):3d} = {k/len(sw)*100:5.1f}% CP95[{lo*100:.0f},{hi*100:.0f}]"
          f"  p vs 1/3 = {L.binom_exact_2sided(k,len(sw),1/3):.2e}")

print("\n=== hardness-adjusted (Mantel-Haenszel) comparison of models on P(B|A wrong) ===")
# MH common odds ratio, each model vs the pooled rest, strata = hardness
for m in MODELS:
    num = den = 0.0
    for h in (1, 2, 3, 4):
        sub = [r for r in aw if len(awrong_by_item[r["question_id"]]) == h]
        a = sum(1 for r in sub if r["model"] == m and r["B_correct"])
        b = sum(1 for r in sub if r["model"] == m and not r["B_correct"])
        c = sum(1 for r in sub if r["model"] != m and r["B_correct"])
        d = sum(1 for r in sub if r["model"] != m and not r["B_correct"])
        n = a + b + c + d
        if n:
            num += a * d / n
            den += b * c / n
    print(f"  {short[m]:>22s} MH odds ratio vs rest = {num/den if den else float('nan'):.2f}")

print("\n=== per-model cluster bootstrap of the NOTA-share-of-switches ===")
for m in MODELS:
    units = defaultdict(list)
    for r in rows:
        if r["model"] == m:
            units[r["cluster"]].append(r)

    def f(rs):
        sw = [r for r in rs if r["A_correct"] == 0 and r["B_selected"] != r["A_selected"]]
        if not sw:
            return None
        return sum(1 for r in sw if r["B_selected"] == r["correct_letter"]) / len(sw)

    lo, hi, dist = L.cluster_bootstrap(units, f, reps=20000, seed=4242)
    frac = sum(1 for v in dist if v <= 1 / 3) / len(dist)
    print(f"  {short[m]:>22s} 95% CI [{lo*100:5.1f},{hi*100:5.1f}]  frac reps<=1/3 = {frac:.4f}")

print("\n=== how concentrated are the 45 NOTA hits? ===")
hits = [r for r in aw if r["B_correct"] == 1]
print("  distinct items:", len({r['question_id'] for r in hits}),
      " distinct clusters:", len({r['cluster'] for r in hits}),
      " max hits in one cluster:", Counter(r["cluster"] for r in hits).most_common(1))
sw = [r for r in aw if r["B_selected"] != r["A_selected"]]
print("  switches: distinct clusters:", len({r['cluster'] for r in sw}),
      " leave-one-cluster-out worst NOTA-share:",
      min((sum(1 for r in sw if r['cluster'] != c and r["B_selected"] == r["correct_letter"]) /
           max(1, sum(1 for r in sw if r['cluster'] != c)))
          for c in {r["cluster"] for r in sw}))

print("\n=== does 'A wrong' behave like 'does not know'? negated-stem / context split ===")
for key in ("negated_stem", "has_context"):
    for v in (False, True):
        sub = [r for r in aw if bool(r[key]) == v]
        if not sub:
            continue
        k = sum(r["B_correct"] for r in sub)
        swv = [r for r in sub if r["B_selected"] != r["A_selected"]]
        kk = sum(1 for r in swv if r["B_selected"] == r["correct_letter"])
        print(f"  {key}={v}: P(B|Awrong)={k}/{len(sub)}={k/len(sub)*100:.1f}%   "
              f"NOTA-share-of-switches={kk}/{len(swv)}="
              f"{kk/len(swv)*100 if swv else float('nan'):.1f}%")

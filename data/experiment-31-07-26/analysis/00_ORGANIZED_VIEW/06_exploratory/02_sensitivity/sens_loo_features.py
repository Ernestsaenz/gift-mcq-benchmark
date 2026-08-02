#!/usr/bin/env python3
"""
sens_loo_features.py -- do the most-influential ITEMS share anything?
Two definitions of "influential":
  (a) the literal top-10 by |shift in pooled delta| (what the brief asks for)
  (b) the 25 items at |net| >= 3 -- the group the top-10 is an arbitrary slice of
Tested against all remaining items with a label-shuffling permutation test
(20000 shuffles, two-sided, statistic = difference in proportion / difference in mean).
Stdlib only.
"""
import json, collections, random

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
cells = [r for r in json.load(open(PATH)) if r["analysis_include"]]
N = len(cells); S = sum(c["B_correct"] - c["A_correct"] for c in cells); D0 = 100.0 * S / N

net = collections.defaultdict(int); cnt = collections.Counter(); meta = {}
for c in cells:
    net[c["question_id"]] += c["B_correct"] - c["A_correct"]
    cnt[c["question_id"]] += 1
    meta[c["question_id"]] = c
items = list(net)

def shift(i):
    return 100.0 * (S - net[i]) / (N - cnt[i]) - D0

ranked = sorted(items, key=lambda i: -abs(shift(i)))
top10 = ranked[:10]
big = [i for i in items if abs(net[i]) >= 3]
print(f"top10 = {top10}")
print(f"|net|>=3 group: n={len(big)}")

FEATS = {
    "letter_is_b":  lambda m: 1.0 if m["correct_letter"] == "b" else 0.0,
    "letter_is_c":  lambda m: 1.0 if m["correct_letter"] == "c" else 0.0,
    "letter_is_d":  lambda m: 1.0 if m["correct_letter"] == "d" else 0.0,
    "negated_stem": lambda m: 1.0 if m["negated_stem"] else 0.0,
    "has_context":  lambda m: 1.0 if m["has_context"] else 0.0,
    "qlen":         lambda m: float(m["qlen"]),
    "year>=2021":   lambda m: 1.0 if m["year"] >= 2021 else 0.0,
    "part==main":   lambda m: 1.0 if m["exam_part"] == "main" else 0.0,
}

def perm(group, label, B=20000, seed=7):
    g = set(group)
    rest = [i for i in items if i not in g]
    print(f"\n--- {label} (n={len(g)}) vs rest (n={len(rest)}) "
          f"-- permutation test, {B} label shuffles, two-sided ---")
    rnd = random.Random(seed)
    for fname, f in FEATS.items():
        vals = {i: f(meta[i]) for i in items}
        a = sum(vals[i] for i in g) / len(g)
        b = sum(vals[i] for i in rest) / len(rest)
        obs = a - b
        pool = [vals[i] for i in items]
        k = len(g); ge = 0
        for _ in range(B):
            rnd.shuffle(pool)
            sa = sum(pool[:k]) / k
            sb = sum(pool[k:]) / (len(pool) - k)
            if abs(sa - sb) >= abs(obs) - 1e-12: ge += 1
        p = (1 + ge) / (1 + B)
        star = " *" if p < 0.05 else ""
        print(f"  {fname:>13}: group={a:8.3f}  rest={b:8.3f}  diff={obs:+8.3f}  p={p:.4f}{star}")

perm(top10, "literal top-10 most influential items")
perm(big,   "all items at |net|>=3")

# what fraction of the effect lives in each stratum?
print("\nstratified pooled delta (all analysis cells, no LOO):")
def strat(keyfn, name):
    agg = collections.defaultdict(lambda: [0, 0])
    for c in cells:
        k = keyfn(c); agg[k][0] += c["B_correct"] - c["A_correct"]; agg[k][1] += 1
    print(f"  by {name}:")
    for k in sorted(agg, key=lambda z: str(z)):
        s, n = agg[k]
        print(f"    {str(k):>22}: n={n:>5}  delta={100.0*s/n:+8.3f} pp")
strat(lambda c: c["correct_letter"], "correct_letter")
strat(lambda c: c["has_context"], "has_context")
strat(lambda c: c["negated_stem"], "negated_stem")
strat(lambda c: "short(<=150)" if c["qlen"] <= 150 else ("med(151-500)" if c["qlen"] <= 500 else "long(>500)"), "qlen band")

# cluster 3 identity (the single most influential cluster)
print("\nmost-influential cluster (id 3) contents:")
c3 = [c for c in cells if c["cluster"] == 3]
ids3 = sorted(set(c["question_id"] for c in c3), key=lambda s: int(s[1:]))
print(f"  {len(ids3)} items, {len(c3)} cells, net={sum(x['B_correct']-x['A_correct'] for x in c3)}")
print(f"  region={c3[0]['region']} year={c3[0]['year']} part={c3[0]['exam_part']} "
      f"has_context={c3[0]['has_context']}")
print(f"  items: {ids3}")
per = collections.defaultdict(int)
for c in c3: per[c["question_id"]] += c["B_correct"] - c["A_correct"]
print(f"  per-item net: {dict(sorted(per.items(), key=lambda t: int(t[0][1:])))}")

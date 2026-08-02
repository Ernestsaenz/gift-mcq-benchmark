"""Step 3: THE SHARPEST TEST -- where does the model go when it 'abandons the NOTA slot'?

If the mechanism is a disposition against endorsing the NOTA *string* (the claim), the
model has no positive reason to prefer any particular survivor; destinations should look
like an arbitrary/positional fallback and should NOT agree across independently-run models.

If the mechanism is that one surviving distractor is positively attractive -- i.e. the
model never established the true answer was absent, it just matched the next-best claim
(loss of the recognition shortcut / failure to reject) -- then different models should
CONVERGE on the SAME distractor far more often than chance.
"""
import collections, random
from math import comb
from mech_ref_acc_lib import load_cells, binom_test_exact, cp_ci, chisq_sf

cells = load_cells()
SHORT = {"google/gemini-3.6-flash": "gemini", "z-ai/glm-5.2": "glm",
         "qwen/qwen3.6-35b-a3b": "qwen", "google/gemma-4-26b-a4b-it": "gemma"}
MODELS = ["gemini", "glm", "qwen", "gemma"]
LETTERS = ["a", "b", "c", "d"]
for r in cells:
    r["m"] = SHORT[r["model"]]
by_item = collections.defaultdict(dict)
for r in cells:
    by_item[r["question_id"]][r["m"]] = r

print("=" * 100)
print("A) Positional structure of the B-arm 'abandonment'.  NOTA never sits at letter 'a'")
print("   in the analysis set (correct_letter in {b,c,d}), so 'a' is always a survivor.")
print("=" * 100)
print(f"{'':8} {'A-arm selections':>34} | {'B-arm selections':>34}")
print(f"{'model':8} " + " ".join(f"{L:>8}" for L in LETTERS) + " | " + " ".join(f"{L:>8}" for L in LETTERS))
for m in MODELS:
    rs = [r for r in cells if r["m"] == m]
    ca = collections.Counter(r["A_selected"] for r in rs)
    cb = collections.Counter(r["B_selected"] for r in rs)
    print(f"{m:8} " + " ".join(f"{ca.get(L,0):8}" for L in LETTERS) + " | "
          + " ".join(f"{cb.get(L,0):8}" for L in LETTERS))

print()
print("   Destination of the 247 'refusal' cells (A correct -> B wrong), vs what is available.")
print("   For each such cell the survivors are the 3 letters != correct_letter.")
print(f"   {'model':8} {'n':>5} " + " ".join(f"{L:>10}" for L in LETTERS) + f" {'exp a':>8} {'binom p':>9}")
tot_obs_a = tot_exp_a = tot_n = 0
for m in MODELS + ["POOLED"]:
    rs = [r for r in cells if (m == "POOLED" or r["m"] == m) and r["A_correct"] and not r["B_correct"]]
    c = collections.Counter(r["B_selected"] for r in rs)
    n = len(rs)
    exp_a = sum(1 / 3 for r in rs)          # 'a' is a survivor in every such cell
    obs_a = c.get("a", 0)
    p = binom_test_exact(obs_a, n, 1 / 3)
    if m != "POOLED":
        tot_obs_a += obs_a
        tot_exp_a += exp_a
        tot_n += n
    print(f"   {m:8} {n:5} " + " ".join(f"{c.get(L,0):10}" for L in LETTERS)
          + f" {exp_a:8.1f} {p:9.2g}")
print("   method: exact two-sided binomial test of obs('a') vs p0=1/3 (uniform over the 3 survivors).")

print()
print("=" * 100)
print("B) CROSS-MODEL CONVERGENCE of the abandonment destination.")
print("   Items where >=2 models both went A-correct -> B-wrong.  Do they pick the SAME letter?")
print("   Null: each failing model picks uniformly among the 3 survivors, independently.")
print("=" * 100)
pairs_same = pairs_tot = 0
detail = []
for qid, d in by_item.items():
    fails = [r for r in d.values() if r["A_correct"] and not r["B_correct"]]
    if len(fails) < 2:
        continue
    ls = [r["B_selected"] for r in fails]
    for i in range(len(ls)):
        for j in range(i + 1, len(ls)):
            pairs_tot += 1
            pairs_same += (ls[i] == ls[j])
    detail.append((qid, len(fails), collections.Counter(ls).most_common()))
lo, hi = cp_ci(pairs_same, pairs_tot)
print(f"   concordant model-pairs: {pairs_same}/{pairs_tot} = {100*pairs_same/pairs_tot:.1f}% "
      f"CP95 [{100*lo:.1f},{100*hi:.1f}]   null = 33.3%")
print(f"   exact binomial test vs p0=1/3: p = {binom_test_exact(pairs_same, pairs_tot, 1/3):.3g}")
print("   (pairs are not independent across items -> cluster permutation test below)")

# Cluster permutation: reshuffle each failing model's letter uniformly among survivors,
# preserving the item structure. Monte-Carlo p-value.
rng = random.Random(7)
items = []
for qid, d in by_item.items():
    fails = [r for r in d.values() if r["A_correct"] and not r["B_correct"]]
    if len(fails) >= 2:
        surv = [L for L in LETTERS if L != fails[0]["correct_letter"]]
        items.append((len(fails), surv))
B = 20000
ge = 0
for _ in range(B):
    s = 0
    for nf, surv in items:
        ls = [rng.choice(surv) for _ in range(nf)]
        for i in range(nf):
            for j in range(i + 1, nf):
                s += (ls[i] == ls[j])
    ge += (s >= pairs_same)
print(f"   Monte-Carlo cluster permutation (B={B}, resample destinations uniformly over the 3")
print(f"   survivors within each item): P(concordance >= observed) = {(ge+1)/(B+1):.4g}")

print()
print("   Items where >=3 models abandoned NOTA, and what they chose:")
for qid, nf, mc in sorted(detail, key=lambda t: -t[1])[:14]:
    if nf >= 3:
        print(f"     {qid:>6}  nfail={nf}  correct_letter={by_item[qid][MODELS[0]]['correct_letter']}  -> {mc}")

print()
print("=" * 100)
print("C) Does the destination in B match the destination the model picks when it fails A?")
print("   (i.e. is the B error just the item's pre-existing attractive distractor?)")
print("=" * 100)
# Use OTHER models' A-arm errors on the same item as an item-level 'attractive distractor' marker.
hit = tot = 0
for qid, d in by_item.items():
    # attractive distractor = modal wrong letter chosen in the A arm by any model on this item
    wrongA = [o["A_selected"] for o in d.values() if not o["A_correct"]]
    if not wrongA:
        continue
    modal = collections.Counter(wrongA).most_common(1)[0][0]
    for m, r in d.items():
        if r["A_correct"] and not r["B_correct"]:
            tot += 1
            hit += (r["B_selected"] == modal)
if tot:
    lo, hi = cp_ci(hit, tot)
    print(f"   B-abandonment landed on the item's A-arm attractive distractor: {hit}/{tot} = "
          f"{100*hit/tot:.1f}%  CP95 [{100*lo:.1f},{100*hi:.1f}]  null=33.3%")
    print(f"   exact binomial vs p0=1/3: p = {binom_test_exact(hit, tot, 1/3):.3g}")
    print(f"   (restricted to items with >=1 A-arm error anywhere in the 4-model panel: n={tot} cells)")

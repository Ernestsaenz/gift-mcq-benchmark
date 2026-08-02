import sys, collections, math
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_ref_nota2_lib import *

d = load()
models = sorted({r["model"] for r in d})

# ---------------------------------------------------------------
# 0. per-model marginals: is model ability correlated with model NOTA rate?
# ---------------------------------------------------------------
print("=== per-model marginals (B_correct IS 'selected the NOTA slot') ===")
print(f"{'model':28s} {'A acc':>7s} {'B acc':>7s} {'drop pp':>8s}")
for m in models:
    s = [r for r in d if r["model"] == m]
    aa = sum(r["A_correct"] for r in s) / len(s)
    bb = sum(r["B_correct"] for r in s) / len(s)
    print(f"{m:28s} {aa:7.3f} {bb:7.3f} {100*(aa-bb):8.1f}")
print("-> models with high A accuracy also have high NOTA-pick rate: A_correct is a PROXY FOR MODEL IDENTITY")

# ---------------------------------------------------------------
# 1. conditional logit: item fixed effects, WITH and WITHOUT model adjustment
#    (MH holds the item fixed but lets MODEL vary -- that is the comparison it makes)
# ---------------------------------------------------------------
by_item = collections.defaultdict(list)
for r in d:
    by_item[r["question_id"]].append(r)

def build(with_model):
    strata = []
    for q, rs in by_item.items():
        X, y = [], []
        for r in rs:
            v = [float(r["A_correct"])]
            if with_model:
                v += [1.0 if r["model"] == m else 0.0 for m in models[1:]]
            X.append(v)
            y.append(int(r["B_correct"]))
        strata.append((X, y))
    return strata

print("\n=== conditional logistic regression, strata = question_id (exact conditional likelihood) ===")
r0 = clogit(build(False))
print(f"[item FE only]            beta(A_correct) = {r0['beta'][0]:+.4f}  OR = {math.exp(r0['beta'][0]):.3f}"
      f"  SE = {r0['se'][0]:.4f}  z = {r0['z'][0]:.2f}  p = {r0['p'][0]:.3g}   strata used = {r0['n_strata']}")
r1 = clogit(build(True))
names = ["A_correct"] + [m for m in models[1:]]
print(f"[item FE + MODEL FE]")
for j, nm in enumerate(names):
    print(f"    {nm:28s} beta = {r1['beta'][j]:+.4f}  OR = {math.exp(r1['beta'][j]):6.3f}"
          f"  SE = {r1['se'][j]:.4f}  z = {r1['z'][j]:6.2f}  p = {r1['p'][j]:.3g}")
lr = 2 * (r1["loglik"] - r0["loglik"])
print(f"    LR test for adding model FE: chi2({len(models)-1}) = {lr:.2f}")
shrink = 100 * (1 - (math.exp(r1['beta'][0]) - 1) / (math.exp(r0['beta'][0]) - 1))
print(f"  -> adjusting for MODEL shrinks the A_correct odds ratio by {shrink:.0f}% of its excess over 1")

# how much of the item-stratified signal is model identity alone?
r2 = clogit([(  [[1.0 if r["model"] == m else 0.0 for m in models[1:]] for r in rs],
                [int(r["B_correct"]) for r in rs]) for q, rs in by_item.items()])
print(f"  model-FE-only model (no A_correct): loglik = {r2['loglik']:.2f} vs item-FE-only-with-A_correct "
      f"{r0['loglik']:.2f}, full {r1['loglik']:.2f}")

# ---------------------------------------------------------------
# 2. PLACEBO: letter-level stickiness at DISTRACTOR letters
#    distractor option TEXT is byte-identical in A and B; only the correct
#    option's text changed. So agreement at a distractor letter measures pure
#    response reproducibility with zero knowledge / zero NOTA reasoning.
# ---------------------------------------------------------------
print("\n=== PLACEBO: same MH machinery applied to letters where NOTHING changed ===")
letters = ["a", "b", "c", "d"]
tab_correct, tab_distr = [], []
for q, rs in by_item.items():
    L = rs[0]["correct_letter"]
    for lt in letters:
        a = sum(1 for r in rs if r["A_selected"] == lt and r["B_selected"] == lt)
        b = sum(1 for r in rs if r["A_selected"] == lt and r["B_selected"] != lt)
        c = sum(1 for r in rs if r["A_selected"] != lt and r["B_selected"] == lt)
        e = sum(1 for r in rs if r["A_selected"] != lt and r["B_selected"] != lt)
        (tab_correct if lt == L else tab_distr).append((a, b, c, e))

mhc = mantel_haenszel(tab_correct)
mhd = mantel_haenszel(tab_distr)
print(f"  correct/NOTA letter L (text REPLACED): OR_MH = {mhc['or_mh']:.2f}  CI [{mhc['ci'][0]:.2f},{mhc['ci'][1]:.2f}]"
      f"  informative strata = {mhc['n_informative']}")
print(f"  distractor letters   (text IDENTICAL): OR_MH = {mhd['or_mh']:.2f}  CI [{mhd['ci'][0]:.2f},{mhd['ci'][1]:.2f}]"
      f"  informative strata = {mhd['n_informative']}")
print("  -> a null transformation reproduces the same qualitative 'signal' with a LARGER OR")

# raw agreement
same = sum(1 for r in d if r["A_selected"] == r["B_selected"])
print(f"\n  raw P(B_selected == A_selected) = {same}/{len(d)} = {same/len(d):.3f}")
for m in models:
    s = [r for r in d if r["model"] == m]
    aw = [r for r in s if not r["A_correct"]]
    print(f"    {m:28s} all {sum(1 for r in s if r['A_selected']==r['B_selected'])/len(s):.3f}"
          f"   among A-wrong {sum(1 for r in aw if r['A_selected']==r['B_selected'])/len(aw):.3f} (n={len(aw)})")

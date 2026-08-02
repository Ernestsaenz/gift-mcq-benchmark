"""Extra discriminating tests:
 E1 exam year (a crude memorisation proxy) in the lost model
 E2 does A-correctness still predict B-correctness after controlling item B-difficulty?
 E3 is the peer-difficulty effect on loss just regression to the mean?
 E4 is condition B a constant logit shift, or does it interact with model?
 E5 does the manipulation change WHICH distractor is attractive, or only how often?
"""
import math, collections, random
from mech_who_00_build import cells
from mech_who_lib import logit_fit, cluster_robust, report, wald_joint, _norm_cdf, _chi2_sf

random.seed(11)
MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]

def zc(rows, f):
    v = [f(r) for r in rows]
    m = sum(v) / len(v); s = math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))
    return lambda r: (f(r) - m) / s

def fit(rows, y, terms, label):
    X = [[1.0] + [t[1](r) for t in terms] for r in rows]
    names = ["(intercept)"] + [t[0] for t in terms]
    yy = [float(y(r)) for r in rows]
    cl = [r["cluster"] for r in rows]
    beta, bread, p, ll = logit_fit(X, yy, ridge=1e-8)
    V, G = cluster_robust(X, yy, p, bread, cl)
    print("=" * 90)
    print(f"{label}  n={len(rows)} events={int(sum(yy))}")
    report(names, beta, V, G, "")
    return beta, V, names

print()
Ac = [r for r in cells if r["A_correct"]]
yrs = sorted(set(r["year"] for r in cells))
print("exam years present:", collections.Counter(r["year"] for r in cells))
terms = [("model=gemma-4-26b", lambda r: float(r["model"] == MODELS[1])),
         ("model=qwen3.6-35b", lambda r: float(r["model"] == MODELS[2])),
         ("model=glm-5.2", lambda r: float(r["model"] == MODELS[3])),
         ("peer A-accuracy (LOO)", lambda r: r["loo_A_acc"]),
         ("year (centred on 2022)", lambda r: (r["year"] - 2022)),
         ("negated_stem", lambda r: float(r["negated_stem"])),
         ("has_context", lambda r: float(r["has_context"])),
         ("qlen (z)", zc(Ac, lambda r: r["qlen"])),
         ("NOTA slot = c (vs b)", lambda r: float(r["correct_letter"] == "c")),
         ("NOTA slot = d (vs b)", lambda r: float(r["correct_letter"] == "d"))]
fit(Ac, lambda r: r["lost"], terms, "E1. P(LOST | A correct) with exam year added")

print()
Aw = [r for r in cells if not r["A_correct"]]
b_l, V_l, _ = None, None, None
X = [[1.0] + [t[1](r) for t in terms] for r in Ac]
# ---- E3 reversion test ----
print("=" * 90)
print("E3. IS THE PEER-DIFFICULTY EFFECT ON LOSS JUST REGRESSION TO THE MEAN?")
print("    Under pure reversion (a cell whose A result is out of line with the item's")
print("    difficulty is more likely to flip, in EITHER direction), the peer-accuracy")
print("    coefficient in the LOST model and in the GAINED model must be equal and")
print("    opposite:  beta_lost + beta_gained = 0.")
t_small = [("model=gemma-4-26b", lambda r: float(r["model"] == MODELS[1])),
           ("model=qwen3.6-35b", lambda r: float(r["model"] == MODELS[2])),
           ("model=glm-5.2", lambda r: float(r["model"] == MODELS[3])),
           ("peer A-accuracy (LOO)", lambda r: r["loo_A_acc"])]
bl, Vl, nl = fit(Ac, lambda r: r["lost"], t_small, "   LOST model (A-correct cells)")
bg, Vg, ng = fit(Aw, lambda r: r["gained"], t_small, "   GAINED model (A-wrong cells)")
i = nl.index("peer A-accuracy (LOO)")
s = bl[i] + bg[i]
se = math.sqrt(Vl[i][i] + Vg[i][i])     # disjoint samples -> independent estimates
z = s / se
print(f"\n    beta_lost = {bl[i]:.3f} (SE {math.sqrt(Vl[i][i]):.3f}),  "
      f"beta_gained = {bg[i]:.3f} (SE {math.sqrt(Vg[i][i]):.3f})")
print(f"    sum = {s:.3f}, SE = {se:.3f}, z = {z:.2f}, two-sided p = {2*(1-_norm_cdf(abs(z))):.3f}")
print("    (Wald test on independent samples; p > .05 means the data are consistent with")
print("     the difficulty effect being pure regression to the mean.)")

print()
print("=" * 90)
print("E2. DOES A-CORRECTNESS PREDICT B-CORRECTNESS ONCE ITEM B-DIFFICULTY IS CONTROLLED?")
print("    If condition-A success were mostly a recognition/lookup shortcut it should")
print("    carry little information about performance once the string is gone.")
t2 = [("model=gemma-4-26b", lambda r: float(r["model"] == MODELS[1])),
      ("model=qwen3.6-35b", lambda r: float(r["model"] == MODELS[2])),
      ("model=glm-5.2", lambda r: float(r["model"] == MODELS[3])),
      ("peer B-accuracy on this item (LOO)", lambda r: r["loo_B_acc"]),
      ("peer A-accuracy on this item (LOO)", lambda r: r["loo_A_acc"]),
      ("own A_correct", lambda r: float(r["A_correct"]))]
fit(cells, lambda r: r["B_correct"], t2, "   P(B correct) | peers' B difficulty + own A result")

print()
print("=" * 90)
print("E4. IS CONDITION B A CONSTANT LOGIT SHIFT ACROSS MODELS?  (stacked long data)")
long = []
for r in cells:
    for cond, corr in (("A", r["A_correct"]), ("B", r["B_correct"])):
        long.append(dict(r, cond=cond, y=corr))
t4 = [("model=gemma-4-26b", lambda r: float(r["model"] == MODELS[1])),
      ("model=qwen3.6-35b", lambda r: float(r["model"] == MODELS[2])),
      ("model=glm-5.2", lambda r: float(r["model"] == MODELS[3])),
      ("condition B", lambda r: float(r["cond"] == "B")),
      ("B x gemma", lambda r: float(r["cond"] == "B" and r["model"] == MODELS[1])),
      ("B x qwen", lambda r: float(r["cond"] == "B" and r["model"] == MODELS[2])),
      ("B x glm", lambda r: float(r["cond"] == "B" and r["model"] == MODELS[3]))]
b4, V4, n4 = fit(long, lambda r: r["y"], t4, "   correct ~ model * condition")
ix = [n4.index(x) for x in ("B x gemma", "B x qwen", "B x glm")]
st, df, pv = wald_joint(b4, V4, ix)
print(f"    joint Wald, model x condition interaction: chi2={st:.2f}, df={df}, p={pv:.4g}")
# non-clustered LRT as a sensitivity check
Xf = [[1.0] + [t[1](r) for t in t4] for r in long]
Xr = [row[:len(row) - 3] for row in Xf]
yy = [float(r["y"]) for r in long]
_, _, _, llf = logit_fit(Xf, yy)
_, _, _, llr = logit_fit(Xr, yy)
st2, df2, pv2 = _chi2_sf(2 * (llf - llr), 3), 3, None
print(f"    naive LRT (ignores clustering): chi2={2*(llf-llr):.2f}, df=3, p={st2:.4g}")
print("    (a null interaction = the manipulation costs every model the same number of")
print("     logits, i.e. it behaves like a uniform increase in item difficulty)")

print()
print("=" * 90)
print("E5. DOES THE MANIPULATION CHANGE *WHICH* DISTRACTOR ATTRACTS, OR ONLY HOW OFTEN?")
# (a) slot-level inflation
Aw_c = collections.Counter(r["A_selected"] for r in cells if not r["A_correct"])
Bw_c = collections.Counter(r["B_selected"] for r in cells if not r["B_correct"])
avail = collections.Counter()
for r in cells:
    for L in "abcd":
        if L != r["correct_letter"]: avail[L] += 1
print("    slot-level: pick-rate per available distractor slot")
tot_a, tot_b = sum(Aw_c.values()), sum(Bw_c.values())
chi = 0.0
for L in "abcd":
    ea = tot_a * (Aw_c[L] + Bw_c[L]) / (tot_a + tot_b)
    eb = tot_b * (Aw_c[L] + Bw_c[L]) / (tot_a + tot_b)
    chi += (Aw_c[L] - ea) ** 2 / ea + (Bw_c[L] - eb) ** 2 / eb
print(f"      chi2 homogeneity of the distractor-slot distribution (A-wrong vs B-wrong) "
      f"= {chi:.2f}, df=3, p={_chi2_sf(chi,3):.3f}")
print(f"      inflation factor per slot: " +
      "  ".join(f"{L}:{(Bw_c[L]/avail[L])/(Aw_c[L]/avail[L]):.2f}x" for L in "abcd"))
# (b) item-level lure identity
modA, modB = {}, {}
for r in cells:
    if not r["A_correct"]: modA.setdefault(r["question_id"], []).append(r["A_selected"])
    if not r["B_correct"]: modB.setdefault(r["question_id"], []).append(r["B_selected"])
both = [q for q in modA if q in modB]
agree = sum(1 for q in both
            if collections.Counter(modA[q]).most_common(1)[0][0]
            == collections.Counter(modB[q]).most_common(1)[0][0])
print(f"    item-level: items with >=1 wrong answer in BOTH conditions: {len(both)}")
print(f"      modal lure in A == modal lure in B: {agree}/{len(both)} = {agree/len(both):.3f}")
# permutation null: reshuffle the B lure among the 3 distractors of the item
perm = []
for _ in range(5000):
    a = 0
    for q in both:
        ml = collections.Counter(modA[q]).most_common(1)[0][0]
        cl = [r for r in cells if r["question_id"] == q][0]["correct_letter"]
        opts = [L for L in "abcd" if L != cl]
        a += int(random.choice(opts) == ml)
    perm.append(a / len(both))
perm.sort()
print(f"      permutation null (B lure uniform over the 3 distractors): "
      f"mean {sum(perm)/len(perm):.3f}, 97.5th pct {perm[int(.975*len(perm))]:.3f}")
print(f"      one-sided permutation p = "
      f"{sum(1 for x in perm if x >= agree/len(both))/len(perm):.4f}")

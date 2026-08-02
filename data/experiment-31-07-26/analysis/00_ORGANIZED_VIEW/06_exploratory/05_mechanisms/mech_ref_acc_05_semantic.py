"""Step 5: two structural tests the claim's account cannot produce.

T1 STEM POLARITY. On a negated stem ("senala la respuesta FALSA", "cual NO estaria
   indicado") the arm-B edit deletes the one false statement. If any surviving option is
   also false -- common in real exam items, which are written so that exactly one is
   *most* false -- that survivor is a legitimately correct answer and NOTA is not
   uniquely correct. A disposition against the NOTA string predicts no polarity
   interaction; a broken-construct account predicts a large one.

T2 SEMANTIC COMPETITION. For each 'refusal' cell, rank the 3 surviving options by token
   overlap with the DELETED correct text (pulled from arm A at the same letter). Under
   the claim (arbitrary fallback after refusing a string) the chosen survivor's rank is
   uniform. If the model is still tracking the medicine and simply landed on the nearest
   surviving expression of it, the chosen survivor is the most similar far too often.
"""
import collections, random, re, unicodedata
from mech_ref_acc_lib import (load_cells, load_questions, cp_ci, fisher_2x2,
                              binom_test_exact, chisq_sf)

cells = load_cells()
Q = load_questions()
SHORT = {"google/gemini-3.6-flash": "gemini", "z-ai/glm-5.2": "glm",
         "qwen/qwen3.6-35b-a3b": "qwen", "google/gemma-4-26b-a4b-it": "gemma"}
MODELS = ["gemini", "glm", "qwen", "gemma"]
LETTERS = ["a", "b", "c", "d"]
for r in cells:
    r["m"] = SHORT[r["model"]]

print("=" * 100)
print("T1  P(B correct | A correct) by STEM POLARITY")
print("=" * 100)
print(f"   {'model':8} {'negated stem':>24}   {'plain stem':>24}   {'Fisher p':>9}")
tk1 = tn1 = tk2 = tn2 = 0
for m in MODELS:
    sub = [r for r in cells if r["m"] == m and r["A_correct"]]
    g1 = [r for r in sub if r["negated_stem"]]
    g2 = [r for r in sub if not r["negated_stem"]]
    k1, n1 = sum(r["B_correct"] for r in g1), len(g1)
    k2, n2 = sum(r["B_correct"] for r in g2), len(g2)
    tk1 += k1; tn1 += n1; tk2 += k2; tn2 += n2
    print(f"   {m:8} {k1:4}/{n1:<4} {100*k1/n1:6.1f}%{'':7} {k2:4}/{n2:<4} {100*k2/n2:6.1f}%{'':7} "
          f"{fisher_2x2(k1, n1-k1, k2, n2-k2):9.3g}")
lo1, hi1 = cp_ci(tk1, tn1); lo2, hi2 = cp_ci(tk2, tn2)
print(f"   {'POOLED':8} {tk1:4}/{tn1:<4} {100*tk1/tn1:6.1f}%{'':7} {tk2:4}/{tn2:<4} "
      f"{100*tk2/tn2:6.1f}%{'':7} {fisher_2x2(tk1, tn1-tk1, tk2, tn2-tk2):9.3g}")
print(f"      CP95 negated [{100*lo1:.1f},{100*hi1:.1f}]  plain [{100*lo2:.1f},{100*hi2:.1f}]")
print(f"      'refusal' rate: negated {100-100*tk1/tn1:.1f}%   plain {100-100*tk2/tn2:.1f}%")
print("   method: Fisher exact 2x2, two-sided.")
nref = tn1 - tk1
print(f"      negated-stem items are {100*tn1/(tn1+tn2):.0f}% of A-correct cells but carry "
      f"{100*nref/(nref + tn2-tk2):.0f}% of all 'refusal' cells")

# ---------------- T2 ----------------
_STOP = set("""de la el los las un una unos unas y o u en a al del que se es son por para con sin
sobre como mas menos su sus lo le les ha han hay ser esta este estos estas no ni tras entre""".split())


def toks(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return {t for t in re.findall(r"[a-z0-9]+", s) if len(t) > 3 and t not in _STOP}


def jac(a, b):
    A, B = toks(a), toks(b)
    return len(A & B) / len(A | B) if A and B else 0.0


print()
print("=" * 100)
print("T2  Is the abandoned-to option the surviving option NEAREST the deleted correct text?")
print("=" * 100)
rankcnt = collections.Counter()
ties = 0
n_used = 0
per_model = collections.defaultdict(collections.Counter)
for r in cells:
    if not (r["A_correct"] and not r["B_correct"]):
        continue
    qid, cl = r["question_id"], r["correct_letter"]
    if qid not in Q or "A" not in Q[qid]:
        continue
    deleted = Q[qid]["A"]["opts"][cl]
    surv = [L for L in LETTERS if L != cl]
    sims = {L: jac(deleted, Q[qid]["B"]["opts"][L]) for L in surv}
    order = sorted(surv, key=lambda L: -sims[L])
    ch = r["B_selected"]
    if ch not in sims:
        continue
    # rank 1 = most similar to the deleted correct answer
    rank = 1 + sum(1 for L in surv if sims[L] > sims[ch])
    nsame = sum(1 for L in surv if abs(sims[L] - sims[ch]) < 1e-12)
    if nsame > 1:
        ties += 1
    n_used += 1
    rankcnt[rank] += 1
    per_model[r["m"]][rank] += 1

print(f"   n = {n_used} refusal cells ({ties} involved a similarity tie)")
print(f"   {'rank of chosen survivor':>26} : " + " ".join(f"{i:>7}" for i in (1, 2, 3)))
print(f"   {'observed':>26} : " + " ".join(f"{rankcnt.get(i,0):>7}" for i in (1, 2, 3)))
exp = [n_used / 3] * 3
print(f"   {'uniform null':>26} : " + " ".join(f"{e:>7.1f}" for e in exp))
obs = [rankcnt.get(i, 0) for i in (1, 2, 3)]
x2 = sum((o - e) ** 2 / e for o, e in zip(obs, exp))
print(f"   Pearson chi-square GOF vs uniform: X2={x2:.2f}, df=2, p={chisq_sf(x2,2):.3g}")
k1 = obs[0]
lo, hi = cp_ci(k1, n_used)
print(f"   P(chosen = nearest survivor) = {k1}/{n_used} = {100*k1/n_used:.1f}% "
      f"CP95 [{100*lo:.1f},{100*hi:.1f}]  null 33.3%  "
      f"exact binomial p={binom_test_exact(k1, n_used, 1/3):.3g}")
print("   per model (rank1/rank2/rank3):")
for m in MODELS:
    c = per_model[m]
    tot = sum(c.values())
    print(f"     {m:8} {c.get(1,0):3}/{c.get(2,0):3}/{c.get(3,0):3}   "
          f"P(nearest)={100*c.get(1,0)/tot:.1f}%  p={binom_test_exact(c.get(1,0), tot, 1/3):.3g}")

print()
print("   CONTROL: same ranking computed on B-arm cells that were answered CORRECTLY is")
print("   undefined (they chose NOTA), so instead run the identical statistic on A-arm")
print("   errors -- where no NOTA slot exists and no 'refusal' can occur.")
rc2 = collections.Counter()
n2 = 0
for r in cells:
    if r["A_correct"]:
        continue
    qid, cl = r["question_id"], r["correct_letter"]
    deleted = Q[qid]["A"]["opts"][cl]
    surv = [L for L in LETTERS if L != cl]
    sims = {L: jac(deleted, Q[qid]["A"]["opts"][L]) for L in surv}
    ch = r["A_selected"]
    if ch not in sims:
        continue
    rank = 1 + sum(1 for L in surv if sims[L] > sims[ch])
    rc2[rank] += 1
    n2 += 1
o2 = [rc2.get(i, 0) for i in (1, 2, 3)]
print(f"   A-arm errors, rank of chosen distractor by similarity to the true option:")
print(f"     n={n2}  obs {o2}  P(nearest)={100*o2[0]/n2:.1f}%  "
      f"exact binomial p={binom_test_exact(o2[0], n2, 1/3):.3g}")

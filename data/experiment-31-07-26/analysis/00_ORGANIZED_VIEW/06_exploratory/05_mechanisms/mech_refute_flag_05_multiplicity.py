#!/usr/bin/env python3
"""REFUTE step 5:
(a) does the claim's own misclassification model predict the shipped-flag null?
(b) FWER-corrected, cluster-respecting p for 'the smallest of four labelings'.
"""
import json, math, random, collections, sys
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_refute_lib import fisher2x2

ANA = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
BAR = "=" * 96

rows = [r for r in json.load(open(f"{ANA}/paired_clean.json")) if r["analysis_include"]]
L = json.load(open(f"{ANA}/mech_refute_labels.json"))
OVR = {"b30", "b49", "b158", "b384"}
qids = sorted(L)

LB = {
    "shipped_flag": {q: L[q]["flag"] for q in qids},
    "raw_lexicon": {q: bool(L[q]["explicit"]) or L[q]["bare_no"] for q in qids},
    "adjudicated": {q: (q not in OVR) and (bool(L[q]["explicit"]) or L[q]["bare_no"]) for q in qids},
    "explicit_only": {q: bool(L[q]["explicit"]) for q in qids},
}
AW = [r for r in rows if not r["A_correct"]]

print(BAR)
print("STEP 14 -- does the claim's OWN mechanism predict the shipped-flag result?")
print(BAR)
print("  Under the claim's model: flag sensitivity = 84/149 = {:.3f}, specificity = 1.000"
      .format(84 / 149))
print("  (verified: every flag=T item is adjudicated-negated, so the exposed arm is")
print("   uncontaminated and ALL the bias lives in the comparison arm).")
p1 = 27 / 61
p0 = 18 / 72
n_neg_in_comp = sum(1 for r in AW if not L[r["question_id"]]["flag"] and L[r["question_id"]]["adj"])
n_pos_in_comp = sum(1 for r in AW if not L[r["question_id"]]["flag"] and not L[r["question_id"]]["adj"])
exp_comp = (n_neg_in_comp * p1 + n_pos_in_comp * p0) / (n_neg_in_comp + n_pos_in_comp)
or_pred = (p1 / (1 - p1)) / (exp_comp / (1 - exp_comp))
print(f"  true rates from the adjudicated fit: neg {p1:.3f}, pos {p0:.3f}")
print(f"  comparison arm under the flag = {n_neg_in_comp} truly-negated + {n_pos_in_comp}"
      f" truly-positive A-wrong cells")
print(f"  => predicted contaminated comparison rate {exp_comp:.3f}"
      f" (observed 32/99 = {32/99:.3f})")
print(f"  => OR the flag-based analysis SHOULD show if the adjudicated effect is real:"
      f" {or_pred:.3f}")
print(f"     observed shipped-flag OR = 1.296")
print("  The claim's own model therefore predicts a shipped-flag OR near 1.8, i.e. a")
print("  clearly non-null point estimate that this sample cannot resolve -- NOT the")
print("  'the shortcut disappears' reading the claim puts on p=0.536.")

print()
print(BAR)
print("STEP 15 -- FWER-corrected p for 'the best of four labelings', permuting whole")
print("           items (and whole clusters) so item/cluster dependence is respected")
print(BAR)
obs = {}
for nm, lab in LB.items():
    a = sum(r["B_correct"] for r in AW if lab[r["question_id"]])
    b = sum(1 for r in AW if lab[r["question_id"]]) - a
    c = sum(r["B_correct"] for r in AW if not lab[r["question_id"]])
    d = sum(1 for r in AW if not lab[r["question_id"]]) - c
    obs[nm] = fisher2x2(a, b, c, d)[1]
print("  observed p per labeling: " + "  ".join(f"{k}={v:.4g}" for k, v in obs.items()))
minp = min(obs.values())
print(f"  min p = {minp:.4g} (adjudicated / raw_lexicon)")

itemrows = collections.defaultdict(list)
for r in AW:
    itemrows[r["question_id"]].append(r)
cl_of = {r["question_id"]: r["cluster"] for r in rows}
tuples = [tuple(LB[k][q] for k in LB) for q in qids]
keys = list(LB)


def minp_for(assign):
    best = 1.0
    for i, nm in enumerate(keys):
        a = b = c = d = 0
        for q, t in assign:
            for r in itemrows.get(q, ()):
                if t[i]:
                    if r["B_correct"]: a += 1
                    else: b += 1
                else:
                    if r["B_correct"]: c += 1
                    else: d += 1
        if a + b == 0 or c + d == 0:
            continue
        pv = fisher2x2(a, b, c, d)[1]
        best = min(best, pv)
    return best


NP = 5000
rng = random.Random(20260731)
idx = list(range(len(qids)))
cnt = 0
for _ in range(NP):
    rng.shuffle(idx)
    assign = [(qids[i], tuples[idx[i]]) for i in range(len(qids))]
    if minp_for(assign) <= minp + 1e-12:
        cnt += 1
print(f"  [item-level max-T permutation, {NP} perms] FWER-adjusted p for the best"
      f" labeling = {(cnt+1)/(NP+1):.4g}")

# cluster-level: move the whole label-tuple vector of a cluster
byc = collections.defaultdict(list)
for q in qids:
    byc[cl_of[q]].append(q)
cls = sorted(byc)
vecs = [[tuple(LB[k][q] for k in LB) for q in byc[c]] for c in cls]
cidx = list(range(len(cls)))
rng2 = random.Random(1717)
cnt2 = 0
for _ in range(NP):
    rng2.shuffle(cidx)
    assign = []
    for tgt, src in enumerate(cidx):
        v = vecs[src]
        for j, q in enumerate(byc[cls[tgt]]):
            assign.append((q, v[j % len(v)]))
    if minp_for(assign) <= minp + 1e-12:
        cnt2 += 1
print(f"  [cluster-level max-T permutation, {NP} perms] FWER-adjusted p = {(cnt2+1)/(NP+1):.4g}")

print()
print(BAR)
print("STEP 16 -- summary of every valid p for the adjudicated primary contrast")
print(BAR)
print("""  naive Fisher, cells treated as independent .................. 0.027
  item-level permutation (log-OR) ............................. 0.064
  item-level permutation (rate difference) .................... 0.061
  cluster-level permutation ................................... 0.051
  cluster bootstrap of the log-OR ............................. 0.080
  Mantel-Haenszel by model (ignores item clustering) .......... 0.019
  max-T over the four labelings, item-level ................... see STEP 15
  max-T over the four labelings, cluster-level ................ see STEP 15""")

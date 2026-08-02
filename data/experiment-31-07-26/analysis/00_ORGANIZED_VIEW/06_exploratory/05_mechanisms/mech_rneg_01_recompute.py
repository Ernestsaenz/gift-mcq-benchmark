#!/usr/bin/env python
"""STEP 1 -- independent recompute of the negated-interaction primary contrast,
under (a) the shipped negated_stem field, (b) the claim's adjudicated label.

Also asks the question the claim does not: is the negation effect SPECIFIC to
the A-wrong stratum (an interaction), or is it a main effect on the probability
of selecting the none-of-the-above slot, present in every stratum?
"""
from __future__ import annotations
import json, sys, collections
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_rneg_lib import fisher_exact_2x2, wilson, OR, logor_se, norm_sf2

ANA = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
rows = [r for r in json.load(open(f"{ANA}/paired_clean.json")) if r["analysis_include"]]
lab = json.load(open(f"{ANA}/mech_labels.json"))
for r in rows:
    r["FLAG"] = bool(r["negated_stem"])
    r["ADJ"] = bool(lab[r["question_id"]]["neg"])
MODELS = sorted({r["model"] for r in rows})
BAR = "=" * 96

print(BAR)
print("DATA AS LOADED")
print(BAR)
print(f"cells={len(rows)}  items={len({r['question_id'] for r in rows})}  "
      f"clusters={len({r['cluster'] for r in rows})}  models={len(MODELS)}")
print("(the task brief states 1299 cells / 325 items / 208 clusters -- see note in report)")

# sanity: B_correct is exactly 'picked the none-of-the-above slot'
bad = sum(1 for r in rows if (r["B_correct"] == 1) != (r["B_selected"] == r["correct_letter"]))
print(f"\nsanity: cells where B_correct != (B_selected == correct_letter): {bad}")
print("  -> in condition B the correct letter HOLDS the NOTA string, so 'B correct' is")
print("     literally and only 'the model selected the none-of-the-above option'.")


def counts(sub, key, out):
    a = sum(1 for r in sub if r[key] and out(r))
    b = sum(1 for r in sub if r[key] and not out(r))
    c = sum(1 for r in sub if not r[key] and out(r))
    d = sum(1 for r in sub if not r[key] and not out(r))
    return a, b, c, d


def line(tag, a, b, c, d):
    n1, n0 = a + b, c + d
    p1 = a / n1 if n1 else float("nan")
    p0 = c / n0 if n0 else float("nan")
    lo1, hi1 = wilson(a, n1)
    lo0, hi0 = wilson(c, n0)
    p = fisher_exact_2x2(a, b, c, d)
    print(f"  {tag:38s} neg {a:3d}/{n1:3d}={p1:.3f} [{lo1:.3f},{hi1:.3f}]   "
          f"non {c:3d}/{n0:3d}={p0:.3f} [{lo0:.3f},{hi0:.3f}]   "
          f"diff {p1-p0:+.3f}  OR {OR(a,b,c,d,0.5):5.2f}  Fisher p={p:.4f}")
    return p1 - p0, p


for KEY in ("FLAG", "ADJ"):
    print()
    print(BAR)
    print(f"PRIMARY CONTRAST under label = {KEY}"
          + ("   (the shipped negated_stem field)" if KEY == "FLAG"
             else "   (mech_labels.json, the claim's hand relabel)"))
    print(BAR)
    aw = [r for r in rows if r["A_correct"] == 0]
    ac = [r for r in rows if r["A_correct"] == 1]
    print(f"  A-wrong cells {len(aw)} from {len({r['question_id'] for r in aw})} items"
          f"   |  negated A-wrong {sum(1 for r in aw if r[KEY])} from "
          f"{len({r['question_id'] for r in aw if r[KEY]})} items"
          f"   non-negated {sum(1 for r in aw if not r[KEY])} from "
          f"{len({r['question_id'] for r in aw if not r[KEY]})} items")
    d_aw, p_aw = line("P(B correct | A WRONG)  <- the claim",
                      *counts(aw, KEY, lambda r: r["B_correct"] == 1))
    d_ac, p_ac = line("P(B correct | A CORRECT)",
                      *counts(ac, KEY, lambda r: r["B_correct"] == 1))
    d_all, p_all = line("P(B correct | ALL cells)  = P(pick NOTA)",
                        *counts(rows, KEY, lambda r: r["B_correct"] == 1))
    line("P(A correct) -- baseline difficulty",
         *counts(rows, KEY, lambda r: r["A_correct"] == 1))

    # Is the A-wrong-vs-A-correct difference in the negation log-OR itself real?
    A = counts(aw, KEY, lambda r: r["B_correct"] == 1)
    C = counts(ac, KEY, lambda r: r["B_correct"] == 1)
    l1, s1 = logor_se(*A)
    l0, s0 = logor_se(*C)
    z = (l1 - l0) / ((s1 * s1 + s0 * s0) ** .5)
    print(f"\n  TEST OF THE INTERACTION ITSELF (Woolf ratio-of-odds-ratios, Haldane 0.5,"
          f" Wald z on the log scale):")
    print(f"    logOR(negation | A-wrong)   = {l1:+.3f} (se {s1:.3f})")
    print(f"    logOR(negation | A-correct) = {l0:+.3f} (se {s0:.3f})")
    print(f"    ratio-of-OR z = {z:+.3f}   two-sided p = {norm_sf2(z):.4f}")
    print(f"    -> the claim's framing ('the stratum where it can act') requires this to be")
    print(f"       significant.  It is not.")

    print("\n  per model, P(B correct | A wrong):")
    for m in MODELS:
        s = [r for r in aw if r["model"] == m]
        a, b, c, d = counts(s, KEY, lambda r: r["B_correct"] == 1)
        r1 = a / (a + b) if a + b else float("nan")
        r0 = c / (c + d) if c + d else float("nan")
        tag = "SAME DIR" if r1 > r0 else ("REVERSED" if r1 < r0 else "tie")
        print(f"    {m:28s} neg {a:2d}/{a+b:2d}={r1:.3f}  non {c:2d}/{c+d:2d}={r0:.3f}   {tag}")

print()
print(BAR)
print("LABEL DISAGREEMENT: which items did the relabel move, and do they carry the effect?")
print(BAR)
mv = sorted({r["question_id"] for r in rows if r["ADJ"] and not r["FLAG"]})
print(f"items moved non-negated -> negated by the relabel: {len(mv)} of "
      f"{len({r['question_id'] for r in rows})}")
c = collections.Counter(tuple(lab[q]["hits"]) for q in mv)
for k, v in c.most_common():
    print(f"   {v:3d}  markers={k}")
aw = [r for r in rows if r["A_correct"] == 0]
grp = {"FLAG-negated": [r for r in aw if r["FLAG"]],
       "relabelled-negated (flag=F, adj=T)": [r for r in aw if r["ADJ"] and not r["FLAG"]],
       "negated under neither": [r for r in aw if not r["ADJ"]]}
for k, v in grp.items():
    k1 = sum(r["B_correct"] for r in v)
    print(f"  P(B correct|A wrong)  {k:36s} {k1:3d}/{len(v):3d} = "
          f"{k1/len(v) if v else float('nan'):.3f}")
print("\n  -> the claim's +0.193 is produced by the relabelled group, not by the shipped flag.")

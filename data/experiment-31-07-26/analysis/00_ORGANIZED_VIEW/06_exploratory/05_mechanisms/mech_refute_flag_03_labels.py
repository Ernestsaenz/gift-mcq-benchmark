#!/usr/bin/env python3
"""REFUTE step 3: what is the 'adjudicated' label actually made of, and which
items carry the significance?

The adjudicated label = automatic lexicon over the trailing clause, whose
decisive rule is a bare \\bno\\b, plus 4 manual exclusions that (by the claim's
own admission) contribute zero A-wrong cells.  So the label is 100% automatic
on the analysis sample.  Decompose it.
"""
import json, collections, sys
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_refute_lib import fisher2x2, wilson

ANA = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
BAR = "=" * 96

rows = [r for r in json.load(open(f"{ANA}/paired_clean.json")) if r["analysis_include"]]
L = json.load(open(f"{ANA}/mech_refute_labels.json"))
qids = sorted(L)

OVR = {"b30", "b49", "b158", "b384"}


def group(q):
    v = L[q]
    if q in OVR:
        return "MANUAL-OVERRIDE"
    if v["explicit"]:
        return "EXPLICIT"
    if v["bare_no"]:
        return "BARE-NO-ONLY"
    return "POSITIVE"


print(BAR); print("STEP 6 -- composition of the 'adjudicated' negated set"); print(BAR)
g = collections.Counter(group(q) for q in qids)
print(f"  items: {dict(g)}")
print(f"  adjudicated negated = EXPLICIT ({g['EXPLICIT']}) + BARE-NO-ONLY ({g['BARE-NO-ONLY']})"
      f" = {g['EXPLICIT']+g['BARE-NO-ONLY']}")
print(f"  shipped flag negated = {sum(1 for q in qids if L[q]['flag'])}"
      f"  (all of them adjudicated-negated: "
      f"{all(L[q]['adj'] for q in qids if L[q]['flag'])}) -> the flag has ZERO false")
print("  positives; its only error is under-detection.")
print()
print("  flag coverage by group:")
for grp in ("EXPLICIT", "BARE-NO-ONLY", "MANUAL-OVERRIDE", "POSITIVE"):
    qq = [q for q in qids if group(q) == grp]
    f = sum(1 for q in qq if L[q]["flag"])
    print(f"    {grp:16s} n={len(qq):3d}  flagged {f:3d} ({f/len(qq) if qq else 0:.2f})")

print()
print(BAR); print("STEP 7 -- three-way recovery contrast: EXPLICIT vs BARE-NO-ONLY vs POSITIVE"); print(BAR)
AW = [r for r in rows if not r["A_correct"]]
tab = {}
for grp in ("EXPLICIT", "BARE-NO-ONLY", "POSITIVE", "MANUAL-OVERRIDE"):
    cells = [r for r in AW if group(r["question_id"]) == grp]
    k = sum(r["B_correct"] for r in cells)
    tab[grp] = (k, len(cells))
    lo, hi = wilson(k, len(cells)) if cells else (float("nan"),) * 2
    print(f"  {grp:16s} recovery {k:3d}/{len(cells):3d} = "
          f"{(k/len(cells) if cells else float('nan')):.3f}  [{lo:.3f},{hi:.3f}]")

print()
ke, ne = tab["EXPLICIT"]; kb, nb = tab["BARE-NO-ONLY"]; kp, np_ = tab["POSITIVE"]
o, p, _ = fisher2x2(ke, ne - ke, kp, np_ - kp)
print(f"  EXPLICIT vs POSITIVE     : OR={o:.3f}  Fisher exact p={p:.4g}")
o, p, _ = fisher2x2(kb, nb - kb, kp, np_ - kp)
print(f"  BARE-NO-ONLY vs POSITIVE : OR={o:.3f}  Fisher exact p={p:.4g}")
o, p, _ = fisher2x2(ke, ne - ke, kb, nb - kb)
print(f"  EXPLICIT vs BARE-NO-ONLY : OR={o:.3f}  Fisher exact p={p:.4g}")
o, p, _ = fisher2x2(ke + kb, ne + nb - ke - kb, kp, np_ - kp)
print(f"  (both) vs POSITIVE       : OR={o:.3f}  Fisher exact p={p:.4g}   <- the headline")
print()
print("  => the headline significance is carried by the BARE-NO-ONLY items, i.e. exactly")
print("     the items whose negation status rests on an unreviewed regex for the word 'no'.")

print()
print(BAR); print("STEP 8 -- read the BARE-NO-ONLY trailing clauses that supply A-wrong cells"); print(BAR)
contrib = collections.Counter(r["question_id"] for r in AW)
bn = [q for q in qids if group(q) == "BARE-NO-ONLY" and contrib[q]]
print(f"  {len(bn)} BARE-NO-ONLY items contribute {sum(contrib[q] for q in bn)} A-wrong cells."
      f"  Their clauses:\n")
for q in sorted(bn, key=lambda x: -contrib[x]):
    cells = [r for r in AW if r["question_id"] == q]
    rec = sum(r["B_correct"] for r in cells)
    cl = " ".join(L[q]["clause"].split())
    print(f"  [{q}] Awrong={len(cells)} recovered={rec}")
    print(f"        {cl[:300]}")

print()
print(BAR); print("STEP 9 -- leave-one-rule-out: which lexical rule creates the p<0.05?"); print(BAR)
import re, unicodedata


def strip_acc(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


RULES = [
    (r"\bfals[ao]s?\b", "FALSO"), (r"\bincorrect[ao]s?\b", "INCORRECTO"),
    (r"\berrone[ao]s?\b", "ERRONEO"), (r"\binciert[ao]s?\b", "INCIERTO"),
    (r"\bexcepto\b", "EXCEPTO"), (r"\bsalvo\b", "SALVO"),
    (r"\bexcepcion(?:es)?\b", "EXCEPCION"), (r"\bmenos\s+una?\b", "MENOS-UNA"),
    (r"\bnunca\b", "NUNCA"), (r"\bningun", "NINGUN"),
    (r"\bcontraindicad", "CONTRAINDICADO"), (r"\bdesaconsej", "DESACONSEJADO"),
    (r"\bno\b", "NO"),
]
clause = {q: strip_acc(L[q]["clause"].lower()) for q in qids}


def run(active):
    lab = {q: (q not in OVR) and any(re.search(p, clause[q]) for p, t in RULES if t in active)
           for q in qids}
    a = sum(r["B_correct"] for r in AW if lab[r["question_id"]])
    b = sum(1 for r in AW if lab[r["question_id"]]) - a
    c = sum(r["B_correct"] for r in AW if not lab[r["question_id"]])
    d = sum(1 for r in AW if not lab[r["question_id"]]) - c
    o, p, _ = fisher2x2(a, b, c, d)
    return sum(lab.values()), a, b, c, d, o, p


ALL = {t for _, t in RULES}
n, a, b, c, d, o, p = run(ALL)
print(f"  all rules            items={n:3d}  {a}/{a+b} vs {c}/{c+d}  OR={o:.3f}  p={p:.4g}")
for _, t in RULES:
    n, a, b, c, d, o, p = run(ALL - {t})
    mark = "  <-- drops below/above 0.05" if (p < 0.05) != (0.027 < 0.05) else ""
    print(f"  drop {t:16s} items={n:3d}  {a}/{a+b} vs {c}/{c+d}  OR={o:.3f}  p={p:.4g}{mark}")

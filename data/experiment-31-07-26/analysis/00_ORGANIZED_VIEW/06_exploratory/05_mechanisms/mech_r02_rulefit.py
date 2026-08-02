"""Test the claimed reverse-engineered rule for negated_stem, and search for rival rules."""
import json, itertools, re

D = json.load(open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/mech_r02_stems.json"))
ids = sorted(D, key=lambda q: int(q[1:]) if q[1:].isdigit() else 0)

CLAIM = ['falsa','falso','incorrecta','errónea','excepto',
         'no es cierta','no es correcta','NO es','NO se','NO está','NO esta']

def apply(pats, s, ci=False):
    t = s.lower() if ci else s
    ps = [p.lower() for p in pats] if ci else pats
    return any(p in t for p in ps)

for ci in (False, True):
    tp = fp = fn = tn = 0
    mism = []
    for q in ids:
        pred = apply(CLAIM, D[q]["stem"], ci)
        act = D[q]["flag"]
        if pred and act: tp += 1
        elif pred and not act: fp += 1; mism.append((q, "FP"))
        elif not pred and act: fn += 1; mism.append((q, "FN"))
        else: tn += 1
    print(("case-INSENSITIVE" if ci else "case-SENSITIVE"),
          "tp=%d fp=%d fn=%d tn=%d  mismatches=%d/%d" % (tp, fp, fn, tn, len(mism), len(ids)))
    if mism and len(mism) <= 40:
        for q, k in mism:
            print("   ", k, q, repr(D[q]["stem"][-110:]))
print()

# which patterns are actually load-bearing (case-sensitive)?
base = [apply(CLAIM, D[q]["stem"]) for q in ids]
act = [D[q]["flag"] for q in ids]
print("per-pattern hit counts among flag=True items (case-sensitive), and unique coverage:")
for p in CLAIM:
    hits = [q for q in ids if p in D[q]["stem"]]
    others = [x for x in CLAIM if x != p]
    uniq = [q for q in hits if not apply(others, D[q]["stem"])]
    print("  %-16s hits=%3d  unique=%3d  all_flagged=%s" %
          (p, len(hits), len(uniq), all(D[q]["flag"] for q in hits)))

# is the rule unique?  try dropping each pattern
print("\ndrop-one-pattern reproduction:")
for p in CLAIM:
    sub = [x for x in CLAIM if x != p]
    mm = sum(1 for q in ids if apply(sub, D[q]["stem"]) != D[q]["flag"])
    print("  without %-16s mismatches=%d" % (p, mm))

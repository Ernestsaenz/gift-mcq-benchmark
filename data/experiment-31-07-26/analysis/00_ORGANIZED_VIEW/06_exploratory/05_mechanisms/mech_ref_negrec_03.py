#!/usr/bin/env python3
"""mech_ref_negrec_03 -- where the adjudicated-label effect physically lives, and
whether those cells support 'logic shortcut' or an item/scoring artifact."""
import json, math, collections, sqlite3, sys
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_ref_negrec_01 import fisher2x2, wilson, rows, MODELS, BAR

lab = json.load(open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/mech_labels.json"))
aw = [r for r in rows if not r["A_correct"]]
neg = [r for r in aw if r["neg_adj"]]
pos = [r for r in aw if not r["neg_adj"]]
items = collections.defaultdict(list)
for r in rows:
    items[r["question_id"]].append(r)
adiff = {q: sum(x["A_correct"] for x in v) for q, v in items.items()}

print(BAR); print("PART 7 -- the effect is concentrated in a 12-cell stratum"); print(BAR)
kn, kp = sum(r["B_correct"] for r in neg), sum(r["B_correct"] for r in pos)
o, p = fisher2x2(kn, len(neg) - kn, kp, len(pos) - kp)
print(f"  full contrast          neg {kn}/{len(neg)}={kn/len(neg):.4f} vs {kp}/{len(pos)}={kp/len(pos):.4f}"
      f"  OR={o:.3f} p={p:.4f}")
for drop, dtag in ((0, "items where 0/4 models got A right"),):
    a = [r for r in neg if adiff[r["question_id"]] != drop]
    b = [r for r in pos if adiff[r["question_id"]] != drop]
    ka, kb = sum(r["B_correct"] for r in a), sum(r["B_correct"] for r in b)
    o2, p2 = fisher2x2(ka, len(a) - ka, kb, len(b) - kb)
    print(f"  EXCLUDING {dtag}:")
    print(f"      (that stratum is neg 7/8 vs non-neg 0/4 -- 12 cells, 7 events)")
    print(f"      remaining              neg {ka}/{len(a)}={ka/len(a):.4f} vs {kb}/{len(b)}={kb/len(b):.4f}"
          f"  OR={o2:.3f} Fisher p={p2:.4f}")

print()
print("  the 0/4 items contributing (all four models failed condition A):")
qs04 = sorted({r["question_id"] for r in aw if adiff[r["question_id"]] == 0})
con = sqlite3.connect("file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro", uri=True)
cur = con.cursor()
for q in qs04:
    v = items[q]
    L = lab[q]
    selA = collections.Counter(r["A_selected"] for r in v)
    selB = collections.Counter(r["B_selected"] for r in v)
    nb = sum(r["B_correct"] for r in v)
    print(f"    {q:6s} neg={L['neg']} hits={L['hits']} key={v[0]['correct_letter']}"
          f"  A picks={dict(selA)}  B picks={dict(selB)}  B correct={nb}/{len(v)}")
    print(f"           Q: {L['q'][:150]}")
    cur.execute("SELECT dataset_id, option_a, option_b, option_c, option_d, correct_letter "
                "FROM questions WHERE question_id=? ", (q,))
    for row in cur.fetchall():
        ds = row[0]
        opts = row[1:5]
        print(f"           [{ds}] " + " | ".join(
            f"{L2}) {(t or '')[:60]}" for L2, t in zip("abcd", opts)))

print()
print(BAR); print("PART 8 -- exact reproduction of the claim's subtype comparisons"); print(BAR)
def sub(r):
    L = lab[r["question_id"]]
    if not L["neg"]:
        return "POS"
    return "TRUTH-NEG" if any(t in L["hits"] for t in ("FALSO", "INCORRECTO", "ERRONEO", "INCIERTO")) else "SET-NEG"
S = {}
for tag in ("TRUTH-NEG", "SET-NEG", "POS"):
    s = [r for r in aw if sub(r) == tag]
    S[tag] = (sum(r["B_correct"] for r in s), len(s))
    print(f"  {tag:10s} {S[tag][0]}/{S[tag][1]} = {S[tag][0]/S[tag][1]:.4f}"
          f"  (items={len({r['question_id'] for r in rows if sub(r)==tag})})")
for a_, b_ in (("TRUTH-NEG", "POS"), ("SET-NEG", "POS"), ("TRUTH-NEG", "SET-NEG")):
    ka, na = S[a_]; kb, nb2 = S[b_]
    o2, p2 = fisher2x2(ka, na - ka, kb, nb2 - kb)
    print(f"  {a_} vs {b_}: OR={o2:.3f} Fisher p={p2:.4f}")
print("  -> 3 pairwise subtype tests + 1 overall + >=4 labelings were run; the single")
print("     p=0.045 (SET-NEG vs POS) is nominal and does not survive any multiplicity"
      " adjustment\n     (Bonferroni over just the 3 subtype tests: 0.045*3 = 0.135).")

print()
print(BAR); print("PART 9 -- does the shortcut show any *process* signature?"); print(BAR)
print("  A logic shortcut ('NOTA is trivially the false/non-member one') should be CHEAP.")
print("  Tokens spent in B, A-wrong cells, recovered vs not, by polarity:")
for tag, s in (("negated", neg), ("non-negated", pos)):
    rec = [r for r in s if r["B_correct"]]
    nrec = [r for r in s if not r["B_correct"]]
    def med(v, k):
        z = sorted(x[k] for x in v)
        return z[len(z) // 2] if z else float("nan")
    print(f"    {tag:12s} recovered n={len(rec):3d} median B_tokens={med(rec,'B_tokens'):7.0f}"
          f"  A_tokens={med(rec,'A_tokens'):7.0f}   |  not-recovered n={len(nrec):3d}"
          f" median B_tokens={med(nrec,'B_tokens'):7.0f}")
print()
print("  Whole-sample: median B_tokens by polarity (all cells) -- a real shortcut on")
print("  negated stems should reduce effort in B relative to non-negated:")
for key in ("neg_adj",):
    for sel, tag in ((True, "negated"), (False, "non-negated")):
        s = [r for r in rows if bool(r[key]) == sel]
        zA = sorted(r["A_tokens"] for r in s); zB = sorted(r["B_tokens"] for r in s)
        print(f"    {tag:12s} n={len(s):4d}  median A_tokens={zA[len(zA)//2]:6.0f}"
              f"  median B_tokens={zB[len(zB)//2]:6.0f}"
              f"  median delta={zB[len(zB)//2]-zA[len(zA)//2]:+6.0f}")

print()
print(BAR); print("PART 10 -- the 'no detectable heterogeneity' claim, adjudicated label"); print(BAR)
for m in MODELS:
    a = [r for r in neg if r["model"] == m]
    b = [r for r in pos if r["model"] == m]
    ka, kb = sum(r["B_correct"] for r in a), sum(r["B_correct"] for r in b)
    o2, p2 = fisher2x2(ka, len(a) - ka, kb, len(b) - kb)
    aa, bb, cc, dd = ka + .5, len(a) - ka + .5, kb + .5, len(b) - kb + .5
    lo_ = math.log(aa * dd / (bb * cc)); v = 1 / aa + 1 / bb + 1 / cc + 1 / dd
    print(f"  {m:28s} {ka}/{len(a)}={ka/len(a):.3f} vs {kb}/{len(b)}={kb/len(b):.3f}"
          f"  OR={o2:6.3f} p={p2:.3f}   Haldane logOR CI OR"
          f" [{math.exp(lo_-1.96*math.sqrt(v)):.2f},{math.exp(lo_+1.96*math.sqrt(v)):.2f}]")
print("  Not one model reaches p<0.05 on its own. 'Consistent direction across four'")
print("  = exact sign test p=0.125, and one model (qwen) REVERSES under the shipped flag")
print("  (0.364 vs 0.423), so even the direction claim is label-contingent.")
con.close()

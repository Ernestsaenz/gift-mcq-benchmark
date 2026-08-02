#!/usr/bin/env python3
"""mech_06: the decisive sub-analysis.

On a TRUTH-NEG item ('senale la FALSA / INCORRECTA') a model that answered A
correctly demonstrated it judged the OTHER THREE options to be true statements.
In B those same three options are unchanged and the fourth is
'Ninguna de las respuestas anteriores es correcta.' -- necessarily FALSE if the
other three are true, hence the answer, by pure logic, with no extra medical
knowledge.  So P(B wrong | A correct, TRUTH-NEG) is a pure reasoning-failure
rate that no 'lost recognition shortcut' or 'added difficulty' story can absorb.

Also: NOTA-position effects, has_context/qlen confound checks, robustness of the
recovery interaction to dropping each model, and the detectable-effect floor.
"""
import json, math, collections, random, sys
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_stats import (fisher_exact_2x2, wilson, logistic_fit,
                        cluster_robust_se, two_sided_z_p)
from stats_lib import mcnemar_exact_p, binom_exact_ci, chi2_sf

ANA = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
rows = [r for r in json.load(open(f"{ANA}/paired_clean.json")) if r["analysis_include"]]
lab = json.load(open(f"{ANA}/mech_labels.json"))
for r in rows:
    L = lab[r["question_id"]]
    r["neg_adj"] = L["neg"]
    h = L["hits"]
    r["subtype"] = ("POS" if not L["neg"] else
                    "TRUTH-NEG" if any(t in h for t in ("FALSO", "INCORRECTO", "ERRONEO", "INCIERTO"))
                    else "SET-NEG")
MODELS = sorted({r["model"] for r in rows})
B = "=" * 92

print(B); print("PART A -- logic-sufficient cells: TRUTH-NEG and A_correct==1"); print(B)
print("  In A the model picked the one FALSE statement, so it treated the other three as TRUE.")
print("  In B those three are byte-identical and the fourth is the NOTA string, which must")
print("  then be false -> it is the answer of a 'senale la FALSA' stem by logic alone.\n")
ls = [r for r in rows if r["subtype"] == "TRUTH-NEG" and r["A_correct"] == 1]
k = sum(r["B_correct"] for r in ls)
lo, hi = binom_exact_ci(len(ls) - k, len(ls))
print(f"  cells = {len(ls)}   B correct {k}  B WRONG {len(ls)-k}"
      f"   failure rate = {(len(ls)-k)/len(ls):.4f}  Clopper-Pearson 95% CI [{lo:.4f},{hi:.4f}]")
print("  per model:")
for m in MODELS:
    s = [r for r in ls if r["model"] == m]
    kk = sum(r["B_correct"] for r in s)
    l2, h2 = binom_exact_ci(len(s) - kk, len(s))
    print(f"    {m:28s} {len(s)-kk:3d}/{len(s):3d} = {(len(s)-kk)/len(s):.4f}  [{l2:.4f},{h2:.4f}]")
comp = [r for r in rows if r["subtype"] == "POS" and r["A_correct"] == 1]
kc = sum(r["B_correct"] for r in comp)
o, p = fisher_exact_2x2(len(ls) - k, k, len(comp) - kc, kc)
print(f"\n  comparison, POS & A_correct: failure {len(comp)-kc}/{len(comp)}"
      f" = {(len(comp)-kc)/len(comp):.4f}")
print(f"  Fisher exact, failure-given-A-correct, TRUTH-NEG vs POS: OR={o:.3f} p={p:.4g}")
sn = [r for r in rows if r["subtype"] == "SET-NEG" and r["A_correct"] == 1]
ks = sum(r["B_correct"] for r in sn)
print(f"  comparison, SET-NEG & A_correct: failure {len(sn)-ks}/{len(sn)}"
      f" = {(len(sn)-ks)/len(sn):.4f}")

print("\n" + B); print("PART B -- where the wrong B answers go"); print(B)
for tag in ("TRUTH-NEG", "SET-NEG", "POS"):
    rs = [r for r in rows if r["subtype"] == tag and r["B_correct"] == 0]
    c = collections.Counter(r["B_selected"] for r in rs)
    print(f"  {tag:10s} wrong-B cells {len(rs):4d}   selected letters {dict(sorted(c.items()))}")
print("  (the NOTA slot is never among these by construction; a wrong B answer is an")
print("   endorsement of one of the three ORIGINAL distractors -- on a 'senale la FALSA'")
print("   stem that means calling a true statement false.)")

print("\n" + B); print("PART C -- NOTA slot position (b / c / d) effects in condition B"); print(B)
for tag, sel in (("all", lambda r: True), ("TRUTH-NEG", lambda r: r["subtype"] == "TRUTH-NEG"),
                 ("POS", lambda r: r["subtype"] == "POS")):
    print(f"  {tag}")
    tab = []
    for L in "bcd":
        rs = [r for r in rows if sel(r) and r["correct_letter"] == L]
        if not rs:
            continue
        a = sum(r["A_correct"] for r in rs) / len(rs)
        b = sum(r["B_correct"] for r in rs) / len(rs)
        tab.append((L, len(rs), a, b))
        print(f"    NOTA at {L}: n={len(rs):4d}  A={a:.3f}  B={b:.3f}  delta={a-b:+.3f}")
    # chi-square of B-correct by position
    obs = [[sum(r["B_correct"] for r in rows if sel(r) and r["correct_letter"] == L),
            sum(1 - r["B_correct"] for r in rows if sel(r) and r["correct_letter"] == L)]
           for L in "bcd"]
    n = sum(sum(r) for r in obs)
    rt = [sum(r) for r in obs]; ct = [sum(o[j] for o in obs) for j in range(2)]
    x2 = sum((obs[i][j] - rt[i]*ct[j]/n)**2 / (rt[i]*ct[j]/n) for i in range(3) for j in range(2)
             if rt[i]*ct[j] > 0)
    print(f"    Pearson chi-square (2 df) on B accuracy by NOTA position: X2={x2:.3f}"
          f"  p={chi2_sf(x2,2):.4g}")

print("\n" + B); print("PART D -- is the negation x condition interaction a proxy for context length?"); print(B)
neg = [r for r in rows if r["neg_adj"]]; pos = [r for r in rows if not r["neg_adj"]]
print(f"  has_context rate: negated {sum(r['has_context'] for r in neg)/len(neg):.3f}"
      f"   non-negated {sum(r['has_context'] for r in pos)/len(pos):.3f}")
print(f"  median qlen: negated {sorted(r['qlen'] for r in neg)[len(neg)//2]}"
      f"   non-negated {sorted(r['qlen'] for r in pos)[len(pos)//2]}")
X, y, cl = [], [], []
for r in rows:
    g = 1.0 if r["neg_adj"] else 0.0
    h = 1.0 if r["has_context"] else 0.0
    ql = math.log(max(r["qlen"], 1)) - 6.0
    for cond in (0.0, 1.0):
        X.append([1.0, cond, g, cond * g, h, cond * h, ql, cond * ql])
        y.append(float(r["B_correct"] if cond else r["A_correct"]))
        cl.append(r["question_id"])
beta = logistic_fit(X, y)
se, _ = cluster_robust_se(X, y, beta, cl)
nm = ["intercept", "condB", "negated", "condB x negated", "has_context",
      "condB x has_context", "log qlen", "condB x log qlen"]
print("  Logistic regression with covariates, CR0 cluster-robust SE (cluster = item), Wald z:")
for a_, b_, s_ in zip(nm, beta, se):
    print(f"    {a_:20s} b={b_:+.4f} se={s_:.4f} z={b_/s_:+.3f} p={two_sided_z_p(b_/s_):.4g}")

print("\n" + B); print("PART E -- recovery interaction: leave-one-model-out and heterogeneity"); print(B)


def rec(rs):
    aw = [r for r in rs if r["A_correct"] == 0]
    return sum(r["B_correct"] for r in aw), len(aw)


kn, nn = rec(neg); kp, np_ = rec(pos)
o, p = fisher_exact_2x2(kn, nn - kn, kp, np_ - kp)
print(f"  ALL MODELS   neg {kn}/{nn}={kn/nn:.3f}   non-neg {kp}/{np_}={kp/np_:.3f}"
      f"   OR={o:.3f} Fisher p={p:.4g}")
for drop in MODELS:
    n2 = [r for r in neg if r["model"] != drop]; p2 = [r for r in pos if r["model"] != drop]
    a, b = rec(n2); c, d = rec(p2)
    o2, p2v = fisher_exact_2x2(a, b - a, c, d - c)
    print(f"  drop {drop:28s} neg {a}/{b}={a/b:.3f}  non-neg {c}/{d}={c/d:.3f}"
          f"  OR={o2:.3f} p={p2v:.4g}")
# Woolf test of OR homogeneity across models on the recovery 2x2
lo_, w_ = [], []
for m in MODELS:
    a, b = rec([r for r in neg if r["model"] == m]); c, d = rec([r for r in pos if r["model"] == m])
    a2, b2, c2, d2 = a + .5, b - a + .5, c + .5, d - c + .5
    lo_.append(math.log(a2 * d2 / (b2 * c2)))
    w_.append(1 / (1 / a2 + 1 / b2 + 1 / c2 + 1 / d2))
lbar = sum(w * l for w, l in zip(w_, lo_)) / sum(w_)
Q = sum(w * (l - lbar) ** 2 for w, l in zip(w_, lo_))
print(f"  Woolf test of homogeneity of the recovery log-OR across the 4 models (Haldane"
      f" 0.5 correction): Q={Q:.3f} df=3 p={chi2_sf(Q,3):.4g}; pooled OR={math.exp(lbar):.3f}")

print("\n" + B); print("PART F -- what interaction size could this design have detected?"); print(B)
byc = collections.defaultdict(list)
for r in rows:
    byc[r["cluster"]].append(r)
keys = list(byc); rng = random.Random(99)
bs = []
for _ in range(4000):
    samp = []
    for _ in range(len(keys)):
        samp.extend(byc[keys[rng.randrange(len(keys))]])
    a = [r for r in samp if r["neg_adj"]]; b = [r for r in samp if not r["neg_adj"]]
    if not a or not b:
        continue
    bs.append(sum(r["A_correct"] - r["B_correct"] for r in b) / len(b)
              - sum(r["A_correct"] - r["B_correct"] for r in a) / len(a))
bs.sort()
sd = (sum((v - sum(bs)/len(bs))**2 for v in bs) / (len(bs)-1)) ** .5
print(f"  cluster-bootstrap SE of (delta_nonneg - delta_neg) = {sd:.4f}")
print(f"  minimum detectable difference at 80% power, alpha .05 (2.80*SE) = {2.80*sd:.4f}"
      f" ({100*2.80*sd:.1f} points)")
print(f"  observed difference {sum(r['A_correct']-r['B_correct'] for r in pos)/len(pos) - sum(r['A_correct']-r['B_correct'] for r in neg)/len(neg):+.4f}")
print(f"  headline pooled delta {sum(r['A_correct']-r['B_correct'] for r in rows)/len(rows):+.4f}")

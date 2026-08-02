#!/usr/bin/env python3
"""mech_08: covariate-adjusted recovery model + concrete Spanish exemplars."""
import json, math, sqlite3, collections, sys
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_stats import logistic_fit, cluster_robust_se, two_sided_z_p, fisher_exact_2x2

ANA = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"
rows = [r for r in json.load(open(f"{ANA}/paired_clean.json")) if r["analysis_include"]]
lab = json.load(open(f"{ANA}/mech_labels.json"))
for r in rows:
    L = lab[r["question_id"]]
    r["neg_adj"] = L["neg"]
    r["subtype"] = ("POS" if not L["neg"] else
                    "TRUTH-NEG" if any(t in L["hits"] for t in ("FALSO", "INCORRECTO", "ERRONEO", "INCIERTO"))
                    else "SET-NEG")

BAR = "=" * 92
print(BAR); print("PART A -- recovery model on the A-WRONG cells, adjusted for context and length"); print(BAR)
aw = [r for r in rows if not r["A_correct"]]
print(f"  n = {len(aw)} A-wrong cells   has_context: neg"
      f" {sum(r['has_context'] for r in aw if r['neg_adj'])}/{sum(1 for r in aw if r['neg_adj'])}"
      f"  non-neg {sum(r['has_context'] for r in aw if not r['neg_adj'])}/{sum(1 for r in aw if not r['neg_adj'])}")
X, y, cl = [], [], []
mods = sorted({r["model"] for r in rows})
for r in aw:
    ql = math.log(max(r["qlen"], 1)) - 6.0
    d = [1.0 if r["model"] == m else 0.0 for m in mods[1:]]
    X.append([1.0, 1.0 if r["neg_adj"] else 0.0, 1.0 if r["has_context"] else 0.0, ql] + d)
    y.append(float(r["B_correct"])); cl.append(r["question_id"])
beta = logistic_fit(X, y)
se, _ = cluster_robust_se(X, y, beta, cl)
nm = ["intercept", "negated", "has_context", "log qlen"] + [f"model={m}" for m in mods[1:]]
print("  Logistic: B_correct ~ negated + has_context + log qlen + model FE,"
      " CR0 cluster-robust SE (item), Wald z")
for a_, b_, s_ in zip(nm, beta, se):
    print(f"    {a_:30s} b={b_:+.4f} se={s_:.4f} z={b_/s_:+.3f} p={two_sided_z_p(b_/s_):.4g}"
          f" OR={math.exp(b_):.3f}")

print("\n" + BAR); print("PART B -- subtype recovery against the same POS comparison group"); print(BAR)
for tag in ("TRUTH-NEG", "SET-NEG"):
    a = [r for r in aw if r["subtype"] == tag]; b = [r for r in aw if r["subtype"] == "POS"]
    ka, kb = sum(r["B_correct"] for r in a), sum(r["B_correct"] for r in b)
    o, p = fisher_exact_2x2(ka, len(a)-ka, kb, len(b)-kb)
    print(f"  {tag:10s} {ka}/{len(a)}={ka/len(a):.3f}  vs POS {kb}/{len(b)}={kb/len(b):.3f}"
          f"  OR={o:.3f} Fisher exact p={p:.4g}")

print("\n" + BAR); print("PART C -- exemplars"); print(BAR)
con = sqlite3.connect(DB, uri=True)
ds = {n: i for i, n in con.execute("select id,name from datasets")}
Q = {}
for tag, did in (("A", ds["balanced_a_310726"]), ("B", ds["balanced_b_310726"])):
    for q, qt, oa, ob, oc, od, cl_ in con.execute(
            "select question_id,question_text,option_a,option_b,option_c,option_d,correct_letter"
            " from questions where dataset_id=?", (did,)):
        Q[(q, tag)] = (qt, {"a": oa, "b": ob, "c": oc, "d": od}, cl_)

byq = collections.defaultdict(list)
for r in rows:
    byq[r["question_id"]].append(r)


def dump(qid, why):
    qt, opts, cl_ = Q[(qid, "A")]
    _, optsB, _ = Q[(qid, "B")]
    print(f"\n  --- {qid}  ({why})  correct_letter={cl_}  subtype={byq[qid][0]['subtype']}")
    print(f"  STEM: ...{qt[-260:]}")
    for L in "abcd":
        mark = " <-- correct" if L == cl_ else ""
        print(f"    A.{L}) {opts[L][:150]}{mark}")
    print(f"    B.{cl_}) {optsB[cl_]}   [only this option changed]")
    for r in sorted(byq[qid], key=lambda r: r["model"]):
        print(f"      {r['model']:28s} A={r['A_selected']}({r['A_correct']})"
              f"  B={r['B_selected']}({r['B_correct']})")


# a TRUTH-NEG item where every model got A right and at least one failed B
cand = [q for q, rs in byq.items()
        if rs[0]["subtype"] == "TRUTH-NEG" and all(r["A_correct"] for r in rs)
        and sum(1 for r in rs if not r["B_correct"]) >= 2]
for q in cand[:2]:
    dump(q, "logic-sufficient yet failed in B")

# a negated item where models recovered in B after failing A
cand2 = [q for q, rs in byq.items()
         if rs[0]["neg_adj"] and sum(1 for r in rs if not r["A_correct"] and r["B_correct"]) >= 2]
for q in cand2[:1]:
    dump(q, "A wrong -> B right, the shortcut in action")

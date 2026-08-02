#!/usr/bin/env python3
"""mech_ref_negrec_04 -- final: influence of the two artifact items on EVERY test
the claim reports, plus the whole-sample manifestations of the same mechanism."""
import math, random, collections, sys
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_ref_negrec_01 import (fisher2x2, norm_sf2, t_sf2, logit_fit, cr_se,
                                rows, MODELS, BAR)

KEY = "neg_adj"
DROP = {"b248", "b413"}


def battery(rs, tag):
    aw = [r for r in rs if not r["A_correct"]]
    neg = [r for r in aw if r[KEY]]
    pos = [r for r in aw if not r[KEY]]
    kn, kp = sum(r["B_correct"] for r in neg), sum(r["B_correct"] for r in pos)
    obs = kn / len(neg) - kp / len(pos)
    o, pf = fisher2x2(kn, len(neg) - kn, kp, len(pos) - kp)
    print(f"  {tag}")
    print(f"    counts        neg {kn}/{len(neg)}={kn/len(neg):.4f}  non-neg {kp}/{len(pos)}={kp/len(pos):.4f}"
          f"  diff {obs:+.4f}  OR={o:.3f}")
    print(f"    Fisher exact 2x2 (exact hypergeometric, two-sided p<=p_obs)      p={pf:.4f}")

    byc = collections.defaultdict(list)
    for r in rs:
        byc[r["cluster"]].append(r)
    keys = list(byc)
    rng = random.Random(20260731)
    bs = []
    for _ in range(12000):
        samp = []
        for _ in range(len(keys)):
            samp.extend(byc[keys[rng.randrange(len(keys))]])
        a = [r for r in samp if r[KEY] and not r["A_correct"]]
        b = [r for r in samp if not r[KEY] and not r["A_correct"]]
        if len(a) < 5 or len(b) < 5:
            continue
        bs.append(sum(r["B_correct"] for r in a) / len(a) - sum(r["B_correct"] for r in b) / len(b))
    bs.sort()
    fr = sum(1 for v in bs if v <= 0) / len(bs)
    print(f"    cluster bootstrap (12000 resamples of clusters)  95% CI"
          f" [{bs[int(.025*len(bs))]:+.4f},{bs[int(.975*len(bs))]:+.4f}]  p~{2*min(fr,1-fr):.4f}")

    items = collections.defaultdict(list)
    for r in rs:
        items[r["question_id"]].append(r)
    qs = list(items)
    labs = [items[q][0][KEY] for q in qs]
    rng2 = random.Random(11)
    NP = 20000
    cnt = 0
    for _ in range(NP):
        rng2.shuffle(labs)
        a1 = a0 = b1 = b0 = 0
        for q, l in zip(qs, labs):
            for r in items[q]:
                if r["A_correct"]:
                    continue
                if l:
                    a1 += r["B_correct"]; a0 += 1
                else:
                    b1 += r["B_correct"]; b0 += 1
        if a0 and b0 and abs(a1 / a0 - b1 / b0) >= abs(obs) - 1e-12:
            cnt += 1
    print(f"    item-level permutation of polarity ({NP} perms)                  p={(cnt+1)/(NP+1):.4f}")

    mdix = {m: i for i, m in enumerate(MODELS)}
    X, y, cl = [], [], []
    for r in aw:
        row = [1.0, 1.0 if r[KEY] else 0.0, 1.0 if r["has_context"] else 0.0, math.log(r["qlen"])]
        row += [1.0 if mdix[r["model"]] == j else 0.0 for j in range(1, len(MODELS))]
        X.append(row); y.append(float(r["B_correct"])); cl.append(r["question_id"])
    beta = logit_fit(X, y)
    for kind in ("CR0", "CR1"):
        se, G = cr_se(X, y, beta, cl, kind)
        z = beta[1] / se[1]
        print(f"    logistic + covariates, {kind} cluster-robust (G={G})   b={beta[1]:+.4f}"
              f" se={se[1]:.4f} z={z:+.3f}  p={norm_sf2(z):.4f}  t({G-1}) p={t_sf2(z,G-1):.4f}"
              f"  OR={math.exp(beta[1]):.2f}")
    return


print(BAR)
print("PART 11 -- run the claim's ENTIRE test battery with and without the two items")
print("           b248 and b413 (the two 0/4-difficulty negated items where the inserted")
print("           NOTA string is trivially the false / non-member option)")
print(BAR)
battery(rows, "ALL 325 items (as claimed)")
print()
battery([r for r in rows if r["question_id"] not in DROP], "DROPPING b248 + b413 (323 items, 8 of 1299 cells)")

print()
print(BAR)
print("PART 12 -- whole-sample manifestations of the SAME mechanism (no conditioning)")
print(BAR)
for key, name in (("neg_flag", "shipped flag"), ("neg_adj", "adjudicated")):
    n_ = [r for r in rows if r[key]]
    p_ = [r for r in rows if not r[key]]
    for cond in ("A_correct", "B_correct"):
        kn2 = sum(r[cond] for r in n_); kp2 = sum(r[cond] for r in p_)
        o, p = fisher2x2(kn2, len(n_) - kn2, kp2, len(p_) - kp2)
        print(f"  {name:13s} {cond}: neg {kn2/len(n_):.4f} vs non-neg {kp2/len(p_):.4f}"
              f"  OR={o:.3f} Fisher p={p:.4g}")
print("  -> the shortcut is supposed to raise B accuracy on negated stems. B accuracy is")
print("     0.750 vs 0.735 (adjudicated), p=0.55. Nothing.")
print()
print("  If the inserted NOTA string were trivially recognisable as the false/non-member")
print("  option on negated stems, B accuracy there should approach ceiling. Instead:")
for key, name in (("neg_adj", "adjudicated"),):
    for sel, tag in ((True, "negated"), (False, "non-negated")):
        s = [r for r in rows if bool(r[key]) == sel]
        b = sum(r["B_correct"] for r in s)
        print(f"    {tag:12s} B accuracy {b}/{len(s)} = {b/len(s):.4f}"
              f"   -> {len(s)-b} failures on supposedly logic-sufficient items")

print()
print(BAR)
print("PART 13 -- summary table of every p-value for the primary contrast")
print(BAR)
tbl = [
    ("shipped negated_stem field, Fisher exact", 0.5356, "OR 1.30"),
    ("adjudicated label, Fisher exact (claim's headline)", 0.0270, "OR 2.38"),
    ("adjudicated, cluster bootstrap over clusters", 0.0756, "95% CI [-0.021,+0.388] covers 0"),
    ("adjudicated, item-level permutation", 0.0582, "-"),
    ("adjudicated, logistic CR0 (claim reports this)", 0.0344, "OR 3.12"),
    ("adjudicated, logistic CR1 finite-cluster corrected", 0.0400, "OR 3.12"),
    ("adjudicated, logistic CR1 with t(G-1) reference", 0.0431, "OR 3.12"),
    ("adjudicated, wild cluster bootstrap-t (null imposed)", 0.0480, "OR 3.12"),
    ("adjudicated, Fisher after dropping items b248+b413", None, "see PART 11"),
    ("adjudicated, Fisher excluding 0/4-difficulty stratum", 0.2367, "OR 1.68"),
    ("explicit-polarity-words-only label, Fisher exact", 0.3030, "OR 1.60"),
    ("TRUTH-NEG vs POS subtype, Fisher exact", 0.1199, "OR 2.14"),
    ("SET-NEG vs POS subtype, Fisher exact", 0.0445, "OR 2.77, 1 of 3 subtype tests"),
    ("TRUTH-NEG vs SET-NEG, Fisher exact", 0.7937, "subtypes do not differ"),
    ("per-model, best single model (gemma), Fisher exact", 0.0980, "OR 2.71"),
    ("4/4 direction consistency, exact sign test", 0.1250, "-"),
    ("interaction condB x negated, logistic CR1 (all 1299 cells)", 0.7566, "OR 1.08"),
    ("P(B wrong | A correct) neg vs non-neg, Fisher exact", 0.8294, "OR 1.03"),
    ("B accuracy neg vs non-neg, Fisher exact", None, "see PART 12"),
]
for name, p, note in tbl:
    ps = f"{p:.4f}" if p is not None else "  --  "
    print(f"  {name:58s} p={ps}   {note}")

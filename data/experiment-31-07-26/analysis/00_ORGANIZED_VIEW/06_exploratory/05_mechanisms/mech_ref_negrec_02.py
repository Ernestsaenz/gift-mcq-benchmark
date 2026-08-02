#!/usr/bin/env python3
"""mech_ref_negrec_02 -- stress-test the recovery contrast under the ADJUDICATED
polarity label (the label the claim's numbers 27/61 vs 18/72 actually come from).
"""
import json, math, random, collections, sys
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_ref_negrec_01 import (fisher2x2, wilson, norm_sf2, t_sf2, logit_fit,
                                cr_se, rows, MODELS, BAR)

KEY = "neg_adj"
aw = [r for r in rows if not r["A_correct"]]
neg = [r for r in aw if r[KEY]]
pos = [r for r in aw if not r[KEY]]
kn, kp = sum(r["B_correct"] for r in neg), sum(r["B_correct"] for r in pos)
obs = kn / len(neg) - kp / len(pos)
print()
print(BAR); print("PART 6 -- ADJUDICATED label: reproduce, then break"); print(BAR)
o, p = fisher2x2(kn, len(neg) - kn, kp, len(pos) - kp)
print(f"  reproduced: neg {kn}/{len(neg)}={kn/len(neg):.4f}  non-neg {kp}/{len(pos)}={kp/len(pos):.4f}"
      f"  diff {obs:+.4f}  OR={o:.4f}  Fisher p={p:.4f}")
print(f"  total recovery events in the whole contrast: {kn+kp}. "
      f"Excess attributable to polarity = {len(neg)*obs:.1f} cells out of {len(rows)}.")

# ---- 6a: cluster-aware inference, done four ways
print()
print("  6a. cluster-aware inference (clusters = the 208 near-duplicate item clusters;"
      "\n      A-wrong cells come from %d items / %d clusters)"
      % (len({r['question_id'] for r in aw}), len({r['cluster'] for r in aw})))
byc = collections.defaultdict(list)
for r in rows:
    byc[r["cluster"]].append(r)
keys = list(byc)
rng = random.Random(20260731)
bs = []
for _ in range(20000):
    samp = []
    for _ in range(len(keys)):
        samp.extend(byc[keys[rng.randrange(len(keys))]])
    a = [r for r in samp if r[KEY] and not r["A_correct"]]
    b = [r for r in samp if not r[KEY] and not r["A_correct"]]
    if len(a) < 5 or len(b) < 5:
        continue
    bs.append(sum(r["B_correct"] for r in a) / len(a) - sum(r["B_correct"] for r in b) / len(b))
bs.sort()
frac = sum(1 for v in bs if v <= 0) / len(bs)
print(f"      cluster bootstrap 20000x : 95% CI [{bs[int(.025*len(bs))]:+.4f},"
      f"{bs[int(.975*len(bs))]:+.4f}]  two-sided p ~ {2*min(frac,1-frac):.4f}"
      f"   -> CI COVERS ZERO" if bs[int(.025*len(bs))] <= 0 <= bs[int(.975*len(bs))] else "")

items = collections.defaultdict(list)
for r in rows:
    items[r["question_id"]].append(r)
qs = list(items)
labs = [items[q][0][KEY] for q in qs]
rng2 = random.Random(11)
NP = 50000
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
print(f"      item-level permutation {NP}x : p={(cnt+1)/(NP+1):.4f}")

mdix = {m: i for i, m in enumerate(MODELS)}
X, y, cl = [], [], []
for r in aw:
    row = [1.0, 1.0 if r[KEY] else 0.0, 1.0 if r["has_context"] else 0.0, math.log(r["qlen"])]
    row += [1.0 if mdix[r["model"]] == j else 0.0 for j in range(1, len(MODELS))]
    X.append(row); y.append(float(r["B_correct"])); cl.append(r["question_id"])
beta = logit_fit(X, y)
for kind in ("CR0", "CR0g", "CR1"):
    se, G = cr_se(X, y, beta, cl, kind)
    z = beta[1] / se[1]
    print(f"      logistic {kind:4s} (G={G}): b={beta[1]:+.4f} se={se[1]:.4f} z={z:+.3f}"
          f"  normal p={norm_sf2(z):.4f}  t({G-1}) p={t_sf2(z, G-1):.4f}  OR={math.exp(beta[1]):.3f}")

# wild cluster bootstrap-t on the logistic coefficient
Xr = [[v for j, v in enumerate(x) if j != 1] for x in X]
br = logit_fit(Xr, y)
mu0 = []
for i in range(len(Xr)):
    e = sum(Xr[i][j] * br[j] for j in range(len(br)))
    mu0.append(1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, e)))))
res = [y[i] - mu0[i] for i in range(len(y))]
se_obs, G = cr_se(X, y, beta, cl, "CR1")
t_obs = beta[1] / se_obs[1]
clusters = sorted(set(cl))
rng3 = random.Random(4242)
big = ok = 0
for _ in range(9999):
    w = {c: (1.0 if rng3.random() < 0.5 else -1.0) for c in clusters}
    ystar = [1.0 if (mu0[i] + w[cl[i]] * res[i]) > 0.5 else 0.0 for i in range(len(y))]
    if sum(ystar) in (0, len(ystar)):
        continue
    try:
        bstar = logit_fit(X, ystar)
        sestar, _ = cr_se(X, ystar, bstar, cl, "CR1")
        t = bstar[1] / sestar[1]
    except Exception:
        continue
    ok += 1
    if abs(t) >= abs(t_obs) - 1e-12:
        big += 1
print(f"      wild cluster bootstrap-t (Rademacher, null imposed, {ok} reps):"
      f" t_obs={t_obs:+.3f}  p={(big+1)/(ok+1):.4f}")

# ---- 6b: the interaction the shortcut hypothesis actually predicts
print()
print("  6b. the shortcut predicts a SMALLER A->B drop on negated stems. It is absent.")
for key, name in (("neg_flag", "shipped flag"), ("neg_adj", "adjudicated")):
    n_ = [r for r in rows if r[key]]
    p_ = [r for r in rows if not r[key]]
    An = sum(r["A_correct"] for r in n_) / len(n_); Bn = sum(r["B_correct"] for r in n_) / len(n_)
    Ap = sum(r["A_correct"] for r in p_) / len(p_); Bp = sum(r["B_correct"] for r in p_) / len(p_)
    ln = sum(1 for r in n_ if r["A_correct"] and not r["B_correct"])
    lp = sum(1 for r in p_ if r["A_correct"] and not r["B_correct"])
    an = sum(r["A_correct"] for r in n_); ap = sum(r["A_correct"] for r in p_)
    ol, pl = fisher2x2(ln, an - ln, lp, ap - lp)
    print(f"      {name:13s} drop neg {An-Bn:+.4f} vs non-neg {Ap-Bp:+.4f}"
          f"  -> difference {(Ap-Bp)-(An-Bn):+.4f}")
    print(f"      {'':13s} P(B-|A+) neg {ln}/{an}={ln/an:.4f} vs non-neg {lp}/{ap}={lp/ap:.4f}"
          f"  OR={ol:.3f} Fisher p={pl:.4g}   <- shortcut should protect these too; it does not")

# ---- 6c: rival -- item difficulty, not polarity
print()
print("  6c. RIVAL: the two A-wrong strata are drawn from items of different difficulty.")
print("      Item A-difficulty = how many of the 4 models got condition A right.")
adiff = {}
for q, v in items.items():
    adiff[q] = sum(r["A_correct"] for r in v)
print("      distribution of item A-difficulty among A-WRONG cells:")
for tag, s in (("negated", neg), ("non-negated", pos)):
    c = collections.Counter(adiff[r["question_id"]] for r in s)
    tot = len(s)
    print(f"        {tag:12s} n={tot:3d}  " +
          "  ".join(f"{k}/4:{c.get(k,0)}({c.get(k,0)/tot:.2f})" for k in range(5)))
print("      recovery WITHIN each item-difficulty stratum:")
num = den = 0.0
for k in range(4):
    a = [r for r in neg if adiff[r["question_id"]] == k]
    b = [r for r in pos if adiff[r["question_id"]] == k]
    if not a or not b:
        print(f"        {k}/4 correct in A: neg n={len(a)} non-neg n={len(b)} -- skipped")
        continue
    ka, kb = sum(r["B_correct"] for r in a), sum(r["B_correct"] for r in b)
    o2, p2 = fisher2x2(ka, len(a) - ka, kb, len(b) - kb)
    print(f"        {k}/4 correct in A: neg {ka}/{len(a)}={ka/len(a):.3f}"
          f"  non-neg {kb}/{len(b)}={kb/len(b):.3f}  OR={o2:.3f} p={p2:.3f}")
    a11, a12 = ka, len(a) - ka
    a21, a22 = kb, len(b) - kb
    N = len(a) + len(b)
    num += a11 * a22 / N
    den += a12 * a21 / N
print(f"        Mantel-Haenszel OR stratified on item A-difficulty = {num/den:.4f}"
      f"   (crude OR {o:.4f})")

# ---- 6d: fragility
print()
print("  6d. FRAGILITY -- leave-one-item-out and leave-one-cluster-out on the Fisher p")
base_items = sorted({r["question_id"] for r in aw})
worst = []
for q in base_items:
    a = [r for r in neg if r["question_id"] != q]
    b = [r for r in pos if r["question_id"] != q]
    ka, kb = sum(r["B_correct"] for r in a), sum(r["B_correct"] for r in b)
    o2, p2 = fisher2x2(ka, len(a) - ka, kb, len(b) - kb)
    worst.append((p2, o2, q))
worst.sort()
print(f"      leave-one-ITEM-out Fisher p: min={worst[0][0]:.4f} max={worst[-1][0]:.4f}"
      f"  #(of {len(worst)}) that rise above 0.05: {sum(1 for w in worst if w[0] > 0.05)}")
for pv, ov, q in worst[-5:]:
    print(f"        drop item {q:6s} -> OR={ov:.3f} p={pv:.4f}")
cl_all = sorted({r["cluster"] for r in aw})
wc = []
for c in cl_all:
    a = [r for r in neg if r["cluster"] != c]
    b = [r for r in pos if r["cluster"] != c]
    ka, kb = sum(r["B_correct"] for r in a), sum(r["B_correct"] for r in b)
    o2, p2 = fisher2x2(ka, len(a) - ka, kb, len(b) - kb)
    wc.append((p2, o2, c))
wc.sort()
print(f"      leave-one-CLUSTER-out Fisher p: min={wc[0][0]:.4f} max={wc[-1][0]:.4f}"
      f"  #(of {len(wc)}) above 0.05: {sum(1 for w in wc if w[0] > 0.05)}")
for pv, ov, c in wc[-5:]:
    print(f"        drop cluster {c:4d} -> OR={ov:.3f} p={pv:.4f}")

# how many single-cell flips kill it
print("      how many single A-wrong cells must flip to push Fisher p above 0.05?")
for flip in range(0, 6):
    kn2 = kn - flip
    o2, p2 = fisher2x2(kn2, len(neg) - kn2, kp, len(pos) - kp)
    print(f"        {flip} negated recoveries removed: {kn2}/{len(neg)} vs {kp}/{len(pos)}"
          f"  OR={o2:.3f} p={p2:.4f}" + ("   <-- crosses 0.05" if p2 > 0.05 else ""))

# ---- 6e: label sensitivity / forking paths
print()
print("  6e. FORKING PATHS -- the contrast under every defensible polarity labeling")
lab = json.load(open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/mech_labels.json"))
STRONG = ("FALSO", "INCORRECTO", "ERRONEO", "INCIERTO", "EXCEPTO", "MENOS-UNA")
defs = {
    "shipped negated_stem field": lambda r: bool(r["negated_stem"]),
    "adjudicated (claim uses this)": lambda r: bool(lab[r["question_id"]]["neg"]),
    "raw lexicon, no overrides": lambda r: len(lab[r["question_id"]]["hits"]) > 0,
    "explicit polarity words only": lambda r: any(t in lab[r["question_id"]]["hits"] for t in STRONG),
    "truth-negation only (FALSO/INCORRECTO/ERRONEO)":
        lambda r: any(t in lab[r["question_id"]]["hits"] for t in ("FALSO", "INCORRECTO", "ERRONEO")),
    "set-negation only (NO/EXCEPTO/MENOS-UNA)":
        lambda r: bool(lab[r["question_id"]]["neg"]) and not any(
            t in lab[r["question_id"]]["hits"] for t in ("FALSO", "INCORRECTO", "ERRONEO")),
}
for name, f in defs.items():
    a = [r for r in aw if f(r)]
    b = [r for r in aw if not f(r)]
    if not a or not b:
        continue
    ka, kb = sum(r["B_correct"] for r in a), sum(r["B_correct"] for r in b)
    o2, p2 = fisher2x2(ka, len(a) - ka, kb, len(b) - kb)
    nit = len({r["question_id"] for r in rows if f(r)})
    print(f"      {name:47s} items={nit:3d}  neg {ka}/{len(a)}={ka/len(a):.3f}"
          f"  non {kb}/{len(b)}={kb/len(b):.3f}  OR={o2:.3f}  p={p2:.4f}")

# ---- 6f: where does the adjudicated effect live?
print()
print("  6f. the 65 items the shipped flag misses vs the 84 both labels call negated")
g_both = [r for r in aw if r["neg_flag"]]
g_moved = [r for r in aw if r["neg_adj"] and not r["neg_flag"]]
g_pos = [r for r in aw if not r["neg_adj"]]
for tag, s in (("both labels negated (84 items)", g_both),
               ("relabelled only (65 items)", g_moved),
               ("negated by neither (176 items)", g_pos)):
    k = sum(r["B_correct"] for r in s)
    lo, hi = wilson(k, len(s))
    print(f"      {tag:34s} {k}/{len(s)} = {k/len(s):.4f} [{lo:.3f},{hi:.3f}]")
o2, p2 = fisher2x2(sum(r["B_correct"] for r in g_both), len(g_both) - sum(r["B_correct"] for r in g_both),
                   sum(r["B_correct"] for r in g_pos), len(g_pos) - sum(r["B_correct"] for r in g_pos))
print(f"      both-labels-negated vs never-negated: OR={o2:.3f} Fisher p={p2:.4f}")

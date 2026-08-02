#!/usr/bin/env python3
"""mech_05: does the A->B drop shrink on negated stems (logic shortcut)?

Primary contrast: P(B correct | A wrong) -- 'recovery' -- negated vs not.
Interaction tested four ways (all named in the output).
Uses BOTH the shipped negated_stem flag and the hand-adjudicated label
(mech_labels.json) so the attenuation from flag error is visible.
"""
import json, math, random, collections, sys
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_stats import (fisher_exact_2x2, wilson, logistic_fit,
                        cluster_robust_se, two_sided_z_p)
from stats_lib import mcnemar_exact_p

ANA = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
rows = [r for r in json.load(open(f"{ANA}/paired_clean.json")) if r["analysis_include"]]
lab = json.load(open(f"{ANA}/mech_labels.json"))
for r in rows:
    r["neg_adj"] = lab[r["question_id"]]["neg"]
    r["neg_flag"] = r["negated_stem"]
    h = lab[r["question_id"]]["hits"]
    if not r["neg_adj"]:
        r["subtype"] = "POS"
    elif any(t in h for t in ("FALSO", "INCORRECTO", "ERRONEO", "INCIERTO")):
        r["subtype"] = "TRUTH-NEG"
    else:
        r["subtype"] = "SET-NEG"

MODELS = sorted({r["model"] for r in rows})
BAR = "=" * 92


def cell_counts(rs):
    """(A,B) 2x2 within the same item: n11,n10,n01,n00."""
    n11 = sum(1 for r in rs if r["A_correct"] and r["B_correct"])
    n10 = sum(1 for r in rs if r["A_correct"] and not r["B_correct"])
    n01 = sum(1 for r in rs if not r["A_correct"] and r["B_correct"])
    n00 = sum(1 for r in rs if not r["A_correct"] and not r["B_correct"])
    return n11, n10, n01, n00


def blk(rs):
    n = len(rs)
    a = sum(r["A_correct"] for r in rs)
    b = sum(r["B_correct"] for r in rs)
    n11, n10, n01, n00 = cell_counts(rs)
    aw = n01 + n00
    rec = n01 / aw if aw else float("nan")
    loss = n10 / (n11 + n10) if (n11 + n10) else float("nan")
    return dict(n=n, A=a / n, B=b / n, d=(a - b) / n, n11=n11, n10=n10,
                n01=n01, n00=n00, rec=rec, rec_n=aw, loss=loss,
                loss_n=n11 + n10, mcp=mcnemar_exact_p(n10, n01))


def show(tag, rs):
    s = blk(rs)
    lo, hi = wilson(s["n01"], s["rec_n"]) if s["rec_n"] else (float("nan"),) * 2
    print(f"  {tag:26s} n={s['n']:4d}  A={s['A']:.3f}  B={s['B']:.3f}  delta={s['d']:+.3f}"
          f"   rec=P(B+|A-)={s['rec']:.3f} [{lo:.3f},{hi:.3f}] ({s['n01']}/{s['rec_n']})"
          f"   loss=P(B-|A+)={s['loss']:.3f} ({s['n10']}/{s['loss_n']})"
          f"   McNemar p={s['mcp']:.3g}")
    return s


def interaction_block(rs, key, title):
    print(BAR)
    print(title)
    print(BAR)
    neg = [r for r in rs if r[key]]
    pos = [r for r in rs if not r[key]]
    print(" POOLED")
    sn = show("negated", neg)
    sp = show("non-negated", pos)
    print(f"  -> delta difference (non-neg minus neg) = {sp['d'] - sn['d']:+.4f}")
    print(f"  -> recovery difference (neg minus non-neg) = {sn['rec'] - sp['rec']:+.4f}")

    # (1) recovery contrast, Fisher exact on A-wrong cells
    orr, p = fisher_exact_2x2(sn["n01"], sn["n00"], sp["n01"], sp["n00"])
    print(f"\n  [T1] Fisher exact 2x2 on A-wrong cells (recovers vs not) x (neg vs non-neg):"
          f"  OR={orr:.3f}  p={p:.4g}")

    # (2) interaction in the paired/conditional-logistic sense
    orr2, p2 = fisher_exact_2x2(sn["n01"], sn["n10"], sp["n01"], sp["n10"])
    print(f"  [T2] Fisher exact on DISCORDANT pairs only (gain A-B+ vs loss A+B-) x polarity"
          f"  -- test of homogeneity of the McNemar/conditional-logistic OR:"
          f"\n       neg {sn['n01']}gain/{sn['n10']}loss   nonneg {sp['n01']}gain/{sp['n10']}loss"
          f"   ratio-of-paired-OR={orr2:.3f}  p={p2:.4g}")

    # (3) logistic DiD with cluster-robust SE
    X, y, cl = [], [], []
    for r in rs:
        g = 1.0 if r[key] else 0.0
        X.append([1.0, 0.0, g, 0.0]); y.append(float(r["A_correct"])); cl.append(r["question_id"])
        X.append([1.0, 1.0, g, g]);   y.append(float(r["B_correct"])); cl.append(r["question_id"])
    beta = logistic_fit(X, y)
    se, _ = cluster_robust_se(X, y, beta, cl)
    names = ["intercept", "condB", "negated", "condB x negated"]
    print("\n  [T3] Logistic regression correct ~ condB + negated + condB:negated,"
          " CR0 cluster-robust SE (cluster = item), Wald z:")
    for nm, b_, s_ in zip(names, beta, se):
        print(f"        {nm:16s} b={b_:+.4f}  se={s_:.4f}  z={b_/s_:+.3f}  p={two_sided_z_p(b_/s_):.4g}"
              f"  OR={math.exp(b_):.3f}")

    # (4) cluster bootstrap on the difference-in-deltas (probability scale)
    byc = collections.defaultdict(list)
    for r in rs:
        byc[r["cluster"]].append(r)
    keys = list(byc)
    rng = random.Random(20260731)
    boots = []
    for _ in range(5000):
        samp = []
        for _ in range(len(keys)):
            samp.extend(byc[keys[rng.randrange(len(keys))]])
        nn = [r for r in samp if r[key]]
        pp = [r for r in samp if not r[key]]
        if not nn or not pp:
            continue
        dn = (sum(r["A_correct"] - r["B_correct"] for r in nn)) / len(nn)
        dp = (sum(r["A_correct"] - r["B_correct"] for r in pp)) / len(pp)
        boots.append(dp - dn)
    boots.sort()
    lo = boots[int(0.025 * len(boots))]; hi = boots[int(0.975 * len(boots))]
    frac = sum(1 for v in boots if v <= 0) / len(boots)
    print(f"\n  [T4] Cluster bootstrap (5000 resamples of the {len(keys)} clusters) on"
          f" delta_nonneg - delta_neg:\n       point {sp['d']-sn['d']:+.4f}  95% CI"
          f" [{lo:+.4f},{hi:+.4f}]  bootstrap two-sided p ~ {2*min(frac,1-frac):.4g}")

    # (5) item-level permutation of the polarity label
    items = {}
    for r in rs:
        items.setdefault(r["question_id"], []).append(r)
    labs = [(q, v[0][key]) for q, v in items.items()]
    obs = sp["d"] - sn["d"]
    rng2 = random.Random(7)
    cnt = 0; NPERM = 10000
    vals = [l for _, l in labs]
    qs = [q for q, _ in labs]
    for _ in range(NPERM):
        rng2.shuffle(vals)
        dn_num = dn_den = dp_num = dp_den = 0
        for q, l in zip(qs, vals):
            for r in items[q]:
                dd = r["A_correct"] - r["B_correct"]
                if l: dn_num += dd; dn_den += 1
                else: dp_num += dd; dp_den += 1
        st = dp_num / dp_den - dn_num / dn_den
        if abs(st) >= abs(obs) - 1e-12:
            cnt += 1
    print(f"  [T5] Item-level permutation of the polarity label (10000 perms, whole item"
          f" i.e. all 4 model rows moved together): observed {obs:+.4f}, two-sided p={(cnt+1)/(NPERM+1):.4g}")

    print("\n  PER MODEL")
    for m in MODELS:
        rn = [r for r in neg if r["model"] == m]
        rp = [r for r in pos if r["model"] == m]
        a = blk(rn); b = blk(rp)
        o, pv = fisher_exact_2x2(a["n01"], a["n00"], b["n01"], b["n00"])
        print(f"   {m}")
        show("   negated", rn)
        show("   non-negated", rp)
        print(f"     -> delta diff {b['d']-a['d']:+.4f} | recovery diff {a['rec']-b['rec']:+.4f}"
              f" | Fisher exact on recovery OR={o:.3f} p={pv:.4g}")
    return sn, sp


print(BAR)
print("SETUP")
print(BAR)
print(f"cells {len(rows)}  items {len({r['question_id'] for r in rows})}"
      f"  clusters {len({r['cluster'] for r in rows})}  models {len(MODELS)}")
print("items by adjudicated polarity:",
      collections.Counter(lab[q]["neg"] for q in {r["question_id"] for r in rows}))
print("cells by adjudicated polarity:", collections.Counter(r["neg_adj"] for r in rows))
print("cells by shipped flag:", collections.Counter(r["neg_flag"] for r in rows))
print("cells by subtype:", collections.Counter(r["subtype"] for r in rows))

sn_f, sp_f = interaction_block(rows, "neg_flag",
                               "PART 1 -- using the SHIPPED negated_stem flag (84 items marked)")
sn_a, sp_a = interaction_block(rows, "neg_adj",
                               "PART 2 -- using the ADJUDICATED polarity label (149 items)")

print(BAR)
print("PART 3 -- subtype split (TRUTH-NEG = 'senale la FALSA/INCORRECTA' where the inserted"
      "\n          NOTA string is itself literally a false statement; SET-NEG = 'cual NO es X'"
      "\n          / EXCEPTO membership-exclusion; POS = ordinary positive stem)")
print(BAR)
sub = {}
for st in ("TRUTH-NEG", "SET-NEG", "POS"):
    sub[st] = show(st, [r for r in rows if r["subtype"] == st])
o, p = fisher_exact_2x2(sub["TRUTH-NEG"]["n01"], sub["TRUTH-NEG"]["n00"],
                        sub["POS"]["n01"], sub["POS"]["n00"])
print(f"  TRUTH-NEG vs POS recovery, Fisher exact: OR={o:.3f} p={p:.4g}")
o, p = fisher_exact_2x2(sub["SET-NEG"]["n01"], sub["SET-NEG"]["n00"],
                        sub["POS"]["n01"], sub["POS"]["n00"])
print(f"  SET-NEG   vs POS recovery, Fisher exact: OR={o:.3f} p={p:.4g}")
o, p = fisher_exact_2x2(sub["TRUTH-NEG"]["n01"], sub["TRUTH-NEG"]["n00"],
                        sub["SET-NEG"]["n01"], sub["SET-NEG"]["n00"])
print(f"  TRUTH-NEG vs SET-NEG recovery, Fisher exact: OR={o:.3f} p={p:.4g}")

print(BAR)
print("PART 4 -- what happens to the headline delta if negated items are dropped")
print(BAR)


def pooled(rs):
    n = len(rs)
    return (sum(r["A_correct"] for r in rs) / n, sum(r["B_correct"] for r in rs) / n,
            sum(r["A_correct"] - r["B_correct"] for r in rs) / n, n)


for name, rs in (("ALL items (headline)", rows),
                 ("drop shipped-flag negated", [r for r in rows if not r["neg_flag"]]),
                 ("drop adjudicated negated", [r for r in rows if not r["neg_adj"]]),
                 ("drop TRUTH-NEG only", [r for r in rows if r["subtype"] != "TRUTH-NEG"])):
    A, B, d, n = pooled(rs)
    print(f"  {name:28s} n={n:4d}  A={A:.4f}  B={B:.4f}  delta={d:+.4f}")
A0, B0, d0, n0 = pooled(rows)
A1, B1, d1, n1 = pooled([r for r in rows if not r["neg_adj"]])
print(f"\n  pooled delta ALL          = {d0:+.4f}")
print(f"  pooled delta NON-NEGATED  = {d1:+.4f}")
print(f"  change                    = {d1-d0:+.4f}  ({100*(d1-d0)/d0:+.1f}% relative)")
print("  per model, delta all -> delta non-negated:")
for m in MODELS:
    a = pooled([r for r in rows if r["model"] == m])
    b = pooled([r for r in rows if r["model"] == m and not r["neg_adj"]])
    print(f"    {m:28s} {a[2]:+.4f} -> {b[2]:+.4f}  ({b[2]-a[2]:+.4f})")

# cluster bootstrap CI for the change in the headline delta
byc = collections.defaultdict(list)
for r in rows:
    byc[r["cluster"]].append(r)
keys = list(byc)
rng = random.Random(1234)
bs = []
for _ in range(5000):
    samp = []
    for _ in range(len(keys)):
        samp.extend(byc[keys[rng.randrange(len(keys))]])
    nn = [r for r in samp if not r["neg_adj"]]
    if not nn:
        continue
    bs.append(pooled(nn)[2] - pooled(samp)[2])
bs.sort()
print(f"  cluster bootstrap 95% CI for the change: [{bs[int(.025*len(bs))]:+.4f},"
      f" {bs[int(.975*len(bs))]:+.4f}]")

print(BAR)
print("PART 5 -- rival explanations")
print(BAR)
neg = [r for r in rows if r["neg_adj"]]
pos = [r for r in rows if not r["neg_adj"]]
print(f"  baseline (condition A) accuracy: negated {sum(r['A_correct'] for r in neg)/len(neg):.4f}"
      f"  non-negated {sum(r['A_correct'] for r in pos)/len(pos):.4f}")
oA, pA = fisher_exact_2x2(sum(r["A_correct"] for r in neg), len(neg) - sum(r["A_correct"] for r in neg),
                          sum(r["A_correct"] for r in pos), len(pos) - sum(r["A_correct"] for r in pos))
print(f"    Fisher exact on A accuracy neg vs non-neg: OR={oA:.3f} p={pA:.4g}"
      "   (tests 'negated items are simply easier')")
oB, pB = fisher_exact_2x2(sum(r["B_correct"] for r in neg), len(neg) - sum(r["B_correct"] for r in neg),
                          sum(r["B_correct"] for r in pos), len(pos) - sum(r["B_correct"] for r in pos))
print(f"    Fisher exact on B accuracy neg vs non-neg: OR={oB:.3f} p={pB:.4g}")

print("\n  B-condition answer placement: how often is the NOTA slot chosen at all?")
for tag, rs in (("negated", neg), ("non-negated", pos)):
    picked = sum(1 for r in rs if r["B_selected"] == r["correct_letter"])
    print(f"    {tag:12s} picked NOTA slot {picked}/{len(rs)} = {picked/len(rs):.4f}")
print("  (B_correct == picked NOTA slot by construction, so this is the 'willingness to"
      "\n   select none-of-the-above' rate; a blanket NOTA aversion cannot differ by stem polarity"
      "\n   unless polarity supplies information.)")

print("\n  Among A-CORRECT cells (model knew the medicine in A), recovery in B:")
for tag, rs in (("negated", neg), ("non-negated", pos)):
    s = blk(rs)
    print(f"    {tag:12s} P(B correct | A correct) = {s['n11']}/{s['n11']+s['n10']}"
          f" = {s['n11']/(s['n11']+s['n10']):.4f}")
s1 = blk(neg); s2 = blk(pos)
o, p = fisher_exact_2x2(s1["n11"], s1["n10"], s2["n11"], s2["n10"])
print(f"    Fisher exact: OR={o:.3f} p={p:.4g}")

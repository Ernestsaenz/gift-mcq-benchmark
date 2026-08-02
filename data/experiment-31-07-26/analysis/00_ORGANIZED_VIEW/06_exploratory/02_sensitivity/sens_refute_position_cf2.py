#!/usr/bin/env python
"""
sens_refute_position_cf2.py -- stress the ASSUMPTIONS behind the counterfactual,
not just its arithmetic.

The claim's counterfactual imputes each position-(a) cell with its own model's
mean d over that model's b/c/d cells.  That is valid only if

  (A1) the b/c/d cells are themselves defect-free donors, and
  (A2) the (a)-vs-(bcd) gap is caused by the missing-antecedent defect rather
       than by item composition or a pre-existing position effect.

If (A1) fails -- e.g. slot (b) also has a degenerate antecedent set (only one
preceding option) -- the donor is contaminated downward and the attributable
share is UNDERSTATED.  If (A2) fails the share is OVERSTATED.

Methods:
  * cluster bootstrap, 20,000 replicates, resampling the 281 clusters; every
    donor mean and every substitution recomputed inside each replicate.
  * direct standardisation on has_context x qlen-tercile (terciles from the 423
    items); strata lacking either group dropped, weights renormalised.
  * randomisation tests relabel at the ITEM level (all model cells move together).
"""
import json, random, math, collections

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
B = 20000
SEEDS = [20260731, 424242, 7]

rows = json.load(open(PATH))
MODELS = sorted(set(r["model"] for r in rows))
LETTERS = ["a", "b", "c", "d"]
for r in rows:
    r["d"] = r["B_correct"] - r["A_correct"]
    r["is_a"] = (r["correct_letter"] == "a")


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def quantile(s, q):
    if not s:
        return float("nan")
    p = q * (len(s) - 1)
    lo, hi = int(math.floor(p)), int(math.ceil(p))
    return s[lo] if lo == hi else s[lo] + (s[hi] - s[lo]) * (p - lo)


def ci(v):
    s = sorted(x for x in v if x == x)
    return quantile(s, .025), quantile(s, .975)


def hd(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


items = {}
for r in rows:
    items.setdefault(r["question_id"], r)
qs = sorted(r["qlen"] for r in items.values())
T1, T2 = quantile(qs, 1 / 3), quantile(qs, 2 / 3)
for r in rows:
    r["stratum"] = (r["has_context"], 0 if r["qlen"] <= T1 else (1 if r["qlen"] <= T2 else 2))
ITEM_W = collections.Counter(v["stratum"] for v in
                             [dict(x, stratum=(x["has_context"],
                                               0 if x["qlen"] <= T1 else (1 if x["qlen"] <= T2 else 2)))
                              for x in items.values()])

by_cluster = collections.defaultdict(list)
for r in rows:
    by_cluster[r["cluster"]].append(r)
CLUSTERS = list(by_cluster.values())
K = len(CLUSTERS)


# --------------------------------------------------------------- estimators
def cf_donor(rs, donors):
    """Counterfactual pooled delta: (a) cells get their model's mean d over `donors`."""
    n = len(rs)
    don = {}
    for m in MODELS:
        v = [r["d"] for r in rs if r["model"] == m and r["correct_letter"] in donors]
        if not v:
            return float("nan")
        don[m] = mean(v)
    tot = sum(don[r["model"]] if r["is_a"] else r["d"] for r in rs)
    return 100 * tot / n


def cf_strat(rs):
    """Counterfactual with a covariate-matched donor: model x stratum mean over b/c/d;
    falls back to the model-wide b/c/d mean when a model x stratum donor cell is empty."""
    n = len(rs)
    cellmean, modmean = {}, {}
    for m in MODELS:
        v = [r["d"] for r in rs if r["model"] == m and not r["is_a"]]
        if not v:
            return float("nan")
        modmean[m] = mean(v)
    acc = collections.defaultdict(lambda: [0.0, 0])
    for r in rs:
        if not r["is_a"]:
            acc[(r["model"], r["stratum"])][0] += r["d"]
            acc[(r["model"], r["stratum"])][1] += 1
    for k, (s, c) in acc.items():
        cellmean[k] = s / c
    tot = 0.0
    for r in rs:
        if r["is_a"]:
            tot += cellmean.get((r["model"], r["stratum"]), modmean[r["model"]])
        else:
            tot += r["d"]
    return 100 * tot / n


def stats_of(rs):
    o = {}
    n = len(rs)
    o["raw"] = 100 * mean(r["d"] for r in rs)
    for L in LETTERS:
        v = [r["d"] for r in rs if r["correct_letter"] == L]
        o["d_" + L] = 100 * mean(v) if v else float("nan")
    nb = [r["d"] for r in rs if not r["is_a"]]
    o["d_bcd"] = 100 * mean(nb) if nb else float("nan")

    # primary + alternative donor sets
    for name, don in [("cf_bcd", ("b", "c", "d")), ("cf_b", ("b",)), ("cf_c", ("c",)),
                      ("cf_d", ("d",)), ("cf_cd", ("c", "d")), ("cf_bd", ("b", "d"))]:
        o[name] = cf_donor(rs, don)
        o[name + "_att"] = o["raw"] - o[name]
        o[name + "_sh"] = o[name + "_att"] / o["raw"] if o["raw"] else float("nan")

    # covariate-matched donor
    o["cf_strat"] = cf_strat(rs)
    o["cf_strat_att"] = o["raw"] - o["cf_strat"]
    o["cf_strat_sh"] = o["cf_strat_att"] / o["raw"] if o["raw"] else float("nan")

    # pre-existing A-arm position effect (before the swap): is (a) already harder?
    aa = [r["A_correct"] for r in rs if r["is_a"]]
    ab = [r["A_correct"] for r in rs if not r["is_a"]]
    o["Aarm_gap"] = (100 * mean(aa) - 100 * mean(ab)) if aa and ab else float("nan")

    # ceiling-corrected: flip rate among A-correct cells
    fa = [1 - r["B_correct"] for r in rs if r["is_a"] and r["A_correct"] == 1]
    fb = [1 - r["B_correct"] for r in rs if not r["is_a"] and r["A_correct"] == 1]
    o["flip_gap"] = (100 * mean(fa) - 100 * mean(fb)) if fa and fb else float("nan")

    # restrict to non-item-defect cells: isolate the POSITION exclusion alone
    sub = [r for r in rs if not r["excl_item_defect"]]
    if sub:
        o["raw_nd"] = 100 * mean(r["d"] for r in sub)
        o["cf_nd"] = cf_donor(sub, ("b", "c", "d"))
        o["cf_nd_att"] = o["raw_nd"] - o["cf_nd"]
        o["cf_nd_sh"] = o["cf_nd_att"] / o["raw_nd"] if o["raw_nd"] else float("nan")
    else:
        o["raw_nd"] = o["cf_nd"] = o["cf_nd_att"] = o["cf_nd_sh"] = float("nan")

    # ITEM-level weighting instead of cell-level
    per_item = collections.defaultdict(list)
    for r in rs:
        per_item[(r["question_id"], r["is_a"])].append(r["d"])
    ia = [mean(v) for (q, g), v in per_item.items() if g]
    ib = [mean(v) for (q, g), v in per_item.items() if not g]
    if ia and ib:
        wa = len(ia) / (len(ia) + len(ib))
        o["raw_item"] = 100 * (wa * mean(ia) + (1 - wa) * mean(ib))
        o["cf_item"] = 100 * mean(ib)
        o["cf_item_att"] = o["raw_item"] - o["cf_item"]
        o["cf_item_sh"] = o["cf_item_att"] / o["raw_item"] if o["raw_item"] else float("nan")
    else:
        o["raw_item"] = o["cf_item"] = o["cf_item_att"] = o["cf_item_sh"] = float("nan")
    return o


point = stats_of(rows)

hd("1. DELTA BY CORRECT LETTER -- is slot (b) a clean donor?")
print("If 'Ninguna de las respuestas ANTERIORES' degrades with FEWER antecedents,")
print("delta should be monotone in slot position: a (0 antecedents) worst, then b (1), c (2), d (3).")
print(f"{'letter':<8}{'cells':>7}{'items':>7}{'delta pp':>11}{'A-arm acc%':>13}{'B-arm acc%':>13}")
for L in LETTERS:
    sub = [r for r in rows if r["correct_letter"] == L]
    print(f"{L:<8}{len(sub):>7}{len(set(r['question_id'] for r in sub)):>7}"
          f"{point['d_'+L]:>11.2f}{100*mean(r['A_correct'] for r in sub):>13.2f}"
          f"{100*mean(r['B_correct'] for r in sub):>13.2f}")
print(f"{'b,c,d':<8}{sum(1 for r in rows if not r['is_a']):>7}{'':>7}{point['d_bcd']:>11.2f}")

hd("2. PRE-EXISTING POSITION EFFECT IN THE A ARM (no NOTA string present)")
print(f"A-arm accuracy gap (a) - (b,c,d): {point['Aarm_gap']:+.2f} pp")
print("  A nonzero gap here means part of the (a)-vs-(bcd) delta gap is item")
print("  composition / headroom, NOT the inserted-string defect.")
print(f"ceiling-corrected flip-rate gap (a)-(bcd), among A-correct cells: {point['flip_gap']:+.2f} pp")

# -------------------------------------------------------------- bootstrap
allboot = {}
for seed in SEEDS:
    rng = random.Random(seed)
    boot = collections.defaultdict(list)
    for _ in range(B):
        samp = []
        for _ in range(K):
            samp.extend(CLUSTERS[rng.randrange(K)])
        s = stats_of(samp)
        for k, v in s.items():
            boot[k].append(v)
    allboot[seed] = boot

hd(f"3. SEED STABILITY OF THE HEADLINE CIs ({B} replicates each)")
print(f"{'seed':<12}{'cf delta':>26}{'attributable':>26}{'share':>24}")
for seed in SEEDS:
    b = allboot[seed]
    l1, h1 = ci(b["cf_bcd"]); l2, h2 = ci(b["cf_bcd_att"]); l3, h3 = ci(b["cf_bcd_sh"])
    print(f"{seed:<12}[{l1:+.2f}, {h1:+.2f}]{'':>7}[{l2:+.2f}, {h2:+.2f}]{'':>7}"
          f"[{l3:.3f}, {h3:.3f}]")

boot = allboot[SEEDS[0]]


def rep(k, lab, f="{:+.3f}"):
    lo, hi = ci(boot[k])
    print(f"{lab:<48}{f.format(point[k]):>9}   95% CI [{f.format(lo)}, {f.format(hi)}]")


hd("4. HOW MUCH DOES THE ANSWER DEPEND ON THE DONOR CHOICE?")
print(f"{'donor set for the 364 (a) cells':<34}{'cf delta':>10}{'attrib':>10}{'share':>9}"
      f"   95% CI on share")
for k, lab in [("cf_bcd", "b,c,d  (claim's primary)"), ("cf_b", "b only  (1 antecedent)"),
               ("cf_c", "c only  (2 antecedents)"), ("cf_d", "d only  (3 antecedents)"),
               ("cf_cd", "c,d only (>=2 antecedents)"), ("cf_bd", "b,d only"),
               ("cf_strat", "b,c,d matched on ctx x qlen")]:
    lo, hi = ci(boot[k + "_sh"])
    print(f"{lab:<34}{point[k]:>+10.3f}{point[k+'_att']:>+10.3f}{point[k+'_sh']:>9.4f}"
          f"   [{lo:.3f}, {hi:.3f}]")

hd("5. OTHER SPECIFICATION CHOICES")
rep("raw", "raw pooled delta (cell-weighted, n=1691)")
rep("cf_bcd", "counterfactual (claim)")
rep("cf_bcd_att", "attributable (claim)")
rep("cf_bcd_sh", "share (claim)", "{:.4f}")
print()
rep("raw_nd", "raw delta, 11 item-defect items removed (n=1647)")
rep("cf_nd", "counterfactual, item-defect items removed")
rep("cf_nd_att", "attributable, item-defect items removed")
rep("cf_nd_sh", "share, item-defect items removed", "{:.4f}")
print()
rep("raw_item", "raw delta, ITEM-weighted (423 items)")
rep("cf_item", "counterfactual, ITEM-weighted")
rep("cf_item_att", "attributable, ITEM-weighted")
rep("cf_item_sh", "share, ITEM-weighted", "{:.4f}")

hd("6. RANDOMISATION TEST FOR SLOT MONOTONICITY (is (b) also degraded?)")
by_item = collections.defaultdict(list)
for r in rows:
    by_item[r["question_id"]].append(r)
item_ids = list(by_item)
item_letter = {q: by_item[q][0]["correct_letter"] for q in item_ids}
pool = [item_letter[q] for q in item_ids]


def slope_stat(lab):
    """Spearman-free linear slope of mean d on slot index 0..3, n-weighted."""
    s = collections.defaultdict(float); n = collections.defaultdict(int)
    for q in item_ids:
        L = lab[q]
        for r in by_item[q]:
            s[L] += r["d"]; n[L] += 1
    xs, ys, ws = [], [], []
    for i, L in enumerate(LETTERS):
        if n[L]:
            xs.append(i); ys.append(100 * s[L] / n[L]); ws.append(n[L])
    mx = sum(w * x for w, x in zip(ws, xs)) / sum(ws)
    my = sum(w * y for w, y in zip(ws, ys)) / sum(ws)
    num = sum(w * (x - mx) * (y - my) for w, x, y in zip(ws, xs, ys))
    den = sum(w * (x - mx) ** 2 for w, x in zip(ws, xs))
    return num / den if den else float("nan")


obs = slope_stat(item_letter)
rng = random.Random(31337)
NP = 20000
cnt = 0
for _ in range(NP):
    p = pool[:]; rng.shuffle(p)
    if slope_stat(dict(zip(item_ids, p))) >= obs:
        cnt += 1
print(f"n-weighted slope of delta on slot index (a=0..d=3): {obs:+.3f} pp per slot")
print(f"one-sided randomisation p (slope >= observed, i.e. later slots better) = "
      f"{(cnt+1)/(NP+1):.5g}   [{NP} item-level letter reassignments]")
print("delta by slot again for reference: " +
      ", ".join(f"{L}={point['d_'+L]:+.2f}" for L in LETTERS))

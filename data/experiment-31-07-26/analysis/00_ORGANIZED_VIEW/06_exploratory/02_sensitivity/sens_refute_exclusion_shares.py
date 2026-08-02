#!/usr/bin/env python3
"""
sens_refute_exclusion_shares.py

Independent recomputation of the "exclusion-grid" robustness claim:

  "The position-(a) rule does essentially 100% of the headline movement; the
   defect exclusion moves the pooled headline by a statistically
   indistinguishable amount."

Everything below is re-implemented from paired_clean.json.  stdlib only.

METHODS (all p-values / CIs stated explicitly where printed):

 (M1) delta = mean(B_correct) - mean(A_correct) over the cells retained by a
      filter.  Positive contrast between two filters = the first shows LESS
      degradation.

 (M2) PAIRED cluster bootstrap.  One replicate = draw C=281 clusters with
      replacement from the 281 clusters of the UNFILTERED file; recompute the
      delta under all four nested filters on that single resample; contrasts
      are formed replicate-wise.  95% percentile CI.  Two-sided p =
      2*min(P(diff<=0), P(diff>=0)) over replicates (percentile-bootstrap p,
      the inversion of the percentile CI).  Ties at exactly 0 are counted in
      BOTH tails and are reported separately so the reader can see how much of
      the p-value is degeneracy rather than evidence.

 (M3) Share of the total shift attributable to a rule = (Sx - S1)/(S4 - S1),
      bootstrapped replicate-wise on the SAME resamples (a ratio whose
      denominator is itself noisy -> Fieller-type instability is reported).

 (M4) Direct contrast of the EXCLUDED items against the RETAINED items
      (delta_excluded - delta_retained), same paired cluster bootstrap.  This
      is the powered version of the question "do these items behave
      differently"; the induced headline shift is that contrast multiplied by
      the excluded fraction, so it can be large while the shift is small.

 (M5) Per-item leverage = induced shift / number of items the rule removes.
"""

import json, os, math, random
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = json.load(open(os.path.join(HERE, "paired_clean.json")))
META = json.load(open(os.path.join(HERE, "dataset_meta.json")))

MODELS = sorted(set(r["model"] for r in ROWS))
R = 20000
SEED = 987654321          # deliberately NOT the 20260731 seed of the original
KEYS = ["*"] + MODELS

FILTERS = {
    "S1_none":        lambda r: True,
    "S2_drop_defect": lambda r: not r["excl_item_defect"],
    "S3_drop_posA":   lambda r: not r["excl_nota_position_a"],
    "S4_drop_both":   lambda r: r["analysis_include"],
}
SIDS = list(FILTERS)

# extra "sets" used only for the excluded-vs-retained contrast (M4)
SUBSETS = {
    "X_defect_only":  lambda r: r["excl_item_defect"],
    "X_posA_only":    lambda r: r["excl_nota_position_a"],
    # defect items that survive the posA rule -> the marginal S4-S3 population
    "X_defect_notA":  lambda r: r["excl_item_defect"] and not r["excl_nota_position_a"],
}
ALL = dict(FILTERS); ALL.update(SUBSETS)
AIDS = list(ALL)

# ---------------------------------------------------------------- bookkeeping
print("=" * 100)
print("(0) WHAT THE FILE ACTUALLY CONTAINS  vs  WHAT dataset_meta.json DOCUMENTS")
print("=" * 100)
items = defaultdict(list)
for r in ROWS:
    items[r["question_id"]].append(r)
meta_admin = set(META["exclusions"]["administrative_legal_out_of_domain"])
meta_key = set(META["exclusions"]["adjudicated_key_defect"])
meta_defect = meta_admin | meta_key
file_defect = set(q for q, rs in items.items() if rs[0]["excl_item_defect"])
file_posA = set(q for q, rs in items.items() if rs[0]["excl_nota_position_a"])
print(f"  meta documents defect items      : {len(meta_defect)}  ({len(meta_admin)} admin + {len(meta_key)} key)")
print(f"  file flags excl_item_defect      : {len(file_defect)}")
print(f"  documented but ABSENT from file  : {sorted(meta_defect - set(items))}")
print(f"  documented, present, NOT flagged : {sorted((meta_defect & set(items)) - file_defect)}")
print(f"  posA items {len(file_posA)}   overlap defect&posA {len(file_defect & file_posA)} -> {sorted(file_defect & file_posA)}")
for sid, f in FILTERS.items():
    cells = [r for r in ROWS if f(r)]
    print(f"  {sid:<16} cells={len(cells):5d}  items={len({r['question_id'] for r in cells}):4d}"
          f"  clusters={len({r['cluster'] for r in cells}):4d}")
for sid, f in SUBSETS.items():
    cells = [r for r in ROWS if f(r)]
    print(f"  {sid:<16} cells={len(cells):5d}  items={len({r['question_id'] for r in cells}):4d}"
          f"  clusters={len({r['cluster'] for r in cells}):4d}")

# ------------------------------------------------------------------ aggregate
tab = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0, 0, 0])))
for r in ROWS:
    for sid, f in ALL.items():
        if not f(r):
            continue
        for k in (r["model"], "*"):
            t = tab[r["cluster"]][sid][k]
            t[0] += 1; t[1] += r["A_correct"]; t[2] += r["B_correct"]

clusters = sorted(tab)
C = len(clusters)
flat = [[(sid, k, v[0], v[1], v[2]) for sid in AIDS for k, v in tab[c][sid].items()] for c in clusters]


def deltas(acc):
    return {s: {k: ((acc[s][k][2] - acc[s][k][1]) / acc[s][k][0] if acc[s][k][0] else None)
                for k in KEYS} for s in AIDS}


def blank():
    return {s: {k: [0, 0, 0] for k in KEYS} for s in AIDS}


A0 = blank()
for cf in flat:
    for (sid, k, n, sa, sb) in cf:
        a = A0[sid][k]; a[0] += n; a[1] += sa; a[2] += sb
OBS = deltas(A0)

rng = random.Random(SEED)
reps = []
for _ in range(R):
    acc = blank()
    for _ in range(C):
        for (sid, k, n, sa, sb) in flat[rng.randrange(C)]:
            a = acc[sid][k]; a[0] += n; a[1] += sa; a[2] += sb
    reps.append(deltas(acc))


def pct(v, q):
    v = sorted(v); i = q * (len(v) - 1)
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return v[lo] if lo == hi else v[lo] + (v[hi] - v[lo]) * (i - lo)


def ci_p(vals):
    lo, hi = pct(vals, 0.025), pct(vals, 0.975)
    nle = sum(1 for x in vals if x <= 0); nge = sum(1 for x in vals if x >= 0)
    ties = sum(1 for x in vals if x == 0)
    p = min(1.0, 2 * min(nle, nge) / len(vals))
    return lo, hi, p, ties


print()
print("=" * 100)
print("(1) LEVELS -- pooled delta under each filter (M1/M2, 20000 paired cluster-bootstrap reps, seed 987654321)")
print("=" * 100)
for s in SIDS:
    v = [rep[s]["*"] for rep in reps]
    print(f"  {s:<16} delta={OBS[s]['*']:+.4f}  95% CI [{pct(v,.025):+.4f},{pct(v,.975):+.4f}]")
for s in SUBSETS:
    v = [rep[s]["*"] for rep in reps if rep[s]["*"] is not None]
    print(f"  {s:<16} delta={OBS[s]['*']:+.4f}  95% CI [{pct(v,.025):+.4f},{pct(v,.975):+.4f}]  "
          f"(n_cells={A0[s]['*'][0]})")

print()
print("=" * 100)
print("(2) PAIRED CONTRASTS -- reproduction of the claim's four numbers (positive = LESS degradation)")
print("=" * 100)
PAIRS = [("S4_drop_both", "S1_none"), ("S3_drop_posA", "S1_none"),
         ("S2_drop_defect", "S1_none"), ("S4_drop_both", "S3_drop_posA"),
         ("S4_drop_both", "S2_drop_defect")]
CLAIMED = {("S4_drop_both", "S1_none"): (+0.0178, +0.0029, +0.0333, 0.0194),
           ("S3_drop_posA", "S1_none"): (+0.0158, +0.0012, +0.0307, 0.0343),
           ("S2_drop_defect", "S1_none"): (+0.0027, -0.0015, +0.0073, 0.2085),
           ("S4_drop_both", "S3_drop_posA"): (+0.0020, -0.0010, +0.0058, 0.2269)}
for a, b in PAIRS:
    vals = [rep[a]["*"] - rep[b]["*"] for rep in reps]
    obs = OBS[a]["*"] - OBS[b]["*"]
    lo, hi, p, ties = ci_p(vals)
    c = CLAIMED.get((a, b))
    tag = ""
    if c:
        tag = f"   | claimed {c[0]:+.4f} [{c[1]:+.4f},{c[2]:+.4f}] p={c[3]:.4f}"
    print(f"  {a:<15} - {b:<15} {obs:+.4f}  [{lo:+.4f},{hi:+.4f}]  p={p:.4f}  ties@0={ties}{tag}")

print()
print("  additivity check (exact, non-bootstrap):")
d41 = OBS["S4_drop_both"]["*"] - OBS["S1_none"]["*"]
d31 = OBS["S3_drop_posA"]["*"] - OBS["S1_none"]["*"]
d43 = OBS["S4_drop_both"]["*"] - OBS["S3_drop_posA"]["*"]
d21 = OBS["S2_drop_defect"]["*"] - OBS["S1_none"]["*"]
d42 = OBS["S4_drop_both"]["*"] - OBS["S2_drop_defect"]["*"]
print(f"    path via posA-first : (S3-S1)={d31:+.4f} + (S4-S3)={d43:+.4f} = {d31+d43:+.4f}   (S4-S1={d41:+.4f})")
print(f"    path via defect-first: (S2-S1)={d21:+.4f} + (S4-S2)={d42:+.4f} = {d21+d42:+.4f}")
print(f"    -> the decomposition is ORDER-DEPENDENT: posA share is {d31/d41:.1%} if posA goes first,")
print(f"       but {d42/d41:.1%} if defect goes first; defect share is {d43/d41:.1%} vs {d21/d41:.1%}.")

print()
print("=" * 100)
print("(3) THE SHARE ITSELF -- bootstrap distribution of (S3-S1)/(S4-S1)  [M3]")
print("=" * 100)
sh, bad = [], 0
for rep in reps:
    den = rep["S4_drop_both"]["*"] - rep["S1_none"]["*"]
    num = rep["S3_drop_posA"]["*"] - rep["S1_none"]["*"]
    if abs(den) < 1e-12:
        bad += 1; continue
    sh.append(num / den)
print(f"  observed share = {d31/d41:.4f}")
print(f"  bootstrap 95% percentile interval for the share: [{pct(sh,.025):.3f}, {pct(sh,.975):.3f}]")
print(f"  bootstrap 80%                                  : [{pct(sh,.10):.3f}, {pct(sh,.90):.3f}]")
print(f"  P(share > 1)  = {sum(1 for x in sh if x > 1)/len(sh):.3f}   "
      f"P(share < 0.5) = {sum(1 for x in sh if x < 0.5)/len(sh):.3f}   "
      f"P(denominator S4-S1 <= 0) = {sum(1 for rep in reps if rep['S4_drop_both']['*']-rep['S1_none']['*'] <= 0)/R:.4f}")
print("  NOTE: the denominator's own CI [+0.0029,+0.0333] nearly touches 0, so this ratio is a")
print("        Fieller-unstable quantity; a point estimate of '89%' has essentially no precision.")

print()
print("=" * 100)
print("(4) THE POWERED QUESTION -- do the excluded items actually behave differently?  [M4]")
print("    contrast = delta(excluded subset) - delta(the set it is removed from)")
print("=" * 100)
CON = [("X_posA_only", "S1_none", "posA items vs everything"),
       ("X_defect_only", "S1_none", "defect items vs everything"),
       ("X_defect_notA", "S3_drop_posA", "defect items (non-posA) vs the posA-filtered set")]
for a, b, lab in CON:
    vals = [rep[a]["*"] - rep[b]["*"] for rep in reps if rep[a]["*"] is not None]
    obs = OBS[a]["*"] - OBS[b]["*"]
    lo, hi, p, ties = ci_p(vals)
    print(f"  {lab:<48} {obs:+.4f}  [{lo:+.4f},{hi:+.4f}]  p={p:.4f}  (n_reps={len(vals)})")

print()
print("=" * 100)
print("(5) PER-ITEM LEVERAGE  [M5] -- shift produced per item removed")
print("=" * 100)
n_posA = len(file_posA)
n_def = len(file_defect)
n_def_notA = len(file_defect - file_posA)
print(f"  posA rule   : {n_posA:3d} items -> shift {d31:+.4f}   = {d31/n_posA*1e4:+.3f} x 1e-4 per item")
print(f"  defect rule : {n_def:3d} items -> shift {d21:+.4f}   = {d21/n_def*1e4:+.3f} x 1e-4 per item")
print(f"  defect|posA : {n_def_notA:3d} items -> shift {d43:+.4f}   = {d43/n_def_notA*1e4:+.3f} x 1e-4 per item")
lev = []
for rep in reps:
    a = (rep["S3_drop_posA"]["*"] - rep["S1_none"]["*"]) / n_posA
    b = (rep["S2_drop_defect"]["*"] - rep["S1_none"]["*"]) / n_def
    lev.append(b - a)
lo, hi, p, ties = ci_p(lev)
print(f"  per-item leverage difference (defect - posA): {d21/n_def - d31/n_posA:+.3e}"
      f"  [{lo:+.3e},{hi:+.3e}]  p={p:.4f}")
print("  -> if this straddles 0, the two rules are equally distorting PER ITEM and the posA rule")
print("     dominates the headline only because it removes ~8x more items.")

print()
print("=" * 100)
print("(6) PER-MODEL: is the 'defect rule contributes nothing' statement true for every model?")
print("=" * 100)
print(f"  {'model':<26}{'S4-S1':>20}{'S3-S1':>20}{'S2-S1':>20}{'S4-S3':>20}")
for k in KEYS:
    nm = "POOLED" if k == "*" else k.split("/")[-1]
    line = f"  {nm:<26}"
    for a, b in [("S4_drop_both", "S1_none"), ("S3_drop_posA", "S1_none"),
                 ("S2_drop_defect", "S1_none"), ("S4_drop_both", "S3_drop_posA")]:
        vals = [rep[a][k] - rep[b][k] for rep in reps if rep[a][k] is not None and rep[b][k] is not None]
        obs = OBS[a][k] - OBS[b][k]
        lo, hi, p, ties = ci_p(vals)
        star = "*" if (lo > 0 or hi < 0) else " "
        line += f"{obs:+.4f}{star}p={p:.3f}".rjust(20)
    print(line)

print()
print("=" * 100)
print("(7) SEED / R STABILITY of the two 'null' p-values")
print("=" * 100)
for seed in (20260731, 987654321, 11, 555_000_111):
    for RR in (5000, 20000):
        rg = random.Random(seed)
        v21, v43 = [], []
        for _ in range(RR):
            acc = blank()
            for _ in range(C):
                for (sid, k, n, sa, sb) in flat[rg.randrange(C)]:
                    if k != "*":
                        continue
                    a = acc[sid][k]; a[0] += n; a[1] += sa; a[2] += sb
            dd = {s: ((acc[s]["*"][2] - acc[s]["*"][1]) / acc[s]["*"][0] if acc[s]["*"][0] else None)
                  for s in AIDS}
            v21.append(dd["S2_drop_defect"] - dd["S1_none"])
            v43.append(dd["S4_drop_both"] - dd["S3_drop_posA"])
        l1, h1, p1, _ = ci_p(v21)
        l2, h2, p2, _ = ci_p(v43)
        print(f"  seed={seed:<12} R={RR:<6}  S2-S1 p={p1:.4f} [{l1:+.4f},{h1:+.4f}]   "
              f"S4-S3 p={p2:.4f} [{l2:+.4f},{h2:+.4f}]")

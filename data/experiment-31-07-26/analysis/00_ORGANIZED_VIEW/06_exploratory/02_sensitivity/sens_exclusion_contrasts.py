#!/usr/bin/env python3
"""
sens_exclusion_contrasts.py -- companion to sens_exclusion_grid.py

Two questions the marginal grid cannot answer:

(1) Is the SHIFT in the headline caused by an exclusion rule itself statistically
    distinguishable from zero?  The four exclusion sets are NESTED, so their
    deltas are not independent.  Method: PAIRED cluster bootstrap -- resample the
    281 clusters of the unfiltered set once per replicate, then recompute the
    delta under all four filters on THAT SAME resample.  The replicate-wise
    difference delta(Sx) - delta(Sy) is then a properly paired quantity; report
    its 95% percentile CI and a two-sided bootstrap p.

(2) Does the rank order of models flip?  Method: for every ordered model pair,
    the bootstrap probability that model i shows less degradation than model j,
    per exclusion set.  A rank that is "robust" should sit near 0 or 1 in every
    column; a rank near 0.5 is a coin flip and its apparent reordering across
    exclusion sets is noise.

stdlib only.
"""

import json, os, random, math
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "paired_clean.json")))
MODELS = sorted(set(r["model"] for r in rows))
R = 20000
SEED = 20260731

FILTERS = {
    "S1_none":        lambda r: True,
    "S2_drop_defect": lambda r: not r["excl_item_defect"],
    "S3_drop_posA":   lambda r: not r["excl_nota_position_a"],
    "S4_drop_both":   lambda r: r["analysis_include"],
}
SIDS = list(FILTERS)

# per cluster: {set_id: {key: [n, sa, sb]}}
tab = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0, 0, 0])))
for r in rows:
    for sid, f in FILTERS.items():
        if not f(r):
            continue
        for k in (r["model"], "*"):
            t = tab[r["cluster"]][sid][k]
            t[0] += 1; t[1] += r["A_correct"]; t[2] += r["B_correct"]

clusters = sorted(tab)
C = len(clusters)
KEYS = ["*"] + MODELS
flat = [[(sid, k, v[0], v[1], v[2]) for sid in SIDS for k, v in tab[c][sid].items()] for c in clusters]


def observed():
    acc = {s: {k: [0, 0, 0] for k in KEYS} for s in SIDS}
    for cf in flat:
        for (sid, k, n, sa, sb) in cf:
            a = acc[sid][k]; a[0] += n; a[1] += sa; a[2] += sb
    return {s: {k: ((acc[s][k][2] - acc[s][k][1]) / acc[s][k][0] if acc[s][k][0] else None) for k in KEYS}
            for s in SIDS}


OBS = observed()

rng = random.Random(SEED)
reps = []
for _ in range(R):
    acc = {s: {k: [0, 0, 0] for k in KEYS} for s in SIDS}
    for _ in range(C):
        for (sid, k, n, sa, sb) in flat[rng.randrange(C)]:
            a = acc[sid][k]; a[0] += n; a[1] += sa; a[2] += sb
    reps.append({s: {k: ((acc[s][k][2] - acc[s][k][1]) / acc[s][k][0] if acc[s][k][0] else None) for k in KEYS}
                 for s in SIDS})


def pct(v, q):
    v = sorted(v); i = q * (len(v) - 1)
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return v[lo] if lo == hi else v[lo] + (v[hi] - v[lo]) * (i - lo)


def ci_p(vals, obs):
    lo, hi = pct(vals, 0.025), pct(vals, 0.975)
    nle = sum(1 for x in vals if x <= 0); nge = sum(1 for x in vals if x >= 0)
    p = min(1.0, 2 * min(nle, nge) / len(vals))
    return lo, hi, p


print("=" * 104)
print("(1) PAIRED CLUSTER-BOOTSTRAP CONTRASTS BETWEEN EXCLUSION SETS  (R=20000, same clusters per replicate)")
print("    positive = the first set shows LESS degradation (delta closer to 0)")
print("=" * 104)
PAIRS = [("S4_drop_both", "S1_none"), ("S4_drop_both", "S2_drop_defect"),
         ("S4_drop_both", "S3_drop_posA"), ("S3_drop_posA", "S1_none"),
         ("S2_drop_defect", "S1_none")]
for k in KEYS:
    nm = "POOLED" if k == "*" else k.split("/")[-1]
    print(f"\n  {nm}")
    for a, b in PAIRS:
        vals = [rep[a][k] - rep[b][k] for rep in reps if rep[a][k] is not None and rep[b][k] is not None]
        obs = OBS[a][k] - OBS[b][k]
        lo, hi, p = ci_p(vals, obs)
        star = " *" if (lo > 0 or hi < 0) else ""
        print(f"    {a:<15} - {b:<15} {obs:+.4f}  [{lo:+.4f},{hi:+.4f}]  p={p:.4f}{star}")

print()
print("=" * 104)
print("(2) BOOTSTRAP P(model i LESS degraded than model j)  -- 0.5 == coin flip == rank is not identified")
print("=" * 104)
hdr = f"{'contrast':<50}" + "".join(f"{s:>16}" for s in SIDS)
print(hdr)
for i in range(len(MODELS)):
    for j in range(len(MODELS)):
        if i >= j: continue
        mi, mj = MODELS[i], MODELS[j]
        lab = f"{mi.split('/')[-1]} > {mj.split('/')[-1]}"
        line = f"{lab:<50}"
        for s in SIDS:
            v = [1 for rep in reps if rep[s][mi] is not None and rep[s][mj] is not None and rep[s][mi] > rep[s][mj]]
            tot = sum(1 for rep in reps if rep[s][mi] is not None and rep[s][mj] is not None)
            line += f"{len(v)/tot:>16.3f}"
        print(line)

print()
print("=" * 104)
print("(3) FULL RANK-VECTOR STABILITY: bootstrap probability of each complete robustness ordering")
print("=" * 104)
for s in SIDS:
    cnt = Counter()
    for rep in reps:
        order = tuple(sorted(MODELS, key=lambda m: -(rep[s][m] if rep[s][m] is not None else -9)))
        cnt[order] += 1
    print(f"\n  {s}   (observed order: {' > '.join(m.split('/')[-1] for m in sorted(MODELS, key=lambda m: -OBS[s][m]))})")
    for order, n in cnt.most_common(4):
        print(f"      {n/R:.3f}   {' > '.join(o.split('/')[-1] for o in order)}")

print()
print("=" * 104)
print("(4) SIGN / SIGNIFICANCE INVARIANCE CHECK")
print("=" * 104)
print(f"{'key':<26}" + "".join(f"{s:>16}" for s in SIDS) + "   all-neg  all-CI-excl-0")
for k in KEYS:
    nm = "POOLED" if k == "*" else k.split("/")[-1]
    line = f"{nm:<26}"
    negs, excl = [], []
    for s in SIDS:
        v = [rep[s][k] for rep in reps if rep[s][k] is not None]
        lo, hi = pct(v, 0.025), pct(v, 0.975)
        line += f"{OBS[s][k]:>16.4f}"
        negs.append(OBS[s][k] < 0)
        excl.append(hi < 0 or lo > 0)
    print(line + f"     {all(negs)!s:>5}   {all(excl)!s:>5}")

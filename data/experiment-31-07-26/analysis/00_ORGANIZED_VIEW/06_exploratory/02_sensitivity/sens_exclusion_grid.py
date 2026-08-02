#!/usr/bin/env python3
"""
sens_exclusion_grid.py -- full 2x2 sensitivity grid over the two contestable
exclusion rules in the tier1 MCQ paired A->B experiment.

Exclusion rules
  D = excl_item_defect        (out-of-domain administrative-law items + adjudicated wrong keys)
  P = excl_nota_position_a    (correct letter == 'a'; inserted "Ninguna de las respuestas
                               ANTERIORES..." sits in the FIRST slot -> no antecedent)

Grid
  S1 none        : all cells
  S2 drop D only
  S3 drop P only
  S4 drop both   : the published 325-item analysis set (== analysis_include)

Statistics (stdlib only, no numpy/scipy)
  * delta = acc(B) - acc(A), computed on paired cells (identical denominator).
  * 95% CI: nonparametric CLUSTER bootstrap. Clinical-context clusters are the
    resampling unit; a cluster is drawn with replacement together with ALL of its
    items and ALL 4 models' cells for those items. 20000 replicates, percentile CI.
  * p-value: CLUSTER SIGN-FLIP PERMUTATION. Under H0 the A/B label is exchangeable
    within a cluster, so each cluster's paired contribution (sumB - sumA) gets an
    independent random sign. Two-sided p = (#{|delta*| >= |delta_obs|} + 1)/(R+1),
    R = 20000. This is exact-in-distribution for the sharp null of no A->B effect
    and is robust to arbitrary within-cluster dependence.
  * McNemar (uncorrected, binomial exact, two-sided) is also reported as a
    non-clustered reference point; it IGNORES clustering and is anti-conservative.
"""

import json, os, random, math
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "paired_clean.json")
META = os.path.join(HERE, "dataset_meta.json")

R_BOOT = 20000
R_PERM = 20000
SEED = 20260731

rows = json.load(open(DATA))
meta = json.load(open(META))

MODELS = sorted(set(r["model"] for r in rows))

SETS = [
    ("S1_none",        "no exclusions (unfiltered)",        lambda r: True),
    ("S2_drop_defect", "drop 11 defective items only",      lambda r: not r["excl_item_defect"]),
    ("S3_drop_posA",   "drop 91 position-(a) items only",   lambda r: not r["excl_nota_position_a"]),
    ("S4_drop_both",   "published analysis set",            lambda r: r["analysis_include"]),
    # diagnostic: the excluded strata themselves
    ("X_posA_only",    "ONLY the 91 position-(a) items",    lambda r: r["excl_nota_position_a"]),
    ("X_defect_only",  "ONLY the 11 defective items",       lambda r: r["excl_item_defect"]),
]


# ---------------------------------------------------------------- aggregation
def cluster_table(sub):
    """cluster -> {model: [n, sumA, sumB]} plus pooled row under key '*'."""
    tab = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    for r in sub:
        c = r["cluster"]
        for k in (r["model"], "*"):
            t = tab[c][k]
            t[0] += 1
            t[1] += r["A_correct"]
            t[2] += r["B_correct"]
    return tab


def point(sub, key):
    n = sa = sb = 0
    for r in sub:
        if key != "*" and r["model"] != key:
            continue
        n += 1
        sa += r["A_correct"]
        sb += r["B_correct"]
    if n == 0:
        return None
    return dict(n=n, accA=sa / n, accB=sb / n, delta=(sb - sa) / n, sa=sa, sb=sb)


def mcnemar(sub, key):
    """b = A right & B wrong ; c = A wrong & B right ; exact binomial two-sided."""
    b = c = 0
    for r in sub:
        if key != "*" and r["model"] != key:
            continue
        if r["A_correct"] == 1 and r["B_correct"] == 0:
            b += 1
        elif r["A_correct"] == 0 and r["B_correct"] == 1:
            c += 1
    n = b + c
    if n == 0:
        return b, c, 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return b, c, min(1.0, 2 * tail)


# ---------------------------------------------------------------- resampling
def boot(tab, keys, rng, reps=R_BOOT):
    """cluster bootstrap; returns {key: sorted list of delta*} and per-rep delta dict list."""
    clusters = list(tab.keys())
    C = len(clusters)
    # flatten for speed: per cluster, list of (key, n, sa, sb)
    flat = []
    for c in clusters:
        flat.append([(k, v[0], v[1], v[2]) for k, v in tab[c].items()])
    out = {k: [] for k in keys}
    reps_all = []
    for _ in range(reps):
        acc = {k: [0, 0, 0] for k in keys}
        for _ in range(C):
            for (k, n, sa, sb) in flat[rng.randrange(C)]:
                a = acc.get(k)
                if a is None:
                    continue
                a[0] += n; a[1] += sa; a[2] += sb
        rep = {}
        for k in keys:
            n, sa, sb = acc[k]
            rep[k] = (sb - sa) / n if n else None
            if n:
                out[k].append(rep[k])
        reps_all.append(rep)
    for k in keys:
        out[k].sort()
    return out, reps_all


def pct(sorted_vals, q):
    if not sorted_vals:
        return None
    i = q * (len(sorted_vals) - 1)
    lo = int(math.floor(i)); hi = int(math.ceil(i))
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (i - lo)


def perm(tab, key, obs, rng, reps=R_PERM):
    """cluster sign-flip permutation on the paired A/B label."""
    diffs = []
    N = 0
    for c in tab:
        v = tab[c].get(key)
        if v:
            diffs.append(v[2] - v[1])
            N += v[0]
    if N == 0:
        return None
    ao = abs(obs)
    hit = 0
    for _ in range(reps):
        s = 0
        for d in diffs:
            s += d if rng.getrandbits(1) else -d
        if abs(s / N) >= ao - 1e-12:
            hit += 1
    return (hit + 1) / (reps + 1)


# ---------------------------------------------------------------- run grid
KEYS = ["*"] + MODELS
results = {}
boot_reps_store = {}

for sid, label, filt in SETS:
    sub = [r for r in rows if filt(r)]
    tab = cluster_table(sub)
    rng = random.Random(SEED)
    bd, reps_all = boot(tab, KEYS, rng)
    boot_reps_store[sid] = reps_all
    rngp = random.Random(SEED + 1)
    ent = dict(
        label=label,
        n_cells=len(sub),
        n_items=len(set(r["question_id"] for r in sub)),
        n_clusters=len(tab),
        per={},
    )
    for k in KEYS:
        pt = point(sub, k)
        if pt is None:
            continue
        b, c, pmc = mcnemar(sub, k)
        ent["per"][k] = dict(
            **pt,
            lo=pct(bd[k], 0.025),
            hi=pct(bd[k], 0.975),
            se=(sum((x - sum(bd[k]) / len(bd[k])) ** 2 for x in bd[k]) / (len(bd[k]) - 1)) ** 0.5,
            p_perm=perm(tab, k, pt["delta"], rngp),
            mcnemar_b=b, mcnemar_c=c, p_mcnemar=pmc,
        )
    results[sid] = ent

# ---------------------------------------------------------------- report
def f(x, nd=4):
    return "n/a" if x is None else f"{x:+.{nd}f}"

def pp(p):
    if p is None: return "n/a"
    if p < 1 / (R_PERM + 1) * 1.5: return f"<{1/(R_PERM+1):.5f}"
    return f"{p:.5f}"

print("=" * 108)
print("SET COMPOSITION")
print("=" * 108)
print(f"{'set':<16} {'description':<34} {'items':>6} {'cells':>7} {'clusters':>9}")
for sid, _, _ in SETS:
    e = results[sid]
    print(f"{sid:<16} {e['label']:<34} {e['n_items']:>6} {e['n_cells']:>7} {e['n_clusters']:>9}")

for sid, _, _ in SETS:
    e = results[sid]
    print()
    print("=" * 108)
    print(f"{sid}  --  {e['label']}   [items={e['n_items']}  cells={e['n_cells']}  clusters={e['n_clusters']}]")
    print("=" * 108)
    print(f"{'model':<26} {'n':>5} {'accA':>7} {'accB':>7} {'delta':>9} {'95% cluster-boot CI':>24} "
          f"{'p_perm':>10} {'b/c':>10} {'p_McN':>10}")
    for k in KEYS:
        d = e["per"].get(k)
        if not d: continue
        nm = "POOLED" if k == "*" else k
        ci = f"[{d['lo']:+.4f}, {d['hi']:+.4f}]"
        print(f"{nm:<26} {d['n']:>5} {d['accA']:>7.4f} {d['accB']:>7.4f} {d['delta']:>+9.4f} {ci:>24} "
              f"{pp(d['p_perm']):>10} {str(d['mcnemar_b'])+'/'+str(d['mcnemar_c']):>10} {d['p_mcnemar']:>10.2e}")

# ---------------------------------------------------------------- headline movement
print()
print("=" * 108)
print("HEADLINE MOVEMENT (pooled delta)")
print("=" * 108)
base = results["S4_drop_both"]["per"]["*"]["delta"]
for sid in ["S1_none", "S2_drop_defect", "S3_drop_posA", "S4_drop_both"]:
    d = results[sid]["per"]["*"]
    print(f"{sid:<16} delta={d['delta']:+.4f}  CI=[{d['lo']:+.4f},{d['hi']:+.4f}]  "
          f"shift vs published = {d['delta']-base:+.4f} pp*100={100*(d['delta']-base):+.2f}")
mx = max(results[s]["per"]["*"]["delta"] for s in ["S1_none","S2_drop_defect","S3_drop_posA","S4_drop_both"])
mn = min(results[s]["per"]["*"]["delta"] for s in ["S1_none","S2_drop_defect","S3_drop_posA","S4_drop_both"])
print(f"pooled delta range across the 4 sets: [{mn:+.4f}, {mx:+.4f}]  span = {mx-mn:.4f} ({100*(mx-mn):.2f} pts)")

# ---------------------------------------------------------------- robustness ranking
print()
print("=" * 108)
print("ROBUSTNESS RANKING  (most robust = delta closest to 0, i.e. LARGEST delta since all deltas<0)")
print("=" * 108)
for sid in ["S1_none", "S2_drop_defect", "S3_drop_posA", "S4_drop_both"]:
    e = results[sid]["per"]
    order = sorted(MODELS, key=lambda m: -e[m]["delta"])
    s = "  >  ".join(f"{m}({e[m]['delta']:+.4f})" for m in order)
    print(f"{sid:<16} {s}")
print()
print("ranking by raw B accuracy (higher = better under the NOTA swap)")
for sid in ["S1_none", "S2_drop_defect", "S3_drop_posA", "S4_drop_both"]:
    e = results[sid]["per"]
    order = sorted(MODELS, key=lambda m: -e[m]["accB"])
    s = "  >  ".join(f"{m}({e[m]['accB']:.4f})" for m in order)
    print(f"{sid:<16} {s}")

# bootstrap P(model is rank-1 most robust by delta)
print()
print("=" * 108)
print("CLUSTER-BOOTSTRAP P(model has the smallest degradation | exclusion set)  [20000 reps]")
print("=" * 108)
hdr = f"{'set':<16}" + "".join(f"{m.split('/')[-1][:22]:>24}" for m in MODELS)
print(hdr)
for sid in ["S1_none", "S2_drop_defect", "S3_drop_posA", "S4_drop_both"]:
    cnt = Counter()
    reps = boot_reps_store[sid]
    for rep in reps:
        best = max(MODELS, key=lambda m: (rep[m] if rep[m] is not None else -9))
        cnt[best] += 1
    line = f"{sid:<16}" + "".join(f"{cnt[m]/len(reps):>24.3f}" for m in MODELS)
    print(line)

# pairwise delta differences vs the top model of the published set
print()
print("=" * 108)
print("PAIRWISE CONTRASTS IN DELTA (cluster bootstrap, 95% percentile CI; two-sided bootstrap p)")
print("=" * 108)
for sid in ["S1_none", "S2_drop_defect", "S3_drop_posA", "S4_drop_both"]:
    reps = boot_reps_store[sid]
    e = results[sid]["per"]
    print(f"\n-- {sid}")
    for i in range(len(MODELS)):
        for j in range(i + 1, len(MODELS)):
            mi, mj = MODELS[i], MODELS[j]
            diffs = sorted(rep[mi] - rep[mj] for rep in reps if rep[mi] is not None and rep[mj] is not None)
            obs = e[mi]["delta"] - e[mj]["delta"]
            lo, hi = pct(diffs, 0.025), pct(diffs, 0.975)
            nle = sum(1 for x in diffs if x <= 0); nge = sum(1 for x in diffs if x >= 0)
            pb = min(1.0, 2 * min(nle, nge) / len(diffs))
            star = "  *" if (lo > 0 or hi < 0) else ""
            print(f"   {mi.split('/')[-1]:<22} - {mj.split('/')[-1]:<22} "
                  f"{obs:+.4f}  [{lo:+.4f},{hi:+.4f}]  p={pb:.4f}{star}")

json.dump(
    {k: {kk: vv for kk, vv in v.items()} for k, v in results.items()},
    open(os.path.join(HERE, "sens_exclusion_grid_results.json"), "w"),
    indent=2,
)
print("\nwrote sens_exclusion_grid_results.json")

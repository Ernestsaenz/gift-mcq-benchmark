#!/usr/bin/env python3
"""
prim_permutation_exact.py -- EXACT sign-flip (randomisation) null distributions.

The Monte Carlo run in prim_permutation.py bottoms out at p = 1/(B+1) = 5e-5 for
every level, so it cannot separate the three schemes. But the randomisation
statistic is a signed sum of INTEGERS, so its exact null distribution is
computable by convolution: enumerate all 2^K sign vectors implicitly via a DP
over attainable integer totals, with exact big-integer counts. No sampling, no
normal approximation, no floor.

Statistic (raw integer scale): T = sum_u s_u * D_u,  s_u i.i.d. uniform {-1,+1},
where u indexes the exchangeable unit and D_u = sum over that unit's cells of
(A_correct - B_correct).  Delta_pp = 100 * T / n_cells.

Two-sided exact p = #{sign vectors : |T| >= |T_obs|} / 2^K.

Schemes:
  S1 CELL    : u = item x model cell   (all |D_u| = 1 on discordants)
  S2 ITEM    : u = item, 4 models flip together
  S3 CLUSTER : u = clinical-context cluster, every cell in it flips together

Also: cluster bootstrap CI for the pooled delta (supplementary, resampling
whole clusters with replacement).

Standard library only.
"""

import json
import random
from collections import defaultdict, OrderedDict
from fractions import Fraction

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")

with open(DATA) as fh:
    rows = [r for r in json.load(fh) if r["analysis_include"] is True]

models = sorted({r["model"] for r in rows})
for r in rows:
    r["_d"] = r["A_correct"] - r["B_correct"]

by_model = defaultdict(list)
for r in rows:
    by_model[r["model"]].append(r)

LEVELS = models + ["POOLED"]
N = {m: len(by_model[m]) for m in models}
N["POOLED"] = len(rows)
T_OBS = {m: sum(r["_d"] for r in by_model[m]) for m in models}
T_OBS["POOLED"] = sum(r["_d"] for r in rows)


# ---------------------------------------------------------------------------
# Exact sign-flip null distribution by integer convolution
# ---------------------------------------------------------------------------
def exact_signflip(Ds):
    """Ds: per-unit integer totals. Returns (dist, offset, K).

    dist[i] = number of the 2^K sign vectors giving T = i - offset.
    Units with D_u == 0 are dropped (they cannot move T); K counts only the
    units that can. The distribution is symmetric, so sign(D_u) is irrelevant.
    """
    Ds = [abs(d) for d in Ds if d != 0]
    K = len(Ds)
    M = sum(Ds)
    dist = [0] * (2 * M + 1)
    dist[M] = 1
    for d in Ds:
        nd = [0] * (2 * M + 1)
        for i, c in enumerate(dist):
            if c:
                nd[i + d] += c
                nd[i - d] += c
        dist = nd
    return dist, M, K


def exact_p(Ds, t_obs):
    """Two-sided exact randomisation p-value, as an exact Fraction."""
    dist, M, K = exact_signflip(Ds)
    a = abs(t_obs)
    hits = sum(c for i, c in enumerate(dist) if abs(i - M) >= a)
    return Fraction(hits, 1 << K), K, dist, M


def dist_sd_pp(dist, M, K, n_cells):
    """SD of the exact null distribution, on the percentage-point scale."""
    tot = 1 << K
    mean = sum(c * (i - M) for i, c in enumerate(dist)) / tot
    var = sum(c * ((i - M) - mean) ** 2 for i, c in enumerate(dist)) / tot
    return (var ** 0.5) * 100.0 / n_cells, mean * 100.0 / n_cells


# ---------------------------------------------------------------------------
# Build per-unit D totals for each scheme
# ---------------------------------------------------------------------------
def unit_totals(keyfn):
    """-> {level: [D_u, ...]} for the given grouping key."""
    acc = defaultdict(lambda: defaultdict(int))   # unit -> level -> D
    for r in rows:
        u = keyfn(r)
        acc[u][r["model"]] += r["_d"]
        acc[u]["POOLED"] += r["_d"]
    return {lv: [acc[u].get(lv, 0) for u in acc] for lv in LEVELS}, len(acc)


S1, n_u1 = unit_totals(lambda r: (r["question_id"], r["model"]))
S2, n_u2 = unit_totals(lambda r: r["question_id"])
S3, n_u3 = unit_totals(lambda r: r["cluster"])

SCHEMES = [
    ("S1 CELL   (item x model)", S1, n_u1),
    ("S2 ITEM   (4 models flip together)", S2, n_u2),
    ("S3 CLUSTER(all cells flip together)", S3, n_u3),
]

print("=" * 96)
print("EXACT SIGN-FLIP RANDOMISATION TESTS  (full enumeration by integer "
      "convolution; no sampling)")
print("=" * 96)
print(f"cells={N['POOLED']}  items={len({r['question_id'] for r in rows})}  "
      f"clusters={len({r['cluster'] for r in rows})}  models={len(models)}")
print(f"observed T (= b - c, raw counts): "
      + "  ".join(f"{lv.split('/')[-1]}={T_OBS[lv]}" for lv in LEVELS))

results = {}
for name, S, n_units in SCHEMES:
    print()
    print("-" * 96)
    print(f"{name}   exchangeable units in design: {n_units}")
    print("-" * 96)
    print(f"{'level':<26}{'K_active':>10}{'obs_pp':>9}{'null_sd_pp':>12}"
          f"{'z':>7}{'p_exact_2sided':>18}{'min_possible_p':>16}")
    results[name] = {}
    for lv in LEVELS:
        p, K, dist, M = exact_p(S[lv], T_OBS[lv])
        sd_pp, mean_pp = dist_sd_pp(dist, M, K, N[lv])
        obs_pp = 100.0 * T_OBS[lv] / N[lv]
        z = (obs_pp - mean_pp) / sd_pp if sd_pp > 0 else float("nan")
        minp = 2.0 / (1 << K) if K else 1.0
        results[name][lv] = dict(p=float(p), K=K, obs_pp=obs_pp,
                                 null_sd_pp=sd_pp, z=z)
        print(f"{lv:<26}{K:>10}{obs_pp:>9.2f}{sd_pp:>12.3f}{z:>7.2f}"
              f"{float(p):>18.4e}{minp:>16.2e}")

# ---------------------------------------------------------------------------
# Head-to-head: how much does the p-value move as the unit coarsens?
# ---------------------------------------------------------------------------
print()
print("=" * 96)
print("EFFECT OF COARSENING THE EXCHANGEABLE UNIT")
print("=" * 96)
names = [s[0] for s in SCHEMES]
print(f"{'level':<26}{'p(S1 cell)':>14}{'p(S2 item)':>14}{'p(S3 cluster)':>16}"
      f"{'sd S2/S1':>10}{'sd S3/S1':>10}{'p ratio S3/S1':>15}")
for lv in LEVELS:
    r1, r2, r3 = (results[n][lv] for n in names)
    print(f"{lv:<26}{r1['p']:>14.3e}{r2['p']:>14.3e}{r3['p']:>16.3e}"
          f"{r2['null_sd_pp']/r1['null_sd_pp']:>10.3f}"
          f"{r3['null_sd_pp']/r1['null_sd_pp']:>10.3f}"
          f"{r3['p']/r1['p']:>15.3e}")

# ---------------------------------------------------------------------------
# Where the pooled S1 vs S3 gap comes from: within-cluster concordance of the
# A>B direction. If discordances were independent across cells, S1 == S3.
# ---------------------------------------------------------------------------
print()
print("=" * 96)
print("WHY S3 IS WIDER: CLUSTERING OF THE EFFECT")
print("=" * 96)
cl = defaultdict(int)
cl_cells = defaultdict(int)
for r in rows:
    cl[r["cluster"]] += r["_d"]
    cl_cells[r["cluster"]] += 1
Dc = list(cl.values())
pos = sum(1 for x in Dc if x > 0)
neg = sum(1 for x in Dc if x < 0)
tie = sum(1 for x in Dc if x == 0)
print(f"clusters: {len(Dc)}   A>B net: {pos}   A<B net: {neg}   net tie: {tie}")
print(f"cluster |D| distribution: "
      + ", ".join(f"|D|={k}:{sum(1 for x in Dc if abs(x)==k)}"
                  for k in sorted({abs(x) for x in Dc})))
sum_absD = sum(abs(x) for x in Dc)
sum_d_abs = sum(abs(r["_d"]) for r in rows)
print(f"sum|D_cluster| = {sum_absD}   sum|d_cell| = {sum_d_abs}   "
      f"ratio = {sum_absD/sum_d_abs:.3f}  "
      f"(1.0 => perfect within-cluster agreement; ~1/sqrt => independence)")
print(f"variance inflation of the pooled null, S3 vs S1: "
      f"{(results[names[2]]['POOLED']['null_sd_pp']/results[names[0]]['POOLED']['null_sd_pp'])**2:.3f}x "
      f"(design effect)")

# exact cluster sign test on the DIRECTION only (drops magnitudes entirely)
def binom_tail(k, n):
    if n == 0:
        return Fraction(1)
    tot = 0
    for i in range(k + 1):
        c = 1
        for j in range(i):
            c = c * (n - j) // (j + 1)
        tot += c
    return Fraction(tot, 1 << n)

p_dir = min(Fraction(1), 2 * binom_tail(min(pos, neg), pos + neg))
print(f"direction-only cluster sign test (magnitudes discarded, most "
      f"conservative of all): exact 2-sided p = {float(p_dir):.4e}")

# ---------------------------------------------------------------------------
# Supplementary: cluster bootstrap CI for the pooled delta
# ---------------------------------------------------------------------------
print()
print("=" * 96)
print("SUPPLEMENTARY: CLUSTER BOOTSTRAP CI FOR THE POOLED DELTA")
print("=" * 96)
clusters = sorted({r["cluster"] for r in rows})
cl_rows = defaultdict(list)
for r in rows:
    cl_rows[r["cluster"]].append(r)
cl_sum = {c: sum(x["_d"] for x in cl_rows[c]) for c in clusters}
cl_n = {c: len(cl_rows[c]) for c in clusters}

rng = random.Random(4242)
NB = 20000
boots = []
nc = len(clusters)
for _ in range(NB):
    s = 0
    k = 0
    for _ in range(nc):
        c = clusters[rng.randrange(nc)]
        s += cl_sum[c]
        k += cl_n[c]
    boots.append(100.0 * s / k)
boots.sort()
lo = boots[int(0.025 * NB)]
hi = boots[int(0.975 * NB) - 1]
bmean = sum(boots) / NB
bsd = (sum((v - bmean) ** 2 for v in boots) / (NB - 1)) ** 0.5
print(f"method: resample all {nc} clusters with replacement, {NB} replicates, "
      f"delta recomputed as 100*sum(d)/n_cells within each replicate")
print(f"point estimate  {100.0*T_OBS['POOLED']/N['POOLED']:.2f} pp")
print(f"bootstrap mean  {bmean:.2f} pp   SE {bsd:.2f} pp")
print(f"95% percentile CI  [{lo:.2f}, {hi:.2f}] pp")
print(f"replicates with delta <= 0: {sum(1 for v in boots if v <= 0)} / {NB}")

# per-model cluster bootstrap
print()
print(f"{'model':<26}{'delta_pp':>10}{'boot_SE':>10}{'95% CI':>22}")
for m in models:
    cl_sum_m = defaultdict(int)
    cl_n_m = defaultdict(int)
    for r in by_model[m]:
        cl_sum_m[r["cluster"]] += r["_d"]
        cl_n_m[r["cluster"]] += 1
    rngm = random.Random(4242)
    bm = []
    for _ in range(NB):
        s = 0
        k = 0
        for _ in range(nc):
            c = clusters[rngm.randrange(nc)]
            s += cl_sum_m[c]
            k += cl_n_m[c]
        if k:
            bm.append(100.0 * s / k)
    bm.sort()
    mu = sum(bm) / len(bm)
    sd = (sum((v - mu) ** 2 for v in bm) / (len(bm) - 1)) ** 0.5
    print(f"{m:<26}{100.0*T_OBS[m]/N[m]:>10.2f}{sd:>10.2f}"
          f"   [{bm[int(0.025*len(bm))]:>6.2f}, {bm[int(0.975*len(bm))-1]:>6.2f}]")

# ---------------------------------------------------------------------------
out = {"exact": {n: results[n] for n in names},
       "cluster_direction_sign_test_p": float(p_dir),
       "cluster_bootstrap_pooled": {"delta_pp": 100.0*T_OBS['POOLED']/N['POOLED'],
                                    "se_pp": bsd, "ci95_pp": [lo, hi],
                                    "n_boot": NB}}
dest = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/prim_permutation_exact_results.json")
with open(dest, "w") as fh:
    json.dump(out, fh, indent=1)
print(f"\nwrote {dest}")

#!/usr/bin/env python3
"""
prim_refute_permutation_floor.py -- INDEPENDENT recomputation of the Monte Carlo
sign-flip randomisation claim.

CLAIM under test:
  "A 20,000-permutation Monte Carlo randomisation test is USELESS for separating
   these schemes: every level in every scheme hit the resolution floor of the
   test. 14 of 15 level x scheme combinations returned exactly 1/(B+1)=5.00e-05
   (0 hits); the 15th (gemini, cell-level) returned 1.0e-4 from a single hit.
   Permutation z-scores ranged 4.07 to 11.95."

This script re-derives everything from paired_clean.json, from scratch:
  (a) observed A/B rates and discordant b,c counts
  (b) MC sign-flip with the CLAIMED seeds (20260731 / +1 / +2), B=20000
  (c) MC sign-flip with 10 OTHER seed triples, to test whether "14 of 15" is a
      structural fact or a seed accident
  (d) EXACT sign-flip null (integer convolution DP, big-int counts) for each
      level x scheme -> exact p, exact null SD, exact z
  (e) head-to-head: does the MC run separate the schemes on the SD / design-
      effect / z scale, even though the p-values saturate?
  (f) how many of the "15 combinations" are actually distinct tests?

Standard library only. No numpy/scipy.
"""

import json
import random
from collections import defaultdict, OrderedDict
from fractions import Fraction

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")
NPERM = 20000
SEEDS = (20260731, 20260732, 20260733)   # claimed: SEED, SEED+1, SEED+2

with open(DATA) as fh:
    raw = json.load(fh)
rows = [r for r in raw if r["analysis_include"] is True]

models = sorted({r["model"] for r in rows})
LEVELS = models + ["POOLED"]
by_model = defaultdict(list)
for r in rows:
    r["_d"] = r["A_correct"] - r["B_correct"]
    by_model[r["model"]].append(r)

N = {m: len(by_model[m]) for m in models}
N["POOLED"] = len(rows)
T_OBS = {m: sum(r["_d"] for r in by_model[m]) for m in models}
T_OBS["POOLED"] = sum(r["_d"] for r in rows)

print("=" * 100)
print("0. DATA / OBSERVED  (independent recompute)")
print("=" * 100)
print(f"rows={len(raw)}  analysis_include={len(rows)}  "
      f"items={len({r['question_id'] for r in rows})}  "
      f"clusters={len({r['cluster'] for r in rows})}  models={len(models)}")
print(f"{'level':<26}{'n':>6}{'A%':>8}{'B%':>8}{'delta_pp':>10}{'b':>6}{'c':>6}{'b+c':>6}")
disc = {}
for lv in LEVELS:
    rs = rows if lv == "POOLED" else by_model[lv]
    n = len(rs)
    a = sum(r["A_correct"] for r in rs); b = sum(r["B_correct"] for r in rs)
    b_ = sum(1 for r in rs if r["_d"] == 1)
    c_ = sum(1 for r in rs if r["_d"] == -1)
    disc[lv] = (b_, c_)
    print(f"{lv:<26}{n:>6}{100*a/n:>8.2f}{100*b/n:>8.2f}"
          f"{100*(a-b)/n:>10.2f}{b_:>6}{c_:>6}{b_+c_:>6}")

# ---------------------------------------------------------------------------
# Per-unit integer totals D_u for each scheme
# ---------------------------------------------------------------------------
def unit_totals(keyfn):
    acc = defaultdict(lambda: defaultdict(int))
    for r in rows:
        u = keyfn(r)
        acc[u][r["model"]] += r["_d"]
        acc[u]["POOLED"] += r["_d"]
    units = list(acc)
    return {lv: [acc[u].get(lv, 0) for u in units] for lv in LEVELS}, len(units)

S = OrderedDict()
S["S1_cell"], nu1 = unit_totals(lambda r: (r["question_id"], r["model"]))
S["S2_item"], nu2 = unit_totals(lambda r: r["question_id"])
S["S3_cluster"], nu3 = unit_totals(lambda r: r["cluster"])
NU = {"S1_cell": nu1, "S2_item": nu2, "S3_cluster": nu3}

# ---------------------------------------------------------------------------
# (b,c) Monte Carlo sign-flip, generic over schemes, honest per-scheme seeds.
# Vector-valued draw: one sign per unit, applied to that unit's per-level totals,
# so all levels come from the SAME realised relabelling (as prim_permutation.py).
# ---------------------------------------------------------------------------
def mc_run(scheme, seed, B=NPERM):
    """Return {level: list of null statistics on the pp scale}."""
    # active units = those with any nonzero level total
    acc = defaultdict(lambda: defaultdict(int))
    keyfn = {"S1_cell": lambda r: (r["question_id"], r["model"]),
             "S2_item": lambda r: r["question_id"],
             "S3_cluster": lambda r: r["cluster"]}[scheme]
    for r in rows:
        acc[keyfn(r)][r["model"]] += r["_d"]
    vecs = []
    for u in acc:
        v = tuple(acc[u].get(m, 0) for m in models)
        if any(v):
            vecs.append(v)
    K = len(vecs)
    rng = random.Random(seed)
    out = {lv: [] for lv in LEVELS}
    idx = range(len(models))
    for _ in range(B):
        bits = rng.getrandbits(K) if K else 0
        a = [0] * len(models)
        for j, v in enumerate(vecs):
            s = 1 if (bits >> j) & 1 else -1
            for k in idx:
                if v[k]:
                    a[k] += s * v[k]
        for k, m in enumerate(models):
            out[m].append(100.0 * a[k] / N[m])
        out["POOLED"].append(100.0 * sum(a) / N["POOLED"])
    return out, K

def summarise(obs_pp, nulls):
    B = len(nulls)
    hits = sum(1 for v in nulls if abs(v) >= abs(obs_pp) - 1e-12)
    p = (1 + hits) / (B + 1)
    mu = sum(nulls) / B
    sd = (sum((v - mu) ** 2 for v in nulls) / (B - 1)) ** 0.5
    z = (obs_pp - mu) / sd if sd > 0 else float("nan")
    return hits, p, sd, z

OBS_PP = {lv: 100.0 * T_OBS[lv] / N[lv] for lv in LEVELS}

print()
print("=" * 100)
print(f"1. MONTE CARLO WITH THE CLAIMED SEEDS  B={NPERM}, seeds {SEEDS}")
print("=" * 100)
print(f"min attainable p = 1/(B+1) = {1/(NPERM+1):.6e}")
print(f"{'scheme':<12}{'level':<26}{'K':>6}{'obs_pp':>9}{'null_sd':>9}"
      f"{'z':>8}{'hits':>6}{'p_MC':>12}{'at floor?':>11}")
mc_claimed = {}
mc_sd = {}
zs = []
n_floor = 0
for (sch, seed) in zip(S.keys(), SEEDS):
    nulls, K = mc_run(sch, seed)
    mc_claimed[sch] = {}
    mc_sd[sch] = {}
    for lv in LEVELS:
        hits, p, sd, z = summarise(OBS_PP[lv], nulls[lv])
        mc_claimed[sch][lv] = (hits, p, sd, z)
        mc_sd[sch][lv] = sd
        zs.append(z)
        floor = (hits == 0)
        n_floor += floor
        print(f"{sch:<12}{lv:<26}{K:>6}{OBS_PP[lv]:>9.2f}{sd:>9.3f}"
              f"{z:>8.2f}{hits:>6}{p:>12.3e}{'YES' if floor else 'no':>11}")
print(f"\ncombinations exactly at the floor (0 hits): {n_floor} / 15")
print(f"z range across the 15 combinations: {min(zs):.2f} to {max(zs):.2f}")

# ---------------------------------------------------------------------------
# (c) Is "14 of 15" structural, or a seed accident?
# ---------------------------------------------------------------------------
print()
print("=" * 100)
print("2. SEED SENSITIVITY OF THE '14 of 15' SPLIT  (10 alternative seed triples)")
print("=" * 100)
print(f"{'seed base':>12}{'#combos at floor (of 15)':>28}   which combos had >=1 hit")
floor_counts = []
for base in [1, 7, 99, 12345, 555, 20250101, 31337, 424242, 8675309, 2718281]:
    nf = 0
    hitters = []
    for off, sch in enumerate(S.keys()):
        nulls, K = mc_run(sch, base + off)
        for lv in LEVELS:
            hits, p, sd, z = summarise(OBS_PP[lv], nulls[lv])
            if hits == 0:
                nf += 1
            else:
                hitters.append(f"{sch}/{lv.split('/')[-1]}({hits})")
    floor_counts.append(nf)
    print(f"{base:>12}{nf:>28}   {', '.join(hitters) if hitters else '-'}")
print(f"\nfloor-count across 10 seed triples: min={min(floor_counts)} "
      f"max={max(floor_counts)} mean={sum(floor_counts)/len(floor_counts):.1f}")

# ---------------------------------------------------------------------------
# (d) EXACT sign-flip null by integer convolution (no sampling, no floor)
# ---------------------------------------------------------------------------
def exact_signflip(Ds):
    Ds = [abs(d) for d in Ds if d != 0]
    K = len(Ds); M = sum(Ds)
    dist = [0] * (2 * M + 1); dist[M] = 1
    for d in Ds:
        nd = [0] * (2 * M + 1)
        for i, c in enumerate(dist):
            if c:
                nd[i + d] += c; nd[i - d] += c
        dist = nd
    return dist, M, K

def exact_stats(Ds, t_obs, n_cells):
    dist, M, K = exact_signflip(Ds)
    a = abs(t_obs)
    hits = sum(c for i, c in enumerate(dist) if abs(i - M) >= a)
    p = Fraction(hits, 1 << K)
    tot = 1 << K
    mean = sum(c * (i - M) for i, c in enumerate(dist)) / tot
    var = sum(c * ((i - M) - mean) ** 2 for i, c in enumerate(dist)) / tot
    sd_pp = (var ** 0.5) * 100.0 / n_cells
    obs_pp = 100.0 * t_obs / n_cells
    z = (obs_pp - mean * 100.0 / n_cells) / sd_pp if sd_pp > 0 else float("nan")
    return float(p), K, sd_pp, z

print()
print("=" * 100)
print("3. EXACT SIGN-FLIP NULL (full enumeration by convolution) vs the MC RUN")
print("=" * 100)
print(f"{'scheme':<12}{'level':<26}{'K':>6}{'p_exact':>13}{'sd_exact':>10}"
      f"{'sd_MC':>10}{'sd err%':>9}{'z_exact':>9}{'z_MC':>8}{'E[hits]@20k':>13}")
exact = {}
for sch in S:
    exact[sch] = {}
    for lv in LEVELS:
        p, K, sd, z = exact_stats(S[sch][lv], T_OBS[lv], N[lv])
        exact[sch][lv] = (p, K, sd, z)
        sdmc = mc_sd[sch][lv]
        zmc = mc_claimed[sch][lv][3]
        print(f"{sch:<12}{lv:<26}{K:>6}{p:>13.3e}{sd:>10.3f}{sdmc:>10.3f}"
              f"{100*(sdmc-sd)/sd:>9.2f}{z:>9.2f}{zmc:>8.2f}{p*NPERM:>13.2e}")

# ---------------------------------------------------------------------------
# (e) Does the MC run separate the schemes? Design-effect scale.
# ---------------------------------------------------------------------------
print()
print("=" * 100)
print("4. SCHEME SEPARATION ON THE SCALE THE MC RUN *CAN* RESOLVE")
print("=" * 100)
print(f"{'level':<26}{'sdMC S1':>9}{'sdMC S2':>9}{'sdMC S3':>9}"
      f"{'S2/S1':>8}{'S3/S1':>8}{'DEFF S3/S1':>12}{'zMC S1':>9}{'zMC S2':>9}{'zMC S3':>9}")
for lv in LEVELS:
    a, b, c = (mc_sd[s][lv] for s in S)
    z1, z2, z3 = (mc_claimed[s][lv][3] for s in S)
    print(f"{lv:<26}{a:>9.3f}{b:>9.3f}{c:>9.3f}{b/a:>8.3f}{c/a:>8.3f}"
          f"{(c/a)**2:>12.3f}{z1:>9.2f}{z2:>9.2f}{z3:>9.2f}")
print()
print("exact counterpart of the same ratios (ground truth):")
print(f"{'level':<26}{'sdEX S1':>9}{'sdEX S2':>9}{'sdEX S3':>9}{'S2/S1':>8}{'S3/S1':>8}")
for lv in LEVELS:
    a, b, c = (exact[s][lv][2] for s in S)
    print(f"{lv:<26}{a:>9.3f}{b:>9.3f}{c:>9.3f}{b/a:>8.3f}{c/a:>8.3f}")

# ---------------------------------------------------------------------------
# (f) How many of the 15 "combinations" are distinct tests?
# ---------------------------------------------------------------------------
print()
print("=" * 100)
print("5. HOW MANY OF THE 15 COMBINATIONS ARE DISTINCT RANDOMISATION TESTS?")
print("=" * 100)
sig = {}
for sch in S:
    for lv in LEVELS:
        key = tuple(sorted(abs(d) for d in S[sch][lv] if d != 0))
        sig.setdefault(key, []).append(f"{sch}/{lv.split('/')[-1]}")
dup = [v for v in sig.values() if len(v) > 1]
print(f"distinct null distributions among the 15 combinations: {len(sig)}")
for v in sig.values():
    if len(v) > 1:
        print(f"  IDENTICAL test: {v}")
print("\n(For a single model each item contributes exactly one cell, so the "
      "item-level\n flip and the cell-level flip are literally the same "
      "randomisation distribution.)")

# ---------------------------------------------------------------------------
# (g) What B would be needed for MC to resolve the smallest exact p?
# ---------------------------------------------------------------------------
print()
print("=" * 100)
print("6. B REQUIRED FOR MC TO RESOLVE EACH EXACT p (need 1/(B+1) < p)")
print("=" * 100)
print(f"{'scheme':<12}{'level':<26}{'p_exact':>13}{'B needed (~1/p)':>18}")
for sch in S:
    for lv in LEVELS:
        p = exact[sch][lv][0]
        print(f"{sch:<12}{lv:<26}{p:>13.3e}{1.0/p:>18.3e}")

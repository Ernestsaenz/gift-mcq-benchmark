#!/usr/bin/env python3
"""
prim_refute_permutation_seedcheck.py -- is the '14 of 15 / the 15th is gemini
cell-level' split a structural fact, or an artifact of one RNG consumption order?

prim_permutation.py's S1 draws bits MODEL-BY-MODEL inside one RNG stream:
    for m in models: bits = rng.getrandbits(nd_m)
My prim_refute_permutation_floor.py draws all 292 discordant-cell bits in ONE
getrandbits call. Both are valid sign-flip Monte Carlos with the SAME null; they
just consume the stream differently. Compare.
"""
import json, random
from collections import defaultdict

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")
NPERM, SEED = 20000, 20260731
with open(DATA) as fh:
    rows = [r for r in json.load(fh) if r["analysis_include"] is True]
models = sorted({r["model"] for r in rows})
by_model = defaultdict(list)
for r in rows:
    r["_d"] = r["A_correct"] - r["B_correct"]
    by_model[r["model"]].append(r)
N = {m: len(by_model[m]) for m in models}; N["POOLED"] = len(rows)
LEVELS = models + ["POOLED"]
OBS = {m: sum(r["_d"] for r in by_model[m]) / N[m] for m in models}
OBS["POOLED"] = sum(r["_d"] for r in rows) / N["POOLED"]
ND = {m: sum(1 for r in by_model[m] if r["_d"] != 0) for m in models}

def s1_hits(seed, order):
    rng = random.Random(seed)
    hits = {lv: 0 for lv in LEVELS}
    for _ in range(NPERM):
        tot = 0
        for m in order:
            nd = ND[m]
            k = rng.getrandbits(nd).bit_count() if nd else 0
            ssum = 2 * k - nd
            if abs(ssum / N[m]) >= abs(OBS[m]) - 1e-12:
                hits[m] += 1
            tot += ssum
        if abs(tot / N["POOLED"]) >= abs(OBS["POOLED"]) - 1e-12:
            hits["POOLED"] += 1
    return hits

print("prim_permutation.py's exact S1 RNG order (models sorted), seed", SEED)
h = s1_hits(SEED, models)
for lv in LEVELS:
    print(f"  {lv:<26} hits={h[lv]}  p=({1+h[lv]})/{NPERM+1} = {(1+h[lv])/(NPERM+1):.4e}")

print("\nSame seed, models drawn in REVERSE order (equally valid MC):")
h2 = s1_hits(SEED, list(reversed(models)))
for lv in LEVELS:
    print(f"  {lv:<26} hits={h2[lv]}  p={(1+h2[lv])/(NPERM+1):.4e}")

print("\nHow often does gemini/S1 get >=1 hit? exact p=3.4655e-06, B=20000")
p_ex = 3.4654513001441956e-06
print(f"  P(>=1 hit) = 1-(1-p)^B = {1-(1-p_ex)**NPERM:.4f}")
p_ex3 = 1.5100464224815369e-05   # S3 cluster / gemini -- the LARGEST exact p
print(f"  S3/gemini (largest exact p = {p_ex3:.4e}): P(>=1 hit) = "
      f"{1-(1-p_ex3)**NPERM:.4f}  <-- structurally the most likely hitter")
print("\n50 seeds, S1 model-by-model order: how many give gemini >=1 hit?")
c = sum(1 for s in range(1000, 1050) if s1_hits(s, models)["google/gemini-3.6-flash"] > 0)
print(f"  {c}/50 seeds")

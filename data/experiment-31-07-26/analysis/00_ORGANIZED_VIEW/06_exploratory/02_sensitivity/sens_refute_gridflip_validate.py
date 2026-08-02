#!/usr/bin/env python3
"""
sens_refute_gridflip_validate.py -- validate the exact sign-flip DP before relying on it.

V1  DP normalisation: the null distribution must sum to 1.
V2  DP vs brute-force enumeration on a small synthetic cluster set (all 2^k flips).
V3  DP vs 4,000,000-replicate Monte Carlo on the two weakest real cells
    (gemini S3 / S4), where the claimed p was 1.0e-04 and the DP says 1.51e-05.
    At p=1.51e-05 a 4e6-rep sampler expects ~60 hits, so MC can resolve it;
    a 20000-rep sampler expects 0.3 hits and cannot.
V4  bootstrap CI seed-stability for the binding cell (gemini S3) over 5 seeds.
"""
import json, os, math, random
from collections import defaultdict
from itertools import product

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = json.load(open(os.path.join(HERE, "paired_clean.json")))


def cluster_stats(cells):
    g = defaultdict(lambda: [0, 0])
    for r in cells:
        e = g[r["cluster"]]
        e[0] += 1
        e[1] += r["B_correct"] - r["A_correct"]
    return [tuple(v) for v in g.values()]


def exact_signflip(cs, want_mass=False):
    N = sum(n for n, _ in cs)
    Tobs = abs(sum(s for _, s in cs))
    nz = [abs(s) for _, s in cs if s != 0]
    if not nz:
        return (1.0, 1.0) if want_mass else 1.0
    span = sum(nz)
    dist = [0.0] * (2 * span + 1)
    dist[span] = 1.0
    lo = hi = span
    for a in nz:
        nd = [0.0] * (2 * span + 1)
        for i in range(lo, hi + 1):
            p = dist[i]
            if p:
                nd[i - a] += 0.5 * p
                nd[i + a] += 0.5 * p
        dist = nd; lo -= a; hi += a
    tail = sum(dist[i] for i in range(lo, hi + 1) if abs(i - span) >= Tobs)
    mass = sum(dist)
    return (min(1.0, tail), mass) if want_mass else min(1.0, tail)


print("V1  DP normalisation on all 20 real grid cells")
FIL = {"S1_none": lambda r: True,
       "S2_drop_defect": lambda r: not r["excl_item_defect"],
       "S3_drop_posA": lambda r: not r["excl_nota_position_a"],
       "S4_drop_both": lambda r: r["analysis_include"]}
worst = 0.0
for m in [None] + sorted(set(r["model"] for r in ROWS)):
    for sid, f in FIL.items():
        cs = cluster_stats([r for r in ROWS if f(r) and (m is None or r["model"] == m)])
        _, mass = exact_signflip(cs, want_mass=True)
        worst = max(worst, abs(mass - 1.0))
print("    max |sum(dist) - 1| across the grid =", f"{worst:.3e}", "(machine precision -> DP is normalised)")

print("\nV2  DP vs brute-force enumeration of all 2^k sign flips, synthetic sets")
rng = random.Random(11)
bad = 0
for trial in range(6):
    k = rng.randrange(6, 13)
    cs = [(rng.randrange(1, 5), rng.randrange(-3, 4)) for _ in range(k)]
    N = sum(n for n, _ in cs)
    Tobs = abs(sum(s for _, s in cs))
    S = [s for _, s in cs]
    hits = sum(1 for eps in product((-1, 1), repeat=k)
               if abs(sum(e * s for e, s in zip(eps, S))) >= Tobs)
    brute = hits / (2 ** k)
    dp = exact_signflip(cs)
    ok = abs(brute - dp) < 1e-12
    bad += (not ok)
    print(f"    k={k:>2}  brute={brute:.12f}  dp={dp:.12f}  match={ok}")
print("    mismatches:", bad)

print("\nV3  DP vs 4,000,000-rep Monte Carlo on the binding cells")
for sid in ("S3_drop_posA", "S4_drop_both"):
    cells = [r for r in ROWS if FIL[sid](r) and r["model"] == "google/gemini-3.6-flash"]
    cs = cluster_stats(cells)
    N = sum(n for n, _ in cs)
    Tobs = abs(sum(s for _, s in cs))
    nz = [s for _, s in cs if s != 0]
    dp = exact_signflip(cs)
    g = random.Random(4242)
    REPS = 4_000_000
    hits = 0
    for _ in range(REPS):
        t = 0
        for s in nz:
            t += s if g.getrandbits(1) else -s
        if abs(t) >= Tobs:
            hits += 1
    mc = hits / REPS
    se = math.sqrt(max(mc, 1 / REPS) * (1 - mc) / REPS)
    print(f"    gemini {sid:<15} DP={dp:.3e}   MC({REPS:,})={mc:.3e}  hits={hits}  MC 95% CI=[{max(0,mc-1.96*se):.3e},{mc+1.96*se:.3e}]")
    print(f"      -> at 20000 reps the expected hit count is {dp*20000:.2f}; the claim's 'p=0.00010' is 1 hit of 20000 = noise")

print("\nV4  percentile-bootstrap seed stability, gemini S3 (the CI nearest zero)")
cells = [r for r in ROWS if FIL["S3_drop_posA"](r) and r["model"] == "google/gemini-3.6-flash"]
cs = cluster_stats(cells)
C = len(cs)


def pct(v, q):
    i = q * (len(v) - 1); a, b = int(math.floor(i)), int(math.ceil(i))
    return v[a] if a == b else v[a] + (v[b] - v[a]) * (i - a)


for sd in (1, 2, 3, 4, 5):
    g = random.Random(sd)
    out = []
    for _ in range(20000):
        n = s = 0
        for _ in range(C):
            gn, gs = cs[g.randrange(C)]
            n += gn; s += gs
        out.append(s / n)
    out.sort()
    print(f"    seed={sd}  95% CI = [{pct(out,0.025):+.4f}, {pct(out,0.975):+.4f}]   excludes 0: {pct(out,0.975) < 0}")

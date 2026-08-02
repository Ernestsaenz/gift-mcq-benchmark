#!/usr/bin/env python3
"""
stats_refute_multiplicity2.py -- validation of the exact sign-flip DP plus
sizing of the REAL hypothesis-test family on disk.
"""
import json, os, math, collections, random, itertools, re, glob
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
recs = [r for r in json.load(open(os.path.join(HERE, "paired_clean.json")))
        if r["analysis_include"]]
MODELS = sorted({r["model"] for r in recs})
by_model = {m: [r for r in recs if r["model"] == m] for m in MODELS}

def cluster_sums(m):
    cl = collections.defaultdict(int)
    for r in by_model[m]:
        cl[r["cluster"]] += r["A_correct"] - r["B_correct"]
    return list(cl.values())

def dp_exact(S):
    Tobs = sum(S)
    nz = [abs(v) for v in S if v != 0]
    dist = {0: 1}
    for v in nz:
        nd = collections.defaultdict(int)
        for t, w in dist.items():
            nd[t + v] += w
            nd[t - v] += w
        dist = nd
    ge = sum(w for t, w in dist.items() if abs(t) >= abs(Tobs))
    return Fraction(ge, 2 ** len(nz)), Tobs, nz

# --- A. validate DP against brute force on a small subproblem
print("A. DP validated against exhaustive enumeration on a 16-cluster subset")
rng = random.Random(1)
Ssmall = [rng.choice([-2, -1, 1, 1, 2, 3]) for _ in range(16)]
p_dp, Tobs, nz = dp_exact(Ssmall)
brute = 0
for signs in itertools.product([1, -1], repeat=len(nz)):
    if abs(sum(s * v for s, v in zip(signs, nz))) >= abs(Tobs):
        brute += 1
p_brute = Fraction(brute, 2 ** len(nz))
print(f"   S={Ssmall}  T_obs={Tobs}")
print(f"   DP p={p_dp}   brute p={p_brute}   match={p_dp == p_brute}")
print()

# --- B. validate DP against a large Monte Carlo for the binding model
print("B. DP validated against 5,000,000-draw Monte Carlo (gemini, the binding model)")
m = "google/gemini-3.6-flash"
S = cluster_sums(m)
p_dp, Tobs, nz = dp_exact(S)
print(f"   nonzero clusters={len(nz)}  sum|S_k|={sum(nz)}  T_obs={Tobs}")
print(f"   |S_k| multiset: {sorted(collections.Counter(nz).items())}")
rng = random.Random(99)
NB = 5_000_000
hits = 0
for _ in range(NB):
    t = 0
    for v in nz:
        t += v if rng.random() < 0.5 else -v
    if abs(t) >= abs(Tobs):
        hits += 1
mc = hits / NB
se = math.sqrt(max(mc, 1e-12) * (1 - mc) / NB)
print(f"   DP exact p = {float(p_dp):.6e}")
print(f"   MC p       = {mc:.6e}  (hits={hits}, +-1.96SE = [{mc-1.96*se:.3e}, {mc+1.96*se:.3e}])")
print(f"   DP inside MC 95% band: {mc-1.96*se <= float(p_dp) <= mc+1.96*se}")
print()

# --- C. how many hypothesis tests does the programme on disk ACTUALLY contain?
print("C. size of the real test family on disk (p-values actually emitted)")
pat_json = re.compile(r'"(p|p_?raw|p_?exact|p_?value|p_?perm|p_?adj|pval|'
                      r'p_?holm|p_?bh|p_?two|p_?boot|p_?chi|p_?z)"\s*:', re.I)
pat_txt = re.compile(r'\bp\s*=\s*[\d.]+e?-?\d*|\bp_exact\b|\bp_raw\b', re.I)
total_json = 0
for f in sorted(glob.glob(os.path.join(HERE, "*.json"))):
    if os.path.basename(f) in ("paired_clean.json", "dataset_meta.json"):
        continue
    txt = open(f).read()
    n = len(pat_json.findall(txt))
    if n:
        print(f"   {os.path.basename(f):46s} p-value keys: {n:5d}")
        total_json += n
total_txt = 0
for f in sorted(glob.glob(os.path.join(HERE, "*.txt"))):
    txt = open(f).read()
    n = len(pat_txt.findall(txt))
    if n:
        print(f"   {os.path.basename(f):46s} p= mentions : {n:5d}")
        total_txt += n
print(f"   ---- p-values found in *existing* output artifacts only: "
      f"{total_json + total_txt}")
print(f"   ---- analysis scripts on disk: "
      f"{len(glob.glob(os.path.join(HERE, '*.py')))} "
      f"(most have not written their output yet)")
print()

# --- D. what does the answer look like if the family is much bigger?
print("D. break-even: largest Bonferroni family each primary test survives")
prim_p = {"z-ai/glm-5.2": 1.009864e-12, "google/gemma-4-26b-a4b-it": 6.147807e-11,
          "qwen/qwen3.6-35b-a3b": 5.257317e-09, "google/gemini-3.6-flash": 3.465451e-06}
for mm in MODELS:
    pdp, T, nzz = dp_exact(cluster_sums(mm))
    print(f"   {mm:28s} McNemar m*={int(0.05/prim_p[mm]):>14,}   "
          f"cluster-exact m*={int(0.05/float(pdp)):>14,}   "
          f"inflation factor McNemar->cluster = {float(pdp)/prim_p[mm]:8.1f}x")

#!/usr/bin/env python3
"""
stats_refute_multiplicity3.py -- (i) design effect of the cluster nesting on
the primary McNemar tests, (ii) a defensible LOWER BOUND on the real size of
the hypothesis-test family on disk (raw p-values only, adjusted ones excluded).
"""
import json, os, math, collections, glob, re
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
recs = [r for r in json.load(open(os.path.join(HERE, "paired_clean.json")))
        if r["analysis_include"]]
MODELS = sorted({r["model"] for r in recs})
by_model = {m: [r for r in recs if r["model"] == m] for m in MODELS}

print("cluster structure of the analysis set")
sizes = collections.Counter()
cl_items = collections.defaultdict(set)
for r in recs:
    cl_items[r["cluster"]].add(r["question_id"])
for k, v in cl_items.items():
    sizes[len(v)] += 1
print("  items-per-cluster distribution:", dict(sorted(sizes.items())))
print(f"  clusters with >1 item: {sum(v for k,v in sizes.items() if k>1)} / {len(cl_items)}")
print(f"  items in multi-item clusters: "
      f"{sum(k*v for k,v in sizes.items() if k>1)} / {sum(k*v for k,v in sizes.items())}")
print()

print("DESIGN EFFECT of the nesting on each primary McNemar test")
print("  McNemar conditions on b+c discordant pairs and uses Var(b-c)=b+c.")
print("  The cluster sign-flip null has Var(T)=sum_k S_k^2 with S_k the cluster")
print("  net (A-B).  deff = sum_k S_k^2 / (b+c).  deff>1 => McNemar too small.")
print()
print(f"{'model':28s} {'b':>4s} {'c':>4s} {'b+c':>5s} {'T=b-c':>6s} "
      f"{'sumSk^2':>8s} {'deff':>6s} {'z_mcn':>7s} {'z_clu':>7s}")
rows_out = {}
for m in MODELS:
    rows = by_model[m]
    b = sum(1 for r in rows if r["A_correct"] == 1 and r["B_correct"] == 0)
    c = sum(1 for r in rows if r["A_correct"] == 0 and r["B_correct"] == 1)
    cl = collections.defaultdict(int)
    for r in rows:
        cl[r["cluster"]] += r["A_correct"] - r["B_correct"]
    S = list(cl.values())
    T = sum(S)
    ss = sum(v * v for v in S)
    deff = ss / (b + c)
    z_mcn = T / math.sqrt(b + c)
    z_clu = T / math.sqrt(ss)
    rows_out[m] = (b, c, T, ss, deff, z_mcn, z_clu)
    print(f"{m:28s} {b:4d} {c:4d} {b+c:5d} {T:6d} {ss:8d} {deff:6.3f} "
          f"{z_mcn:7.3f} {z_clu:7.3f}")
print()

# exact permutation p again (DP) for the summary table
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
    return Fraction(ge, 2 ** len(nz))

def mcnemar_exact(b, c):
    n = b + c
    lo = sum(math.comb(n, k) for k in range(0, min(b, c) + 1))
    return min(1.0, 2.0 * lo / 2 ** n)

print("HEADLINE vs NESTING-ROBUST, and what each survives")
print(f"{'model':28s} {'McNemar p':>13s} {'clusterExact p':>15s} "
      f"{'ratio':>9s} {'x160 (McN)':>11s} {'x160 (clu)':>11s} {'m* clu':>14s}")
for m in MODELS:
    b, c, T, ss, deff, zm, zc = rows_out[m]
    cl = collections.defaultdict(int)
    for r in by_model[m]:
        cl[r["cluster"]] += r["A_correct"] - r["B_correct"]
    pmc = mcnemar_exact(b, c)
    pcl = float(dp_exact(list(cl.values())))
    print(f"{m:28s} {pmc:13.6e} {pcl:15.6e} {pcl/pmc:9.1f}x "
          f"{pmc*160:11.4e} {pcl*160:11.4e} {int(0.05/pcl):>14,}")
print()

# ---- real family size, strict lower bound: RAW p-values only
print("REAL family size on disk -- strict count, raw p-values only "
      "(adjusted/holm/bh/bonf keys excluded)")
raw_key = re.compile(r'"(p|p_raw|p_exact|p_value|pval|p_two_sided|p_perm|'
                     r'p_boot|p_mcnemar|p_chi|p_z|pvalue)"\s*:', re.I)
adj_key = re.compile(r'holm|bh_|_bh|bonf|adj', re.I)
total = 0
per_file = []
for f in sorted(glob.glob(os.path.join(HERE, "*.json"))):
    base = os.path.basename(f)
    if base in ("paired_clean.json", "dataset_meta.json"):
        continue
    txt = open(f).read()
    n = 0
    for mobj in raw_key.finditer(txt):
        ctx = txt[max(0, mobj.start() - 40):mobj.end()]
        if not adj_key.search(ctx.split('"')[-3] if '"' in ctx else ""):
            n += 1
    if n:
        per_file.append((base, n))
        total += n
for base, n in per_file:
    print(f"   {base:46s} {n:5d}")
print(f"   ---- raw p-values in written artifacts: {total}")
print(f"   ---- analysis scripts present: "
      f"{len(glob.glob(os.path.join(HERE,'*.py')))}; "
      f"written output artifacts: "
      f"{len([f for f in glob.glob(os.path.join(HERE,'*.json')) ])} json + "
      f"{len(glob.glob(os.path.join(HERE,'*.txt')))} txt")
print()
print("Bonferroni over the STRICT on-disk family instead of the claimed 160:")
for m in MODELS:
    b, c, T, ss, deff, zm, zc = rows_out[m]
    cl = collections.defaultdict(int)
    for r in by_model[m]:
        cl[r["cluster"]] += r["A_correct"] - r["B_correct"]
    pmc = mcnemar_exact(b, c)
    pcl = float(dp_exact(list(cl.values())))
    print(f"   {m:28s} McNemar p*{total} = {pmc*total:.4e}   "
          f"clusterExact p*{total} = {pcl*total:.4e}   "
          f"both<.05: {pmc*total < .05 and pcl*total < .05}")

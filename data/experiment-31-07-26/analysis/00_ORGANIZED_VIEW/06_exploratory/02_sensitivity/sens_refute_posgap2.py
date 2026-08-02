#!/usr/bin/env python3
"""
Adversarial stress tests on the 'position-artifact' gap-decomposition claim.
Standard library only. Every p-value / interval states its method inline.
"""
import json, os, random
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(BASE, "paired_clean.json")))

FULL = rows
NO_DEF = [r for r in rows if not r["excl_item_defect"]]
NO_POSA = [r for r in rows if not r["excl_nota_position_a"]]
PUB = [r for r in rows if r["analysis_include"]]
SETS = [("FULL", FULL), ("noDEF", NO_DEF), ("noPOSA", NO_POSA), ("PUBLISHED", PUB)]

def cellmean(sub):
    return 100.0 * sum(r["B_correct"] - r["A_correct"] for r in sub) / len(sub)

def groupmean(sub, key):
    """unweighted mean over groups of the within-group mean d (item- or cluster-weighted estimand)"""
    g = defaultdict(list)
    for r in sub:
        g[key(r)].append(r["B_correct"] - r["A_correct"])
    per = [100.0 * sum(v) / len(v) for v in g.values()]
    return sum(per) / len(per), len(per)

print("=" * 104)
print("TEST A -- is the '~1/10 shrink' specific to the cell-weighted estimand?")
print("=" * 104)
print(f"{'estimand':<28}" + "".join(f"{n:>13}" for n, _ in SETS) + f"{'gap':>10}{'gap/|full|':>12}")
ests = [
    ("cell-weighted (claim)", lambda s: cellmean(s)),
    ("item-weighted", lambda s: groupmean(s, lambda r: r["question_id"])[0]),
    ("cluster-weighted", lambda s: groupmean(s, lambda r: r["cluster"])[0]),
    ("model-weighted", lambda s: groupmean(s, lambda r: r["model"])[0]),
]
for nm, f in ests:
    vals = [f(s) for _, s in SETS]
    gap = vals[3] - vals[0]
    print(f"{nm:<28}" + "".join(f"{v:13.4f}" for v in vals) + f"{gap:10.4f}{100*gap/abs(vals[0]):11.2f}%")

print()
print("=" * 104)
print("TEST B -- per-model: does any model's effect move qualitatively?")
print("=" * 104)
models = sorted({r["model"] for r in rows})
print(f"{'model':<28}" + "".join(f"{n:>13}" for n, _ in SETS) + f"{'gap':>10}{'gap/|full|':>12}")
for m in models:
    vals = [cellmean([r for r in s if r["model"] == m]) for _, s in SETS]
    gap = vals[3] - vals[0]
    print(f"{m:<28}" + "".join(f"{v:13.4f}" for v in vals) + f"{gap:10.4f}{100*gap/abs(vals[0]):11.2f}%")
# rank stability
for nm, s in SETS:
    order = sorted(models, key=lambda m: cellmean([r for r in s if r["model"] == m]))
    print(f"  rank (most->least degraded) {nm:<10}: " + " > ".join(x.split('/')[-1] for x in order))

print()
print("=" * 104)
print("TEST C -- cluster bootstrap on the GAP itself")
print("  method: nonparametric bootstrap resampling CLUSTERS with replacement (B=20000,")
print("          seed 20260731); in each replicate recompute delta on FULL and on the")
print("          analysis_include subset of the SAME resampled clusters, take the")
print("          difference; percentile interval. Clusters are the unit of dependence.")
print("=" * 104)
byclus = defaultdict(list)
for r in rows:
    byclus[r["cluster"]].append(r)
keys = sorted(byclus)
K = len(keys)
rng = random.Random(20260731)
B = 20000
obs_gap = cellmean(PUB) - cellmean(FULL)
reps, degen = [], 0
for _ in range(B):
    pick = [byclus[keys[rng.randrange(K)]] for _ in range(K)]
    sf = sd = nf = np_ = 0
    for cl in pick:
        for r in cl:
            d = r["B_correct"] - r["A_correct"]
            sf += d; nf += 1
            if r["analysis_include"]:
                sd += d; np_ += 1
    if np_ == 0:
        degen += 1
        continue
    reps.append(100.0 * sd / np_ - 100.0 * sf / nf)
reps.sort()
def q(p):
    i = p * (len(reps) - 1)
    lo = int(i); hi = min(lo + 1, len(reps) - 1)
    return reps[lo] + (i - lo) * (reps[hi] - reps[lo])
mean = sum(reps) / len(reps)
se = (sum((x - mean) ** 2 for x in reps) / (len(reps) - 1)) ** 0.5
print(f"  observed gap = {obs_gap:.4f} pp")
print(f"  boot mean={mean:.4f}  SE={se:.4f}  95% pct CI = [{q(0.025):.4f}, {q(0.975):.4f}]  (degenerate reps dropped: {degen})")
frac = [100.0 * r_ / abs(cellmean(FULL)) for r_ in reps]
print(f"  gap as % of |delta_full|: point={100*obs_gap/abs(cellmean(FULL)):.2f}%  "
      f"boot 95% CI = [{sorted(frac)[int(0.025*(len(frac)-1))]:.2f}%, {sorted(frac)[int(0.975*(len(frac)-1))]:.2f}%]")
print(f"  P(gap > 25% of |delta_full|) under cluster boot = {sum(1 for x in frac if x > 25)/len(frac):.4f}")

print()
print("=" * 104)
print("TEST D -- premise audit: is 'FULL unfiltered' actually unfiltered?")
print("=" * 104)
meta = json.load(open(os.path.join(BASE, "dataset_meta.json")))
named = meta["exclusions"]["administrative_legal_out_of_domain"] + meta["exclusions"]["adjudicated_key_defect"]
present = {r["question_id"] for r in rows}
absent = [q_ for q_ in named if q_ not in present]
print(f"  defect items named in meta: {len(named)}   present in paired_clean.json: {len(named)-len(absent)}   ABSENT: {absent}")
print(f"  cells in file: {len(rows)}; items x models if complete = {len(present)*4} -> {len(present)*4-len(rows)} cell(s) already gone (unparsed rule)")
defect_cells = [r for r in rows if r["excl_item_defect"]]
d_def = cellmean(defect_cells)
print(f"  observed defect-cell delta = {d_def:.4f} pp over n={len(defect_cells)}")
print("  counterfactual: restore the 3 absent defect items at 4 cells each, imputed at the")
print("  observed defect-cell delta, and recompute the 'truly full' baseline:")
nF, dF = len(FULL), cellmean(FULL)
for lab, imp in (("defect-cell rate", d_def), ("all-dropped rate", cellmean([r for r in rows if not r["analysis_include"]])), ("-100 pp worst case", -100.0)):
    nF2 = nF + 12
    dF2 = (dF * nF + imp * 12) / nF2
    g2 = cellmean(PUB) - dF2
    print(f"    impute d={imp:8.3f} -> delta_full'={dF2:9.4f}  gap'={g2:7.4f} pp  ({100*g2/abs(dF2):5.2f}% of |full'|)"
          f"  defect-step'={g2-(cellmean(NO_POSA)-dF2)+(cellmean(NO_POSA)-dF2)-(cellmean(NO_POSA)-dF2):.4f}" if False else
          f"    impute d={imp:8.3f} -> delta_full'={dF2:9.4f}  gap'={g2:7.4f} pp  ({100*g2/abs(dF2):5.2f}% of |full'|)")

print()
print("=" * 104)
print("TEST E -- gap vs the published estimator's own uncertainty")
print("=" * 104)
pub = json.load(open(os.path.join(BASE, "prim_cluster_bootstrap_results.json")))
se_pub = pub["cluster_boot"]["pooled"]["se"]
print(f"  published pooled obs = {pub['observed']['pooled']:.4f} (matches recompute: {abs(pub['observed']['pooled']-cellmean(PUB))<1e-9})")
print(f"  published cluster-boot SE = {se_pub:.4f} pp ; 95% CI [{pub['cluster_boot']['pooled']['lo']:.3f}, {pub['cluster_boot']['pooled']['hi']:.3f}]")
print(f"  gap / SE_published = {obs_gap/se_pub:.3f}")
print(f"  is delta_full inside the published 95% CI? {pub['cluster_boot']['pooled']['lo'] <= dF <= pub['cluster_boot']['pooled']['hi']}")

print()
print("=" * 104)
print("TEST F -- order-robustness of the 1.58 / 0.20 split")
print("=" * 104)
dP, dD, dB = cellmean(NO_POSA), cellmean(NO_DEF), cellmean(PUB)
p1a, p1b = dP - dF, dB - dP
p2a, p2b = dD - dF, dB - dD
print(f"  posa share of gap, path1={100*p1a/(dB-dF):.1f}%  path2={100*p2b/(dB-dF):.1f}%  shapley={100*0.5*(p1a+p2b)/(dB-dF):.1f}%")
print(f"  claim states 1.58 / 0.20; ordering ambiguity spans posa in [{min(p1a,p2b):.4f},{max(p1a,p2b):.4f}] pp")

#!/usr/bin/env python3
"""
stats_refute_subgroup_dependence.py

Follow-ups the multiplicity-and-ceiling section did not run:
  (a) BH assumes PRDS.  These 100 tests are 5 re-partitions of ONE dataset,
      crossed with 4 models that answered the SAME items.  Under arbitrary
      dependence the valid FDR procedure is Benjamini-Yekutieli.  Recompute.
  (b) permutation-calibrated null for "how many nominal hits would multiplicity
      alone produce here", using the actual dependence structure (cluster-level
      sign flips) rather than the independence assumption.
  (c) composition of the region / year strata -- what the dossier would lose.
"""

import json, math, os, collections, random

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "paired_clean.json")
SEED = 20260731
NPERM = 5000

def mcnemar_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    lo = sum(math.comb(n, k) for k in range(0, b + 1)) / 2 ** n
    hi = sum(math.comb(n, k) for k in range(b, n + 1)) / 2 ** n
    return min(1.0, 2.0 * min(lo, hi))

def bh_adj(pv):
    idx = sorted(range(len(pv)), key=lambda i: pv[i]); m = len(pv)
    res = [None]*m; run = 1.0
    for r in range(m-1, -1, -1):
        i = idx[r]; run = min(run, min(1.0, pv[i]*m/(r+1))); res[i] = run
    return res

def by_adj(pv):
    """Benjamini-Yekutieli: BH with the harmonic-sum penalty c(m)=sum_{i=1}^m 1/i.
    Valid under ARBITRARY dependence between the tests."""
    m = len(pv)
    cm = sum(1.0/i for i in range(1, m+1))
    idx = sorted(range(m), key=lambda i: pv[i])
    res = [None]*m; run = 1.0
    for r in range(m-1, -1, -1):
        i = idx[r]; run = min(run, min(1.0, pv[i]*m*cm/(r+1))); res[i] = run
    return res

recs = [r for r in json.load(open(DATA)) if r["analysis_include"]]
MODELS = sorted({r["model"] for r in recs})
by_model = {m: [r for r in recs if r["model"] == m] for m in MODELS}

FACTORS = {
    "correct_letter": lambda r: r["correct_letter"],
    "negated_stem":   lambda r: r["negated_stem"],
    "has_context":    lambda r: r["has_context"],
    "region":         lambda r: r["region"],
    "year":           lambda r: r["year"],
}
levels = {f: sorted({str(g(r)) for r in recs}) for f, g in FACTORS.items()}

out = []
def P(s=""):
    out.append(s); print(s)

# ---- build the 100 cells, keeping the row lists so we can permute them
cells = []
for f, g in FACTORS.items():
    for lev in levels[f]:
        for m in MODELS:
            rows = [r for r in by_model[m] if str(g(r)) == lev]
            if not rows:
                continue
            b = sum(1 for r in rows if r["A_correct"] == 1 and r["B_correct"] == 0)
            c = sum(1 for r in rows if r["A_correct"] == 0 and r["B_correct"] == 1)
            cells.append(dict(factor=f, level=lev, model=m, rows=rows, n=len(rows),
                              b=b, c=c, p=mcnemar_p(b, c)))

pv = [x["p"] for x in cells]
BHa, BYa = bh_adj(pv), by_adj(pv)
m = len(pv)
cm = sum(1.0/i for i in range(1, m+1))

P("=" * 78)
P("(a) FDR UNDER DEPENDENCE -- BH vs Benjamini-Yekutieli, m=%d" % m)
P("=" * 78)
P(f"  BH  penalty factor = 1.000        survivors: {sum(1 for a in BHa if a<0.05)}")
P(f"  BY  penalty factor = c(m) = {cm:.3f}   survivors: {sum(1 for a in BYa if a<0.05)}")
P("  The section reports BH only.  BH's FDR guarantee needs positive regression")
P("  dependence; here the 5 factors are complete re-partitions of one dataset and")
P("  the 4 models answered the SAME 325 items, so dependence is not of a form")
P("  that has been checked.  BY is the assumption-free fallback.")
P("")
P("  per-factor survivors: " + "  ".join(
    f"{f}: BH={sum(1 for x,a in zip(cells,BHa) if x['factor']==f and a<0.05)}"
    f"/BY={sum(1 for x,a in zip(cells,BYa) if x['factor']==f and a<0.05)}"
    for f in FACTORS))

# ---- (b) permutation-calibrated null, respecting cluster + crossed structure
P("")
P("=" * 78)
P("(b) HOW MANY NOMINAL HITS DOES MULTIPLICITY ALONE BUY, GIVEN THIS DEPENDENCE?")
P("=" * 78)
P("  Null: A and B are exchangeable within a CLUSTER (flip the A/B labels of a")
P("  whole cluster at once, same flip for all 4 models -> preserves item nesting")
P("  AND the crossed item x model structure).  Recount nominal hits each draw.")
rng = random.Random(SEED)
clusters = sorted({r["cluster"] for r in recs})
cidx = {cl: i for i, cl in enumerate(clusters)}
# precompute per-cell the per-row (A_correct - B_correct) and cluster index
for x in cells:
    x["d"] = [(cidx[r["cluster"]], r["A_correct"] - r["B_correct"]) for r in x["rows"]]

null_hits = []
null_max_bh = []
for _ in range(NPERM):
    flip = [1 if rng.random() < 0.5 else -1 for _ in clusters]
    hits = 0
    for x in cells:
        b = c = 0
        for ci, dv in x["d"]:
            v = flip[ci] * dv
            if v == 1: b += 1
            elif v == -1: c += 1
        if mcnemar_p(b, c) < 0.05:
            hits += 1
    null_hits.append(hits)

null_hits.sort()
def q(v, a):
    k = (len(v)-1)*a; lo, hi = math.floor(k), math.ceil(k)
    return v[lo] if lo == hi else v[lo]*(hi-k)+v[hi]*(k-lo)
obs_hits = sum(1 for p in pv if p < 0.05)
P(f"  observed nominal hits ................ {obs_hits}")
P(f"  null mean nominal hits ............... {sum(null_hits)/len(null_hits):.2f}")
P(f"  null 95th pct ........................ {q(null_hits,0.95):.1f}")
P(f"  null max over {NPERM} draws ............. {null_hits[-1]}")
P(f"  P(null >= {obs_hits}) ......................... "
  f"{(sum(1 for h in null_hits if h>=obs_hits)+1)/(NPERM+1):.5f}")
P("  => even with the full dependence structure, chance multiplicity cannot")
P("     manufacture anything close to 49 hits.")

# ---- (c) what the recommendation would discard
P("")
P("=" * 78)
P("(c) COMPOSITION OF THE STRATA THE RECOMMENDATION WOULD DELETE")
P("=" * 78)
items = {}
for r in recs:
    items[r["question_id"]] = r
NI = len(items)
for f in ("year", "region"):
    g = FACTORS[f]
    cnt = collections.Counter(str(g(r)) for r in items.values())
    P(f"  {f}: {len(cnt)} levels over {NI} items")
    for lev, k in cnt.most_common():
        P(f"    {lev:22s} {k:4d} items  ({100*k/NI:5.1f}%)")
    top = cnt.most_common(1)[0]
    P(f"    -> largest level {top[0]!r} holds {100*top[1]/NI:.1f}% of the corpus")

P("")
P("  Consistency of the A-vs-B sign across these strata (per model), which is")
P("  what a stratum layer is actually FOR:")
for f in ("region", "year"):
    g = FACTORS[f]
    for mo in MODELS:
        pos = neg = zer = 0
        for lev in levels[f]:
            rows = [r for r in by_model[mo] if str(g(r)) == lev]
            if not rows: continue
            d = sum(r["A_correct"]-r["B_correct"] for r in rows)
            if d > 0: pos += 1
            elif d < 0: neg += 1
            else: zer += 1
        nn = pos + neg
        ps = min(1.0, 2*sum(math.comb(nn, i) for i in range(pos, nn+1))/2**nn) if nn else 1.0
        P(f"    {f:7s} {mo.split('/')[-1]:20s} +{pos:3d} / -{neg:2d} / 0:{zer:2d}   "
          f"sign-test p={ps:.4f}")

with open(os.path.join(HERE, "stats_refute_subgroup_dependence_out.txt"), "w") as fh:
    fh.write("\n".join(out) + "\n")

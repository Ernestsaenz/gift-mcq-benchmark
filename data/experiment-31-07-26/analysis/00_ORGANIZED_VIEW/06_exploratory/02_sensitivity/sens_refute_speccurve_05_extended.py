"""Extended specification curve: the published grid PLUS two axes it omits,
both of which are the same *kind* of choice the grid already varies.

  axis E1  position-coherence rule (the grid fixes this at a binary a/not-a):
             keep_all           -- no position rule            (grid: 'none'/'notaA_only')
             drop_a             -- authors' rule               (grid: 'primary'/'defect_only')
             drop_ab            -- plural 'anteriores' needs >=2 antecedents
             drop_abc           -- 'anteriores' must cover every other option (letter d only)
  axis E2  model set (the grid pools all 4 or averages all 4; it never drops one):
             all4, and the 4 leave-one-model-out sets

Everything else (item-defect exclusion, outcome, unit) is held at the published
defaults so the comparison is like-for-like.  p-values: cluster bootstrap
(percentile, clusters resampled with replacement) and exact McNemar.
"""
import json, os, math, random, collections
from math import comb

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "paired_clean.json")))
MODELS = sorted({r["model"] for r in rows})
B_BOOT = 10000
SEED = 4242

POSRULE = {
    "keep_all": set("abcd"),
    "drop_a":   set("bcd"),
    "drop_ab":  set("cd"),
    "drop_abc": set("d"),
}
MODELSETS = {"all4": MODELS}
for m in MODELS:
    MODELSETS["drop:" + m.split("/")[-1]] = [x for x in MODELS if x != m]


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(comb(n, i) for i in range(k + 1)) / 2.0 ** n)


def units(recs):
    """The same five aggregation units used by the published curve."""
    out = {}
    out["cell"] = 100.0 * sum(r["B_correct"] - r["A_correct"] for r in recs) / len(recs)
    byit = collections.defaultdict(list)
    bycl = collections.defaultdict(list)
    for r in recs:
        byit[r["question_id"]].append(r)
        bycl[r["cluster"]].append(r)
    f = lambda v: 100.0 * sum(x["B_correct"] - x["A_correct"] for x in v) / len(v)
    out["item"] = sum(f(v) for v in byit.values()) / len(byit)
    out["cluster"] = sum(f(v) for v in bycl.values()) / len(bycl)
    ms = sorted({r["model"] for r in recs})
    pmc, pmg = [], []
    for m in ms:
        mr = [r for r in recs if r["model"] == m]
        pmc.append(f(mr))
        g = collections.defaultdict(list)
        for r in mr:
            g[r["cluster"]].append(r)
        pmg.append(sum(f(v) for v in g.values()) / len(g))
    out["model"] = sum(pmc) / len(pmc)
    out["sepclust"] = sum(pmg) / len(pmg)
    return out


def boot_ci_p(recs, seed=SEED, B=B_BOOT):
    bycl = collections.defaultdict(list)
    for r in recs:
        bycl[r["cluster"]].append(r)
    CL = sorted(bycl)
    agg = [(sum(x["A_correct"] for x in bycl[g]), sum(x["B_correct"] for x in bycl[g]),
            len(bycl[g])) for g in CL]
    K = len(CL)
    rng = random.Random(seed)
    d = []
    for _ in range(B):
        sA = sB = n = 0
        for _ in range(K):
            a, b, nn = agg[rng.randrange(K)]
            sA += a; sB += b; n += nn
        d.append(100.0 * (sB - sA) / n)
    d.sort()
    lo = sum(1 for x in d if x < 0) + 0.5 * sum(1 for x in d if x == 0)
    hi = sum(1 for x in d if x > 0) + 0.5 * sum(1 for x in d if x == 0)
    p = max(2.0 * min(lo, hi) / B, 1.0 / (B + 1.0))
    return d[int(0.025 * B)], d[int(0.975 * B)], p, K


nodefect = [r for r in rows if not r["excl_item_defect"]]

print("=" * 122)
print(f"{'position rule':<12} {'model set':<26} {'N':>5} {'items':>5} {'K':>4} "
      f"{'cell':>8} {'item':>8} {'cluster':>8} {'model':>8} {'sepclu':>8} "
      f"{'boot 95% CI':>22} {'boot p':>9} {'McN p':>10}")
print("=" * 122)

allvals = []
recorded = []
for pr, letters in POSRULE.items():
    for ms, mods in MODELSETS.items():
        recs = [r for r in nodefect if r["correct_letter"] in letters and r["model"] in mods]
        u = units(recs)
        lo, hi, p, K = boot_ci_p(recs)
        b = sum(1 for r in recs if r["A_correct"] == 1 and r["B_correct"] == 0)
        c = sum(1 for r in recs if r["A_correct"] == 0 and r["B_correct"] == 1)
        mp = mcnemar_exact(b, c)
        vals = [u[k] for k in ("cell", "item", "cluster", "model", "sepclust")]
        allvals.extend(vals)
        recorded.append((pr, ms, vals, p, mp))
        ni = len({r["question_id"] for r in recs})
        print(f"{pr:<12} {ms:<26} {len(recs):>5} {ni:>5} {K:>4} "
              + " ".join(f"{v:>8.3f}" for v in vals)
              + f"   [{lo:>7.3f},{hi:>7.3f}] {p:>9.2e} {mp:>10.2e}")

stored = json.load(open(os.path.join(HERE, "sens_speccurve_results.json")))
gmin = min(r["delta_pp"] for r in stored["results"])
gmax = max(r["delta_pp"] for r in stored["results"])

print()
print("=" * 122)
print("ENVELOPE COMPARISON")
print("=" * 122)
print(f"  published 160-spec curve : [{gmin:.3f}, {gmax:.3f}]   span = {gmax-gmin:.3f} pp")
print(f"  extended curve           : [{min(allvals):.3f}, {max(allvals):.3f}]   "
      f"span = {max(allvals)-min(allvals):.3f} pp   (n = {len(allvals)} estimates)")
outside = [v for v in allvals if v > gmax + 1e-9 or v < gmin - 1e-9]
print(f"  estimates OUTSIDE the published envelope: {len(outside)} / {len(allvals)}"
      f"  (max excursion above the published max: {max(allvals)-gmax:.3f} pp)")
print(f"  all extended estimates negative: {all(v < 0 for v in allvals)}")
print(f"  max bootstrap p over extended specs : {max(r[3] for r in recorded):.3e}")
print(f"  max exact-McNemar p over extended   : {max(r[4] for r in recorded):.3e}")

print("\n  specs whose point estimate sits outside the published [min,max]:")
for pr, ms, vals, p, mp in recorded:
    o = [v for v in vals if v > gmax + 1e-9 or v < gmin - 1e-9]
    if o:
        print(f"    {pr:<10} {ms:<26} units outside = {[round(x,3) for x in o]}")

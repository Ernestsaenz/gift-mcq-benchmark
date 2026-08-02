#!/usr/bin/env python3
"""REFUTE step 2: the primary contrast's inference assumes 133 independent
A-wrong cells.  They are not independent -- 4 models answer every item and
items sit in 208 paraphrase clusters.  Redo the SAME contrast with inference
that respects that structure.
"""
import json, math, random, collections, sys
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_refute_lib import fisher2x2, mantel_haenszel, two_sided_z_p

ANA = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
BAR = "=" * 96

rows = [r for r in json.load(open(f"{ANA}/paired_clean.json")) if r["analysis_include"]]
L = json.load(open(f"{ANA}/mech_refute_labels.json"))
for r in rows:
    r["adj"] = L[r["question_id"]]["adj"]
    r["flag"] = L[r["question_id"]]["flag"]

AW = [r for r in rows if not r["A_correct"]]


def contrast(cells, key):
    a = sum(r["B_correct"] for r in cells if r[key])
    b = sum(1 for r in cells if r[key]) - a
    c = sum(r["B_correct"] for r in cells if not r[key])
    d = sum(1 for r in cells if not r[key]) - c
    return a, b, c, d


def logor(a, b, c, d):
    return math.log(((a + .5) * (d + .5)) / ((b + .5) * (c + .5)))


def ratediff(a, b, c, d):
    if a + b == 0 or c + d == 0:
        return float("nan")
    return a / (a + b) - c / (c + d)


print(BAR); print("STEP 4 -- how much independent information is actually in the 133 cells?"); print(BAR)
items = collections.Counter(r["question_id"] for r in AW)
clus = collections.Counter(r["cluster"] for r in AW)
print(f"  133 A-wrong cells come from {len(items)} distinct items and {len(clus)} distinct clusters")
print(f"  cells per item: {collections.Counter(items.values())}")
print(f"  cells per cluster: {collections.Counter(clus.values())}")

# within-item concordance of the recovery outcome
conc = disc = 0
byit = collections.defaultdict(list)
for r in AW:
    byit[r["question_id"]].append(r["B_correct"])
for q, v in byit.items():
    for i in range(len(v)):
        for j in range(i + 1, len(v)):
            if v[i] == v[j]: conc += 1
            else: disc += 1
print(f"  within-item pairs of A-wrong cells: {conc} concordant / {disc} discordant"
      f"  -> pair concordance {conc/(conc+disc):.3f} (0.5 = independent-ish)")

# one-way ANOVA-style ICC of recovery across items with >=2 A-wrong cells
grp = [v for v in byit.values() if len(v) >= 2]
if grp:
    allv = [x for v in byit.values() for x in v]
    gm = sum(allv) / len(allv)
    k = len(grp)
    nbar = sum(len(v) for v in grp) / k
    msb = sum(len(v) * (sum(v) / len(v) - gm) ** 2 for v in grp) / max(k - 1, 1)
    msw = (sum(sum((x - sum(v) / len(v)) ** 2 for x in v) for v in grp)
           / max(sum(len(v) - 1 for v in grp), 1))
    icc = (msb - msw) / (msb + (nbar - 1) * msw) if (msb + (nbar - 1) * msw) else float("nan")
    deff = 1 + (nbar - 1) * icc
    print(f"  ICC of recovery within item (one-way ANOVA estimator) = {icc:.3f}")
    print(f"  mean cells/item among multi-cell items = {nbar:.2f}"
          f"  -> design effect ~ {deff:.2f}, effective n ~ {133/deff:.0f} of 133")

print()
print(BAR); print("STEP 5 -- SAME contrast, inference that respects item/cluster structure"); print(BAR)
for key, nm in (("flag", "shipped flag"), ("adj", "adjudicated")):
    a, b, c, d = contrast(AW, key)
    orr, p, _ = fisher2x2(a, b, c, d)
    obs_lor = logor(a, b, c, d); obs_rd = ratediff(a, b, c, d)
    print(f"\n  --- {nm}: {a}/{a+b} vs {c}/{c+d}, OR={orr:.3f}, naive Fisher p={p:.4g} ---")

    # (P1) item-level permutation of the polarity label (whole item moves)
    itemlab = {}
    itemrows = collections.defaultdict(list)
    for r in rows:
        itemlab[r["question_id"]] = r[key]
        itemrows[r["question_id"]].append(r)
    qs = list(itemlab); vals = [itemlab[q] for q in qs]
    rng = random.Random(20260731)
    NP = 20000
    cnt_lor = cnt_rd = 0
    for _ in range(NP):
        rng.shuffle(vals)
        a2 = b2 = c2 = d2 = 0
        for q, v in zip(qs, vals):
            for r in itemrows[q]:
                if r["A_correct"]:
                    continue
                if v:
                    if r["B_correct"]: a2 += 1
                    else: b2 += 1
                else:
                    if r["B_correct"]: c2 += 1
                    else: d2 += 1
        if abs(logor(a2, b2, c2, d2)) >= abs(obs_lor) - 1e-12: cnt_lor += 1
        if abs(ratediff(a2, b2, c2, d2)) >= abs(obs_rd) - 1e-12: cnt_rd += 1
    print(f"   [P1] item-level permutation of polarity ({NP} perms, all 4 model rows move"
          f" together)\n        log-OR statistic  p={(cnt_lor+1)/(NP+1):.4g}"
          f"   |   recovery-rate-difference statistic p={(cnt_rd+1)/(NP+1):.4g}")

    # (P2) cluster-level permutation (clusters = paraphrase families)
    cl_of_item = {r["question_id"]: r["cluster"] for r in rows}
    bycl = collections.defaultdict(set)
    for q, cl in cl_of_item.items():
        bycl[cl].add(itemlab[q])
    mixed = sum(1 for v in bycl.values() if len(v) > 1)
    print(f"   [P2] polarity constant within cluster for {len(bycl)-mixed}/{len(bycl)}"
          f" clusters ({mixed} mixed)")
    clrows = collections.defaultdict(list)
    for r in rows:
        clrows[r["cluster"]].append(r)
    cls = list(clrows)
    # permute the whole label vector of each cluster (keeps within-cluster mix)
    clvecs = [[itemlab[q] for q in sorted({r["question_id"] for r in clrows[cl]})] for cl in cls]
    clqs = [sorted({r["question_id"] for r in clrows[cl]}) for cl in cls]
    idx = list(range(len(cls)))
    cnt2 = 0
    rng2 = random.Random(99)
    for _ in range(NP):
        rng2.shuffle(idx)
        lab2 = {}
        for tgt, src in enumerate(idx):
            v = clvecs[src]
            for i, q in enumerate(clqs[tgt]):
                lab2[q] = v[i % len(v)]
        a2 = b2 = c2 = d2 = 0
        for r in AW:
            v = lab2[r["question_id"]]
            if v:
                if r["B_correct"]: a2 += 1
                else: b2 += 1
            else:
                if r["B_correct"]: c2 += 1
                else: d2 += 1
        if abs(logor(a2, b2, c2, d2)) >= abs(obs_lor) - 1e-12: cnt2 += 1
    print(f"        cluster-level permutation ({NP} perms): p={(cnt2+1)/(NP+1):.4g}")

    # (P3) cluster bootstrap CI for the log-OR
    bycl2 = collections.defaultdict(list)
    for r in AW:
        bycl2[r["cluster"]].append(r)
    # resample ALL clusters (incl. those with no A-wrong cells) to keep it honest
    allcl = sorted({r["cluster"] for r in rows})
    bs = []
    rng3 = random.Random(4242)
    for _ in range(5000):
        samp = []
        for _ in range(len(allcl)):
            samp.extend(bycl2.get(allcl[rng3.randrange(len(allcl))], []))
        a2, b2, c2, d2 = contrast(samp, key)
        if a2 + b2 == 0 or c2 + d2 == 0:
            continue
        bs.append(logor(a2, b2, c2, d2))
    bs.sort()
    lo, hi = bs[int(.025 * len(bs))], bs[int(.975 * len(bs))]
    frac = sum(1 for v in bs if v <= 0) / len(bs)
    print(f"   [P3] cluster bootstrap (5000 resamples of {len(allcl)} clusters) log-OR:"
          f"\n        OR 95% CI [{math.exp(lo):.3f}, {math.exp(hi):.3f}]"
          f"   two-sided bootstrap p ~ {2*min(frac,1-frac):.4g}")

    # (P4) Mantel-Haenszel stratified by model
    tabs = []
    for m in sorted({r["model"] for r in rows}):
        sub = [r for r in AW if r["model"] == m]
        tabs.append(contrast(sub, key))
    o, chi2, pmh, se = mantel_haenszel(tabs)
    z = math.log(o) / se
    print(f"   [P4] Mantel-Haenszel stratified by model: OR_MH={o:.3f}"
          f"  95% CI [{math.exp(math.log(o)-1.96*se):.3f},{math.exp(math.log(o)+1.96*se):.3f}]"
          f"  RBG z={z:+.3f} p={two_sided_z_p(z):.4g}  (MH chi2 p={pmh:.4g})")

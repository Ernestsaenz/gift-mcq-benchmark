"""The coverage caveat: GIFT stopped at 83%, so the analysed set is a sequential
prefix, not a random sample. Quantify the selection, then test whether the paired
GIFT-vs-OpenRouter risk difference is sensitive to it.

Key logic: the risk difference is a WITHIN-ITEM paired contrast, so an easier
subset biases it only to the extent that the risk difference itself varies with
difficulty / region. That is exactly what is tested here.
"""
import json, os, sys, math, collections, sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_prim_lib import LCG, percentile

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.path.dirname(BASE), 'experiment.sqlite')
con = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)

rows = [r for r in json.load(open(os.path.join(BASE, 'cross_arm_A.json')))
        if r.get('analysis_include')]
MODELS = sorted({r['model'] for r in rows})
covered_items = sorted({r['question_id'] for r in rows})
cov319 = set(json.load(open(os.path.join(BASE, 'gift_coverage.json')))['complete_all_models'])
meta = json.load(open(os.path.join(BASE, 'dataset_meta.json')))
defect = set(meta['exclusions']['administrative_legal_out_of_domain']) | \
         set(meta['exclusions']['adjudicated_key_defect'])
out = {}

# ---------------------------------------------------- full OpenRouter arm
q = """select lc.model, q.question_id, q.region, q.year, q.exam_part, s.letter_correct
       from logical_calls lc
       join questions q on q.id = lc.question_id
       join parsed_answers pa on pa.logical_call_id = lc.id
       join scores s on s.logical_call_id = lc.id
       where lc.experiment_id = 6 and pa.parse_status = 'ok'"""
orr = list(con.execute(q))
qinfo = {qid: (reg, yr, part) for _, qid, reg, yr, part, _lc in orr}
all_items = sorted(qinfo)
print(f"OpenRouter A cells parsed ok = {len(orr)}; distinct items = {len(all_items)}")


def acc(cells):
    return sum(c for c in cells) / len(cells) if cells else float('nan')


for label, keep, dropdef in [("all 474 items", all_items, False),
                             ("460 non-defective", [i for i in all_items if i not in defect], True)]:
    ks = set(keep)
    inc = [lc for _, qid, _, _, _, lc in orr if qid in ks and qid in cov319]
    outc = [lc for _, qid, _, _, _, lc in orr if qid in ks and qid not in cov319]
    n_in = len({qid for qid in keep if qid in cov319})
    n_out = len({qid for qid in keep if qid not in cov319})
    print(f"[{label}] OR acc on GIFT-covered ({n_in} items, {len(inc)} cells) = {100*acc(inc):.2f}%   "
          f"| never reached ({n_out} items, {len(outc)} cells) = {100*acc(outc):.2f}%   "
          f"gap = {100*(acc(inc)-acc(outc)):.2f}pp")
    out[f"or_acc_{'nondefective' if dropdef else 'all'}"] = {
        "items_covered": n_in, "items_missing": n_out,
        "or_acc_covered_pct": 100 * acc(inc), "or_acc_missing_pct": 100 * acc(outc),
        "difficulty_gap_pp": 100 * (acc(inc) - acc(outc))}

# ------------------------------------------------------------- region mix
reg_cov = collections.Counter(qinfo[i][0] for i in all_items if i in cov319)
reg_mis = collections.Counter(qinfo[i][0] for i in all_items if i not in cov319)
regions = sorted(set(reg_cov) | set(reg_mis))
print("\nregion            covered  missing   %covered")
regtab = {}
for r in regions:
    a, b = reg_cov.get(r, 0), reg_mis.get(r, 0)
    regtab[r] = {"covered": a, "missing": b, "pct_covered": 100 * a / (a + b)}
    print(f"  {r:22s} {a:4d} {b:6d}   {100*a/(a+b):5.1f}%")
out['region_coverage_all474'] = regtab

# ------------------------------------ item difficulty strata from the OR arm
item_or = collections.defaultdict(list)
for _, qid, _, _, _, lc in orr:
    item_or[qid].append(lc)
# difficulty = number of the 4 models OpenRouter got right (0..4); use the
# fraction so the one item with 3 cells (b320 x glm-5.2 unrecoverable) still maps
diff = {qid: sum(v) / len(v) for qid, v in item_or.items()}
STRATA = [(0.0, "0/4 all wrong"), (0.25, "1/4"), (0.5, "2/4"), (0.75, "3/4"), (1.0, "4/4 all right")]


def bucket(qid):
    f = diff[qid]
    return min(STRATA, key=lambda s: abs(s[0] - f))[1]


elig = [i for i in all_items if i not in defect]
dist_cov = collections.Counter(bucket(i) for i in elig if i in cov319)
dist_mis = collections.Counter(bucket(i) for i in elig if i not in cov319)
print("\nOR-difficulty stratum   covered  missing")
for _, name in STRATA:
    print(f"  {name:22s} {dist_cov.get(name,0):5d} {dist_mis.get(name,0):7d}")
out['difficulty_strata_460'] = {name: {"covered": dist_cov.get(name, 0),
                                       "missing": dist_mis.get(name, 0)} for _, name in STRATA}

# ------------------- risk difference by difficulty stratum, on covered items
print("\nRD by OR-difficulty stratum (covered items only):")
strat_rd = {}
for _, name in STRATA:
    sub = [r for r in rows if bucket(r['question_id']) == name]
    if not sub:
        continue
    g = sum(r['gift_correct'] for r in sub) / len(sub)
    o = sum(r['or_correct'] for r in sub) / len(sub)
    b = sum(1 for r in sub if r['gift_correct'] and not r['or_correct'])
    c = sum(1 for r in sub if r['or_correct'] and not r['gift_correct'])
    strat_rd[name] = {"n_items": len({r['question_id'] for r in sub}), "n_cells": len(sub),
                      "gift_pct": 100 * g, "or_pct": 100 * o, "rd_pp": 100 * (g - o),
                      "b": b, "c": c}
    print(f"  {name:22s} items={strat_rd[name]['n_items']:4d} cells={len(sub):5d} "
          f"GIFT={100*g:6.2f}% OR={100*o:6.2f}% RD={100*(g-o):+6.2f}pp (b={b},c={c})")
out['rd_by_difficulty_stratum'] = strat_rd

# ------------------------------------------- post-stratified (reweighted) RD
# Target = the 460 eligible items' stratum distribution; weights fixed, the
# within-stratum RD is re-estimated in each cluster-bootstrap replicate.
target = {name: dist_cov.get(name, 0) + dist_mis.get(name, 0) for _, name in STRATA}
Tsum = sum(target.values())
by_cluster = collections.defaultdict(list)
for r in rows:
    by_cluster[r['cluster']].append(r)
CL = sorted(by_cluster)
clus = [by_cluster[c] for c in CL]


def poststrat(sample_rows, keyf, target_counts):
    agg = collections.defaultdict(lambda: [0, 0, 0])
    for r in sample_rows:
        a = agg[keyf(r)]
        a[0] += r['gift_correct']; a[1] += r['or_correct']; a[2] += 1
    num = den = 0.0
    for k, w in target_counts.items():
        if w and k in agg and agg[k][2]:
            num += w * (agg[k][0] - agg[k][1]) / agg[k][2]
            den += w
    return num / den if den else None


kf = lambda r: bucket(r['question_id'])
pt = poststrat(rows, kf, target)
kfr = lambda r: r['region']
target_reg = {r: reg_cov.get(r, 0) + reg_mis.get(r, 0) for r in regions}
# restrict region target to the eligible 460
target_reg = collections.Counter(qinfo[i][0] for i in elig)
ptr = poststrat(rows, kfr, target_reg)

SEED, B = 20260731, 20000
rng = LCG(SEED)
K = len(clus)
bs_d, bs_r, bs_raw = [], [], []
for _ in range(B):
    samp = []
    for _ in range(K):
        samp.extend(clus[rng.randrange(K)])
    v = poststrat(samp, kf, target)
    if v is not None:
        bs_d.append(v)
    v2 = poststrat(samp, kfr, target_reg)
    if v2 is not None:
        bs_r.append(v2)
    bs_raw.append((sum(r['gift_correct'] for r in samp) - sum(r['or_correct'] for r in samp)) / len(samp))
bs_d.sort(); bs_r.sort(); bs_raw.sort()

raw = (sum(r['gift_correct'] for r in rows) - sum(r['or_correct'] for r in rows)) / len(rows)
out['poststratified_rd'] = {
    "unweighted_rd_pp": 100 * raw,
    "unweighted_ci_pp": (100 * percentile(bs_raw, .025), 100 * percentile(bs_raw, .975)),
    "difficulty_poststratified_rd_pp": 100 * pt,
    "difficulty_ci_pp": (100 * percentile(bs_d, .025), 100 * percentile(bs_d, .975)),
    "region_poststratified_rd_pp": 100 * ptr,
    "region_ci_pp": (100 * percentile(bs_r, .025), 100 * percentile(bs_r, .975)),
    "assumption": "coverage ignorable given the stratum (MAR); not a fix for a "
                  "sequential-prefix stop, only a bound on the measurable part"}
print(f"\nRD unweighted           = {100*raw:+.2f}pp  CI ({100*percentile(bs_raw,.025):+.2f},{100*percentile(bs_raw,.975):+.2f})")
print(f"RD reweighted to 460-item OR-difficulty mix = {100*pt:+.2f}pp  "
      f"CI ({100*percentile(bs_d,.025):+.2f},{100*percentile(bs_d,.975):+.2f})")
print(f"RD reweighted to 460-item region mix        = {100*ptr:+.2f}pp  "
      f"CI ({100*percentile(bs_r,.025):+.2f},{100*percentile(bs_r,.975):+.2f})")

# ------------------------- leave-out: the six Illes Balears 2022 case clusters
big = [c for c in CL if len(by_cluster[c]) >= 24]   # >=6 items x 4 models
print(f"\nlarge clusters (>=6 items): {big} "
      f"covering {sum(len(by_cluster[c]) for c in big)//4} items")
sub = [r for r in rows if r['cluster'] not in big]
lo_rd = (sum(r['gift_correct'] for r in sub) - sum(r['or_correct'] for r in sub)) / len(sub)
clus2 = [by_cluster[c] for c in CL if c not in big]
rng2 = LCG(SEED + 5)
bs2 = []
for _ in range(B):
    s = []
    for _ in range(len(clus2)):
        s.extend(clus2[rng2.randrange(len(clus2))])
    bs2.append((sum(r['gift_correct'] for r in s) - sum(r['or_correct'] for r in s)) / len(s))
bs2.sort()
n_le = sum(1 for v in bs2 if v <= 0)
n_ge = sum(1 for v in bs2 if v >= 0)
out['drop_large_case_clusters'] = {
    "clusters_dropped": big, "items_dropped": (len(rows) - len(sub)) // 4,
    "n_cells_remaining": len(sub), "rd_pp": 100 * lo_rd,
    "ci_pp": (100 * percentile(bs2, .025), 100 * percentile(bs2, .975)),
    "p_boot": min(1.0, 2 * min(n_le, n_ge) / len(bs2))}
print(f"drop 6 big case clusters -> RD={100*lo_rd:+.2f}pp "
      f"CI ({100*percentile(bs2,.025):+.2f},{100*percentile(bs2,.975):+.2f}) "
      f"n_cells={len(sub)} p_boot={out['drop_large_case_clusters']['p_boot']:.4f}")

# ------------------------------------------------------- tipping-point bound
n_cov_items = len([i for i in elig if i in cov319])
n_mis_items = len([i for i in elig if i not in cov319])
tip = {}
for m in MODELS + ['POOLED']:
    sub = rows if m == 'POOLED' else [r for r in rows if r['model'] == m]
    r_cov = (sum(x['gift_correct'] for x in sub) - sum(x['or_correct'] for x in sub)) / len(sub)
    need = -r_cov * n_cov_items / n_mis_items
    tip[m] = {"rd_covered_pp": 100 * r_cov,
              "rd_on_missing_needed_to_null_full_set_pp": 100 * need}
out['tipping_point'] = {"n_items_covered": n_cov_items, "n_items_missing": n_mis_items,
                        "per_model": tip}
print(f"\ntipping point (eligible items: {n_cov_items} covered / {n_mis_items} missing)")
for m, v in tip.items():
    print(f"  {m:28s} RD_cov={v['rd_covered_pp']:+.2f}pp -> GIFT would need "
          f"RD={v['rd_on_missing_needed_to_null_full_set_pp']:+.2f}pp on the unseen items to null it")

json.dump(out, open(os.path.join(BASE, 'ca_prim_03_coverage.json'), 'w'), indent=1, default=str)
print("\nwrote ca_prim_03_coverage.json")

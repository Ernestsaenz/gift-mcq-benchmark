#!/usr/bin/env python3
"""
sens_refute_gridflip_audit.py -- INDEPENDENT recomputation of the "NOTHING FLIPS"
robustness claim from the exclusion-grid analysis.

Written from raw paired_clean.json; does not import or read sens_exclusion_grid.py
or its cached results. stdlib only.

DESIGN
  Paired binary. Unit of observation = (item, model) cell with A_correct, B_correct.
  delta = mean(B_correct) - mean(A_correct) over cells in the subset.
  Items nest in clinical-context clusters -> resampling unit is the CLUSTER.

EXCLUSION SETS (2x2 over the two contested rules)
  S1_none        : every row in paired_clean.json
  S2_drop_defect : drop excl_item_defect
  S3_drop_posA   : drop excl_nota_position_a
  S4_drop_both   : analysis_include (the headline set)

METHODS (all implemented here, no library)
  CI  : nonparametric cluster bootstrap. Resample C clusters WITH replacement from
        the clusters present in that (set, model) subset; recompute delta on the
        pooled resampled cells; R replicates; 2.5/97.5 percentile, linear interp.
  p   : cluster sign-flip (Fisher randomisation) permutation. Under H0 the A/B
        label is exchangeable within an item, so per-cell d = B - A may have its
        sign flipped; flips applied at the CLUSTER level (all cells in a cluster
        share one flip) to respect the dependence structure. Statistic = mean(d).
        p = (1 + #{|T*| >= |T_obs|}) / (R + 1)  <- add-one; smallest attainable
        value is 1/(R+1), so anything quoted below that is a resolution floor,
        not a measured probability.
  McNemar: n10 = A right & B wrong, n01 = A wrong & B right, plus the EXACT
        two-sided binomial p on discordants (ignores clustering; reference only).
"""

import json, os, math, random
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = json.load(open(os.path.join(HERE, "paired_clean.json")))
META = json.load(open(os.path.join(HERE, "dataset_meta.json")))
MODELS = sorted(set(r["model"] for r in ROWS))
R = 20000
SEED = 987654321

FILTERS = {
    "S1_none":        lambda r: True,
    "S2_drop_defect": lambda r: not r["excl_item_defect"],
    "S3_drop_posA":   lambda r: not r["excl_nota_position_a"],
    "S4_drop_both":   lambda r: r["analysis_include"],
}
SIDS = list(FILTERS)


# ---------------------------------------------------------------- helpers
def pct(sorted_vals, q):
    i = q * (len(sorted_vals) - 1)
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (i - lo)


def logC(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def binom_exact_two_sided(k, n):
    if n == 0:
        return 1.0
    obs = logC(n, k)
    tot = 0.0
    for i in range(n + 1):
        if logC(n, i) <= obs + 1e-12:
            tot += math.exp(logC(n, i))
    return min(1.0, tot / (2.0 ** n))


def subset(sid, model=None):
    f = FILTERS[sid]
    return [r for r in ROWS if f(r) and (model is None or r["model"] == model)]


def by_cluster(cells):
    g = defaultdict(list)
    for r in cells:
        g[r["cluster"]].append(r["B_correct"] - r["A_correct"])
    return list(g.values())


def delta(cells):
    n = len(cells)
    return sum(r["B_correct"] - r["A_correct"] for r in cells) / n if n else None


def cluster_bootstrap_ci(cells, reps, rng):
    groups = by_cluster(cells)
    pre = [(len(g), sum(g)) for g in groups]
    C = len(pre)
    out = []
    for _ in range(reps):
        n = s = 0
        for _ in range(C):
            gn, gs = pre[rng.randrange(C)]
            n += gn; s += gs
        if n:
            out.append(s / n)
    out.sort()
    m = sum(out) / len(out)
    sd = math.sqrt(sum((x - m) ** 2 for x in out) / (len(out) - 1))
    nge = sum(1 for x in out if x >= 0)
    return pct(out, 0.025), pct(out, 0.975), nge / len(out), sd


def cluster_signflip_p(cells, reps, rng):
    groups = by_cluster(cells)
    sums = [sum(g) for g in groups]
    n = sum(len(g) for g in groups)
    obs = abs(sum(sums) / n)
    nz = [s for s in sums if s != 0]
    hits = 0
    for _ in range(reps):
        t = 0
        for s in nz:
            t += s if rng.getrandbits(1) else -s
        if abs(t / n) >= obs - 1e-15:
            hits += 1
    return (1 + hits) / (reps + 1), hits, len(nz)


def mcnemar(cells):
    n10 = sum(1 for r in cells if r["A_correct"] == 1 and r["B_correct"] == 0)
    n01 = sum(1 for r in cells if r["A_correct"] == 0 and r["B_correct"] == 1)
    return n10, n01, binom_exact_two_sided(min(n10, n01), n10 + n01)


# ---------------------------------------------------------------- C0 provenance
print("=" * 120)
print("C0  PROVENANCE OF THE 'UNFILTERED' SET S1")
print("=" * 120)
meta_defect = sorted(META["exclusions"]["administrative_legal_out_of_domain"] +
                     META["exclusions"]["adjudicated_key_defect"])
flag_defect = sorted(set(r["question_id"] for r in ROWS if r["excl_item_defect"]))
present = set(r["question_id"] for r in ROWS)
print("dataset_meta says N contested-defect items :", len(meta_defect))
print("items actually carrying excl_item_defect   :", len(flag_defect))
print("meta-listed but ABSENT from paired_clean    :", [q for q in meta_defect if q not in present])
print("posA flag == (correct_letter=='a') ?        :",
      all(r["excl_nota_position_a"] == (r["correct_letter"] == "a") for r in ROWS))
print("analysis_include == not(defect or posA) ?   :",
      all(r["analysis_include"] == (not (r["excl_item_defect"] or r["excl_nota_position_a"])) for r in ROWS))
cells_per_item = Counter(r["question_id"] for r in ROWS)
print("items with < 4 model cells (unparsed drops) :", {k: v for k, v in cells_per_item.items() if v != 4})
print()

# ---------------------------------------------------------------- grid
print("=" * 120)
print("C1  INDEPENDENT 4-SET x (4-MODEL + POOLED) GRID")
print("delta = mean(B_correct) - mean(A_correct).  CI = cluster bootstrap R=%d, percentile." % R)
print("p_perm = cluster sign-flip permutation, two-sided, add-one: FLOOR = 1/(R+1) = %.5f" % (1 / (R + 1)))
print("=" * 120)

grid = {}
print(f"{'key':<24}{'set':<16}{'cells':>6}{'clus':>6}{'accA':>8}{'accB':>8}{'delta':>10}"
      f"{'CI_lo':>10}{'CI_hi':>10}{'width':>8}{'p_perm':>9}{'n10':>6}{'n01':>6}{'p_mcn':>11}")
print("-" * 120)
for key in ["POOLED"] + MODELS:
    model = None if key == "POOLED" else key
    for sid in SIDS:
        cells = subset(sid, model)
        rng = random.Random(SEED + (abs(hash((key, sid))) % 10 ** 8))
        d = delta(cells)
        lo, hi, pge, sd = cluster_bootstrap_ci(cells, R, rng)
        pp, hits, nz = cluster_signflip_p(cells, R, rng)
        n10, n01, pm = mcnemar(cells)
        nclus = len(set(r["cluster"] for r in cells))
        accA = sum(r["A_correct"] for r in cells) / len(cells)
        accB = sum(r["B_correct"] for r in cells) / len(cells)
        grid[(key, sid)] = dict(n=len(cells), clus=nclus, accA=accA, accB=accB, delta=d,
                                lo=lo, hi=hi, sd=sd, p=pp, hits=hits, nz=nz,
                                n10=n10, n01=n01, pm=pm, pge=pge)
        nm = key.split("/")[-1]
        print(f"{nm:<24}{sid:<16}{len(cells):>6}{nclus:>6}{accA:>8.4f}{accB:>8.4f}{d:>10.4f}"
              f"{lo:>10.4f}{hi:>10.4f}{hi-lo:>8.4f}{pp:>9.5f}{n10:>6}{n01:>6}{pm:>11.3e}")
    print("-" * 120)

# ---------------------------------------------------------------- audit
print()
print("=" * 120)
print("C2  CLAIM AUDIT")
print("=" * 120)
notneg = [k for k, v in grid.items() if v["delta"] >= 0]
notexcl = [k for k, v in grid.items() if not (v["hi"] < 0 or v["lo"] > 0)]
print("estimates in grid              :", len(grid))
print("deltas NOT negative            :", notneg or "none")
print("CIs NOT excluding zero         :", notexcl or "none")
w = max(grid.items(), key=lambda kv: kv[1]["hi"] - kv[1]["lo"])
print("widest CI (any key)            :", w[0], f"[{w[1]['lo']:+.4f},{w[1]['hi']:+.4f}] width={w[1]['hi']-w[1]['lo']:.4f}")
wm = max(((k, v) for k, v in grid.items() if k[0] != "POOLED"), key=lambda kv: kv[1]["hi"] - kv[1]["lo"])
print("widest PER-MODEL CI            :", wm[0], f"[{wm[1]['lo']:+.4f},{wm[1]['hi']:+.4f}] width={wm[1]['hi']-wm[1]['lo']:.4f}")
c = max(grid.items(), key=lambda kv: kv[1]["hi"])
print("CI upper bound closest to zero :", c[0], f"hi={c[1]['hi']:+.4f}  (margin {abs(c[1]['hi'])*100:.2f} pts)")
wp = max(grid.items(), key=lambda kv: kv[1]["p"])
print("largest permutation p          :", wp[0], f"p={wp[1]['p']:.5f} (hits={wp[1]['hits']}, non-null clusters={wp[1]['nz']})")
atfloor = [k for k, v in grid.items() if v["hits"] == 0]
print("estimates AT the p floor       :", len(atfloor), "of", len(grid),
      f"-> true p unresolvable below {1/(R+1):.5f}; 95% upper bound from 0/{R} is {3.0/R:.5f}")

json.dump({f"{k[0]}|{k[1]}": v for k, v in grid.items()},
          open(os.path.join(HERE, "sens_refute_gridflip_out.json"), "w"), indent=1)
print("\nwrote sens_refute_gridflip_out.json")

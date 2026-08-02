"""ca_cov_04: bounded extrapolation of the cross-arm delta to the FULL dataset.

Target (finite population): every (item, model) cell of dataset A after the 14
documented item exclusions -- 460 items x 4 models = 1839 scored OR cells
(b320 x glm-5.2 has no OR result and is dropped throughout).

OR is fully observed on all 1839 cells. GIFT is observed on 1244 (the paired
analysis set) + 99 (cells on items GIFT never finished on all four models).
496 cells are unobserved. Everything below is about those 496.

Estimators
  E0  observed        : the published paired estimate, 1244 cells.
  E1  crude transfer  : assume the unobserved cells carry the SAME delta as the
                        observed ones (missing completely at random). Wrong by
                        construction -- reported only as a reference point.
  E2  post-stratified : transfer the delta within (model x difficulty) strata.
                        Assumption: MAR given model and leave-one-out OR
                        difficulty.
  E3  E2 + the 99 directly observed uncovered cells used as observed.
  E4  Manski bounds   : no assumption at all about the 496 unobserved cells.
  E5  sensitivity     : scale the transferred uncovered delta by lambda.
"""
import json, os, sys, random, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ca_lib as L

BASE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
SHORT = {"google/gemini-3.6-flash": "gemini", "google/gemma-4-26b-a4b-it": "gemma",
         "qwen/qwen3.6-35b-a3b": "qwen", "z-ai/glm-5.2": "glm"}

G = json.load(open(os.path.join(BASE, "ca_cov_grid.json")))
orc = {tuple(k.split("|")): v for k, v in G["or_correct"].items()}
gic = {tuple(k.split("|")): v for k, v in G["gift_correct"].items()}
covered = set(G["covered"]); defect = set(G["defect"])
items = json.load(open(os.path.join(BASE, "ca_cov_or_full.json")))["items"]
cross = {(r["model"], r["question_id"]): r for r in L.load(include_only=True)}


def loo_k(q, m):
    vs = [orc[(mm, q)] for mm in MODELS if mm != m and (mm, q) in orc]
    return sum(vs) if len(vs) == 3 else None


# ------------------------------------------------------- build the population
POP = []
for q in items:
    if q in defect:
        continue
    for m in MODELS:
        if (m, q) not in orc:
            continue
        k = loo_k(q, m)
        POP.append({"q": q, "m": m, "or": orc[(m, q)],
                    "gift": gic.get((m, q)),
                    "k": k, "paired": q in covered,
                    "cluster": cross[(m, q)]["cluster"] if (m, q) in cross else None,
                    "region": items[q]["region"]})
print("population cells:", len(POP),
      " items:", len(set(r['q'] for r in POP)))
print("  GIFT observed:", sum(1 for r in POP if r["gift"] is not None),
      "  in paired set:", sum(1 for r in POP if r["paired"]),
      "  unobserved:", sum(1 for r in POP if r["gift"] is None))
bad = [r for r in POP if r["k"] is None]
print("  cells with undefined LOO difficulty (dropped from E2/E3):",
      len(bad), sorted(set(r['q'] for r in bad)))

PAIR = [r for r in POP if r["paired"]]
EXTRA = [r for r in POP if (not r["paired"]) and r["gift"] is not None]
MISS = [r for r in POP if r["gift"] is None]
print(f"  paired={len(PAIR)} extra-observed={len(EXTRA)} missing={len(MISS)}")

N = len(POP)
O_full = sum(r["or"] for r in POP)
G_pair = sum(r["gift"] for r in PAIR)
O_pair = sum(r["or"] for r in PAIR)
G_extra = sum(r["gift"] for r in EXTRA)
O_extra = sum(r["or"] for r in EXTRA)
print(f"\nOR correct over the whole population: {O_full}/{N} = {100*O_full/N:.2f}%")

# ------------------------------------------------------------------ E0 / E1
E0 = (G_pair - O_pair) / len(PAIR)
print(f"\nE0 observed paired delta            : {100*E0:+.2f} pp  (n={len(PAIR)})")
E1 = E0
print(f"E1 crude MCAR transfer to all {N}  : {100*E1:+.2f} pp  "
      f"(identical by construction; it ignores the coverage skew)")

# --------------------------------------------------------- strata definition
def stratum(r, mode):
    if mode == "k4":
        return (r["m"], r["k"])
    if mode == "hard_easy":
        return (r["m"], "E" if r["k"] == 3 else "H")
    if mode == "pooled_hard_easy":
        return ("pooled", "E" if r["k"] == 3 else "H")
    if mode == "pooled_k4":
        return ("pooled", r["k"])
    raise ValueError(mode)


def post_strat(train, targets, mode, fallback):
    """delta per stratum learned on `train`; summed over `targets`.
    Returns imputed GIFT-minus-OR total and a per-stratum audit."""
    agg = {}
    for r in train:
        s = stratum(r, mode)
        a = agg.setdefault(s, [0, 0])
        a[0] += r["gift"] - r["or"]; a[1] += 1
    tot = 0.0
    audit = {}
    for r in targets:
        s = stratum(r, mode)
        d = agg[s][0] / agg[s][1] if s in agg and agg[s][1] > 0 else fallback
        tot += d
        au = audit.setdefault(str(s), [0, 0.0])
        au[0] += 1; au[1] = d
    return tot, agg, audit


MISS_OK = [r for r in MISS if r["k"] is not None]
print(f"\n=== E2  post-stratified transfer  (train = {len(PAIR)} paired cells) ===")
res = {}
for mode in ["hard_easy", "k4", "pooled_hard_easy", "pooled_k4"]:
    tot, agg, audit = post_strat(PAIR, MISS_OK, mode, E0)
    # unobserved cells with undefined k fall back to the crude delta
    tot += E0 * len([r for r in MISS if r["k"] is None])
    num = (G_pair - O_pair) + (G_extra - O_extra) * 0 + tot
    # E2 does NOT use the 99 extra cells: they are treated as missing too
    tot2, _, _ = post_strat(PAIR, [r for r in EXTRA if r["k"] is not None], mode, E0)
    tot2 += E0 * len([r for r in EXTRA if r["k"] is None])
    est = ((G_pair - O_pair) + tot + tot2) / N
    res[mode] = est
    print(f"  strata={mode:18s} n_strata={len(agg):2d}  E2 = {100*est:+.2f} pp")
    if mode == "hard_easy":
        print("     per-stratum delta learned on the paired set:")
        for s in sorted(agg, key=lambda x: (str(x[0]), str(x[1]))):
            d, n_ = agg[s]
            tgt = sum(1 for r in MISS_OK + [x for x in EXTRA if x['k'] is not None]
                      if stratum(r, mode) == s)
            print(f"       {SHORT[s[0]]:7s} {s[1]}  train_n={n_:4d} delta={100*d/n_:+7.2f} pp"
                  f"   -> applied to {tgt:4d} unobserved cells")

E2 = res["hard_easy"]

print(f"\n=== E3  = E2 but the {len(EXTRA)} directly observed uncovered cells "
      f"are used as observed ===")
for mode in ["hard_easy", "k4", "pooled_hard_easy", "pooled_k4"]:
    tot, agg, _ = post_strat(PAIR, MISS_OK, mode, E0)
    tot += E0 * len([r for r in MISS if r["k"] is None])
    est = ((G_pair - O_pair) + (G_extra - O_extra) + tot) / N
    res["E3_" + mode] = est
    print(f"  strata={mode:18s}  E3 = {100*est:+.2f} pp")
E3 = res["E3_hard_easy"]

# E3b: train the transfer on paired + extra cells (extra cells are the only
# real observations from the uncovered region)
print("\n=== E3b = E3 but the transfer is trained on paired + extra cells ===")
for mode in ["hard_easy", "k4", "pooled_hard_easy", "pooled_k4"]:
    tot, agg, _ = post_strat(PAIR + EXTRA, MISS_OK, mode, E0)
    tot += E0 * len([r for r in MISS if r["k"] is None])
    est = ((G_pair - O_pair) + (G_extra - O_extra) + tot) / N
    res["E3b_" + mode] = est
    print(f"  strata={mode:18s}  E3b = {100*est:+.2f} pp")
E3b = res["E3b_hard_easy"]

# ---------------------------------------------------------------- E4 Manski
lo_M = ((G_pair - O_pair) + (G_extra - O_extra) + (0 - sum(r["or"] for r in MISS))) / N
hi_M = ((G_pair - O_pair) + (G_extra - O_extra)
        + (len(MISS) - sum(r["or"] for r in MISS))) / N
print(f"\n=== E4  Manski worst-case bounds on the {len(MISS)} unobserved cells ===")
print(f"  GIFT wrong on all of them : {100*lo_M:+.2f} pp")
print(f"  GIFT right on all of them : {100*hi_M:+.2f} pp")
print(f"  width = {100*(hi_M-lo_M):.1f} pp  -- assumption-free, uninformative about sign")

# ------------------------------------------------------------ E5 sensitivity
print("\n=== E5  sensitivity: transferred uncovered delta scaled by lambda ===")
tot_h, agg_h, _ = post_strat(PAIR, MISS_OK, "hard_easy", E0)
base_unobs = tot_h + E0 * len([r for r in MISS if r["k"] is None])
print(f"{'lambda':>7s} {'full-dataset delta':>20s}")
lam_tab = {}
for lam in [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
    est = ((G_pair - O_pair) + (G_extra - O_extra) + lam * base_unobs) / N
    lam_tab[lam] = est
    print(f"{lam:7.2f} {100*est:+19.2f} pp")

# ---------------------------------------------------- bootstrap uncertainty
def e2_stat(rows, mode="hard_easy"):
    """rows = a bootstrap resample of the paired training cells."""
    agg = {}
    for r in rows:
        s = stratum(r, mode)
        a = agg.setdefault(s, [0, 0]); a[0] += r["gift"] - r["or"]; a[1] += 1
    gp = sum(r["gift"] for r in rows); op = sum(r["or"] for r in rows)
    d0 = (gp - op) / len(rows)
    tot = 0.0
    for r in MISS_OK + EXTRA:
        s = stratum(r, mode)
        tot += (agg[s][0] / agg[s][1]) if (s in agg and agg[s][1] > 0) else d0
    tot += d0 * len([r for r in MISS if r["k"] is None])
    return ((gp - op) * (len(PAIR) / len(rows)) + tot) / N


B = 20000
bs = L.cluster_bootstrap(PAIR, e2_stat, keyf=lambda r: r["cluster"], B=B, seed=515151)
lo2, hi2 = L.ci(bs)
print(f"\nE2 cluster bootstrap (B={B}, resample the 183 paired clusters): "
      f"point {100*E2:+.2f} pp, 95% CI [{100*lo2:+.2f}, {100*hi2:+.2f}] pp")
print("  (this CI covers sampling noise in the learned stratum deltas ONLY;"
      " it does NOT cover failure of the transfer assumption)")

bs0 = L.cluster_bootstrap(PAIR, lambda rs: sum(r["gift"] - r["or"] for r in rs) / len(rs),
                          keyf=lambda r: r["cluster"], B=B, seed=515152)
lo0, hi0 = L.ci(bs0)
print(f"E0 cluster bootstrap 95% CI: [{100*lo0:+.2f}, {100*hi0:+.2f}] pp")

json.dump({"N": N, "n_paired": len(PAIR), "n_extra": len(EXTRA), "n_missing": len(MISS),
           "O_full": O_full, "E0": E0, "E2": E2, "E3": E3, "E3b": E3b,
           "all_variants": res, "manski": [lo_M, hi_M],
           "lambda": {str(k): v for k, v in lam_tab.items()},
           "E2_ci": [lo2, hi2], "E0_ci": [lo0, hi0]},
          open(os.path.join(BASE, "ca_cov_04_out.json"), "w"), indent=1)

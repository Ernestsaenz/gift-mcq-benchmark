#!/usr/bin/env python
"""
sens_refute_position_cf.py -- INDEPENDENT recomputation of the "position-artifact"
counterfactual claim:

  CLAIM: had the 91 position-(a) items behaved like the b/c/d average, the raw
  pooled delta would have been -15.75 pp instead of -17.33 pp; only 9.1% of the
  raw pooled degradation is attributable to the construction defect.

Everything below is written from scratch (no import of the original module).
Stdlib only; bootstrap/permutation implemented by hand.

Methods used, stated explicitly:
  * point estimates: plain arithmetic means over cells (unweighted per cell).
  * CIs: nonparametric cluster bootstrap -- resample the 281 clinical-context
    clusters WITH replacement, K draws per replicate, all cells of a drawn
    cluster enter together; every derived quantity (including the donor means
    used for the substitution) is recomputed inside each replicate.
    Percentile interval at 2.5 / 97.5.
  * randomisation p-values: relabel the correct-letter / is-(a) label across
    ITEMS (all 4 model cells of an item move together), model marginals fixed.
"""
import json, random, math, collections, sys

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
B = 20000
SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 20260731

rows = json.load(open(PATH))
MODELS = sorted(set(r["model"] for r in rows))
for r in rows:
    r["d"] = r["B_correct"] - r["A_correct"]
    r["is_a"] = (r["correct_letter"] == "a")

N = len(rows)


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def quantile(s, q):
    if not s:
        return float("nan")
    p = q * (len(s) - 1)
    lo, hi = int(math.floor(p)), int(math.ceil(p))
    return s[lo] if lo == hi else s[lo] + (s[hi] - s[lo]) * (p - lo)


def ci(v):
    s = sorted(x for x in v if x == x)
    return quantile(s, .025), quantile(s, .975)


def hd(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


# ----------------------------------------------------------------- estimands
def stats_of(rs):
    """All quantities in the claim, recomputed from a (possibly resampled) cell list."""
    o = {}
    n = len(rs)
    o["raw"] = 100 * mean(r["d"] for r in rs)

    a = [r["d"] for r in rs if r["is_a"]]
    b = [r["d"] for r in rs if not r["is_a"]]
    o["d_a"] = 100 * mean(a) if a else float("nan")
    o["d_bcd"] = 100 * mean(b) if b else float("nan")
    o["artifact"] = o["d_a"] - o["d_bcd"]
    o["w_a"] = len(a) / n

    # --- primary counterfactual: model-specific b/c/d donor -----------------
    don = {}
    for m in MODELS:
        v = [r["d"] for r in rs if r["model"] == m and not r["is_a"]]
        don[m] = mean(v) if v else float("nan")
    tot = 0.0
    ok = True
    for r in rs:
        if r["is_a"]:
            dv = don[r["model"]]
            if dv != dv:
                ok = False
                break
            tot += dv
        else:
            tot += r["d"]
    o["cf"] = 100 * tot / n if ok else float("nan")
    o["attrib"] = o["raw"] - o["cf"]
    o["share"] = o["attrib"] / o["raw"] if o["raw"] else float("nan")

    # --- pooled (non-model-specific) donor, for the exact-decomposition check
    o["cf_pooled_donor"] = (1 - o["w_a"]) * o["d_bcd"] + o["w_a"] * o["d_bcd"]
    o["attrib_identity"] = o["w_a"] * o["artifact"]

    # --- "just drop the (a) cells" -- what the exclusion actually did -------
    o["drop_a"] = o["d_bcd"]

    # --- analysis-set delta (the published primary estimand) ----------------
    inc = [r["d"] for r in rs if r["analysis_include"]]
    o["analysis"] = 100 * mean(inc) if inc else float("nan")
    o["share_vs_analysis"] = o["attrib"] / o["analysis"] if inc and o["analysis"] else float("nan")

    # --- per-model pieces ---------------------------------------------------
    for m in MODELS:
        am = [r["d"] for r in rs if r["model"] == m and r["is_a"]]
        bm = [r["d"] for r in rs if r["model"] == m and not r["is_a"]]
        o["art_" + m] = (100 * mean(am) - 100 * mean(bm)) if am and bm else float("nan")
    return o


point = stats_of(rows)

hd("0. SHAPE / BOOKKEEPING (independent of the claim)")
print(f"cells                       {N}")
print(f"items                       {len(set(r['question_id'] for r in rows))}")
print(f"clusters                    {len(set(r['cluster'] for r in rows))}")
print(f"cells with correct_letter=a  {sum(1 for r in rows if r['is_a'])}"
      f"   (items: {len(set(r['question_id'] for r in rows if r['is_a']))})")
print(f"w_a = n_a/N                 {point['w_a']:.6f}   claim says 364/1691 = {364/1691:.6f}")
print(f"cells per model             " +
      ", ".join(f"{m.split('/')[-1]}={sum(1 for r in rows if r['model']==m)}" for m in MODELS))
print(f"(a) cells per model         " +
      ", ".join(f"{m.split('/')[-1]}={sum(1 for r in rows if r['model']==m and r['is_a'])}" for m in MODELS))
print(f"b/c/d cells per model       " +
      ", ".join(f"{m.split('/')[-1]}={sum(1 for r in rows if r['model']==m and not r['is_a'])}" for m in MODELS))

hd("1. POINT ESTIMATES -- recomputed from scratch")
print(f"raw pooled delta (all {N} cells)          {point['raw']:+9.4f} pp    [claim: -17.33]")
print(f"delta | correct letter = a  (n={sum(1 for r in rows if r['is_a'])})       {point['d_a']:+9.4f} pp")
print(f"delta | correct letter in b,c,d (n={sum(1 for r in rows if not r['is_a'])})  {point['d_bcd']:+9.4f} pp")
print(f"artifact  delta(a) - delta(bcd)            {point['artifact']:+9.4f} pp    [claim: -7.3271]")
print()
print(f"COUNTERFACTUAL pooled delta                {point['cf']:+9.4f} pp    [claim: -15.7502]")
print(f"ATTRIBUTABLE  raw - cf                     {point['attrib']:+9.4f} pp    [claim: -1.5768]")
print(f"SHARE of raw  attrib/raw                   {point['share']:9.4f}       [claim:  0.0910]")
print()
print(f"identity check  w_a*(d_a - d_bcd)          {point['attrib_identity']:+9.4f} pp    "
      f"[claim: 0.2153*-7.3271 = -1.5772]")
print(f"  discrepancy vs model-specific-donor attrib: "
      f"{point['attrib'] - point['attrib_identity']:+.6f} pp "
      f"(nonzero only because glm-5.2 has 331 b/c/d cells, not 332)")

hd("2. IS THE 'COUNTERFACTUAL' ANYTHING OTHER THAN delta(b,c,d)?")
print(f"counterfactual pooled delta (model-specific donor)  {point['cf']:+9.4f} pp")
print(f"delta on the b/c/d cells alone (= exclusion result) {point['drop_a']:+9.4f} pp")
print(f"difference                                          {point['cf']-point['drop_a']:+9.6f} pp")
print("-> substituting a subgroup's values with another subgroup's mean makes the")
print("   pooled mean equal that other subgroup's mean, exactly, whenever the donor")
print("   is computed on the same partition used for the weights. The model-specific")
print("   donor introduces only a rounding-scale difference here.")
print()
print(f"published primary estimand: delta on analysis_include cells (n=1299)  "
      f"{point['analysis']:+9.4f} pp")
print(f"attrib as share of the PUBLISHED delta                                "
      f"{point['share_vs_analysis']:9.4f}")

hd("3. PER-MODEL ARTIFACT (donor preserves model main effects -- verify)")
for m in MODELS:
    am = [r["d"] for r in rows if r["model"] == m and r["is_a"]]
    bm = [r["d"] for r in rows if r["model"] == m and not r["is_a"]]
    print(f"{m:<28} d(a)={100*mean(am):+7.2f}  d(bcd)={100*mean(bm):+7.2f}  "
          f"artifact={point['art_'+m]:+7.2f}")

# ------------------------------------------------------------ cluster bootstrap
by_cluster = collections.defaultdict(list)
for r in rows:
    by_cluster[r["cluster"]].append(r)
clusters = list(by_cluster.values())
K = len(clusters)

rng = random.Random(SEED)
boot = collections.defaultdict(list)
for _ in range(B):
    samp = []
    for _ in range(K):
        samp.extend(clusters[rng.randrange(K)])
    s = stats_of(samp)
    for k in ("raw", "cf", "attrib", "share", "artifact", "d_a", "d_bcd",
              "drop_a", "analysis", "share_vs_analysis", "attrib_identity"):
        boot[k].append(s[k])

hd(f"4. CLUSTER BOOTSTRAP ({B} replicates, {K} clusters, seed {SEED}, "
   f"substitution recomputed inside each replicate)")


def rep(k, lab, f="{:+.4f}"):
    lo, hi = ci(boot[k])
    print(f"{lab:<44}{f.format(point[k]):>10}   95% CI [{f.format(lo)}, {f.format(hi)}]")


rep("raw", "raw pooled delta")
rep("cf", "counterfactual pooled delta")
rep("attrib", "attributable to construction defect")
rep("share", "share of raw delta", "{:.4f}")
rep("artifact", "artifact delta(a)-delta(bcd)")
rep("d_a", "delta | a")
rep("d_bcd", "delta | b,c,d")
rep("analysis", "published analysis-set delta (n=1299)")
rep("share_vs_analysis", "attrib / published delta", "{:.4f}")

# how often does the bootstrap put the attributable share above thresholds?
sh = [x for x in boot["share"] if x == x]
for t in (0.0, 0.10, 0.15, 0.20, 0.25):
    print(f"  P*(share > {t:.2f}) = {sum(1 for x in sh if x > t)/len(sh):.4f}")

# ---------------------------------------------------- randomisation test on artifact
hd("5. RANDOMISATION TEST -- is the (a)-vs-(bcd) gap distinguishable from noise?")
by_item = collections.defaultdict(list)
for r in rows:
    by_item[r["question_id"]].append(r)
item_ids = list(by_item)
n_a_items = sum(1 for q in item_ids if by_item[q][0]["is_a"])


def artifact_from_labels(lab):
    sa = sb = 0.0
    na = nb = 0
    for q in item_ids:
        g = lab[q]
        for r in by_item[q]:
            if g:
                sa += r["d"]; na += 1
            else:
                sb += r["d"]; nb += 1
    return 100 * sa / na - 100 * sb / nb


obs = point["artifact"]
rngp = random.Random(SEED + 101)
NP = 20000
cnt = 0
for _ in range(NP):
    sh_ids = item_ids[:]
    rngp.shuffle(sh_ids)
    lab = {q: (i < n_a_items) for i, q in enumerate(sh_ids)}
    if artifact_from_labels(lab) <= obs:      # one-sided: (a) worse than (bcd)
        cnt += 1
print(f"observed artifact {obs:+.4f} pp; one-sided randomisation p = {(cnt+1)/(NP+1):.5g}")
print(f"  [{NP} reassignments of the 91 (a) labels across the 423 items; all 4 model")
print("   cells of an item move together, so within-item dependence is preserved]")

json.dump({k: {"point": point[k], "ci": ci(boot[k])} for k in
           ("raw", "cf", "attrib", "share", "artifact", "d_a", "d_bcd", "analysis",
            "share_vs_analysis")},
          open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
               "experiment-31-07-26/analysis/sens_refute_position_cf_out.json", "w"), indent=1)
print("\nwrote sens_refute_position_cf_out.json")

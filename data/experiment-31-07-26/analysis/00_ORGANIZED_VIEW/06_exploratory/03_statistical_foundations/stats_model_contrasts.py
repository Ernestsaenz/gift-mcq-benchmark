#!/usr/bin/env python3
"""
Precision for the SMALLER effects this design also invites: pairwise between-model
differences in the A->B drop. Because the same 325 items are answered by all 4 models,
these contrasts are themselves paired at the item level, which helps.

Contrast_ij = RD_i - RD_j = mean over items of (d_i - d_j), d = B_correct - A_correct.
CI by the same cluster bootstrap (resample the 208 clusters with replacement, 10000 reps).
MDE = (z.975 + z.80) * cluster-bootstrap SE.
"""
import json, math, random, statistics
from collections import defaultdict

random.seed(31071977)
Z975, Z80 = 1.959963984540054, 0.8416212335729143
PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
REPS = 10000

rows = [r for r in json.load(open(PATH)) if r["analysis_include"]]
MODELS = sorted(set(r["model"] for r in rows))

# cluster -> item -> model -> d
clu = defaultdict(lambda: defaultdict(dict))
for r in rows:
    clu[r["cluster"]][r["question_id"]][r["model"]] = r["B_correct"] - r["A_correct"]
keys = list(clu.keys())
K = len(keys)
pools = [list(clu[k].values()) for k in keys]   # list of {model: d} per item

def contrast(items, mi, mj):
    """mean(d_i - d_j) over items having both models."""
    tot = 0; n = 0
    for it in items:
        if mi in it and mj in it:
            tot += it[mi] - it[mj]; n += 1
    return (tot / n if n else float("nan")), n

all_items = [it for p in pools for it in p]
print("=" * 100)
print("PAIRWISE MODEL CONTRASTS in the A->B drop (item-paired), cluster bootstrap "
      f"{REPS} reps, seed 31071977")
print("=" * 100)
print(f"{'contrast (RD_i - RD_j)':<58}{'est':>9}{'95% CI':>22}{'SE':>8}{'MDE80':>8}")

# per-model RD for reference
rd_model = {}
for m in MODELS:
    v = [it[m] for it in all_items if m in it]
    rd_model[m] = sum(v) / len(v)

results = {}
for a in range(len(MODELS)):
    for b in range(a + 1, len(MODELS)):
        mi, mj = MODELS[a], MODELS[b]
        est, n = contrast(all_items, mi, mj)
        draws = []
        for _ in range(REPS):
            items = []
            for _ in range(K):
                items.extend(pools[random.randrange(K)])
            e, _ = contrast(items, mi, mj)
            if e == e: draws.append(e)
        draws.sort()
        lo = draws[int(0.025 * (len(draws) - 1))]
        hi = draws[int(0.975 * (len(draws) - 1))]
        se = statistics.pstdev(draws)
        mde = (Z975 + Z80) * se
        frac = sum(1 for x in draws if x >= 0) / len(draws)
        p = min(1.0, 2 * min(frac, 1 - frac))
        name = f"{mi.split('/')[-1]} - {mj.split('/')[-1]} (n={n})"
        results[name] = dict(est=est, lo=lo, hi=hi, se=se, mde=mde, p=p, n=n)
        print(f"{name:<58}{100*est:>8.2f}p[{100*lo:>7.2f},{100*hi:>7.2f}]pp"
              f"{100*se:>8.2f}{100*mde:>8.2f}   p_boot={p:.4f}")

print(f"\nper-model RD for reference: " +
      "  ".join(f"{m.split('/')[-1]}={100*rd_model[m]:.2f}pp" for m in MODELS))
spread = max(rd_model.values()) - min(rd_model.values())
print(f"observed spread across models = {100*spread:.2f} pp")
mdes = [v["mde"] for v in results.values()]
print(f"MDE for a pairwise model contrast: {100*min(mdes):.2f} - {100*max(mdes):.2f} pp "
      f"(median {100*statistics.median(mdes):.2f} pp)")
sig = sum(1 for v in results.values() if v["lo"] * v["hi"] > 0)
print(f"{sig}/{len(results)} pairwise contrasts have a CI excluding 0")
json.dump(results, open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
                        "experiment-31-07-26/analysis/stats_model_contrasts_out.json", "w"),
          indent=1)
print("[wrote stats_model_contrasts_out.json]")

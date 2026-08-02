#!/usr/bin/env python3
"""
sens_loo_models.py -- how much does each MODEL drive the pooled delta?
  * per-model delta with cluster bootstrap 95% CI
  * leave-one-model-out pooled delta with its own cluster bootstrap CI
  * heterogeneity test across models: permute the model label WITHIN each item
    (the 3-4 cells of an item are exchangeable under H0: no model effect on B-A),
    statistic = max-min of the four per-model deltas. 20000 permutations.
Stdlib only.
"""
import json, collections, random, math

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
ALL = [r for r in json.load(open(PATH)) if r["analysis_include"]]
MODELS = sorted(set(r["model"] for r in ALL))

def delta(cells):
    n = len(cells)
    return 100.0 * sum(c["B_correct"] - c["A_correct"] for c in cells) / n, n

def boot(cells, B=20000, seed=31072026):
    by = collections.defaultdict(list)
    for c in cells: by[c["cluster"]].append(c)
    g = [(sum(x["B_correct"] - x["A_correct"] for x in v), len(v)) for v in by.values()]
    K = len(g); rnd = random.Random(seed); out = []
    for _ in range(B):
        s = n = 0
        for _ in range(K):
            a, b = g[rnd.randrange(K)]; s += a; n += b
        out.append(100.0 * s / n)
    out.sort()
    return out[int(0.025 * B)], out[int(0.975 * B) - 1]

d0, n0 = delta(ALL)
print(f"pooled delta = {d0:+.4f} pp on {n0} cells")
lo, hi = boot(ALL); print(f"  cluster bootstrap 95% CI = [{lo:+.3f}, {hi:+.3f}]")

print("\nper-model delta (cluster bootstrap 95% CI, 20000 reps):")
for m in MODELS:
    sub = [c for c in ALL if c["model"] == m]
    d, n = delta(sub); l, h = boot(sub)
    flips_down = sum(1 for c in sub if c["A_correct"] == 1 and c["B_correct"] == 0)
    flips_up = sum(1 for c in sub if c["A_correct"] == 0 and c["B_correct"] == 1)
    a_corr = sum(c["A_correct"] for c in sub)
    print(f"  {m:>26} n={n:>4} delta={d:+7.3f} [{l:+7.3f},{h:+7.3f}]  "
          f"A-correct={a_corr:>3}  1->0 flips={flips_down:>3} "
          f"(={100.0*flips_down/a_corr:5.1f}% of its A-correct items)  0->1={flips_up}")

print("\nleave-one-model-out pooled delta (cluster bootstrap 95% CI, 20000 reps):")
for m in MODELS:
    sub = [c for c in ALL if c["model"] != m]
    d, n = delta(sub); l, h = boot(sub)
    print(f"  drop {m:>26} -> delta={d:+7.4f} [{l:+7.3f},{h:+7.3f}] "
          f"shift={d-d0:+7.4f} pp  (n={n})")

# heterogeneity: permute model labels within item
by_item = collections.defaultdict(list)
for c in ALL: by_item[c["question_id"]].append(c)
def spread(assign):
    agg = collections.defaultdict(lambda: [0, 0])
    for (mlab, dv) in assign:
        agg[mlab][0] += dv; agg[mlab][1] += 1
    ds = [100.0 * s / n for s, n in agg.values()]
    return max(ds) - min(ds)

base = [(c["model"], c["B_correct"] - c["A_correct"]) for c in ALL]
obs = spread(base)
rnd = random.Random(11)
B = 20000; ge = 0
items = list(by_item.values())
for _ in range(B):
    perm = []
    for grp in items:
        labs = [c["model"] for c in grp]
        dvs = [c["B_correct"] - c["A_correct"] for c in grp]
        rnd.shuffle(dvs)
        perm.extend(zip(labs, dvs))
    if spread(perm) >= obs - 1e-12: ge += 1
p = (1 + ge) / (1 + B)
print(f"\nmodel heterogeneity in delta: observed max-min = {obs:.3f} pp; "
      f"within-item label permutation p = {p:.5f} ({B} perms)")

# gemini vs the other three
gem = [c for c in ALL if c["model"] == "google/gemini-3.6-flash"]
oth = [c for c in ALL if c["model"] != "google/gemini-3.6-flash"]
dg, _ = delta(gem); do, _ = delta(oth)
print(f"gemini delta={dg:+.3f} vs other-3 pooled delta={do:+.3f}  gap={dg-do:+.3f} pp")
# paired within-item permutation for that contrast
obs2 = dg - do
ge2 = 0
rnd2 = random.Random(12)
for _ in range(B):
    sg = ng = so = no = 0
    for grp in items:
        dvs = [c["B_correct"] - c["A_correct"] for c in grp]
        rnd2.shuffle(dvs)
        labs = [c["model"] for c in grp]
        for lab, dv in zip(labs, dvs):
            if lab == "google/gemini-3.6-flash": sg += dv; ng += 1
            else: so += dv; no += 1
    if abs(100.0 * sg / ng - 100.0 * so / no) >= abs(obs2) - 1e-12: ge2 += 1
print(f"  within-item permutation p for gemini-vs-rest = {(1+ge2)/(1+B):.5f}")

# equal-weight-by-model estimate (model-average instead of cell-pool)
per = []
for m in MODELS:
    sub = [c for c in ALL if c["model"] == m]
    per.append(delta(sub)[0])
print(f"\nunweighted mean of the 4 per-model deltas = {sum(per)/len(per):+.4f} pp "
      f"(vs cell-pooled {d0:+.4f}); sd across models = "
      f"{math.sqrt(sum((x-sum(per)/len(per))**2 for x in per)/(len(per)-1)):.3f} pp")

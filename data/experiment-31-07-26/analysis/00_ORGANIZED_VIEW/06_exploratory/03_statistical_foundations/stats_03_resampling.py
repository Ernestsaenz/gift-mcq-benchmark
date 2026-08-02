"""Step 3: resampling candidates.
  (g) cluster bootstrap on the paired difference  (+ item bootstrap, + naive cell bootstrap)
  (h) permutation / randomisation of the A|B label at three exchangeability units:
        cell-level, item-level, cluster-level, model-level
Everything Monte-Carlo with a fixed seed; analytic null SDs given where they exist.
"""
import sys, math, random
from collections import defaultdict
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from stats_lib import *

random.seed(20260731)
rows = load()
models = sorted({r["model"] for r in rows})
MSHORT = {m: m.split("/")[-1] for m in models}

# d = B_correct - A_correct per cell
for r in rows:
    r["d"] = r["B_correct"] - r["A_correct"]

by_cluster = group(rows, lambda r: r["cluster"])
by_item = group(rows, lambda r: r["question_id"])
clusters = sorted(by_cluster)
items = sorted(by_item)

obs_delta = mean([r["d"] for r in rows])
print("observed pooled delta (mean d) = %+.6f" % obs_delta)

# ------------------------------------------------------------------ BOOTSTRAP
B = 20000

def boot(units_map, unit_keys, label, statfn):
    """Nonparametric bootstrap resampling whole units with replacement."""
    keys = list(unit_keys)
    K = len(keys)
    cache = {k: units_map[k] for k in keys}
    out = []
    for _ in range(B):
        sample = []
        for _ in range(K):
            sample.extend(cache[keys[random.randrange(K)]])
        out.append(statfn(sample))
    out.sort()
    m = mean(out)
    sd = math.sqrt(sum((x - m) ** 2 for x in out) / (len(out) - 1))
    lo, hi = quantile(out, 0.025), quantile(out, 0.975)
    print("%-22s B=%d  boot mean %+0.5f  SE %.5f  95%% pct CI [%+0.5f, %+0.5f]  width %.5f"
          % (label, B, m, sd, lo, hi, hi - lo))
    return out, sd, lo, hi

def stat_delta(sample):
    return sum(r["d"] for r in sample) / len(sample)

print("\n=== (g) BOOTSTRAP on pooled delta, three resampling units ===")
cellmap = {i: [r] for i, r in enumerate(rows)}
b_cell, sd_cell, _, _ = boot(cellmap, list(cellmap), "cell bootstrap", stat_delta)
b_item, sd_item, _, _ = boot(by_item, items, "item bootstrap", stat_delta)
b_clu, sd_clu, lo_clu, hi_clu = boot(by_cluster, clusters, "CLUSTER bootstrap", stat_delta)
print("SE inflation: item/cell = %.3f ; cluster/cell = %.3f ; cluster/item = %.3f"
      % (sd_item / sd_cell, sd_clu / sd_cell, sd_clu / sd_item))
print("implied design effect (variance ratio) cluster vs cell = %.3f" % ((sd_clu / sd_cell) ** 2))
print("analytic paired (McNemar) SE ignoring clustering = %.5f"
      % (math.sqrt(292 - (247 - 45) ** 2 / 1299) / 1299))

# per-model deltas under the cluster bootstrap (same resampled clusters -> keeps models comparable)
print("\n--- cluster bootstrap, per-model deltas and cross-model range (joint resample) ---")
percm = {m: [] for m in models}
rng_boot = []
Kc = len(clusters)
cl_cache = {k: by_cluster[k] for k in clusters}
for _ in range(B):
    sample = []
    for _ in range(Kc):
        sample.extend(cl_cache[clusters[random.randrange(Kc)]])
    acc = {m: [0, 0] for m in models}
    for r in sample:
        a = acc[r["model"]]
        a[0] += r["d"]; a[1] += 1
    ds = {}
    for m in models:
        s, n = acc[m]
        ds[m] = s / n if n else float("nan")
        percm[m].append(ds[m])
    rng_boot.append(max(ds.values()) - min(ds.values()))
for m in models:
    v = sorted(percm[m])
    mm = mean(v)
    sd = math.sqrt(sum((x - mm) ** 2 for x in v) / (len(v) - 1))
    print("%-22s delta=%+0.4f  bootSE %.5f  95%% CI [%+0.4f, %+0.4f]"
          % (MSHORT[m], mean([r["d"] for r in rows if r["model"] == m]), sd,
             quantile(v, 0.025), quantile(v, 0.975)))
rng_boot.sort()
obs_rng = (max(mean([r["d"] for r in rows if r["model"] == m]) for m in models)
           - min(mean([r["d"] for r in rows if r["model"] == m]) for m in models))
print("cross-model range of delta: observed %.4f ; cluster-boot 95%% CI [%.4f, %.4f]"
      % (obs_rng, quantile(rng_boot, 0.025), quantile(rng_boot, 0.975)))

# pairwise: does gemini differ from the other three? (paired by item, cluster bootstrap)
print("\n--- cluster bootstrap on DIFFERENCE-OF-DELTAS (gemini minus each other model) ---")
gem = "google/gemini-3.6-flash"
for m in models:
    if m == gem:
        continue
    diffs = [percm[gem][i] - percm[m][i] for i in range(B)]
    diffs.sort()
    obs = (mean([r["d"] for r in rows if r["model"] == gem])
           - mean([r["d"] for r in rows if r["model"] == m]))
    lo, hi = quantile(diffs, 0.025), quantile(diffs, 0.975)
    # two-sided bootstrap p by CI inversion (proportion of draws on the other side of 0, x2)
    pr = sum(1 for x in diffs if x <= 0) / len(diffs)
    p2 = min(1.0, 2 * min(pr, 1 - pr))
    print("gemini - %-22s obs %+0.4f  95%% CI [%+0.4f, %+0.4f]  boot p=%.4f"
          % (MSHORT[m], obs, lo, hi, p2))

# ---------------------------------------------------------------- PERMUTATION
print("\n=== (h) PERMUTATION of the A/B label, four exchangeability units ===")
NPERM = 50000

def signflip(units, label, exact_sd_note=""):
    """T = mean(d) with the A/B label flipped as a block within each unit."""
    sums = [sum(r["d"] for r in u) for u in units]
    ntot = sum(len(u) for u in units)
    obs = sum(sums) / ntot
    # analytic null: E[T]=0, Var[T] = sum(S_g^2)/n^2  (each s_g = +-1 w.p. 1/2)
    var = sum(s * s for s in sums) / (ntot ** 2)
    sd = math.sqrt(var)
    z = obs / sd
    p_norm = two_sided_z_p(z)
    ge = 0
    for _ in range(NPERM):
        t = 0.0
        for s in sums:
            t += s if random.random() < 0.5 else -s
        if abs(t / ntot) >= abs(obs) - 1e-12:
            ge += 1
    p_mc = (ge + 1) / (NPERM + 1)
    print("%-26s units=%5d  null SD %.5f  z %8.3f  p(normal) %10.3e  p(MC,%d) %.5f %s"
          % (label, len(units), sd, z, p_norm, NPERM, p_mc, exact_sd_note))
    return sd, z, p_mc

u_cell = [[r] for r in rows]
u_item = [by_item[q] for q in items]
u_clu = [by_cluster[c] for c in clusters]
u_mod = [[r for r in rows if r["model"] == m] for m in models]

sd_p_cell, _, _ = signflip(u_cell, "cell-level flip", "<- equals McNemar null")
sd_p_item, _, _ = signflip(u_item, "item-level flip (4 models)")
sd_p_clu, _, _ = signflip(u_clu, "CLUSTER-level flip")
sd_p_mod, _, _ = signflip(u_mod, "model-level flip (k=4)", "<- floor p = 2/2^4 = 0.125")
print("null-SD inflation vs cell-level: item %.3f  cluster %.3f  model %.3f"
      % (sd_p_item / sd_p_cell, sd_p_clu / sd_p_cell, sd_p_mod / sd_p_cell))
print("cell-level analytic null SD = sqrt(n_disc)/n = %.5f (matches above)"
      % (math.sqrt(292) / 1299))

# exhaustive enumeration for the model-level flip: only 2^4 = 16 assignments
sums_m = [sum(r["d"] for r in u) for u in u_mod]
ntot = len(rows)
obs = sum(sums_m) / ntot
import itertools
cnt = 0
for signs in itertools.product([1, -1], repeat=4):
    t = sum(s * v for s, v in zip(signs, sums_m)) / ntot
    if abs(t) >= abs(obs) - 1e-12:
        cnt += 1
print("model-level flip EXHAUSTIVE (16 assignments): p = %d/16 = %.4f" % (cnt, cnt / 16))

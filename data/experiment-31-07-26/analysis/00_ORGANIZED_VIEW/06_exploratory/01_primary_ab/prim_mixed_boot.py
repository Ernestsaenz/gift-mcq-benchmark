"""Part 2: cluster bootstrap, exchangeability permutation test for the
interaction, and a random-intercept GLMM fitted by adaptive-free Gauss-Hermite
quadrature with analytic gradients + hand-rolled BFGS. Stdlib only.
"""
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prim_linalg import (irls_logit, cluster_robust_vcov, model_based_vcov,
                         chisq_sf, two_sided_z_p, quad_form, solve_sym,
                         gauss_hermite, chol, chol_inv)

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
SHORT = {"google/gemini-3.6-flash": "gemini-3.6-flash",
         "google/gemma-4-26b-a4b-it": "gemma-4-26b-a4b-it",
         "qwen/qwen3.6-35b-a3b": "qwen3.6-35b-a3b",
         "z-ai/glm-5.2": "glm-5.2"}
REF = MODELS[0]

out = []
def P(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    out.append(s)

raw = json.load(open(os.path.join(HERE, "paired_clean.json")))
cells = [r for r in raw if r.get("analysis_include") is True]
long = []
for r in cells:
    for cond, key in ((0, "A_correct"), (1, "B_correct")):
        long.append({"y": int(r[key]), "cond": cond, "model": r["model"],
                     "item": r["question_id"], "cluster": r["cluster"]})

# ===================================================================
# 1. CLUSTER BOOTSTRAP (resample the 208 clinical-context clusters)
# ===================================================================
P("=" * 78)
P("CLUSTER BOOTSTRAP: resample 208 clinical clusters with replacement,")
P("refit the saturated model (iii), B=4000 replicates, seed=20260731")
P("=" * 78)

by_cluster = {}
for r in cells:
    by_cluster.setdefault(r["cluster"], []).append(r)
cluster_list = sorted(by_cluster)


def cell_counts(rows):
    """counts[model] = [nA, kA, nB, kB]"""
    c = {m: [0, 0, 0, 0] for m in MODELS}
    for r in rows:
        v = c[r["model"]]
        v[0] += 1
        v[1] += r["A_correct"]
        v[2] += 1
        v[3] += r["B_correct"]
    return c


def contrasts(c, corr=0.0):
    """per-model condition log-odds (B vs A) and risk differences."""
    lo, rd = {}, {}
    for m in MODELS:
        nA, kA, nB, kB = c[m]
        pA = (kA + corr) / (nA + 2 * corr) if nA else float("nan")
        pB = (kB + corr) / (nB + 2 * corr) if nB else float("nan")
        lo[m] = (math.log(pB / (1 - pB)) - math.log(pA / (1 - pA))
                 if 0 < pA < 1 and 0 < pB < 1 else None)
        rd[m] = pB - pA
    return lo, rd


obs_counts = cell_counts(cells)
obs_lo, obs_rd = contrasts(obs_counts)
P("\nobserved per-model condition contrasts (point estimates, saturated cells):")
for m in MODELS:
    nA, kA, nB, kB = obs_counts[m]
    P("  %-20s A %d/%d=%.4f  B %d/%d=%.4f  logOR=%+.4f  riskdiff=%+.4fpp"
      % (SHORT[m], kA, nA, kA / nA, kB, nB, kB / nB, obs_lo[m], 100 * obs_rd[m]))

random.seed(20260731)
B = 4000
boot_lo = {m: [] for m in MODELS}
boot_rd = {m: [] for m in MODELS}
boot_avg_lo, boot_avg_rd, boot_pool_lo = [], [], []
n_corrected = 0
for b in range(B):
    samp = []
    for _ in range(len(cluster_list)):
        samp.extend(by_cluster[cluster_list[random.randrange(len(cluster_list))]])
    c = cell_counts(samp)
    ok = all(0 < c[m][1] < c[m][0] and 0 < c[m][3] < c[m][2] for m in MODELS)
    lo, rd = contrasts(c, 0.0 if ok else 0.5)
    if not ok:
        n_corrected += 1
    for m in MODELS:
        boot_lo[m].append(lo[m])
        boot_rd[m].append(rd[m])
    boot_avg_lo.append(sum(lo[m] for m in MODELS) / 4.0)
    boot_avg_rd.append(sum(rd[m] for m in MODELS) / 4.0)
    tA = sum(c[m][1] for m in MODELS) / sum(c[m][0] for m in MODELS)
    tB = sum(c[m][3] for m in MODELS) / sum(c[m][2] for m in MODELS)
    boot_pool_lo.append(math.log(tB / (1 - tB)) - math.log(tA / (1 - tA)))
P("\n  replicates needing a 0.5 continuity correction (empty/full cell): %d/%d"
  % (n_corrected, B))


def sd(v):
    m = sum(v) / len(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))


def pctl(v, q):
    s = sorted(v)
    i = q * (len(s) - 1)
    lo_i = int(math.floor(i))
    hi_i = min(lo_i + 1, len(s) - 1)
    return s[lo_i] + (i - lo_i) * (s[hi_i] - s[lo_i])


pooled_lo = (math.log(sum(r["B_correct"] for r in cells) / len(cells)
                      / (1 - sum(r["B_correct"] for r in cells) / len(cells)))
             - math.log(sum(r["A_correct"] for r in cells) / len(cells)
                        / (1 - sum(r["A_correct"] for r in cells) / len(cells))))
P("\n  pooled condition log-odds (= model (i) condB): %+.4f" % pooled_lo)
P("  bootstrap SE=%.4f  95%% percentile CI [%+.4f, %+.4f]  OR CI [%.4f, %.4f]"
  % (sd(boot_pool_lo), pctl(boot_pool_lo, .025), pctl(boot_pool_lo, .975),
     math.exp(pctl(boot_pool_lo, .025)), math.exp(pctl(boot_pool_lo, .975))))

obs_avg_lo = sum(obs_lo[m] for m in MODELS) / 4.0
P("\n  equal-weight AVERAGE per-model condition log-odds: %+.4f" % obs_avg_lo)
P("  bootstrap SE=%.4f  95%% percentile CI [%+.4f, %+.4f]  OR=%.4f [%.4f, %.4f]"
  % (sd(boot_avg_lo), pctl(boot_avg_lo, .025), pctl(boot_avg_lo, .975),
     math.exp(obs_avg_lo), math.exp(pctl(boot_avg_lo, .025)),
     math.exp(pctl(boot_avg_lo, .975))))

P("\n  per-model bootstrap SEs / 95% percentile CIs for the condition log-odds:")
for m in MODELS:
    v = boot_lo[m]
    P("    %-20s b=%+.4f SE_boot=%.4f CI [%+.4f, %+.4f]  OR=%.3f [%.3f, %.3f]"
      % (SHORT[m], obs_lo[m], sd(v), pctl(v, .025), pctl(v, .975),
         math.exp(obs_lo[m]), math.exp(pctl(v, .025)), math.exp(pctl(v, .975))))

# bootstrap Wald test for the 3 interaction contrasts (vs reference model)
P("\n  bootstrap Wald test of the 3 interaction contrasts (vs %s):" % SHORT[REF])
others = [m for m in MODELS if m != REF]
for scale, bootd, obsd in (("log-odds", boot_lo, obs_lo),
                           ("risk-difference", boot_rd, obs_rd)):
    D = [[bootd[m][b] - bootd[REF][b] for m in others] for b in range(B)]
    mu = [sum(D[b][j] for b in range(B)) / B for j in range(3)]
    V = [[sum((D[b][a] - mu[a]) * (D[b][c] - mu[c]) for b in range(B)) / (B - 1)
          for c in range(3)] for a in range(3)]
    est = [obsd[m] - obsd[REF] for m in others]
    x = solve_sym(V, est)
    W = sum(est[i] * x[i] for i in range(3))
    P("    scale=%-16s contrasts=%s" % (scale, ", ".join("%+.4f" % e for e in est)))
    P("    scale=%-16s bootstrap-covariance Wald chi2=%.4f df=3 p=%.4g"
      % (scale, W, chisq_sf(W, 3)))

# ===================================================================
# 2. PERMUTATION TEST for heterogeneity of the condition effect
# ===================================================================
P("\n" + "=" * 78)
P("PERMUTATION TEST: H0 = the within-item A->B change score is exchangeable")
P("across the 4 models. Statistic = sum over models of n_m*(dbar_m - dbar)^2.")
P("Model labels permuted WITHIN each item (item structure preserved).")
P("=" * 78)
by_item = {}
for r in cells:
    by_item.setdefault(r["question_id"], []).append(
        (r["model"], r["B_correct"] - r["A_correct"]))
items = sorted(by_item)


def stat(assign):
    tot = {m: [0, 0.0] for m in MODELS}
    for it in items:
        for m, d in assign[it]:
            tot[m][0] += 1
            tot[m][1] += d
    gn = sum(tot[m][0] for m in MODELS)
    gs = sum(tot[m][1] for m in MODELS)
    gbar = gs / gn
    return sum(tot[m][0] * (tot[m][1] / tot[m][0] - gbar) ** 2 for m in MODELS)


obs_stat = stat(by_item)
P("\n  observed mean within-item change score (B - A) per model:")
for m in MODELS:
    ds = [d for it in items for mm, d in by_item[it] if mm == m]
    P("    %-20s n=%d  mean d = %+.4f (= %+.1f pp)"
      % (SHORT[m], len(ds), sum(ds) / len(ds), 100 * sum(ds) / len(ds)))
P("  observed statistic = %.6f" % obs_stat)

random.seed(913371)
NPERM = 20000
ge = 0
for _ in range(NPERM):
    perm = {}
    for it in items:
        rows = by_item[it]
        ms = [m for m, d in rows]
        ds = [d for m, d in rows]
        random.shuffle(ms)
        perm[it] = list(zip(ms, ds))
    if stat(perm) >= obs_stat - 1e-12:
        ge += 1
p_perm = (ge + 1.0) / (NPERM + 1.0)
P("  permutation p = (%d + 1)/(%d + 1) = %.4f  [%d permutations]"
  % (ge, NPERM, p_perm, NPERM))


json.dump({"log": out}, open(os.path.join(HERE, "prim_mixed_boot_log.json"), "w"))
P("\n[done bootstrap+permutation]")

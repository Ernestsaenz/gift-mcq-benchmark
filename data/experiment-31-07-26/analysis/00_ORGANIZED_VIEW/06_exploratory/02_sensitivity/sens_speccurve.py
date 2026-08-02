"""Specification curve for the A -> B ("Ninguna de las anteriores") paired experiment.

Axes (all fully crossed where coherent):
  exclusion  : primary | defect_only | notaA_only | none                (4)
  outcome    : lenient (unparsed cells dropped) | strict (unparsed = 0)  (2)
  unit       : cell | item | cluster | model                            (4)
  inference  : mcnemar_exact | cluster_bootstrap | permutation | robustSE(logit/OLS)
  pooling    : pooled | separate(4 models, Fisher-combined)             (2)

Conventions, stated once and applied everywhere:
  * ESTIMATE is always the A -> B accuracy risk difference in percentage points,
    delta = acc(B) - acc(A), aggregated at the chosen `unit`.
  * The CLUSTER (clinical-context group) is always the independent resampling /
    permutation unit; `unit` changes only how the point estimate is weighted and,
    for robustSE, what a regression row is.
  * cluster_bootstrap p: nonparametric percentile bootstrap over clusters,
    p = 2*min(F(0), 1-F(0)) using the bootstrap distribution of delta,
    floored at 1/(B+1).
  * permutation p: cluster-level random sign flip of the (A,B) labels,
    p = (1 + #{|delta*| >= |delta_obs|}) / (B+1).
  * mcnemar_exact p: exact two-sided binomial on discordant pairs, Bin(b+c, 1/2).
  * robustSE p: unit=cell -> logistic regression correct ~ arm with a
    cluster-robust sandwich SE, Wald t(G-1); other units -> intercept-only OLS on
    the unit-level paired differences with a cluster-robust SE, t(G-1).
  * pooling=separate: the analysis is run inside each model; the reported estimate
    is the unweighted mean of the 4 model deltas and the reported p is Fisher's
    combination of the 4 model p-values (chi2, df=8). The 4 tests share clusters,
    so Fisher's independence assumption is violated; flagged in the write-up.
"""
import json, os, random, sys, math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sens_speccurve_lib import (
    mcnemar_exact_two_sided, logit_cluster_robust_p,
    ols_intercept_cluster_robust_p, chi2_sf_even,
)

DATA = os.path.join(HERE, "paired_clean.json")
B_BOOT = 10000
B_PERM = 10000
SEED = 20260731

rows = json.load(open(DATA))
MODELS = sorted(set(r["model"] for r in rows))
MIDX = {m: i for i, m in enumerate(MODELS)}
NM = len(MODELS)

# ---------------------------------------------------------------------------
# The one paired cell that the published pipeline DROPPED because arm A never
# parsed (z-ai/glm-5.2 on item b320, 10 consecutive failed_no_answer_found
# attempts; arm B parsed 'd' == key 'd').  Verified directly against
# experiment.sqlite (parsed_answers / logical_calls).
# The "strict" outcome scores that unparsed A response as INCORRECT instead of
# discarding the pair.
_b320 = [r for r in rows if r["question_id"] == "b320"][0]
STRICT_EXTRA = dict(
    question_id="b320", model="z-ai/glm-5.2", cluster=_b320["cluster"],
    correct_letter=_b320["correct_letter"],
    A_correct=0, B_correct=1,
    excl_item_defect=False, excl_nota_position_a=False, analysis_include=True,
)

EXCLUSIONS = {
    "primary":     lambda r: (not r["excl_item_defect"]) and (not r["excl_nota_position_a"]),
    "defect_only": lambda r: not r["excl_item_defect"],
    "notaA_only":  lambda r: not r["excl_nota_position_a"],
    "none":        lambda r: True,
}


def get_rows(exclusion, outcome):
    base = rows + ([STRICT_EXTRA] if outcome == "strict" else [])
    keep = EXCLUSIONS[exclusion]
    return [r for r in base if keep(r)]


# ---------------------------------------------------------------------------
# per-cluster precomputation
# ---------------------------------------------------------------------------
def build(recs):
    """Return (clusters, pooled_agg, model_agg) keyed by cluster.

    pooled_agg[g] = (sA, sB, n, item_diff_sum, n_items, cluster_delta)
    model_agg[g]  = tuple over models of (sA_m, sB_m, n_m, cd_m, has_m)
    """
    bycl = {}
    for r in recs:
        bycl.setdefault(r["cluster"], []).append(r)
    clusters, pooled, permod = [], [], []
    for g in sorted(bycl):
        rs = bycl[g]
        sA = sum(r["A_correct"] for r in rs)
        sB = sum(r["B_correct"] for r in rs)
        n = len(rs)
        byit = {}
        for r in rs:
            byit.setdefault(r["question_id"], []).append(r)
        idiff = 0.0
        for q, qr in byit.items():
            idiff += (sum(x["B_correct"] for x in qr) - sum(x["A_correct"] for x in qr)) / len(qr)
        pooled.append((float(sA), float(sB), float(n), idiff, float(len(byit)), (sB - sA) / n))
        pm = []
        for m in MODELS:
            mr = [r for r in rs if r["model"] == m]
            if mr:
                a = sum(r["A_correct"] for r in mr); b = sum(r["B_correct"] for r in mr)
                pm.append((float(a), float(b), float(len(mr)), (b - a) / len(mr), 1.0))
            else:
                pm.append((0.0, 0.0, 0.0, 0.0, 0.0))
        permod.append(tuple(pm))
        clusters.append(g)
    return clusters, pooled, permod


def stats_from(idx, pooled, permod):
    """Aggregate the six pooled + per-model statistics over a list of cluster slots.

    `idx` is a list of (position, flip) where flip=True swaps the A/B labels.
    Returns dict of point estimates in percentage points.
    """
    sA = sB = n = idsum = nit = cdsum = 0.0
    ncl = 0.0
    mA = [0.0] * NM; mB = [0.0] * NM; mn = [0.0] * NM
    mcd = [0.0] * NM; mhas = [0.0] * NM
    for pos, flip in idx:
        a, b, c, ids, ni, cd = pooled[pos]
        if flip:
            a, b, ids, cd = b, a, -ids, -cd
        sA += a; sB += b; n += c; idsum += ids; nit += ni; cdsum += cd; ncl += 1.0
        pm = permod[pos]
        for j in range(NM):
            ma, mb, mnn, mc, mh = pm[j]
            if flip:
                ma, mb, mc = mb, ma, -mc
            mA[j] += ma; mB[j] += mb; mn[j] += mnn
            mcd[j] += mc; mhas[j] += mh
    out = {}
    out["cell"] = 100.0 * (sB - sA) / n
    out["item"] = 100.0 * idsum / nit
    out["cluster"] = 100.0 * cdsum / ncl
    pm_cell = [100.0 * (mB[j] - mA[j]) / mn[j] if mn[j] else float("nan") for j in range(NM)]
    out["model"] = sum(pm_cell) / NM
    out["_pm_cell"] = pm_cell
    out["_pm_cluster"] = [100.0 * mcd[j] / mhas[j] if mhas[j] else float("nan") for j in range(NM)]
    return out


# ---------------------------------------------------------------------------
def boot_perm_distributions(clusters, pooled, permod, seed):
    K = len(clusters)
    rng = random.Random(seed)
    boot = {k: [] for k in ("cell", "item", "cluster", "model")}
    boot_pm_cell = [[] for _ in range(NM)]
    boot_pm_cluster = [[] for _ in range(NM)]
    rr = rng.randrange
    for _ in range(B_BOOT):
        idx = [(rr(K), False) for _ in range(K)]
        s = stats_from(idx, pooled, permod)
        for k in boot:
            boot[k].append(s[k])
        for j in range(NM):
            boot_pm_cell[j].append(s["_pm_cell"][j])
            boot_pm_cluster[j].append(s["_pm_cluster"][j])
    rng2 = random.Random(seed + 1)
    perm = {k: [] for k in ("cell", "item", "cluster", "model")}
    perm_pm_cell = [[] for _ in range(NM)]
    perm_pm_cluster = [[] for _ in range(NM)]
    rb = rng2.getrandbits
    for _ in range(B_PERM):
        bits = rb(K)
        idx = [(i, bool((bits >> i) & 1)) for i in range(K)]
        s = stats_from(idx, pooled, permod)
        for k in perm:
            perm[k].append(s[k])
        for j in range(NM):
            perm_pm_cell[j].append(s["_pm_cell"][j])
            perm_pm_cluster[j].append(s["_pm_cluster"][j])
    return boot, boot_pm_cell, boot_pm_cluster, perm, perm_pm_cell, perm_pm_cluster


def boot_p(dist):
    B = len(dist)
    lo = sum(1 for x in dist if x < 0) + 0.5 * sum(1 for x in dist if x == 0)
    hi = sum(1 for x in dist if x > 0) + 0.5 * sum(1 for x in dist if x == 0)
    p = 2.0 * min(lo, hi) / B
    return max(p, 1.0 / (B + 1.0))


def boot_ci(dist):
    d = sorted(dist)
    B = len(d)
    return d[int(0.025 * B)], d[min(B - 1, int(0.975 * B))]


def perm_p(dist, obs):
    B = len(dist)
    ge = sum(1 for x in dist if abs(x) >= abs(obs) - 1e-12)
    return (1.0 + ge) / (B + 1.0)


def fisher(ps):
    ps = [min(max(p, 1e-300), 1.0) for p in ps]
    stat = -2.0 * sum(math.log(p) for p in ps)
    return chi2_sf_even(stat, 2 * len(ps))


# ---------------------------------------------------------------------------
results = []
detail = {}
for exclusion in ("primary", "defect_only", "notaA_only", "none"):
    for outcome in ("lenient", "strict"):
        recs = get_rows(exclusion, outcome)
        clusters, pooled, permod = build(recs)
        K = len(clusters)
        obs = stats_from([(i, False) for i in range(K)], pooled, permod)
        n_cells = len(recs)
        n_items = len(set(r["question_id"] for r in recs))
        boot, bpm_cell, bpm_clu, perm, ppm_cell, ppm_clu = boot_perm_distributions(
            clusters, pooled, permod, SEED)

        # ---- discordant pair counts (pooled and per model)
        b_pool = sum(1 for r in recs if r["A_correct"] == 1 and r["B_correct"] == 0)
        c_pool = sum(1 for r in recs if r["A_correct"] == 0 and r["B_correct"] == 1)
        mcn_pool = mcnemar_exact_two_sided(b_pool, c_pool)
        mcn_pm = []
        for m in MODELS:
            mr = [r for r in recs if r["model"] == m]
            bb = sum(1 for r in mr if r["A_correct"] == 1 and r["B_correct"] == 0)
            cc = sum(1 for r in mr if r["A_correct"] == 0 and r["B_correct"] == 1)
            mcn_pm.append(mcnemar_exact_two_sided(bb, cc))

        # ---- logistic w/ cluster-robust SE (pooled and per model)
        y = [r["A_correct"] for r in recs] + [r["B_correct"] for r in recs]
        arm = [0.0] * len(recs) + [1.0] * len(recs)
        cl = [r["cluster"] for r in recs] * 2
        blog, selog, plog = logit_cluster_robust_p(y, arm, cl)
        log_pm = []
        for m in MODELS:
            mr = [r for r in recs if r["model"] == m]
            yy = [r["A_correct"] for r in mr] + [r["B_correct"] for r in mr]
            aa = [0.0] * len(mr) + [1.0] * len(mr)
            cc = [r["cluster"] for r in mr] * 2
            log_pm.append(logit_cluster_robust_p(yy, aa, cc))

        # ---- OLS w/ cluster-robust SE at item / cluster / model unit (pooled)
        byit = {}
        for r in recs:
            byit.setdefault(r["question_id"], []).append(r)
        it_d, it_cl = [], []
        for q, qr in byit.items():
            it_d.append(100.0 * (sum(x["B_correct"] for x in qr) - sum(x["A_correct"] for x in qr)) / len(qr))
            it_cl.append(qr[0]["cluster"])
        _, _, p_item_rob = ols_intercept_cluster_robust_p(it_d, it_cl)
        cl_d = [100.0 * p[5] for p in pooled]
        _, _, p_clu_rob = ols_intercept_cluster_robust_p(cl_d, clusters)
        md = obs["_pm_cell"]
        _, _, p_mod_rob = ols_intercept_cluster_robust_p(md, list(range(NM)))

        # ---- per-model OLS at cluster unit (for pooling=separate)
        rob_clu_pm = []
        for j, m in enumerate(MODELS):
            ds, gs = [], []
            for i in range(K):
                if permod[i][j][4]:
                    ds.append(100.0 * permod[i][j][3]); gs.append(clusters[i])
            rob_clu_pm.append(ols_intercept_cluster_robust_p(ds, gs)[2])

        base = dict(exclusion=exclusion, outcome=outcome, n_cells=n_cells,
                    n_items=n_items, n_clusters=K)

        def add(unit, inference, pooling, est, p, extra=None):
            d = dict(base); d.update(unit=unit, inference=inference, pooling=pooling,
                                     delta_pp=est, p=p)
            if extra:
                d.update(extra)
            results.append(d)

        # ============ pooling = pooled ============
        add("cell", "mcnemar_exact", "pooled", obs["cell"], mcn_pool,
            dict(disc_b=b_pool, disc_c=c_pool))
        add("cell", "cluster_bootstrap", "pooled", obs["cell"], boot_p(boot["cell"]),
            dict(ci=boot_ci(boot["cell"])))
        add("cell", "permutation", "pooled", obs["cell"], perm_p(perm["cell"], obs["cell"]))
        add("cell", "logit_robustSE", "pooled", obs["cell"], plog,
            dict(logOR=blog, se=selog, OR=math.exp(blog)))
        add("item", "cluster_bootstrap", "pooled", obs["item"], boot_p(boot["item"]),
            dict(ci=boot_ci(boot["item"])))
        add("item", "permutation", "pooled", obs["item"], perm_p(perm["item"], obs["item"]))
        add("item", "ols_robustSE", "pooled", obs["item"], p_item_rob)
        add("cluster", "cluster_bootstrap", "pooled", obs["cluster"], boot_p(boot["cluster"]),
            dict(ci=boot_ci(boot["cluster"])))
        add("cluster", "permutation", "pooled", obs["cluster"], perm_p(perm["cluster"], obs["cluster"]))
        add("cluster", "ols_robustSE", "pooled", obs["cluster"], p_clu_rob)
        add("model", "cluster_bootstrap", "pooled", obs["model"], boot_p(boot["model"]),
            dict(ci=boot_ci(boot["model"])))
        add("model", "permutation", "pooled", obs["model"], perm_p(perm["model"], obs["model"]))
        add("model", "ols_robustSE", "pooled", obs["model"], p_mod_rob)

        # ============ pooling = separate (Fisher across 4 models) ============
        est_sep_cell = sum(obs["_pm_cell"]) / NM
        est_sep_clu = sum(obs["_pm_cluster"]) / NM
        add("cell", "mcnemar_exact", "separate", est_sep_cell, fisher(mcn_pm),
            dict(per_model_p=mcn_pm, per_model_delta=obs["_pm_cell"]))
        bp = [boot_p(bpm_cell[j]) for j in range(NM)]
        add("cell", "cluster_bootstrap", "separate", est_sep_cell, fisher(bp),
            dict(per_model_p=bp, per_model_delta=obs["_pm_cell"]))
        pp = [perm_p(ppm_cell[j], obs["_pm_cell"][j]) for j in range(NM)]
        add("cell", "permutation", "separate", est_sep_cell, fisher(pp),
            dict(per_model_p=pp))
        lp = [x[2] for x in log_pm]
        add("cell", "logit_robustSE", "separate", est_sep_cell, fisher(lp),
            dict(per_model_p=lp, per_model_logOR=[x[0] for x in log_pm]))
        bpc = [boot_p(bpm_clu[j]) for j in range(NM)]
        add("cluster", "cluster_bootstrap", "separate", est_sep_clu, fisher(bpc),
            dict(per_model_p=bpc, per_model_delta=obs["_pm_cluster"]))
        ppc = [perm_p(ppm_clu[j], obs["_pm_cluster"][j]) for j in range(NM)]
        add("cluster", "permutation", "separate", est_sep_clu, fisher(ppc),
            dict(per_model_p=ppc))
        add("cluster", "ols_robustSE", "separate", est_sep_clu, fisher(rob_clu_pm),
            dict(per_model_p=rob_clu_pm))

        detail[(exclusion, outcome)] = dict(
            accA=100.0 * sum(r["A_correct"] for r in recs) / len(recs),
            accB=100.0 * sum(r["B_correct"] for r in recs) / len(recs),
            n_cells=n_cells, n_items=n_items, n_clusters=K,
            disc_b=b_pool, disc_c=c_pool,
            per_model_delta=obs["_pm_cell"], per_model_mcnemar=mcn_pm,
            boot_ci_cell=boot_ci(boot["cell"]),
        )
        print(f"done {exclusion}/{outcome}  N={n_cells} K={K} delta_cell={obs['cell']:.3f}", flush=True)

out = dict(
    n_specs=len(results),
    seed=SEED, B_boot=B_BOOT, B_perm=B_PERM,
    results=results,
    detail={f"{k[0]}|{k[1]}": v for k, v in detail.items()},
)
with open(os.path.join(HERE, "sens_speccurve_results.json"), "w") as f:
    json.dump(out, f, indent=1)
print("wrote", len(results), "specifications")

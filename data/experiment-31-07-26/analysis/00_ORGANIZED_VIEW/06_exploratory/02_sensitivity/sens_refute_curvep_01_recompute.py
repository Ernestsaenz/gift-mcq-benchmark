"""INDEPENDENT recomputation of the 160-spec specification curve p-values.

Same documented grid and conventions as sens_speccurve.py, but:
  * different RNG seed and a different stream layout,
  * all statistical primitives from sens_refute_curvep_lib.py (validated in
    sens_refute_curvep_00_validate.py against exact closed forms),
  * every p also carried in log10 so nothing is hidden by double underflow,
  * explicit bookkeeping of which p-values are resolution-FLOORED artefacts.

Grid (20 specs per exclusion x outcome cell, 4 x 2 x 20 = 160):
  pooled  : cell x {mcnemar, boot, perm, logitCR}, item x {boot, perm, olsCR},
            cluster x {boot, perm, olsCR}, model x {boot, perm, olsCR}     = 13
  separate: cell x {mcnemar, boot, perm, logitCR}, cluster x {boot,perm,olsCR} = 7
"""
import json, os, sys, math, random, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sens_refute_curvep_lib as L

DATA = os.path.join(HERE, "paired_clean.json")
B_BOOT = 10000
B_PERM = 10000
SEED = 777333111            # DIFFERENT from the original 20260731

rows = json.load(open(DATA))
MODELS = sorted(set(r["model"] for r in rows))
NM = len(MODELS)

_b320 = [r for r in rows if r["question_id"] == "b320"][0]
STRICT_EXTRA = dict(question_id="b320", model="z-ai/glm-5.2", cluster=_b320["cluster"],
                    correct_letter=_b320["correct_letter"], A_correct=0, B_correct=1,
                    excl_item_defect=False, excl_nota_position_a=False,
                    analysis_include=True)

EXCL = {
    "primary":     lambda r: (not r["excl_item_defect"]) and (not r["excl_nota_position_a"]),
    "defect_only": lambda r: not r["excl_item_defect"],
    "notaA_only":  lambda r: not r["excl_nota_position_a"],
    "none":        lambda r: True,
}


def get_rows(ex, oc):
    base = rows + ([STRICT_EXTRA] if oc == "strict" else [])
    return [r for r in base if EXCL[ex](r)]


def build(recs):
    bycl = {}
    for r in recs:
        bycl.setdefault(r["cluster"], []).append(r)
    clusters, pooled, permod = [], [], []
    for g in sorted(bycl):
        rs = bycl[g]
        sA = float(sum(r["A_correct"] for r in rs))
        sB = float(sum(r["B_correct"] for r in rs))
        n = float(len(rs))
        byit = {}
        for r in rs:
            byit.setdefault(r["question_id"], []).append(r)
        idiff = 0.0
        for q, qr in byit.items():
            idiff += (sum(x["B_correct"] for x in qr) - sum(x["A_correct"] for x in qr)) / len(qr)
        pooled.append((sA, sB, n, idiff, float(len(byit)), (sB - sA) / n))
        pm = []
        for m in MODELS:
            mr = [r for r in rs if r["model"] == m]
            if mr:
                a = float(sum(r["A_correct"] for r in mr))
                b = float(sum(r["B_correct"] for r in mr))
                pm.append((a, b, float(len(mr)), (b - a) / len(mr), 1.0))
            else:
                pm.append((0.0, 0.0, 0.0, 0.0, 0.0))
        permod.append(tuple(pm))
        clusters.append(g)
    return clusters, pooled, permod


def stats_from(idx, pooled, permod):
    sA = sB = n = idsum = nit = cdsum = ncl = 0.0
    mA = [0.0]*NM; mB = [0.0]*NM; mn = [0.0]*NM; mcd = [0.0]*NM; mhas = [0.0]*NM
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
            mA[j] += ma; mB[j] += mb; mn[j] += mnn; mcd[j] += mc; mhas[j] += mh
    out = {}
    out["cell"] = 100.0*(sB-sA)/n
    out["item"] = 100.0*idsum/nit
    out["cluster"] = 100.0*cdsum/ncl
    pmc = [100.0*(mB[j]-mA[j])/mn[j] if mn[j] else float("nan") for j in range(NM)]
    out["model"] = sum(pmc)/NM
    out["_pm_cell"] = pmc
    out["_pm_cluster"] = [100.0*mcd[j]/mhas[j] if mhas[j] else float("nan") for j in range(NM)]
    return out


def boot_p(dist, B):
    lo = sum(1 for x in dist if x < 0) + 0.5*sum(1 for x in dist if x == 0)
    hi = sum(1 for x in dist if x > 0) + 0.5*sum(1 for x in dist if x == 0)
    raw = 2.0*min(lo, hi)/B
    return max(raw, 1.0/(B+1.0)), raw < 1.0/(B+1.0)


def perm_p(dist, obs, B):
    ge = sum(1 for x in dist if abs(x) >= abs(obs) - 1e-12)
    return (1.0+ge)/(B+1.0), (ge == 0)


results = []
percell = {}
for exclusion in ("primary", "defect_only", "notaA_only", "none"):
    for outcome in ("lenient", "strict"):
        recs = get_rows(exclusion, outcome)
        clusters, pooled, permod = build(recs)
        K = len(clusters)
        obs = stats_from([(i, False) for i in range(K)], pooled, permod)

        rng = random.Random(SEED + 17*(abs(hash((exclusion, outcome))) % 100000))
        boot = {k: [] for k in ("cell", "item", "cluster", "model")}
        bpm_cell = [[] for _ in range(NM)]; bpm_clu = [[] for _ in range(NM)]
        for _ in range(B_BOOT):
            idx = [(rng.randrange(K), False) for _ in range(K)]
            s = stats_from(idx, pooled, permod)
            for k in boot:
                boot[k].append(s[k])
            for j in range(NM):
                bpm_cell[j].append(s["_pm_cell"][j]); bpm_clu[j].append(s["_pm_cluster"][j])

        rng2 = random.Random(SEED + 999 + 17*(abs(hash((outcome, exclusion))) % 100000))
        perm = {k: [] for k in ("cell", "item", "cluster", "model")}
        ppm_cell = [[] for _ in range(NM)]; ppm_clu = [[] for _ in range(NM)]
        for _ in range(B_PERM):
            idx = [(i, rng2.random() < 0.5) for i in range(K)]
            s = stats_from(idx, pooled, permod)
            for k in perm:
                perm[k].append(s[k])
            for j in range(NM):
                ppm_cell[j].append(s["_pm_cell"][j]); ppm_clu[j].append(s["_pm_cluster"][j])

        b_pool = sum(1 for r in recs if r["A_correct"] == 1 and r["B_correct"] == 0)
        c_pool = sum(1 for r in recs if r["A_correct"] == 0 and r["B_correct"] == 1)
        mcn_pool = L.binom_two_sided_exact(b_pool, c_pool)
        mcn_pool_l10 = L.binom_two_sided_log10(b_pool, c_pool)
        mcn_pm, mcn_pm_l10 = [], []
        for m in MODELS:
            mr = [r for r in recs if r["model"] == m]
            bb = sum(1 for r in mr if r["A_correct"] == 1 and r["B_correct"] == 0)
            cc = sum(1 for r in mr if r["A_correct"] == 0 and r["B_correct"] == 1)
            mcn_pm.append(L.binom_two_sided_exact(bb, cc))
            mcn_pm_l10.append(L.binom_two_sided_log10(bb, cc))

        y = [r["A_correct"] for r in recs] + [r["B_correct"] for r in recs]
        arm = [0.0]*len(recs) + [1.0]*len(recs)
        cl = [r["cluster"] for r in recs]*2
        blog, selog, plog, Glog = L.logit_cluster_robust(y, arm, cl)
        plog_l10 = L.t_two_sided_log10(blog/selog, Glog-1)
        log_pm = []
        for m in MODELS:
            mr = [r for r in recs if r["model"] == m]
            yy = [r["A_correct"] for r in mr] + [r["B_correct"] for r in mr]
            aa = [0.0]*len(mr) + [1.0]*len(mr)
            cc = [r["cluster"] for r in mr]*2
            log_pm.append(L.logit_cluster_robust(yy, aa, cc))

        byit = {}
        for r in recs:
            byit.setdefault(r["question_id"], []).append(r)
        it_d, it_cl = [], []
        for q, qr in byit.items():
            it_d.append(100.0*(sum(x["B_correct"] for x in qr)-sum(x["A_correct"] for x in qr))/len(qr))
            it_cl.append(qr[0]["cluster"])
        mi, sei, p_item_rob, Gi = L.ols_intercept_cluster_robust(it_d, it_cl)
        cl_d = [100.0*p[5] for p in pooled]
        mc, sec, p_clu_rob, Gc = L.ols_intercept_cluster_robust(cl_d, clusters)
        md = obs["_pm_cell"]
        mm, sem, p_mod_rob, Gm = L.ols_intercept_cluster_robust(md, list(range(NM)))

        rob_clu_pm = []
        for j in range(NM):
            ds, gs = [], []
            for i in range(K):
                if permod[i][j][4]:
                    ds.append(100.0*permod[i][j][3]); gs.append(clusters[i])
            rob_clu_pm.append(L.ols_intercept_cluster_robust(ds, gs)[2])

        base = dict(exclusion=exclusion, outcome=outcome, n_cells=len(recs),
                    n_items=len(byit), n_clusters=K)

        def add(unit, inf, pool, est, p, G, floored=False, l10=None, note=""):
            d = dict(base)
            d.update(unit=unit, inference=inf, pooling=pool, delta_pp=est, p=p,
                     G=G, floored=floored, note=note,
                     log10p=(l10 if l10 is not None else (math.log10(p) if p > 0 else float("-inf"))))
            results.append(d)

        # ---------- pooled ----------
        v, f = boot_p(boot["cell"], B_BOOT);  add("cell", "cluster_bootstrap", "pooled", obs["cell"], v, K, f)
        v, f = perm_p(perm["cell"], obs["cell"], B_PERM); add("cell", "permutation", "pooled", obs["cell"], v, K, f)
        add("cell", "mcnemar_exact", "pooled", obs["cell"], mcn_pool, b_pool+c_pool, False, mcn_pool_l10,
            note=f"b={b_pool},c={c_pool},n_disc={b_pool+c_pool}")
        add("cell", "logit_robustSE", "pooled", obs["cell"], plog, Glog, False, plog_l10)
        v, f = boot_p(boot["item"], B_BOOT);  add("item", "cluster_bootstrap", "pooled", obs["item"], v, K, f)
        v, f = perm_p(perm["item"], obs["item"], B_PERM); add("item", "permutation", "pooled", obs["item"], v, K, f)
        add("item", "ols_robustSE", "pooled", obs["item"], p_item_rob, Gi, False,
            L.t_two_sided_log10(mi/sei, Gi-1))
        v, f = boot_p(boot["cluster"], B_BOOT); add("cluster", "cluster_bootstrap", "pooled", obs["cluster"], v, K, f)
        v, f = perm_p(perm["cluster"], obs["cluster"], B_PERM); add("cluster", "permutation", "pooled", obs["cluster"], v, K, f)
        add("cluster", "ols_robustSE", "pooled", obs["cluster"], p_clu_rob, Gc, False,
            L.t_two_sided_log10(mc/sec, Gc-1))
        v, f = boot_p(boot["model"], B_BOOT); add("model", "cluster_bootstrap", "pooled", obs["model"], v, K, f,
                                                  note="resamples CLUSTERS (K), not models")
        v, f = perm_p(perm["model"], obs["model"], B_PERM); add("model", "permutation", "pooled", obs["model"], v, K, f,
                                                                note="sign-flips CLUSTERS (K), not models")
        add("model", "ols_robustSE", "pooled", obs["model"], p_mod_rob, Gm, False, None,
            note=f"THE df=3 spec; mean={mm:+.4f} se={sem:.4f} t={mm/sem:+.4f}")

        # ---------- separate (Fisher across 4 models) ----------
        est_sep_cell = sum(obs["_pm_cell"])/NM
        est_sep_clu = sum(obs["_pm_cluster"])/NM
        f_, _ = L.fisher_combine(mcn_pm)
        stat_exact = -2.0*sum(x*math.log(10.0) for x in mcn_pm_l10)
        add("cell", "mcnemar_exact", "separate", est_sep_cell, f_, NM, False,
            L.chi2_sf_even_log10(stat_exact, 2*NM), note="Fisher; the 4 p share clusters")
        bp, bpf = [], []
        for j in range(NM):
            a, b = boot_p(bpm_cell[j], B_BOOT); bp.append(a); bpf.append(b)
        f_, _ = L.fisher_combine(bp); l_, _ = L.fisher_combine_log10(bp)
        add("cell", "cluster_bootstrap", "separate", est_sep_cell, f_, NM, all(bpf), l_,
            note=f"Fisher of {sum(bpf)}/4 FLOORED boot p")
        pp2, ppf = [], []
        for j in range(NM):
            a, b = perm_p(ppm_cell[j], obs["_pm_cell"][j], B_PERM); pp2.append(a); ppf.append(b)
        f_, _ = L.fisher_combine(pp2); l_, _ = L.fisher_combine_log10(pp2)
        add("cell", "permutation", "separate", est_sep_cell, f_, NM, all(ppf), l_,
            note=f"Fisher of {sum(ppf)}/4 FLOORED perm p")
        lp = [x[2] for x in log_pm]
        lp_l10 = [L.t_two_sided_log10(x[0]/x[1], x[3]-1) for x in log_pm]
        f_, _ = L.fisher_combine(lp)
        stat_exact = -2.0*sum(v2*math.log(10.0) for v2 in lp_l10)
        add("cell", "logit_robustSE", "separate", est_sep_cell, f_, NM, False,
            L.chi2_sf_even_log10(stat_exact, 2*NM), note="Fisher")
        bpc, bpcf = [], []
        for j in range(NM):
            a, b = boot_p(bpm_clu[j], B_BOOT); bpc.append(a); bpcf.append(b)
        f_, _ = L.fisher_combine(bpc); l_, _ = L.fisher_combine_log10(bpc)
        add("cluster", "cluster_bootstrap", "separate", est_sep_clu, f_, NM, all(bpcf), l_,
            note=f"Fisher of {sum(bpcf)}/4 FLOORED boot p")
        ppc, ppcf = [], []
        for j in range(NM):
            a, b = perm_p(ppm_clu[j], obs["_pm_cluster"][j], B_PERM); ppc.append(a); ppcf.append(b)
        f_, _ = L.fisher_combine(ppc); l_, _ = L.fisher_combine_log10(ppc)
        add("cluster", "permutation", "separate", est_sep_clu, f_, NM, all(ppcf), l_,
            note=f"Fisher of {sum(ppcf)}/4 FLOORED perm p")
        f_, _ = L.fisher_combine(rob_clu_pm); l_, _ = L.fisher_combine_log10(rob_clu_pm)
        add("cluster", "ols_robustSE", "separate", est_sep_clu, f_, NM, False, l_, note="Fisher")

        percell[f"{exclusion}|{outcome}"] = dict(
            n=len(recs), K=K, delta_cell=obs["cell"], pm_cell=obs["_pm_cell"],
            b=b_pool, c=c_pool, mod_mean=mm, mod_se=sem, mod_t=mm/sem, mod_p=p_mod_rob)
        print(f"  {exclusion:12s}/{outcome:8s} N={len(recs):5d} K={K:4d} "
              f"delta={obs['cell']:+.3f}  per-model=[{', '.join('%+.2f' % v for v in obs['_pm_cell'])}]"
              f"  df3 t={mm/sem:+.3f} p={p_mod_rob:.5f}", flush=True)

json.dump(dict(n_specs=len(results), seed=SEED, B=B_BOOT, results=results, percell=percell),
          open(os.path.join(HERE, "sens_refute_curvep_out.json"), "w"), indent=1)

# =========================================================================
ps = [r["p"] for r in results]
print("\n" + "=" * 78)
print("INDEPENDENT REPLICATION OF THE CLAIM'S HEADLINE NUMBERS")
print("=" * 78)
print(f"  n specifications : {len(results)}   (claim 160)")
for thr, cl_ in ((0.05, "160/160 = 100.0%"), (0.01, "158/160 = 98.8%"), (0.001, "152/160 = 95.0%")):
    k = sum(1 for x in ps if x < thr)
    print(f"  p<{thr:<6}       : {k}/{len(ps)} = {100*k/len(ps):.1f}%      (claim {cl_})")
print(f"  median p         : {st.median(ps):.4e}   (claim 9.05e-13)")
print(f"  min p            : {min(ps):.4e}   (claim 3.72e-53)")
print(f"  max p            : {max(ps):.4e}   (claim 1.009e-02)")
mn = min(results, key=lambda r: r["log10p"])
print(f"  true min via log10: 10^{mn['log10p']:.3f}  from {mn['exclusion']}/{mn['outcome']}/"
      f"{mn['unit']}/{mn['inference']}/{mn['pooling']}")

fails = [r for r in results if r["p"] >= 0.001]
print(f"\n  specs with p >= 0.001 : {len(fails)}")
for r in sorted(fails, key=lambda r: -r["p"]):
    print(f"    {r['exclusion']:12s} {r['outcome']:8s} {r['unit']:8s} {r['inference']:14s} "
          f"{r['pooling']:9s} G={r['G']:<4} p={r['p']:.5f}  {r['note']}")
print("  all 8 are unit=model / ols_robustSE / pooled : "
      f"{all(r['unit']=='model' and r['inference']=='ols_robustSE' and r['pooling']=='pooled' for r in fails)}")
print(f"  their p range: {min(r['p'] for r in fails):.5f} - {max(r['p'] for r in fails):.5f}"
      f"   (claim 0.00852-0.01009)")

# ---- floored / constant p bookkeeping -----------------------------------
print("\n" + "=" * 78)
print("HOW MANY OF THE 160 p-VALUES ARE RESOLUTION ARTEFACTS?")
print("=" * 78)
nfl = sum(1 for r in results if r["floored"])
print(f"  p-values pinned at a resampling resolution limit : {nfl}/160 = {100*nfl/160:.1f}%")
FISH4 = L.fisher_combine([1.0/(B_BOOT+1.0)]*4)[0]
print(f"  Fisher of four floored resampling p, 1/(B+1)=1/{B_BOOT+1}: {FISH4:.4e}")
print(f"     ... this constant depends ONLY on B, not on the data.")
for BB in (999, 9999, 99999, 999999):
    print(f"       B={BB:>7}: Fisher-of-floors = {L.fisher_combine([1.0/(BB+1.0)]*4)[0]:.4e}")
cnt = sum(1 for r in results if abs(r["p"] - FISH4) < 1e-18)
cnt2 = sum(1 for r in results if abs(r["p"] - 1.0/(B_BOOT+1.0)) < 1e-15)
print(f"  specs whose p IS exactly that constant          : {cnt}/160")
print(f"  specs whose p IS exactly 1/(B+1) = {1.0/(B_BOOT+1.0):.4e}   : {cnt2}/160")
print(f"  -> {cnt+cnt2}/160 = {100*(cnt+cnt2)/160:.1f}% of the curve carries NO data-dependent "
      f"magnitude,\n     only 'smaller than the resampling grid can resolve'.")
print(f"  median of the 160 p = {st.median(ps):.4e};  is it that constant? "
      f"{abs(st.median(ps)-FISH4) < 1e-18}")

# ---- grid composition ---------------------------------------------------
print("\n" + "=" * 78)
print("IS 95% A FINDING, OR THE SHAPE OF THE GRID?")
print("=" * 78)
import collections
gsz = collections.Counter()
for r in results:
    gsz[(r["unit"], r["inference"], r["pooling"])] += 1
small = [k for k in gsz if k == ("model", "ols_robustSE", "pooled")]
print(f"  distinct (unit,inference,pooling) combos: {len(gsz)}  x 8 datasets = {len(results)}")
print(f"  combos whose inferential n is the 4 MODELS: {small} -> 1 of {len(gsz)} = "
      f"{1/len(gsz):.3f} of the grid")
print(f"  1 - 1/20 = {1-1/20:.3f} = 95.0%  <- the claimed 'p<0.001 in 95%' EXACTLY")
byG = collections.Counter(r["G"] for r in results)
print("\n  effective inferential group count G per spec:")
for g, c in sorted(byG.items()):
    print(f"    G={g:<6} n_specs={c}")

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

# ===================================================================
# 3. RANDOM-INTERCEPT GLMM by Gauss-Hermite quadrature
# ===================================================================
P("\n" + "=" * 78)
P("RANDOM-INTERCEPT GLMM  y_ij ~ Bernoulli(logit^-1(x_ij'b + u_i)),")
P("u_i ~ N(0, sigma^2) over the 325 items. Marginal likelihood by")
P("Gauss-Hermite quadrature; analytic gradient; hand-rolled BFGS.")
P("=" * 78)

# ---- quadrature sanity check
for nq in (20, 40, 60):
    xg, wg = gauss_hermite(nq)
    m0 = sum(wg) / math.sqrt(math.pi)
    m2 = sum(wg[i] * (math.sqrt(2.0) * xg[i]) ** 2 for i in range(nq)) / math.sqrt(math.pi)
    m4 = sum(wg[i] * (math.sqrt(2.0) * xg[i]) ** 4 for i in range(nq)) / math.sqrt(math.pi)
    P("  GH check n=%2d : E[1]=%.12f (1)  E[u^2]=%.12f (1)  E[u^4]=%.12f (3)"
      % (nq, m0, m2, m4))


def build_glmm(with_inter):
    names = ["(intercept)", "condB"]
    for m in MODELS:
        if m != REF:
            names.append("model[%s]" % SHORT[m])
    if with_inter:
        for m in MODELS:
            if m != REF:
                names.append("condB:model[%s]" % SHORT[m])
    ix = {n: i for i, n in enumerate(names)}
    groups = {}
    for r in long:
        row = [(0, 1.0)]
        if r["cond"] == 1:
            row.append((ix["condB"], 1.0))
        if r["model"] != REF:
            row.append((ix["model[%s]" % SHORT[r["model"]]], 1.0))
            if with_inter and r["cond"] == 1:
                row.append((ix["condB:model[%s]" % SHORT[r["model"]]], 1.0))
        groups.setdefault(r["item"], []).append((row, r["y"]))
    return names, list(groups.values())


def glmm_obj(par, groups, k, nodes):
    """Returns (-loglik, -gradient). par = beta[0:k] + [log sigma]."""
    beta = par[:k]
    sigma = math.exp(par[k])
    xg, wg = nodes
    nq = len(xg)
    shifts = [math.sqrt(2.0) * sigma * xg[q] for q in range(nq)]
    logw = [math.log(wg[q]) for q in range(nq)]
    half_log_pi = 0.5 * math.log(math.pi)
    ll = 0.0
    grad = [0.0] * (k + 1)
    for g in groups:
        etas = []
        for row, yv in g:
            e = 0.0
            for c, v in row:
                e += beta[c] * v
            etas.append(e)
        logP = [0.0] * nq
        S = [[0.0] * len(g) for _ in range(nq)]  # residuals y - p
        for q in range(nq):
            sh = shifts[q]
            acc = 0.0
            Sq = S[q]
            for j in range(len(g)):
                e = etas[j] + sh
                if e > 500: e = 500.0
                elif e < -500: e = -500.0
                yv = g[j][1]
                # log Bernoulli, numerically stable
                if e >= 0:
                    lse = e + math.log1p(math.exp(-e))
                else:
                    lse = math.log1p(math.exp(e))
                acc += (yv * e) - lse
                p = 1.0 / (1.0 + math.exp(-e))
                Sq[j] = yv - p
            logP[q] = acc
        terms = [logw[q] + logP[q] for q in range(nq)]
        mx = max(terms)
        ssum = 0.0
        for q in range(nq):
            ssum += math.exp(terms[q] - mx)
        ll += mx + math.log(ssum) - half_log_pi
        # posterior weights r_q
        for q in range(nq):
            rq = math.exp(terms[q] - mx) / ssum
            if rq < 1e-300:
                continue
            Sq = S[q]
            tot = 0.0
            for j in range(len(g)):
                res = Sq[j]
                tot += res
                for c, v in g[j][0]:
                    grad[c] += rq * res * v
            grad[k] += rq * tot * (math.sqrt(2.0) * xg[q])
    grad[k] *= sigma  # chain rule for log sigma
    return -ll, [-x for x in grad]


def bfgs(f, x0, maxit=400, gtol=1e-7):
    n = len(x0)
    x = list(x0)
    fx, g = f(x)
    H = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for it in range(maxit):
        if max(abs(v) for v in g) < gtol:
            break
        d = [-sum(H[i][j] * g[j] for j in range(n)) for i in range(n)]
        slope = sum(d[i] * g[i] for i in range(n))
        if slope >= 0:
            H = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
            d = [-g[i] for i in range(n)]
            slope = sum(d[i] * g[i] for i in range(n))
        t = 1.0
        for _ in range(60):
            xn = [x[i] + t * d[i] for i in range(n)]
            fn, gn = f(xn)
            if fn <= fx + 1e-4 * t * slope:
                break
            t *= 0.5
        else:
            break
        s = [xn[i] - x[i] for i in range(n)]
        yv = [gn[i] - g[i] for i in range(n)]
        sy = sum(s[i] * yv[i] for i in range(n))
        if sy > 1e-14:
            Hy = [sum(H[i][j] * yv[j] for j in range(n)) for i in range(n)]
            yHy = sum(yv[i] * Hy[i] for i in range(n))
            for i in range(n):
                for j in range(n):
                    H[i][j] += ((sy + yHy) * s[i] * s[j] / (sy * sy)
                                - (Hy[i] * s[j] + s[i] * Hy[j]) / sy)
        x, fx, g = xn, fn, gn
    return x, fx, g, it


def hessian_fd(f, x, h=1e-5):
    n = len(x)
    H = [[0.0] * n for _ in range(n)]
    for i in range(n):
        xp = list(x); xp[i] += h
        xm = list(x); xm[i] -= h
        _, gp = f(xp)
        _, gm = f(xm)
        for j in range(n):
            H[i][j] = (gp[j] - gm[j]) / (2 * h)
    for i in range(n):
        for j in range(i + 1, n):
            m = 0.5 * (H[i][j] + H[j][i])
            H[i][j] = H[j][i] = m
    return H


results = {}
for with_inter, lab in ((False, "M1: condB + model + (1|item)"),
                        (True, "M2: condB * model + (1|item)")):
    names, groups = build_glmm(with_inter)
    k = len(names)
    # GLM starting values (sigma small)
    X = [row for g in groups for row, _ in g]
    yv = [y for g in groups for _, y in g]
    f0 = irls_logit(X, yv, k)
    P("\n--- %s ---" % lab)
    P("  items (random-effect groups): %d ; rows: %d" % (len(groups), len(yv)))

    nodes20 = gauss_hermite(20)
    # validation: at sigma -> 0 the marginal loglik must equal the GLM loglik
    v0, _ = glmm_obj(f0["beta"] + [math.log(1e-6)], groups, k, nodes20)
    P("  validation: marginal logLik at sigma=1e-6 = %.6f ; GLM logLik = %.6f "
      "(diff %.2e)" % (-v0, f0["loglik"], -v0 - f0["loglik"]))
    # validation: analytic gradient vs central finite differences
    tp = f0["beta"] + [math.log(1.0)]
    _, ga = glmm_obj(tp, groups, k, nodes20)
    maxrel = 0.0
    for i in range(k + 1):
        hh = 1e-6
        xp = list(tp); xp[i] += hh
        xm = list(tp); xm[i] -= hh
        fp, _ = glmm_obj(xp, groups, k, nodes20)
        fm, _ = glmm_obj(xm, groups, k, nodes20)
        fd = (fp - fm) / (2 * hh)
        maxrel = max(maxrel, abs(fd - ga[i]) / max(1.0, abs(fd)))
    P("  validation: max |analytic - finite-diff| gradient (rel) = %.2e" % maxrel)

    for nq in (20, 40, 60):
        nodes = gauss_hermite(nq)
        fobj = lambda p, gg=groups, kk=k, nn=nodes: glmm_obj(p, gg, kk, nn)
        est, nll, gfin, nit = bfgs(fobj, f0["beta"] + [math.log(1.0)])
        sig = math.exp(est[k])
        if nq == 60:
            H = hessian_fd(fobj, est)
            V = chol_inv(chol(H))
            results[lab] = (names, est, V, -nll, sig)
        P("  nq=%2d : logLik=%.5f  sigma=%.5f  condB=%+.6f  |grad|max=%.2e  BFGS it=%d"
          % (nq, -nll, sig, est[1], max(abs(v) for v in gfin), nit))

    names, est, V, ll, sig = results[lab]
    P("  %-30s %10s %10s %10s" % ("term", "coef", "SE", "z"))
    for j, nm in enumerate(names):
        se = math.sqrt(V[j][j])
        P("  %-30s %10.4f %10.4f %10.3f" % (nm, est[j], se, est[j] / se))
    se_ls = math.sqrt(V[k][k])
    P("  %-30s %10.4f %10.4f   (log-scale SE=%.4f -> delta-method SE(sigma)=%.4f)"
      % ("sigma_item", sig, sig * se_ls, se_ls, sig * se_ls))
    icc = sig ** 2 / (sig ** 2 + math.pi ** 2 / 3.0)
    P("  ICC (latent scale) = sigma^2/(sigma^2 + pi^2/3) = %.4f" % icc)
    P("  logLik = %.5f" % ll)

# LRT for sigma = 0 (boundary: 50:50 mixture of chi2_0 and chi2_1)
names1, groups1 = build_glmm(False)
X1 = [row for g in groups1 for row, _ in g]
y1 = [y for g in groups1 for _, y in g]
g1 = irls_logit(X1, y1, len(names1))
ll_glmm = results["M1: condB + model + (1|item)"][3]
lr = 2.0 * (ll_glmm - g1["loglik"])
P("\n  LRT for sigma_item = 0 (M1 vs the same fixed-effects GLM):")
P("    2*(%.5f - %.5f) = %.4f ; boundary-corrected p = 0.5*P(chi2_1 > x) = %.4g"
  % (ll_glmm, g1["loglik"], lr, 0.5 * chisq_sf(lr, 1)))

# GLMM interaction LRT
llM1 = results["M1: condB + model + (1|item)"][3]
llM2 = results["M2: condB * model + (1|item)"][3]
lr2 = 2.0 * (llM2 - llM1)
P("\n  GLMM interaction LRT (M2 vs M1): chi2=%.4f df=3 p=%.4g"
  % (lr2, chisq_sf(lr2, 3)))

# per-model condition effects from the GLMM
names, est, V, ll, sig = results["M2: condB * model + (1|item)"]
P("\n  GLMM per-model CONDITIONAL (subject-specific) condition log-odds:")
for m in MODELS:
    L = [0.0] * len(est)
    L[names.index("condB")] = 1.0
    if m != REF:
        L[names.index("condB:model[%s]" % SHORT[m])] = 1.0
    e = sum(L[j] * est[j] for j in range(len(est)))
    se = math.sqrt(quad_form(L, V))
    P("    %-20s b=%+.4f SE=%.4f OR=%.3f [%.3f, %.3f]"
      % (SHORT[m], e, se, math.exp(e), math.exp(e - 1.96 * se),
         math.exp(e + 1.96 * se)))

json.dump({"log": out}, open(os.path.join(HERE, "prim_mixed_glmm_log.json"), "w"))
P("\n[done part 2]")

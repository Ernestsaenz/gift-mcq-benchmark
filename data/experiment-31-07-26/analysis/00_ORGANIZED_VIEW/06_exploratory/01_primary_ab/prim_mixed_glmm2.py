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
    print(s, flush=True)
    out.append(s)

raw = json.load(open(os.path.join(HERE, "paired_clean.json")))
cells = [r for r in raw if r.get("analysis_include") is True]
long = []
for r in cells:
    for cond, key in ((0, "A_correct"), (1, "B_correct")):
        long.append({"y": int(r[key]), "cond": cond, "model": r["model"],
                     "item": r["question_id"], "cluster": r["cluster"]})

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


def bfgs(f, x0, maxit=60, gtol=2e-5, ftol=1e-9):
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
        improved = fx - fn
        x, fx, g = xn, fn, gn
        if improved >= 0 and improved < ftol:
            break
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

    warm = f0["beta"] + [math.log(1.0)]
    for nq in (20, 30, 40):
        nodes = gauss_hermite(nq)
        fobj = lambda p, gg=groups, kk=k, nn=nodes: glmm_obj(p, gg, kk, nn)
        est, nll, gfin, nit = bfgs(fobj, warm)
        warm = list(est)
        sig = math.exp(est[k])
        if nq == 40:
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

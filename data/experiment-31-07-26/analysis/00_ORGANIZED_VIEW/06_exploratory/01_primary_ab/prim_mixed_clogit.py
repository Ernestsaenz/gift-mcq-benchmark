"""Part 4: CONDITIONAL (fixed-effects) logit -- the bias-free item-FE model.

The unconditional item-FE logit in part 1 is inconsistent (incidental
parameters): with T=2 per stratum its MLE is exactly 2x the truth, which
part 3 confirmed numerically. Here we condition on each item's total number
of correct answers, which eliminates the 325 item intercepts exactly.

Conditional likelihood for item i with T_i rows and s_i = sum y:
    P(y_i | s_i) = exp(sum_j y_ij eta_ij) / sum_{d in D(T_i, s_i)} exp(sum_j d_j eta_ij)
Newton-Raphson with exact gradient and Hessian by enumerating D(T_i, s_i).
Cluster-robust sandwich from the per-stratum score contributions.
Stdlib only.
"""
import json
import math
import os
import sys
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prim_linalg import chol, chol_inv, chol_solve, matmul, chisq_sf, \
    two_sided_z_p, quad_form, solve_sym

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
SHORT = {m: m.split("/")[1] for m in MODELS}
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


def build(with_inter):
    names = ["condB"]
    for m in MODELS:
        if m != REF:
            names.append("model[%s]" % SHORT[m])
    if with_inter:
        for m in MODELS:
            if m != REF:
                names.append("condB:model[%s]" % SHORT[m])
    ix = {n: i for i, n in enumerate(names)}
    strata = {}
    for r in long:
        row = []
        if r["cond"] == 1:
            row.append((ix["condB"], 1.0))
        if r["model"] != REF:
            row.append((ix["model[%s]" % SHORT[r["model"]]], 1.0))
            if with_inter and r["cond"] == 1:
                row.append((ix["condB:model[%s]" % SHORT[r["model"]]], 1.0))
        strata.setdefault(r["item"], {"rows": [], "y": [], "cluster": r["cluster"]})
        strata[r["item"]]["rows"].append(row)
        strata[r["item"]]["y"].append(r["y"])
    keep = {}
    for it, s in strata.items():
        tot = sum(s["y"])
        if 0 < tot < len(s["y"]):
            s["subsets"] = list(combinations(range(len(s["y"])), tot))
            keep[it] = s
    return names, keep


def clogit_terms(names, strata, beta, want_hess=True):
    k = len(names)
    ll = 0.0
    grad = [0.0] * k
    H = [[0.0] * k for _ in range(k)] if want_hess else None
    scores = {}
    for it, s in strata.items():
        rows, y = s["rows"], s["y"]
        eta = []
        for row in rows:
            e = 0.0
            for c, v in row:
                e += beta[c] * v
            eta.append(e)
        num = sum(eta[j] for j in range(len(y)) if y[j] == 1)
        subs = s["subsets"]
        es = [sum(eta[j] for j in sub) for sub in subs]
        mx = max(es)
        ws = [math.exp(e - mx) for e in es]
        Z = sum(ws)
        ll += num - mx - math.log(Z)
        # E[x] and E[xx'] under the conditional distribution
        Ex = [0.0] * k
        Exx = [[0.0] * k for _ in range(k)] if want_hess else None
        for si, sub in enumerate(subs):
            p = ws[si] / Z
            xs = [0.0] * k
            for j in sub:
                for c, v in rows[j]:
                    xs[c] += v
            for c in range(k):
                if xs[c]:
                    Ex[c] += p * xs[c]
            if want_hess:
                for c in range(k):
                    if xs[c] == 0.0:
                        continue
                    Ec = Exx[c]
                    pc = p * xs[c]
                    for d in range(k):
                        if xs[d]:
                            Ec[d] += pc * xs[d]
        obs = [0.0] * k
        for j in range(len(y)):
            if y[j] == 1:
                for c, v in rows[j]:
                    obs[c] += v
        sc = [obs[c] - Ex[c] for c in range(k)]
        scores[it] = (sc, s["cluster"])
        for c in range(k):
            grad[c] += sc[c]
        if want_hess:
            for c in range(k):
                for d in range(k):
                    H[c][d] -= (Exx[c][d] - Ex[c] * Ex[d])
    return ll, grad, H, scores


def fit_clogit(names, strata, maxit=100, tol=1e-12):
    k = len(names)
    beta = [0.0] * k
    for it in range(maxit):
        ll, g, H, sc = clogit_terms(names, strata, beta)
        negH = [[-H[a][b] for b in range(k)] for a in range(k)]
        delta = chol_solve(chol(negH), g)
        beta = [beta[c] + delta[c] for c in range(k)]
        if max(abs(d) for d in delta) < tol:
            break
    ll, g, H, sc = clogit_terms(names, strata, beta)
    negH = [[-H[a][b] for b in range(k)] for a in range(k)]
    V = chol_inv(chol(negH))
    return {"beta": beta, "loglik": ll, "V": V, "negH": negH,
            "scores": sc, "iters": it + 1, "grad": g, "names": names}


def robust(fit, strata, by="item"):
    k = len(fit["names"])
    bread = fit["V"]
    groups = {}
    for it, (sc, cl) in fit["scores"].items():
        key = it if by == "item" else cl
        g = groups.setdefault(key, [0.0] * k)
        for c in range(k):
            g[c] += sc[c]
    meat = [[0.0] * k for _ in range(k)]
    for g in groups.values():
        for a in range(k):
            if g[a] == 0.0:
                continue
            for b in range(k):
                meat[a][b] += g[a] * g[b]
    G = len(groups)
    f = G / (G - 1.0)
    for a in range(k):
        for b in range(k):
            meat[a][b] *= f
    return matmul(matmul(bread, meat), bread), G


P("=" * 78)
P("CONDITIONAL (fixed-effects) LOGIT -- item strata eliminated exactly")
P("Newton-Raphson on the exact conditional likelihood; enumerated strata.")
P("=" * 78)

# ---- validation against the closed-form matched-pair result, one model
P("\n[validation] single model, condition only, strata = item (T=2 pairs):")
for m in MODELS:
    sub = [r for r in cells if r["model"] == m]
    n10 = sum(1 for r in sub if r["A_correct"] == 1 and r["B_correct"] == 0)
    n01 = sum(1 for r in sub if r["A_correct"] == 0 and r["B_correct"] == 1)
    strata = {}
    for r in sub:
        strata[r["question_id"]] = {
            "rows": [[], [(0, 1.0)]], "y": [r["A_correct"], r["B_correct"]],
            "cluster": r["cluster"]}
    strata = {k2: v for k2, v in strata.items() if 0 < sum(v["y"]) < 2}
    for v in strata.values():
        v["subsets"] = list(combinations(range(2), sum(v["y"])))
    f = fit_clogit(["condB"], strata)
    P("  %-20s clogit b=%+.6f   closed form log(n01/n10)=%+.6f   diff=%.2e"
      % (SHORT[m], f["beta"][0], math.log(n01 / n10),
         abs(f["beta"][0] - math.log(n01 / n10))))

# ---- main conditional-logit fits on the full crossed data
for with_inter, lab in ((False, "(iv-b) clogit: condB + model | item strata"),
                        (True, "(iv-c) clogit: condB * model | item strata")):
    names, strata = build(with_inter)
    f = fit_clogit(names, strata)
    Vi, Gi = robust(f, strata, "item")
    Vc, Gc = robust(f, strata, "cluster")
    k = len(names)
    P("\n" + "-" * 78)
    P(lab)
    P("-" * 78)
    P("  informative item strata: %d   Newton iterations: %d   condL logLik: %.5f"
      % (len(strata), f["iters"], f["loglik"]))
    P("  max |score| at optimum: %.2e" % max(abs(v) for v in f["grad"]))
    P("  robust clusters: item G=%d ; clinical cluster G=%d" % (Gi, Gc))
    P("  %-30s %10s %10s %11s %12s" % ("term", "coef", "SE(model)",
                                        "SE[item]", "SE[cluster]"))
    for j, nm in enumerate(names):
        P("  %-30s %10.4f %10.4f %11.4f %12.4f"
          % (nm, f["beta"][j], math.sqrt(f["V"][j][j]),
             math.sqrt(Vi[j][j]), math.sqrt(Vc[j][j])))
    if not with_inter:
        b = f["beta"][0]
        for nm2, se in (("model-based", math.sqrt(f["V"][0][0])),
                        ("cluster-robust[item]", math.sqrt(Vi[0][0])),
                        ("cluster-robust[cluster]", math.sqrt(Vc[0][0]))):
            z = b / se
            P("  condB  %-26s b=%+.4f SE=%.4f z=%.3f p=%.4g OR=%.4f [%.4f, %.4f]"
              % (nm2, b, se, z, two_sided_z_p(z), math.exp(b),
                 math.exp(b - 1.959964 * se), math.exp(b + 1.959964 * se)))
        f_noint = f
        ll_noint = f["loglik"]
    else:
        P("\n  per-model within-item condition log-odds:")
        for m in MODELS:
            L = [0.0] * k
            L[names.index("condB")] = 1.0
            if m != REF:
                L[names.index("condB:model[%s]" % SHORT[m])] = 1.0
            e = sum(L[j] * f["beta"][j] for j in range(k))
            se = math.sqrt(quad_form(L, Vc))
            P("    %-20s b=%+.4f SE_cluster=%.4f OR=%.3f [%.3f, %.3f]"
              % (SHORT[m], e, se, math.exp(e), math.exp(e - 1.96 * se),
                 math.exp(e + 1.96 * se)))
        ix = [names.index("condB:model[%s]" % SHORT[m])
              for m in MODELS if m != REF]
        bv = [f["beta"][j] for j in ix]
        lr = 2.0 * (f["loglik"] - ll_noint)
        P("\n  interaction LRT (conditional likelihood): chi2=%.4f df=3 p=%.4g"
          % (lr, chisq_sf(lr, 3)))
        for cn, V in (("model-based", f["V"]), ("item", Vi), ("cluster", Vc)):
            Vs = [[V[a][b] for b in ix] for a in ix]
            x = solve_sym(Vs, bv)
            W = sum(bv[i] * x[i] for i in range(3))
            P("  interaction Wald [%-11s]: chi2=%.4f df=3 p=%.4g"
              % (cn, W, chisq_sf(W, 3)))

json.dump({"log": out}, open(os.path.join(HERE, "prim_mixed_clogit_log.json"), "w"))

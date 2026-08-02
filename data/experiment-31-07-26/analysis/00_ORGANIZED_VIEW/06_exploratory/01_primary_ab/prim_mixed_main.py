"""Progressive logistic regression of correctness on condition (A=0, B=1).

Hand-rolled IRLS, cluster-robust sandwich SEs, item fixed effects, cluster
bootstrap, and a Gauss-Hermite random-intercept GLMM. Stdlib only.
"""
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prim_linalg import (irls_logit, cluster_robust_vcov, model_based_vcov,
                         chisq_sf, two_sided_z_p, quad_form, solve_sym,
                         gauss_hermite, chol, chol_inv, matmul)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "paired_clean.json")

MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
SHORT = {"google/gemini-3.6-flash": "gemini-3.6-flash",
         "google/gemma-4-26b-a4b-it": "gemma-4-26b-a4b-it",
         "qwen/qwen3.6-35b-a3b": "qwen3.6-35b-a3b",
         "z-ai/glm-5.2": "glm-5.2"}
REF = MODELS[0]  # reference level for model fixed effects

out = []
def P(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    out.append(s)


# ------------------------------------------------------------------- load data
raw = json.load(open(DATA))
cells = [r for r in raw if r.get("analysis_include") is True]
P("rows in file            :", len(raw))
P("analysis_include cells  :", len(cells))
P("distinct items          :", len(set(r["question_id"] for r in cells)))
P("distinct clusters       :", len(set(r["cluster"] for r in cells)))
P("distinct models         :", len(set(r["model"] for r in cells)))

# observed marginals (confirmation)
P("\n--- observed accuracies (clean subset) ---")
for m in MODELS:
    sub = [r for r in cells if r["model"] == m]
    a = sum(r["A_correct"] for r in sub) / len(sub)
    b = sum(r["B_correct"] for r in sub) / len(sub)
    P("  %-20s n=%d  A %.4f (%.1f%%)  B %.4f (%.1f%%)  diff %+.1fpp"
      % (SHORT[m], len(sub), a, 100 * a, b, 100 * b, 100 * (b - a)))
allA = sum(r["A_correct"] for r in cells) / len(cells)
allB = sum(r["B_correct"] for r in cells) / len(cells)
P("  %-20s n=%d  A %.4f (%.1f%%)  B %.4f (%.1f%%)  diff %+.1fpp"
  % ("POOLED", len(cells), allA, 100 * allA, allB, 100 * allB, 100 * (allB - allA)))

# ------------------------------------------------------------- long form (2598)
long = []
for r in cells:
    for cond, key in ((0, "A_correct"), (1, "B_correct")):
        long.append({
            "y": int(r[key]), "cond": cond, "model": r["model"],
            "item": r["question_id"], "cluster": r["cluster"],
        })
P("\nlong-form rows          :", len(long), "(expect 2 x %d = %d)"
  % (len(cells), 2 * len(cells)))

items = sorted(set(r["item"] for r in long))
item_ix = {it: i for i, it in enumerate(items)}
model_ix = {m: i for i, m in enumerate(MODELS)}


# ------------------------------------------------------------ design builders
def build(spec):
    """Return (X sparse rows, y, ncol, names)."""
    names = ["(intercept)", ]
    cols = {"(intercept)": 0}

    def col(nm):
        if nm not in cols:
            cols[nm] = len(names)
            names.append(nm)
        return cols[nm]

    if "cond" in spec:
        col("condB")
    if "model" in spec:
        for m in MODELS:
            if m != REF:
                col("model[%s]" % SHORT[m])
    if "inter" in spec:
        for m in MODELS:
            if m != REF:
                col("condB:model[%s]" % SHORT[m])
    X, y = [], []
    for r in long:
        row = [(0, 1.0)]
        if "cond" in spec and r["cond"] == 1:
            row.append((cols["condB"], 1.0))
        if "model" in spec and r["model"] != REF:
            row.append((cols["model[%s]" % SHORT[r["model"]]], 1.0))
        if "inter" in spec and r["cond"] == 1 and r["model"] != REF:
            row.append((cols["condB:model[%s]" % SHORT[r["model"]]], 1.0))
        X.append(row)
        y.append(r["y"])
    return X, y, len(names), names


def report(fit, names, X, y, label, clusters=None):
    Vm = model_based_vcov(fit)
    P("\n" + "=" * 78)
    P(label)
    P("=" * 78)
    P("  IRLS converged=%s in %d Fisher-scoring iterations; logLik=%.4f; k=%d"
      % (fit["converged"], fit["iters"], fit["loglik"], fit["ncol"]))
    Vs = {}
    if clusters:
        for cname, cid in clusters.items():
            V, G = cluster_robust_vcov(fit, X, y, cid)
            Vs[cname] = (V, G)
    hdr = "  %-30s %10s %10s" % ("term", "coef", "SE(naive)")
    for cname in Vs:
        hdr += " %12s" % ("SE[%s]" % cname)
    P(hdr)
    for j, nm in enumerate(names):
        line = "  %-30s %10.4f %10.4f" % (nm, fit["beta"][j], math.sqrt(Vm[j][j]))
        for cname in Vs:
            line += " %12.4f" % math.sqrt(Vs[cname][0][j][j])
        P(line)
    return Vm, Vs


clusters = {"item(325)": [r["item"] for r in long],
            "cluster(208)": [r["cluster"] for r in long]}

# ------------------------------------------------------- (i) condition only
X1, y1, k1, n1 = build({"cond"})
f1 = irls_logit(X1, y1, k1)
V1m, V1s = report(f1, n1, X1, y1, "(i)  y ~ condB", clusters)

# ------------------------------------------------ (ii) + model fixed effects
X2, y2, k2, n2 = build({"cond", "model"})
f2 = irls_logit(X2, y2, k2)
V2m, V2s = report(f2, n2, X2, y2, "(ii) y ~ condB + model", clusters)

# --------------------------------------------------- (iii) + interaction
X3, y3, k3, n3 = build({"cond", "model", "inter"})
f3 = irls_logit(X3, y3, k3)
V3m, V3s = report(f3, n3, X3, y3, "(iii) y ~ condB * model", clusters)


def ci_or(b, se, z=1.959963984540054):
    return math.exp(b), math.exp(b - z * se), math.exp(b + z * se)


P("\n--- (i) condition effect, odds-ratio scale ---")
b = f1["beta"][1]
for lab, se in [("naive (independence)", math.sqrt(V1m[1][1]))] + \
        [("cluster-robust %s" % c, math.sqrt(V1s[c][0][1][1])) for c in V1s]:
    orv, lo, hi = ci_or(b, se)
    z = b / se
    P("  %-28s b=%+.4f SE=%.4f z=%.3f p=%.3g  OR=%.4f [%.4f, %.4f]"
      % (lab, b, se, z, two_sided_z_p(z), orv, lo, hi))

P("\n--- (ii) condition effect adjusted for model, odds-ratio scale ---")
b = f2["beta"][1]
for lab, se in [("naive (independence)", math.sqrt(V2m[1][1]))] + \
        [("cluster-robust %s" % c, math.sqrt(V2s[c][0][1][1])) for c in V2s]:
    orv, lo, hi = ci_or(b, se)
    z = b / se
    P("  %-28s b=%+.4f SE=%.4f z=%.3f p=%.3g  OR=%.4f [%.4f, %.4f]"
      % (lab, b, se, z, two_sided_z_p(z), orv, lo, hi))

# ------------------------------------- per-model condition effect from (iii)
P("\n--- (iii) per-model condition log-odds (linear combos of beta) ---")
per_model = {}
for m in MODELS:
    L = [0.0] * k3
    L[n3.index("condB")] = 1.0
    if m != REF:
        L[n3.index("condB:model[%s]" % SHORT[m])] = 1.0
    est = sum(L[j] * f3["beta"][j] for j in range(k3))
    ses = {}
    for c in V3s:
        ses[c] = math.sqrt(quad_form(L, V3s[c][0]))
    se_n = math.sqrt(quad_form(L, V3m))
    per_model[m] = (est, se_n, ses)
    se = ses["cluster(208)"]
    orv, lo, hi = ci_or(est, se)
    P("  %-20s b=%+.4f  SE_naive=%.4f SE_item=%.4f SE_cluster=%.4f "
      "OR=%.3f [%.3f, %.3f]"
      % (SHORT[m], est, se_n, ses["item(325)"], ses["cluster(208)"], orv, lo, hi))

# average condition effect across the 4 models (equal weights)
L = [0.0] * k3
L[n3.index("condB")] = 1.0
for m in MODELS:
    if m != REF:
        L[n3.index("condB:model[%s]" % SHORT[m])] = 0.25
avg = sum(L[j] * f3["beta"][j] for j in range(k3))
se_avg_c = math.sqrt(quad_form(L, V3s["cluster(208)"][0]))
se_avg_i = math.sqrt(quad_form(L, V3s["item(325)"][0]))
orv, lo, hi = ci_or(avg, se_avg_c)
P("  %-20s b=%+.4f  SE_item=%.4f SE_cluster=%.4f OR=%.3f [%.3f, %.3f]"
  % ("AVG over 4 models", avg, se_avg_i, se_avg_c, orv, lo, hi))

# --------------------------------------------- interaction tests (3 df)
P("\n--- interaction test: does the condition effect differ across models? ---")
ix = [n3.index("condB:model[%s]" % SHORT[m]) for m in MODELS if m != REF]
bvec = [f3["beta"][j] for j in ix]
P("  interaction coefficients (vs %s): %s"
  % (SHORT[REF], ", ".join("%s=%+.4f" % (SHORT[m], f3["beta"][j])
                           for m, j in zip([m for m in MODELS if m != REF], ix))))
# LRT (naive, independence working likelihood)
lrt = 2.0 * (f3["loglik"] - f2["loglik"])
P("  LRT (naive, assumes independent rows): chi2=%.4f df=3 p=%.4g"
  % (lrt, chisq_sf(lrt, 3)))
for cname in ["item(325)", "cluster(208)"]:
    V = V3s[cname][0]
    Vs3 = [[V[a][b] for b in ix] for a in ix]
    x = solve_sym(Vs3, bvec)
    W = sum(bvec[i] * x[i] for i in range(3))
    P("  Wald, cluster-robust [%s]: chi2=%.4f df=3 p=%.4g"
      % (cname, W, chisq_sf(W, 3)))

# ---------------------------------------------- (iv-a) item fixed effects
P("\n" + "=" * 78)
P("(iv-a) item fixed effects: y ~ condB * model + item FE")
P("=" * 78)
# items with no within-item variation in y are perfectly separated: their FE
# diverges and they contribute nothing to the conditional likelihood -> drop.
by_item = {}
for r in long:
    by_item.setdefault(r["item"], []).append(r["y"])
informative = [it for it in items if 0 < sum(by_item[it]) < len(by_item[it])]
allone = [it for it in items if sum(by_item[it]) == len(by_item[it])]
allzero = [it for it in items if sum(by_item[it]) == 0]
P("  items all-correct (dropped, separated) : %d" % len(allone))
P("  items all-wrong   (dropped, separated) : %d" % len(allzero))
P("  informative items retained             : %d" % len(informative))

inf_set = set(informative)
sub = [r for r in long if r["item"] in inf_set]
P("  rows in FE fit                         : %d" % len(sub))

fe_names = ["condB"]
fe_cols = {"condB": 0}
for m in MODELS:
    if m != REF:
        fe_cols["model[%s]" % SHORT[m]] = len(fe_names)
        fe_names.append("model[%s]" % SHORT[m])
for m in MODELS:
    if m != REF:
        fe_cols["condB:model[%s]" % SHORT[m]] = len(fe_names)
        fe_names.append("condB:model[%s]" % SHORT[m])
base_k = len(fe_names)
for it in informative:  # item FE absorb the intercept (no global intercept)
    fe_cols["item[%s]" % it] = len(fe_names)
    fe_names.append("item[%s]" % it)

Xf, yf, cf_item, cf_cluster = [], [], [], []
for r in sub:
    row = [(fe_cols["item[%s]" % r["item"]], 1.0)]
    if r["cond"] == 1:
        row.append((fe_cols["condB"], 1.0))
    if r["model"] != REF:
        row.append((fe_cols["model[%s]" % SHORT[r["model"]]], 1.0))
        if r["cond"] == 1:
            row.append((fe_cols["condB:model[%s]" % SHORT[r["model"]]], 1.0))
    Xf.append(row)
    yf.append(r["y"])
    cf_item.append(r["item"])
    cf_cluster.append(r["cluster"])

# reorder so the intercept-like column is first for the IRLS warm start
ff = irls_logit(Xf, yf, len(fe_names))
P("  IRLS converged=%s in %d iterations; logLik=%.4f; k=%d (7 structural + %d item FE)"
  % (ff["converged"], ff["iters"], ff["loglik"], len(fe_names), len(informative)))
Vfm = model_based_vcov(ff)
Vfi, Gi = cluster_robust_vcov(ff, Xf, yf, cf_item)
Vfc, Gc = cluster_robust_vcov(ff, Xf, yf, cf_cluster)
P("  %-30s %10s %10s %12s %12s"
  % ("term", "coef", "SE(naive)", "SE[item]", "SE[cluster]"))
for j in range(base_k):
    P("  %-30s %10.4f %10.4f %12.4f %12.4f"
      % (fe_names[j], ff["beta"][j], math.sqrt(Vfm[j][j]),
         math.sqrt(Vfi[j][j]), math.sqrt(Vfc[j][j])))

P("\n  per-model condition log-odds WITHIN item (item FE model):")
for m in MODELS:
    L = [0.0] * len(fe_names)
    L[fe_cols["condB"]] = 1.0
    if m != REF:
        L[fe_cols["condB:model[%s]" % SHORT[m]]] = 1.0
    est = sum(L[j] * ff["beta"][j] for j in range(len(fe_names)))
    se = math.sqrt(quad_form(L, Vfc))
    orv, lo, hi = ci_or(est, se)
    P("    %-20s b=%+.4f SE_cluster=%.4f OR=%.3f [%.3f, %.3f]"
      % (SHORT[m], est, se, orv, lo, hi))

# item-FE model without interaction, for a within-item LRT
fe2_names = fe_names[:1] + fe_names[1:4] + fe_names[base_k:]
fe2_cols = {nm: i for i, nm in enumerate(fe2_names)}
Xf2 = []
for r in sub:
    row = [(fe2_cols["item[%s]" % r["item"]], 1.0)]
    if r["cond"] == 1:
        row.append((fe2_cols["condB"], 1.0))
    if r["model"] != REF:
        row.append((fe2_cols["model[%s]" % SHORT[r["model"]]], 1.0))
    Xf2.append(row)
ff2 = irls_logit(Xf2, yf, len(fe2_names))
Vf2i, _ = cluster_robust_vcov(ff2, Xf2, yf, cf_item)
Vf2c, _ = cluster_robust_vcov(ff2, Xf2, yf, cf_cluster)
P("\n  item-FE, no interaction: condB=%+.4f SE_naive=%.4f SE_item=%.4f SE_cluster=%.4f"
  % (ff2["beta"][0], math.sqrt(model_based_vcov(ff2)[0][0]),
     math.sqrt(Vf2i[0][0]), math.sqrt(Vf2c[0][0])))
orv, lo, hi = ci_or(ff2["beta"][0], math.sqrt(Vf2c[0][0]))
P("  item-FE, no interaction: OR=%.4f [%.4f, %.4f] (cluster-robust)" % (orv, lo, hi))
lrt_fe = 2.0 * (ff["loglik"] - ff2["loglik"])
P("  item-FE interaction LRT (naive): chi2=%.4f df=3 p=%.4g"
  % (lrt_fe, chisq_sf(lrt_fe, 3)))
ixf = [fe_cols["condB:model[%s]" % SHORT[m]] for m in MODELS if m != REF]
bv = [ff["beta"][j] for j in ixf]
for cname, V in (("item", Vfi), ("cluster", Vfc)):
    Vsm = [[V[a][b] for b in ixf] for a in ixf]
    x = solve_sym(Vsm, bv)
    W = sum(bv[i] * x[i] for i in range(3))
    P("  item-FE interaction Wald, cluster-robust [%s]: chi2=%.4f df=3 p=%.4g"
      % (cname, W, chisq_sf(W, 3)))

json.dump({"log": out}, open(os.path.join(HERE, "prim_mixed_main_log.json"), "w"))
P("\n[done part 1]")

"""Step 4: GEE candidates.
  (i) marginal logistic GEE, working correlation = independence and exchangeable,
      cluster-robust (sandwich) variance, cluster = clinical cluster.
  (ii) empirical Pearson-residual correlations BY PAIR TYPE -- the direct test of
      whether 'exchangeable' is a defensible working structure here.
  (iii) small-sample diagnostics: effective number of clusters, cluster-size
      concentration, bias-corrected sandwich, t reference.

Exchangeable R has a closed-form inverse, so no dense linear algebra is needed:
  R = (1-a)I + aJ  =>  R^-1 = 1/(1-a) [ I - a/(1+(n-1)a) J ]
"""
import sys, math
from collections import defaultdict
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from stats_lib import *

rows = load()
models = sorted({r["model"] for r in rows})
MSHORT = {m: m.split("/")[-1] for m in models}

# long format: two observations per cell
obs = []
for r in rows:
    obs.append(dict(y=r["A_correct"], x=0, item=r["question_id"], cluster=r["cluster"],
                    model=r["model"], cell=(r["question_id"], r["model"])))
    obs.append(dict(y=r["B_correct"], x=1, item=r["question_id"], cluster=r["cluster"],
                    model=r["model"], cell=(r["question_id"], r["model"])))
print("long-format observations:", len(obs))

def expit(t):
    if t >= 0:
        e = math.exp(-t); return 1.0 / (1.0 + e)
    e = math.exp(t); return e / (1.0 + e)

def gee(obs, cluster_key, exchangeable, maxit=100, tol=1e-11, verbose_name=""):
    groups = defaultdict(list)
    for o in obs:
        groups[cluster_key(o)].append(o)
    G = list(groups.values())
    beta = [0.0, 0.0]
    alpha = 0.0
    for it in range(maxit):
        # --- moment estimate of alpha from current Pearson residuals
        if exchangeable:
            num = 0.0; den = 0.0
            for g in G:
                res = []
                for o in g:
                    mu = expit(beta[0] + beta[1] * o["x"])
                    res.append((o["y"] - mu) / math.sqrt(mu * (1 - mu)))
                s = sum(res); ss = sum(r * r for r in res)
                num += (s * s - ss) / 2.0          # sum over j<k of r_j r_k
                n = len(g); den += n * (n - 1) / 2.0
            alpha = num / (den - 2) if den > 2 else 0.0
            alpha = max(-0.9, min(0.95, alpha))
        # --- Fisher scoring step
        Bm = [[0.0, 0.0], [0.0, 0.0]]
        U = [0.0, 0.0]
        scores = []
        for g in G:
            n = len(g)
            Z = []; e = []
            for o in g:
                mu = expit(beta[0] + beta[1] * o["x"])
                w = math.sqrt(mu * (1 - mu))
                Z.append([w * 1.0, w * o["x"]])
                e.append((o["y"] - mu) / w)
            a = alpha if exchangeable else 0.0
            inv = 1.0 / (1.0 - a) if a != 1.0 else 0.0
            cc = a / (1.0 + (n - 1) * a) if (1.0 + (n - 1) * a) != 0 else 0.0
            ZtZ = [[sum(Z[i][p] * Z[i][q] for i in range(n)) for q in range(2)] for p in range(2)]
            Zt1 = [sum(Z[i][p] for i in range(n)) for p in range(2)]
            Zte = [sum(Z[i][p] * e[i] for i in range(n)) for p in range(2)]
            e1 = sum(e)
            Bg = [[inv * (ZtZ[p][q] - cc * Zt1[p] * Zt1[q]) for q in range(2)] for p in range(2)]
            Ug = [inv * (Zte[p] - cc * Zt1[p] * e1) for p in range(2)]
            for p in range(2):
                U[p] += Ug[p]
                for q in range(2):
                    Bm[p][q] += Bg[p][q]
            scores.append(Ug)
        Binv = mat_inv2(Bm)
        step = [Binv[0][0] * U[0] + Binv[0][1] * U[1], Binv[1][0] * U[0] + Binv[1][1] * U[1]]
        beta = [beta[0] + step[0], beta[1] + step[1]]
        if max(abs(s) for s in step) < tol:
            break
    # --- sandwich
    M = [[0.0, 0.0], [0.0, 0.0]]
    for Ug in scores:
        for p in range(2):
            for q in range(2):
                M[p][q] += Ug[p] * Ug[q]
    V = matmul(matmul(Binv, M), Binv)
    K = len(G)
    se = [math.sqrt(V[0][0]), math.sqrt(V[1][1])]
    # model-based (naive) variance = Binv
    se_naive = [math.sqrt(Binv[0][0]), math.sqrt(Binv[1][1])]
    # simple df correction K/(K-p)
    corr = K / (K - 2.0)
    se_c = [s * math.sqrt(corr) for s in se]
    return dict(beta=beta, alpha=alpha, se=se, se_naive=se_naive, se_c=se_c, K=K,
                iters=it + 1, name=verbose_name, scores=scores)

print("\n=== (i) GEE, marginal logit P(correct) = b0 + b1*[condition B] ===")
runs = [
    ("independence / cluster-robust", lambda o: o["cluster"], False),
    ("exchangeable  / cluster-robust", lambda o: o["cluster"], True),
    ("independence / item-robust",     lambda o: o["item"], False),
    ("exchangeable  / item-robust",    lambda o: o["item"], True),
    ("independence / cell-robust",     lambda o: o["cell"], False),
    ("exchangeable  / cell-robust",    lambda o: o["cell"], True),
]
out = {}
for name, key, exch in runs:
    g = gee(obs, key, exch, verbose_name=name)
    out[name] = g
    z = g["beta"][1] / g["se"][1]
    zc = g["beta"][1] / g["se_c"][1]
    print("%-32s K=%4d alpha=%7.4f  b1=%+.4f  OR=%.3f  robSE=%.4f (naiveSE=%.4f)  z=%.3f p=%.3e"
          % (name, g["K"], g["alpha"], g["beta"][1], math.exp(g["beta"][1]),
             g["se"][1], g["se_naive"][1], z, two_sided_z_p(z)))
    print("%-32s   df-corrected SE=%.4f  z=%.3f  95%% CI for OR [%.3f, %.3f]"
          % ("", g["se_c"][1], zc,
             math.exp(g["beta"][1] - 1.96 * g["se_c"][1]),
             math.exp(g["beta"][1] + 1.96 * g["se_c"][1])))

gc = out["independence / cluster-robust"]
print("\nsandwich/naive SE ratio (independence, cluster-robust) = %.3f"
      % (gc["se"][1] / gc["se_naive"][1]))
_b = sum(1 for r in rows if r["A_correct"] == 1 and r["B_correct"] == 0)
_c = sum(1 for r in rows if r["A_correct"] == 0 and r["B_correct"] == 1)
print("note: the marginal GEE log-OR (%.4f, OR %.3f) is NOT the McNemar conditional log-OR (%.4f, OR %.3f)"
      % (gc["beta"][1], math.exp(gc["beta"][1]), -math.log(_b / _c), _c / _b))

print("\n=== (ii) IS THE WORKING CORRELATION EXCHANGEABLE? empirical Pearson-residual correlations by pair type ===")
# fit marginal means first (independence), then correlate residuals within cluster by pair type
b0, b1 = gc["beta"]
for o in obs:
    mu = expit(b0 + b1 * o["x"])
    o["r"] = (o["y"] - mu) / math.sqrt(mu * (1 - mu))

def paircorr():
    acc = defaultdict(lambda: [0.0, 0])
    byc = defaultdict(list)
    for o in obs:
        byc[o["cluster"]].append(o)
    for c, g in byc.items():
        n = len(g)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = g[i], g[j]
                same_item = a["item"] == b["item"]
                same_model = a["model"] == b["model"]
                same_cond = a["x"] == b["x"]
                if same_item and same_model:
                    k = "1 same CELL (same item+model, A vs B)"
                elif same_item and not same_model and same_cond:
                    k = "2 same item, diff model, same condition"
                elif same_item and not same_model:
                    k = "3 same item, diff model, diff condition"
                elif not same_item and same_model and same_cond:
                    k = "4 diff item (same cluster), same model, same cond"
                elif not same_item and same_model:
                    k = "5 diff item (same cluster), same model, diff cond"
                elif not same_item and same_cond:
                    k = "6 diff item, diff model, same condition"
                else:
                    k = "7 diff item, diff model, diff condition"
                acc[k][0] += a["r"] * b["r"]
                acc[k][1] += 1
    return acc

acc = paircorr()
print("%-52s %8s %10s" % ("pair type (both members in same cluster)", "n pairs", "mean r_i*r_j"))
for k in sorted(acc):
    s, n = acc[k]
    print("%-52s %8d %10.4f" % (k, n, s / n))
print("\n'exchangeable' asserts ALL of these are the SAME constant. They are not:")
vals = {k: acc[k][0] / acc[k][1] for k in acc}
print("  max/min ratio across pair types = %.2f  (range %.4f to %.4f)"
      % (max(vals.values()) / min(v for v in vals.values() if v > 0),
         min(vals.values()), max(vals.values())))

print("\n=== (iii) small-sample / leverage diagnostics for the cluster-robust sandwich ===")
sizes = sorted((len(v) for v in group(rows, lambda r: r["cluster"]).values()), reverse=True)
tot = sum(sizes)
print("clusters K=%d ; cell counts: largest 5 = %s ; total %d" % (len(sizes), sizes[:5], tot))
print("share of data in the largest cluster = %.3f ; in the largest 5 = %.3f"
      % (sizes[0] / tot, sum(sizes[:5]) / tot))
# Kish-style effective number of clusters
eff_K = (sum(sizes) ** 2) / sum(s * s for s in sizes)
print("Kish effective number of clusters (sum n)^2/sum n^2 = %.1f (nominal %d)" % (eff_K, len(sizes)))
# score-based effective K: how concentrated is the sandwich meat?
sc = [s[1] for s in gc["scores"]]
tot2 = sum(x * x for x in sc)
sc2 = sorted((x * x for x in sc), reverse=True)
print("share of sandwich 'meat' from the single most influential cluster = %.3f ; top 5 = %.3f"
      % (sc2[0] / tot2, sum(sc2[:5]) / tot2))
print("effective K from meat concentration = %.1f" % (tot2 ** 2 / sum(x ** 4 for x in sc) if sum(x**4 for x in sc) else float('nan')))

"""Second, parametric check of the MECHANISM behind the condB SE ratio.

The claim asserts the ~1.07 CR/naive ratio for condB is "a structural property of
the design" because condB is a within-item contrast so the item random intercept
"contributes almost nothing to its variance".

Testable prediction: data generated from a PURE item-random-intercept logistic
model (item level varies, but NO item x condition heterogeneity) should reproduce
a condB CR/naive ratio of ~1.07.

We simulate exactly that, at the observed item-level dispersion and at a range of
sigma, refit marginal model (ii), and look at the ratio.
"""
import json, math, os, random
HERE = os.path.dirname(os.path.abspath(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location(
    "se1", os.path.join(HERE, "prim_refute_se_inflation.py"))

# ---- re-implement the small pieces we need (no import; that script runs a lot)
def inv(M):
    n = len(M)
    A = [list(M[i]) + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(A[r][c]))
        A[c], A[piv] = A[piv], A[c]
        d = A[c][c]
        A[c] = [v / d for v in A[c]]
        for r in range(n):
            if r == c: continue
            f = A[r][c]
            if f: A[r] = [A[r][k] - f * A[c][k] for k in range(2 * n)]
    return [row[n:] for row in A]

def mm(A, B):
    n, m, p = len(A), len(B), len(B[0])
    return [[sum(A[i][k] * B[k][j] for k in range(m)) for j in range(p)] for i in range(n)]

def mv(A, v):
    return [sum(A[i][k] * v[k] for k in range(len(v))) for i in range(len(A))]

def irls(X, y, maxit=60):
    n, k = len(X), len(X[0])
    beta = [0.0] * k
    for it in range(maxit):
        XtWX = [[0.0] * k for _ in range(k)]; XtWz = [0.0] * k
        for i in range(n):
            eta = sum(X[i][j] * beta[j] for j in range(k))
            eta = max(-500.0, min(500.0, eta))
            pi = 1.0 / (1.0 + math.exp(-eta))
            w = max(pi * (1 - pi), 1e-10); r = y[i] - pi
            for a in range(k):
                xa = X[i][a]
                if xa == 0.0: continue
                XtWz[a] += xa * r
                for b in range(k):
                    XtWX[a][b] += xa * w * X[i][b]
        step = mv(inv(XtWX), XtWz)
        beta = [beta[j] + step[j] for j in range(k)]
        if max(abs(s) for s in step) < 1e-10: break
    p = []
    XtWX = [[0.0] * k for _ in range(k)]
    for i in range(n):
        eta = sum(X[i][j] * beta[j] for j in range(k))
        eta = max(-500.0, min(500.0, eta))
        pi = 1.0 / (1.0 + math.exp(-eta)); p.append(pi)
        w = pi * (1 - pi)
        for a in range(k):
            xa = X[i][a]
            if xa == 0.0: continue
            for b in range(k):
                XtWX[a][b] += xa * w * X[i][b]
    return {"beta": beta, "p": p, "XtWX": XtWX, "n": n, "k": k}

def sand(fit, X, y, cid):
    k, n = fit["k"], fit["n"]
    bread = inv(fit["XtWX"]); g = {}
    for i in range(n):
        s = g.setdefault(cid[i], [0.0] * k); r = y[i] - fit["p"][i]
        for a in range(k):
            if X[i][a]: s[a] += X[i][a] * r
    G = len(g)
    meat = [[0.0] * k for _ in range(k)]
    for s in g.values():
        for a in range(k):
            if s[a] == 0.0: continue
            for b in range(k):
                meat[a][b] += s[a] * s[b]
    c = (G / (G - 1.0)) * ((n - 1.0) / (n - k))
    meat = [[meat[a][b] * c for b in range(k)] for a in range(k)]
    return mm(mm(bread, meat), bread)

OUT = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)

MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
SHORT = {MODELS[0]: "gemini", MODELS[1]: "gemma", MODELS[2]: "qwen", MODELS[3]: "glm"}
REF = MODELS[0]; NONREF = MODELS[1:]

raw = json.load(open(os.path.join(HERE, "paired_clean.json")))
cells = [r for r in raw if r.get("analysis_include") is True]
long = []
for r in cells:
    for cond, key in ((0, "A_correct"), (1, "B_correct")):
        long.append({"y": int(r[key]), "cond": cond, "model": r["model"],
                     "item": r["question_id"], "cluster": r["cluster"]})
X, y = [], []
for r in long:
    X.append([1.0, float(r["cond"])] + [1.0 if r["model"] == m else 0.0 for m in NONREF])
    y.append(r["y"])
cid_item = [r["item"] for r in long]
cid_clus = [r["cluster"] for r in long]
items = sorted(set(cid_item))

f2 = irls(X, y)
Vn = inv(f2["XtWX"]); Vi = sand(f2, X, y, cid_item); Vc = sand(f2, X, y, cid_clus)
obs_i = math.sqrt(Vi[1][1]) / math.sqrt(Vn[1][1])
obs_c = math.sqrt(Vc[1][1]) / math.sqrt(Vn[1][1])
P("OBSERVED model (ii): condB beta=%+.4f naive=%.4f CR1[item]=%.4f (r=%.4f) CR1[clus]=%.4f (r=%.4f)"
  % (f2["beta"][1], math.sqrt(Vn[1][1]), math.sqrt(Vi[1][1]), obs_i,
     math.sqrt(Vc[1][1]), obs_c))

# ---------- fit sigma_item by matching the observed CR1[item] intercept inflation
# simple grid: simulate pure random-intercept data, see which sigma reproduces the
# observed model-(i) intercept CR/naive ratio of 1.443 and item ICC.
X1 = [[1.0, float(r["cond"])] for r in long]
f1 = irls(X1, y)
V1n = inv(f1["XtWX"]); V1i = sand(f1, X1, y, cid_item); V1c = sand(f1, X1, y, cid_clus)
obs_int_i = math.sqrt(V1i[0][0]) / math.sqrt(V1n[0][0])
obs_int_c = math.sqrt(V1c[0][0]) / math.sqrt(V1n[0][0])
P("OBSERVED model (i):  intercept naive=%.4f CR1[item]=%.4f (r=%.4f) CR1[clus]=%.4f (r=%.4f)"
  % (math.sqrt(V1n[0][0]), math.sqrt(V1i[0][0]), obs_int_i,
     math.sqrt(V1c[0][0]), obs_int_c))

random.seed(31072026)
def gauss():
    return random.gauss(0.0, 1.0)

beta0 = f2["beta"]
P("\n" + "=" * 96)
P("PARAMETRIC NULL: y ~ Bern(logit^-1(b0 + bcond*condB + bmodel + a_item)),  a_item~N(0,s^2)")
P("i.e. a PURE item random intercept, NO item x condition heterogeneity.")
P("Claim predicts the condB CR/naive ratio should still land near 1.07.")
P("=" * 96)
P("  %6s %5s | %-34s | %-34s | %s"
  % ("sigma", "reps", "condB CR1[item]/naive", "condB CR1[clus]/naive",
     "(i) intercept CR1[item]/naive"))
NREP = 200
for sigma in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5):
    ri, rc, rint = [], [], []
    for _ in range(NREP):
        a = {it: sigma * gauss() for it in items}
        ys = []
        for i, r in enumerate(long):
            eta = sum(X[i][j] * beta0[j] for j in range(len(beta0))) + a[r["item"]]
            eta = max(-500.0, min(500.0, eta))
            ys.append(1 if random.random() < 1.0 / (1.0 + math.exp(-eta)) else 0)
        try:
            fs = irls(X, ys)
            Vns = inv(fs["XtWX"]); Vis = sand(fs, X, ys, cid_item)
            Vcs = sand(fs, X, ys, cid_clus)
            ri.append(math.sqrt(Vis[1][1]) / math.sqrt(Vns[1][1]))
            rc.append(math.sqrt(Vcs[1][1]) / math.sqrt(Vns[1][1]))
            fs1 = irls(X1, ys)
            V1ns = inv(fs1["XtWX"]); V1is = sand(fs1, X1, ys, cid_item)
            rint.append(math.sqrt(V1is[0][0]) / math.sqrt(V1ns[0][0]))
        except Exception:
            pass
    def stat(v):
        v = sorted(v)
        return (sum(v) / len(v), v[int(.025 * len(v))], v[min(len(v) - 1, int(.975 * len(v)))])
    mi, li, hi = stat(ri); mc, lc, hc = stat(rc); mn, ln, hn = stat(rint)
    P("  %6.2f %5d | mean %.4f  [%.4f,%.4f] | mean %.4f  [%.4f,%.4f] | mean %.4f [%.4f,%.4f]"
      % (sigma, len(ri), mi, li, hi, mc, lc, hc, mn, ln, hn))
P("\n  OBSERVED: condB CR1[item]/naive = %.4f   CR1[clus]/naive = %.4f   (i)intercept = %.4f"
  % (obs_i, obs_c, obs_int_i))
P("  -> read off which sigma reproduces the observed (i)-intercept ratio %.3f, then check"
  % obs_int_i)
P("     whether that same sigma reproduces the observed condB ratio %.3f." % obs_i)

json.dump({"log": OUT}, open(os.path.join(HERE, "prim_refute_se_inflation2_out.json"), "w"))
P("\n[done]")

"""INDEPENDENT recomputation of naive vs cluster-robust SEs for the condition
coefficient in the pooled logistic models (i) y~condB and (ii) y~condB+model.

Everything hand-rolled: dense IRLS (Newton-Raphson / Fisher scoring), Gaussian
elimination inverse, CR0/CR1/CR2-ish sandwich meats at two nesting levels.
No numpy/scipy/pandas.

Goal: check the four claimed SE numbers/ratios AND the mechanistic story
("condition is a purely within-item contrast so the item random intercept
cancels; clustering matters much more for the intercept and for between-model
comparisons").
"""
import json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "paired_clean.json")

MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
SHORT = {"google/gemini-3.6-flash": "gemini", "google/gemma-4-26b-a4b-it": "gemma",
         "qwen/qwen3.6-35b-a3b": "qwen", "z-ai/glm-5.2": "glm"}
REF = MODELS[0]

OUT = []
def P(*a):
    s = " ".join(str(x) for x in a)
    print(s); OUT.append(s)

# ------------------------------------------------------------------ linear alg
def inv(M):
    """Gauss-Jordan inverse with partial pivoting."""
    n = len(M)
    A = [list(M[i]) + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(A[r][c]))
        if abs(A[piv][c]) < 1e-14:
            raise ValueError("singular at col %d" % c)
        A[c], A[piv] = A[piv], A[c]
        d = A[c][c]
        A[c] = [v / d for v in A[c]]
        for r in range(n):
            if r == c:
                continue
            f = A[r][c]
            if f != 0.0:
                A[r] = [A[r][k] - f * A[c][k] for k in range(2 * n)]
    return [row[n:] for row in A]

def mm(A, B):
    n, m, p = len(A), len(B), len(B[0])
    return [[sum(A[i][k] * B[k][j] for k in range(m)) for j in range(p)] for i in range(n)]

def mv(A, v):
    return [sum(A[i][k] * v[k] for k in range(len(v))) for i in range(len(A))]

def qform(L, V):
    return sum(L[a] * V[a][b] * L[b] for a in range(len(L)) for b in range(len(L)))

# ------------------------------------------------------------------- IRLS
def irls(X, y, tol=1e-12, maxit=200):
    """Dense IRLS for logistic regression. X: list of rows (list of floats)."""
    n, k = len(X), len(X[0])
    beta = [0.0] * k
    ll_old = None
    for it in range(maxit):
        XtWX = [[0.0] * k for _ in range(k)]
        XtWz = [0.0] * k
        ll = 0.0
        p = [0.0] * n
        for i in range(n):
            eta = sum(X[i][j] * beta[j] for j in range(k))
            if eta > 500: eta = 500.0
            if eta < -500: eta = -500.0
            pi = 1.0 / (1.0 + math.exp(-eta))
            p[i] = pi
            ll += y[i] * math.log(max(pi, 1e-300)) + (1 - y[i]) * math.log(max(1 - pi, 1e-300))
            w = max(pi * (1 - pi), 1e-12)
            r = y[i] - pi
            for a in range(k):
                xa = X[i][a]
                if xa == 0.0: continue
                XtWz[a] += xa * r
                for b in range(k):
                    XtWX[a][b] += xa * w * X[i][b]
        step = mv(inv(XtWX), XtWz)
        beta = [beta[j] + step[j] for j in range(k)]
        if ll_old is not None and abs(ll - ll_old) < tol and max(abs(s) for s in step) < 1e-10:
            ll_old = ll
            break
        ll_old = ll
    # final quantities at converged beta
    XtWX = [[0.0] * k for _ in range(k)]
    p = [0.0] * n
    ll = 0.0
    for i in range(n):
        eta = sum(X[i][j] * beta[j] for j in range(k))
        pi = 1.0 / (1.0 + math.exp(-eta))
        p[i] = pi
        ll += y[i] * math.log(max(pi, 1e-300)) + (1 - y[i]) * math.log(max(1 - pi, 1e-300))
        w = pi * (1 - pi)
        for a in range(k):
            xa = X[i][a]
            if xa == 0.0: continue
            for b in range(k):
                XtWX[a][b] += xa * w * X[i][b]
    return {"beta": beta, "p": p, "XtWX": XtWX, "n": n, "k": k, "loglik": ll, "iters": it + 1}

def naive_vcov(fit):
    return inv(fit["XtWX"])

def sandwich(fit, X, y, cid, correction="CR1"):
    k, n = fit["k"], fit["n"]
    bread = inv(fit["XtWX"])
    g = {}
    for i in range(n):
        s = g.setdefault(cid[i], [0.0] * k)
        r = y[i] - fit["p"][i]
        for a in range(k):
            if X[i][a] != 0.0:
                s[a] += X[i][a] * r
    G = len(g)
    meat = [[0.0] * k for _ in range(k)]
    for s in g.values():
        for a in range(k):
            if s[a] == 0.0: continue
            for b in range(k):
                meat[a][b] += s[a] * s[b]
    if correction == "CR1":
        c = (G / (G - 1.0)) * ((n - 1.0) / (n - k))
    elif correction == "CR0":
        c = 1.0
    elif correction == "G":          # only the G/(G-1) part
        c = G / (G - 1.0)
    else:
        raise ValueError(correction)
    meat = [[meat[a][b] * c for b in range(k)] for a in range(k)]
    V = mm(mm(bread, meat), bread)
    for a in range(k):
        for b in range(a + 1, k):
            m = 0.5 * (V[a][b] + V[b][a]); V[a][b] = V[b][a] = m
    return V, G, g, bread

# ------------------------------------------------------------------ load
raw = json.load(open(DATA))
cells = [r for r in raw if r.get("analysis_include") is True]
P("cells=%d items=%d clusters=%d models=%d"
  % (len(cells), len(set(r["question_id"] for r in cells)),
     len(set(r["cluster"] for r in cells)), len(set(r["model"] for r in cells))))
P("\n--- observed marginals (confirm) ---")
for m in MODELS:
    sub = [r for r in cells if r["model"] == m]
    a = sum(r["A_correct"] for r in sub) / len(sub)
    b = sum(r["B_correct"] for r in sub) / len(sub)
    P("  %-8s n=%4d A %.4f B %.4f  %+.1fpp" % (SHORT[m], len(sub), a, b, 100 * (b - a)))

long = []
for r in cells:
    for cond, key in ((0, "A_correct"), (1, "B_correct")):
        long.append({"y": int(r[key]), "cond": cond, "model": r["model"],
                     "item": r["question_id"], "cluster": r["cluster"]})
P("long rows = %d" % len(long))
cid_item = [r["item"] for r in long]
cid_clus = [r["cluster"] for r in long]
NONREF = [m for m in MODELS if m != REF]

# ---------------------------------------------------------- design matrices
def design(with_model=False, with_inter=False):
    names = ["(intercept)", "condB"]
    if with_model: names += ["model[%s]" % SHORT[m] for m in NONREF]
    if with_inter: names += ["condB:model[%s]" % SHORT[m] for m in NONREF]
    X, y = [], []
    for r in long:
        row = [1.0, float(r["cond"])]
        if with_model:
            row += [1.0 if r["model"] == m else 0.0 for m in NONREF]
        if with_inter:
            row += [float(r["cond"]) if r["model"] == m else 0.0 for m in NONREF]
        X.append(row); y.append(r["y"])
    return X, y, names

def report(label, X, y, names):
    fit = irls(X, y)
    Vn = naive_vcov(fit)
    Vi, Gi, gi, bread = sandwich(fit, X, y, cid_item)
    Vc, Gc, gc, _ = sandwich(fit, X, y, cid_clus)
    Vi0, _, _, _ = sandwich(fit, X, y, cid_item, "CR0")
    Vc0, _, _, _ = sandwich(fit, X, y, cid_clus, "CR0")
    P("\n" + "=" * 100)
    P("%s   (iters=%d logLik=%.4f k=%d G_item=%d G_clus=%d)"
      % (label, fit["iters"], fit["loglik"], fit["k"], Gi, Gc))
    P("  %-26s %9s %9s %9s %6s %9s %6s | %9s %9s"
      % ("term", "coef", "SE_naive", "SEcr1_it", "ratio", "SEcr1_cl", "ratio",
         "SEcr0_it", "SEcr0_cl"))
    for j, nm in enumerate(names):
        sn = math.sqrt(Vn[j][j]); si = math.sqrt(Vi[j][j]); sc = math.sqrt(Vc[j][j])
        P("  %-26s %+9.4f %9.4f %9.4f %6.3f %9.4f %6.3f | %9.4f %9.4f"
          % (nm, fit["beta"][j], sn, si, si / sn, sc, sc / sn,
             math.sqrt(Vi0[j][j]), math.sqrt(Vc0[j][j])))
    return fit, Vn, Vi, Vc, names

X1, y1, n1 = design(False, False)
f1, V1n, V1i, V1c, _ = report("(i)  y ~ condB", X1, y1, n1)
X2, y2, n2 = design(True, False)
f2, V2n, V2i, V2c, _ = report("(ii) y ~ condB + model", X2, y2, n2)
X3, y3, n3 = design(True, True)
f3, V3n, V3i, V3c, _ = report("(iii) y ~ condB * model", X3, y3, n3)

# ------------------------------------------------- claimed numbers check
P("\n" + "#" * 100)
P("CLAIM CHECK (claim states: (ii) condB 0.1145 -> 0.1223 ratio 1.068;")
P("             (ii) intercept 0.1834 -> 0.1992 ratio 1.086;")
P("             (i)  intercept 0.0915 -> 0.1321 ratio 1.44;")
P("             (ii) condB item-clustered 0.1237 vs cluster-clustered 0.1223)")
P("#" * 100)
def chk(lab, got, claimed):
    P("  %-46s computed=%.4f claimed=%.4f  %s"
      % (lab, got, claimed, "MATCH" if abs(got - claimed) < 5e-4 else "*** MISMATCH ***"))
chk("(ii) condB naive SE", math.sqrt(V2n[1][1]), 0.1145)
chk("(ii) condB CR1[cluster208]", math.sqrt(V2c[1][1]), 0.1223)
chk("(ii) condB CR1[item325]", math.sqrt(V2i[1][1]), 0.1237)
chk("(ii) intercept naive SE", math.sqrt(V2n[0][0]), 0.1834)
chk("(ii) intercept CR1[cluster208]", math.sqrt(V2c[0][0]), 0.1992)
chk("(i)  intercept naive SE", math.sqrt(V1n[0][0]), 0.0915)
chk("(i)  intercept CR1[cluster208]", math.sqrt(V1c[0][0]), 0.1321)
P("  ratios: (ii)condB cl=%.4f it=%.4f | (ii)intercept cl=%.4f | (i)intercept cl=%.4f it=%.4f"
  % (math.sqrt(V2c[1][1]) / math.sqrt(V2n[1][1]),
     math.sqrt(V2i[1][1]) / math.sqrt(V2n[1][1]),
     math.sqrt(V2c[0][0]) / math.sqrt(V2n[0][0]),
     math.sqrt(V1c[0][0]) / math.sqrt(V1n[0][0]),
     math.sqrt(V1i[0][0]) / math.sqrt(V1n[0][0])))
P("  ALSO (i) condB: naive=%.4f CR1[item]=%.4f (r=%.3f) CR1[clus]=%.4f (r=%.3f)"
  % (math.sqrt(V1n[1][1]), math.sqrt(V1i[1][1]),
     math.sqrt(V1i[1][1]) / math.sqrt(V1n[1][1]), math.sqrt(V1c[1][1]),
     math.sqrt(V1c[1][1]) / math.sqrt(V1n[1][1])))

# -------------------------------------- MECHANISM TEST 1: model contrasts
P("\n" + "#" * 100)
P("MECHANISM TEST 1 -- the claim says clustering 'matters much more for ... the")
P("between-model comparisons'.  But model contrasts are ALSO purely WITHIN-item")
P("(crossed design: every item is answered by all 4 models), so by the claim's own")
P("logic the item intercept should cancel out of them too.  Ratios from model (ii):")
P("#" * 100)
for j, nm in enumerate(n2):
    sn = math.sqrt(V2n[j][j])
    P("  %-26s SE_naive=%.4f  CR1[item]=%.4f (r=%.3f)  CR1[cluster]=%.4f (r=%.3f)"
      % (nm, sn, math.sqrt(V2i[j][j]), math.sqrt(V2i[j][j]) / sn,
         math.sqrt(V2c[j][j]), math.sqrt(V2c[j][j]) / sn))

# pairwise model contrasts (all 6), model (ii)
P("\n  All 6 pairwise between-model contrasts (model (ii)), SE ratios:")
for a in range(4):
    for b in range(a + 1, 4):
        L = [0.0] * len(n2)
        if MODELS[a] != REF: L[n2.index("model[%s]" % SHORT[MODELS[a]])] = 1.0
        if MODELS[b] != REF: L[n2.index("model[%s]" % SHORT[MODELS[b]])] = -1.0
        sn = math.sqrt(qform(L, V2n)); si = math.sqrt(qform(L, V2i)); sc = math.sqrt(qform(L, V2c))
        P("    %-8s - %-8s  est=%+.4f SE_naive=%.4f CR1[item]=%.4f (r=%.3f) CR1[clus]=%.4f (r=%.3f)"
          % (SHORT[MODELS[a]], SHORT[MODELS[b]],
             sum(L[j] * f2["beta"][j] for j in range(len(n2))), sn, si, si / sn, sc, sc / sn))

# ------------------------------ MECHANISM TEST 2: does the item intercept cancel?
P("\n" + "#" * 100)
P("MECHANISM TEST 2 -- direct test of 'the item random intercept cancels out of the")
P("condition contrast'.  The influence function of beta_j is  IF_g = e_j' A^-1 u_g.")
P("Decompose each item's condB influence contribution into the part driven by the")
P("item's OVERALL level (sum of residuals) vs the WITHIN-item A-vs-B difference.")
P("#" * 100)
# recompute per-item score vectors for model (ii)
_, _, gi2, bread2 = sandwich(f2, X2, y2, cid_item)
k2 = f2["k"]
e_cond = [0.0] * k2; e_cond[1] = 1.0
a_cond = mv([[bread2[r][c] for c in range(k2)] for r in range(k2)], e_cond)  # A^-1 e_cond
e_int = [0.0] * k2; e_int[0] = 1.0
a_int = mv(bread2, e_int)
P("  A^-1 e_condB      = [%s]" % ", ".join("%+.4f" % v for v in a_cond))
P("  A^-1 e_intercept  = [%s]" % ", ".join("%+.4f" % v for v in a_int))
P("  -> the condB row of A^-1 puts weight %+.4f on the INTERCEPT score (sum of ALL"
  % a_cond[0])
P("     residuals in the item) and %+.4f on the condB score (sum of B-row residuals)."
  % a_cond[1])
P("     Because these are nearly equal and opposite, IF_condB(item) is (up to the")
P("     model-dummy terms) proportional to  mean(B resid) - mean(A resid): the item")
P("     level cancels.  Verify numerically item-by-item:")

if_cond = {}
if_int = {}
for it, u in gi2.items():
    if_cond[it] = sum(a_cond[j] * u[j] for j in range(k2))
    if_int[it] = sum(a_int[j] * u[j] for j in range(k2))
# item-level "level" statistic = sum of all 8 residuals; "difference" = sum B - sum A
lev, dif = {}, {}
for i, r in enumerate(long):
    res = y2[i] - f2["p"][i]
    lev[r["item"]] = lev.get(r["item"], 0.0) + res
    dif[r["item"]] = dif.get(r["item"], 0.0) + (res if r["cond"] == 1 else -res)

def corr(d1, d2):
    ks = list(d1)
    n = len(ks)
    m1 = sum(d1[k] for k in ks) / n; m2 = sum(d2[k] for k in ks) / n
    s12 = sum((d1[k] - m1) * (d2[k] - m2) for k in ks)
    s11 = sum((d1[k] - m1) ** 2 for k in ks); s22 = sum((d2[k] - m2) ** 2 for k in ks)
    return s12 / math.sqrt(s11 * s22)

P("    corr(IF_condB , item LEVEL  sum-of-residuals) = %+.4f" % corr(if_cond, lev))
P("    corr(IF_condB , item B-minus-A difference)    = %+.4f" % corr(if_cond, dif))
P("    corr(IF_intercept, item LEVEL)                = %+.4f" % corr(if_int, lev))
P("    corr(IF_intercept, item B-minus-A difference) = %+.4f" % corr(if_int, dif))

# ------------------- MECHANISM TEST 3: what would pure random-intercept predict?
P("\n" + "#" * 100)
P("MECHANISM TEST 3 -- how much of the residual +7% is item level vs item x condition?")
P("Compare CR1[item] on the FULL long data against a version where within each item")
P("the A/B labels are randomly swapped (destroys item x condition interaction but")
P("KEEPS the item level intact).  If the item intercept truly contributes nothing,")
P("swapping should leave the condB CR SE at the naive value.")
P("#" * 100)
random.seed(20260731)
by_item = {}
for i, r in enumerate(long):
    by_item.setdefault((r["item"], r["model"]), []).append(i)
NPERM = 400
rat_i, rat_c = [], []
for _ in range(NPERM):
    yp = list(y2)
    for it in set(r["item"] for r in long):
        # swap A/B within the whole item (all 4 models together): keeps item level
        if random.random() < 0.5:
            continue
    # simpler: swap within each (item,model) cell independently, per replicate
    for key, idxs in by_item.items():
        if random.random() < 0.5 and len(idxs) == 2:
            yp[idxs[0]], yp[idxs[1]] = yp[idxs[1]], yp[idxs[0]]
    fp = irls(X2, yp)
    Vpn = naive_vcov(fp)
    Vpi, _, _, _ = sandwich(fp, X2, yp, cid_item)
    Vpc, _, _, _ = sandwich(fp, X2, yp, cid_clus)
    rat_i.append(math.sqrt(Vpi[1][1]) / math.sqrt(Vpn[1][1]))
    rat_c.append(math.sqrt(Vpc[1][1]) / math.sqrt(Vpn[1][1]))
rat_i.sort(); rat_c.sort()
def q(v, p): return v[min(len(v) - 1, int(p * len(v)))]
P("  A/B-swapped within (item,model) [item level preserved, itemxcond destroyed]:")
P("    condB CR1[item]/naive   ratio: mean=%.4f  median=%.4f  [2.5%%,97.5%%]=[%.4f,%.4f]"
  % (sum(rat_i) / len(rat_i), q(rat_i, .5), q(rat_i, .025), q(rat_i, .975)))
P("    condB CR1[clus]/naive   ratio: mean=%.4f  median=%.4f  [2.5%%,97.5%%]=[%.4f,%.4f]"
  % (sum(rat_c) / len(rat_c), q(rat_c, .5), q(rat_c, .025), q(rat_c, .975)))
P("    OBSERVED ratios: item=%.4f cluster=%.4f"
  % (math.sqrt(V2i[1][1]) / math.sqrt(V2n[1][1]),
     math.sqrt(V2c[1][1]) / math.sqrt(V2n[1][1])))
pi_ = sum(1 for v in rat_i if v >= math.sqrt(V2i[1][1]) / math.sqrt(V2n[1][1]))
P("    perm p (one-sided, obs item-ratio >= null): %.4f" % ((pi_ + 1) / (NPERM + 1.0)))

# ------------------------------------- ICC of the item random effect, for context
P("\n" + "#" * 100)
P("CONTEXT: how large is the item-level ICC actually?")
P("#" * 100)
# residual-based item ICC on the Pearson residual scale, model (ii)
by_it = {}
for i, r in enumerate(long):
    w = f2["p"][i] * (1 - f2["p"][i])
    by_it.setdefault(r["item"], []).append((y2[i] - f2["p"][i]) / math.sqrt(max(w, 1e-12)))
num = den = 0.0
allr = [v for vs in by_it.values() for v in vs]
mbar = sum(allr) / len(allr)
npairs = 0
for vs in by_it.values():
    for a in range(len(vs)):
        for b in range(len(vs)):
            if a != b:
                num += (vs[a] - mbar) * (vs[b] - mbar); npairs += 1
den = sum((v - mbar) ** 2 for v in allr)
P("  Pearson-residual intra-item correlation (moment est.) = %.4f (pairs=%d)"
  % ((num / npairs) / (den / len(allr)), npairs))
# same for clusters
by_cl = {}
for i, r in enumerate(long):
    w = f2["p"][i] * (1 - f2["p"][i])
    by_cl.setdefault(r["cluster"], []).append((y2[i] - f2["p"][i]) / math.sqrt(max(w, 1e-12)))
num = 0.0; npairs = 0
for vs in by_cl.values():
    for a in range(len(vs)):
        for b in range(len(vs)):
            if a != b:
                num += (vs[a] - mbar) * (vs[b] - mbar); npairs += 1
P("  Pearson-residual intra-CLUSTER correlation             = %.4f (pairs=%d)"
  % ((num / npairs) / (den / len(allr)), npairs))
# A-vs-B within (item,model) tetrachoric-ish: phi correlation of A_correct,B_correct
n11 = sum(1 for r in cells if r["A_correct"] and r["B_correct"])
n10 = sum(1 for r in cells if r["A_correct"] and not r["B_correct"])
n01 = sum(1 for r in cells if not r["A_correct"] and r["B_correct"])
n00 = sum(1 for r in cells if not r["A_correct"] and not r["B_correct"])
N = len(cells)
phi = (n11 * n00 - n10 * n01) / math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
P("  phi(A_correct, B_correct) within cell = %.4f  (n11=%d n10=%d n01=%d n00=%d)"
  % (phi, n11, n10, n01, n00))

json.dump({"log": OUT}, open(os.path.join(HERE, "prim_refute_se_inflation_out.json"), "w"))
P("\n[done]")

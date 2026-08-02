"""INDEPENDENT recompute: cluster-robust vs naive SE inflation, model (i)/(ii)/(iii).

Refutation target: "condition is a purely WITHIN-item contrast so the item random
intercept cancels; clustering matters much more for the intercept and the
between-model comparisons."

Everything hand-rolled: Gauss-Jordan inverse, dense IRLS, CR0/CR1/CR2-ish
sandwiches, moment ICC, cluster bootstrap. Stdlib only. Deliberately does NOT
import prim_linalg (independent code path).
"""
import json, math, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "paired_clean.json")

MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
SHORT = {"google/gemini-3.6-flash": "gemini", "google/gemma-4-26b-a4b-it": "gemma",
         "qwen/qwen3.6-35b-a3b": "qwen", "z-ai/glm-5.2": "glm"}
REF = MODELS[0]

LOG = []
def P(*a):
    s = " ".join(str(x) for x in a)
    print(s); LOG.append(s)


# ------------------------------------------------------- dense linear algebra
def inv(A):
    """Gauss-Jordan with partial pivoting. Independent of prim_linalg's Cholesky."""
    n = len(A)
    M = [list(A[i]) + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-14:
            raise ValueError("singular at col %d" % c)
        M[c], M[piv] = M[piv], M[c]
        d = M[c][c]
        M[c] = [v / d for v in M[c]]
        for r in range(n):
            if r == c:
                continue
            f = M[r][c]
            if f == 0.0:
                continue
            Mr, Mc = M[r], M[c]
            for j in range(c, 2 * n):
                Mr[j] -= f * Mc[j]
    return [row[n:] for row in M]


def mm(A, B):
    n, m, p = len(A), len(B), len(B[0])
    C = [[0.0] * p for _ in range(n)]
    for i in range(n):
        Ai, Ci = A[i], C[i]
        for k in range(m):
            a = Ai[k]
            if a:
                Bk = B[k]
                for j in range(p):
                    Ci[j] += a * Bk[j]
    return C


def qform(L, V):
    return sum(L[i] * sum(V[i][j] * L[j] for j in range(len(L))) for i in range(len(L)))


def z_p(z):
    return math.erfc(abs(z) / math.sqrt(2.0))


# ---------------------------------------------------------------- dense IRLS
def irls(X, y, tol=1e-12, maxit=100):
    """X dense list-of-lists (n x k). Newton-Raphson on the logit likelihood."""
    n, k = len(X), len(X[0])
    b = [0.0] * k
    ybar = min(max(sum(y) / n, 1e-9), 1 - 1e-9)
    b[0] = math.log(ybar / (1 - ybar))
    for it in range(maxit):
        H = [[0.0] * k for _ in range(k)]
        g = [0.0] * k
        for i in range(n):
            xi = X[i]
            eta = sum(xi[j] * b[j] for j in range(k))
            eta = max(-500.0, min(500.0, eta))
            pi = 1.0 / (1.0 + math.exp(-eta))
            w = max(pi * (1 - pi), 1e-12)
            r = y[i] - pi
            nz = [j for j in range(k) if xi[j]]
            for j in nz:
                g[j] += xi[j] * r
                wv = w * xi[j]
                Hj = H[j]
                for j2 in nz:
                    Hj[j2] += wv * xi[j2]
        Hi = inv(H)
        d = [sum(Hi[j][l] * g[l] for l in range(k)) for j in range(k)]
        b = [b[j] + d[j] for j in range(k)]
        if max(abs(v) for v in d) < tol:
            break
    # final pass
    H = [[0.0] * k for _ in range(k)]
    p = [0.0] * n
    ll = 0.0
    for i in range(n):
        xi = X[i]
        eta = max(-500.0, min(500.0, sum(xi[j] * b[j] for j in range(k))))
        pi = 1.0 / (1.0 + math.exp(-eta))
        p[i] = pi
        ll += y[i] * math.log(max(pi, 1e-300)) + (1 - y[i]) * math.log(max(1 - pi, 1e-300))
        w = max(pi * (1 - pi), 1e-12)
        nz = [j for j in range(k) if xi[j]]
        for j in nz:
            wv = w * xi[j]
            Hj = H[j]
            for j2 in nz:
                Hj[j2] += wv * xi[j2]
    return {"beta": b, "p": p, "XtWX": H, "n": n, "k": k, "loglik": ll, "iters": it + 1}


def V_naive(fit):
    return inv(fit["XtWX"])


def V_cr(fit, X, y, gid, kind="CR1"):
    """Sandwich. kind in {CR0, CR1}. CR1 factor G/(G-1) * (N-1)/(N-k)."""
    k, n = fit["k"], fit["n"]
    bread = inv(fit["XtWX"])
    p = fit["p"]
    U = {}
    for i in range(n):
        s = U.setdefault(gid[i], [0.0] * k)
        r = y[i] - p[i]
        xi = X[i]
        for j in range(k):
            if xi[j]:
                s[j] += xi[j] * r
    meat = [[0.0] * k for _ in range(k)]
    for s in U.values():
        for a in range(k):
            if s[a]:
                for bb in range(k):
                    meat[a][bb] += s[a] * s[bb]
    G = len(U)
    if kind == "CR1":
        c = (G / (G - 1.0)) * ((n - 1.0) / (n - k))
        for a in range(k):
            for bb in range(k):
                meat[a][bb] *= c
    V = mm(mm(bread, meat), bread)
    for a in range(k):
        for bb in range(a + 1, k):
            m = 0.5 * (V[a][bb] + V[bb][a])
            V[a][bb] = V[bb][a] = m
    return V, G


# --------------------------------------------------------------------- data
raw = json.load(open(DATA))
cells = [r for r in raw if r.get("analysis_include") is True]
P("cells=%d items=%d clusters=%d models=%d"
  % (len(cells), len(set(r["question_id"] for r in cells)),
     len(set(r["cluster"] for r in cells)), len(set(r["model"] for r in cells))))

P("\n--- observed marginals (independent recompute) ---")
for m in MODELS:
    s = [r for r in cells if r["model"] == m]
    a = sum(r["A_correct"] for r in s) / len(s)
    b = sum(r["B_correct"] for r in s) / len(s)
    P("  %-8s n=%4d  A %6.2f%%  B %6.2f%%  %+.2fpp" % (SHORT[m], len(s), 100*a, 100*b, 100*(b-a)))

# balance check
cnt = {}
for r in cells:
    cnt[r["question_id"]] = cnt.get(r["question_id"], 0) + 1
from collections import Counter
P("  models-per-item distribution:", dict(Counter(cnt.values())))

long = []
for r in cells:
    for cond, key in ((0, "A_correct"), (1, "B_correct")):
        long.append({"y": int(r[key]), "cond": cond, "model": r["model"],
                     "item": r["question_id"], "cluster": r["cluster"],
                     "hasctx": int(bool(r["has_context"])),
                     "neg": int(bool(r["negated_stem"])),
                     "qlen": r["qlen"]})
P("  long rows =", len(long))

item_ids = [r["item"] for r in long]
clus_ids = [r["cluster"] for r in long]

qmean = sum(r["qlen"] for r in long) / len(long)
qsd = math.sqrt(sum((r["qlen"] - qmean) ** 2 for r in long) / len(long))


def design(terms):
    names = ["(intercept)"]
    if "cond" in terms:
        names.append("condB")
    if "model" in terms:
        names += ["model[%s]" % SHORT[m] for m in MODELS if m != REF]
    if "inter" in terms:
        names += ["condB:model[%s]" % SHORT[m] for m in MODELS if m != REF]
    if "between" in terms:
        names += ["has_context", "negated_stem", "qlen_z"]
    idx = {nm: i for i, nm in enumerate(names)}
    X, y = [], []
    for r in long:
        row = [0.0] * len(names)
        row[0] = 1.0
        if "cond" in terms and r["cond"] == 1:
            row[idx["condB"]] = 1.0
        if "model" in terms and r["model"] != REF:
            row[idx["model[%s]" % SHORT[r["model"]]]] = 1.0
        if "inter" in terms and r["cond"] == 1 and r["model"] != REF:
            row[idx["condB:model[%s]" % SHORT[r["model"]]]] = 1.0
        if "between" in terms:
            row[idx["has_context"]] = float(r["hasctx"])
            row[idx["negated_stem"]] = float(r["neg"])
            row[idx["qlen_z"]] = (r["qlen"] - qmean) / qsd
        X.append(row); y.append(r["y"])
    return X, y, names


def table(label, terms):
    X, y, names = design(terms)
    fit = irls(X, y)
    Vn = V_naive(fit)
    Vi1, Gi = V_cr(fit, X, y, item_ids, "CR1")
    Vc1, Gc = V_cr(fit, X, y, clus_ids, "CR1")
    Vi0, _ = V_cr(fit, X, y, item_ids, "CR0")
    Vc0, _ = V_cr(fit, X, y, clus_ids, "CR0")
    P("\n" + "=" * 104)
    P("%s   (iters=%d loglik=%.4f k=%d)" % (label, fit["iters"], fit["loglik"], fit["k"]))
    P("=" * 104)
    P("  %-26s %9s %9s %9s %7s %9s %7s %9s %9s"
      % ("term", "coef", "SE_naive", "SEitem1", "ratio", "SEclus1", "ratio", "SEitem0", "SEclus0"))
    res = {}
    for j, nm in enumerate(names):
        sn = math.sqrt(Vn[j][j]); si = math.sqrt(Vi1[j][j]); sc = math.sqrt(Vc1[j][j])
        si0 = math.sqrt(Vi0[j][j]); sc0 = math.sqrt(Vc0[j][j])
        P("  %-26s %9.4f %9.4f %9.4f %7.3f %9.4f %7.3f %9.4f %9.4f"
          % (nm, fit["beta"][j], sn, si, si/sn, sc, sc/sn, si0, sc0))
        res[nm] = dict(b=fit["beta"][j], se_naive=sn, se_item=si, se_clus=sc,
                       r_item=si/sn, r_clus=sc/sn, se_item0=si0, se_clus0=sc0)
    return fit, names, X, y, Vn, Vi1, Vc1, res


f1, n1, X1, y1, Vn1, Vi1, Vc1, R1 = table("(i)   y ~ condB", {"cond"})
f2, n2, X2, y2, Vn2, Vi2, Vc2, R2 = table("(ii)  y ~ condB + model", {"cond", "model"})
f3, n3, X3, y3, Vn3, Vi3, Vc3, R3 = table("(iii) y ~ condB * model", {"cond", "model", "inter"})
f4, n4, X4, y4, Vn4, Vi4, Vc4, R4 = table(
    "(iv)  y ~ condB + model + has_context + negated_stem + qlen_z  [WITHIN vs BETWEEN item]",
    {"cond", "model", "between"})

# --------------------------------------------------- claim numbers, verbatim
P("\n" + "=" * 104)
P("CLAIMED NUMBERS vs RECOMPUTED")
P("=" * 104)
claims = [
    ("(ii) condB naive SE",     0.1145, R2["condB"]["se_naive"]),
    ("(ii) condB CR cluster",   0.1223, R2["condB"]["se_clus"]),
    ("(ii) condB ratio",        1.068,  R2["condB"]["r_clus"]),
    ("(ii) intercept naive",    0.1834, R2["(intercept)"]["se_naive"]),
    ("(ii) intercept CR clus",  0.1992, R2["(intercept)"]["se_clus"]),
    ("(ii) intercept ratio",    1.086,  R2["(intercept)"]["r_clus"]),
    ("(i)  intercept naive",    0.0915, R1["(intercept)"]["se_naive"]),
    ("(i)  intercept CR clus",  0.1321, R1["(intercept)"]["se_clus"]),
    ("(i)  intercept ratio",    1.44,   R1["(intercept)"]["r_clus"]),
    ("(ii) condB CR item",      0.1237, R2["condB"]["se_item"]),
]
for lab, c, got in claims:
    tag = "MATCH" if abs(c - got) <= max(0.0006, 0.006 * abs(c)) else "**MISMATCH**"
    P("  %-24s claimed %8.4f   recomputed %8.4f   %s" % (lab, c, got, tag))

# ------------------------------------ WITHIN vs BETWEEN item variable ratios
P("\n" + "=" * 104)
P("STRUCTURAL TEST: is 'within-item' the reason for the small ratio?")
P("=" * 104)
P("  In model (iv) all terms come from ONE fit, so bread/meat are shared.")
P("  condB  : within-item (every item has both conditions)      ")
P("  model[]: within-item (every item answered by all 4 models) ")
P("  has_context / negated_stem / qlen_z: CONSTANT within item -> purely between-item")
P("")
P("  %-26s %-14s %8s %8s %8s" % ("term", "variation", "r_item", "r_clus", "SE_naive"))
kinds = {"(intercept)": "level (betw.)", "condB": "WITHIN-item",
         "model[gemma]": "WITHIN-item", "model[qwen]": "WITHIN-item",
         "model[glm]": "WITHIN-item", "has_context": "BETWEEN-item",
         "negated_stem": "BETWEEN-item", "qlen_z": "BETWEEN-item"}
for nm in n4:
    P("  %-26s %-14s %8.3f %8.3f %8.4f"
      % (nm, kinds.get(nm, "?"), R4[nm]["r_item"], R4[nm]["r_clus"], R4[nm]["se_naive"]))

# ------------------------------------------------- ICC of the binary outcome
P("\n" + "=" * 104)
P("ICC (is it in fact 'large'?)")
P("=" * 104)


def icc_anova(vals_by_group):
    """One-way random-effects ICC(1) on the 0/1 outcome, unequal group sizes."""
    groups = [v for v in vals_by_group.values() if len(v) > 0]
    k = len(groups)
    N = sum(len(v) for v in groups)
    gm = sum(sum(v) for v in groups) / N
    msb = sum(len(v) * (sum(v) / len(v) - gm) ** 2 for v in groups) / (k - 1)
    msw = sum(sum((x - sum(v) / len(v)) ** 2 for x in v) for v in groups) / (N - k)
    n0 = (N - sum(len(v) ** 2 for v in groups) / N) / (k - 1)
    return (msb - msw) / (msb + (n0 - 1) * msw), msb, msw, n0


by_item, by_clus = {}, {}
for r in long:
    by_item.setdefault(r["item"], []).append(float(r["y"]))
    by_clus.setdefault(r["cluster"], []).append(float(r["y"]))
ii, msb, msw, n0 = icc_anova(by_item)
P("  ICC(1) on y, item level     = %.4f   (MSB=%.4f MSW=%.4f n0=%.2f)" % (ii, msb, msw, n0))
ic, msb, msw, n0 = icc_anova(by_clus)
P("  ICC(1) on y, cluster level  = %.4f   (MSB=%.4f MSW=%.4f n0=%.2f)" % (ic, msb, msw, n0))

# ICC of the WITHIN-ITEM CONDITION CONTRAST (the quantity that actually matters
# for the condB SE) at the clinical-cluster level.
dif = {}
for r in cells:
    dif.setdefault(r["question_id"], []).append(r["B_correct"] - r["A_correct"])
item_d = {k: sum(v) / len(v) for k, v in dif.items()}
by_clus_d = {}
for r in cells:
    by_clus_d.setdefault(r["cluster"], set()).add(r["question_id"])
cd = {c: [item_d[q] for q in qs] for c, qs in by_clus_d.items()}
cd2 = {c: v for c, v in cd.items() if len(v) > 1}
if len(cd2) > 1:
    icd, msb, msw, n0 = icc_anova(cd)
    P("  ICC(1) of the per-item condition DIFFERENCE across items in a clinical cluster = %.4f" % icd)

# --------------------------------- variance decomposition of the condB score
P("\n" + "=" * 104)
P("WHY the item-clustered condB SE is only mildly inflated: decompose the meat")
P("=" * 104)
P("  Compare CR1 sandwich vs an 'independence meat' (sum of per-ROW outer products,")
P("  = HC0-style). The item cluster meat differs from it by the sum of CROSS-ROW")
P("  terms within item. Split those cross terms into:")
P("    (a) same-model, A-vs-B pairs   -> the pairing, should REDUCE contrast variance")
P("    (b) same-condition, model-model -> shared item difficulty, INCREASES it")
P("    (c) cross-condition, cross-model")


def meat_parts(fit, X, y, gid, k):
    p = fit["p"]
    rows = {}
    for i in range(fit["n"]):
        rows.setdefault(gid[i], []).append(i)
    parts = {"diag": [[0.0] * k for _ in range(k)],
             "a": [[0.0] * k for _ in range(k)],
             "b": [[0.0] * k for _ in range(k)],
             "c": [[0.0] * k for _ in range(k)]}
    for g, idxs in rows.items():
        for i in idxs:
            ri = y[i] - p[i]
            for j in idxs:
                rj = y[j] - p[j]
                if i == j:
                    tgt = parts["diag"]
                else:
                    same_model = long[i]["model"] == long[j]["model"]
                    same_cond = long[i]["cond"] == long[j]["cond"]
                    tgt = parts["a"] if (same_model and not same_cond) else \
                          (parts["b"] if (same_cond and not same_model) else parts["c"])
                for a in range(k):
                    if X[i][a]:
                        va = X[i][a] * ri
                        for bb in range(k):
                            if X[j][bb]:
                                tgt[a][bb] += va * X[j][bb] * rj
    return parts


PARTS = meat_parts(f2, X2, y2, item_ids, f2["k"])
bread2 = inv(f2["XtWX"])
jc = n2.index("condB")
ji = 0
P("\n  contribution to Var(beta) [bread*part*bread] diagonal, model (ii), CR0 scale:")
P("  %-34s %14s %14s" % ("meat component", "-> Var(condB)", "-> Var(intercept)"))
tot_c = tot_i = 0.0
for key, lab in (("diag", "independence (row diagonal)"),
                 ("a", "(a) same model, A-B pair"),
                 ("b", "(b) same condition, diff model"),
                 ("c", "(c) diff cond & diff model")):
    Vp = mm(mm(bread2, PARTS[key]), bread2)
    tot_c += Vp[jc][jc]; tot_i += Vp[ji][ji]
    P("  %-34s %14.6e %14.6e" % (lab, Vp[jc][jc], Vp[ji][ji]))
P("  %-34s %14.6e %14.6e" % ("TOTAL (= CR0 variance)", tot_c, tot_i))
P("  check: CR0 SE condB = %.4f (sandwich) vs %.4f (decomposition sum)"
  % (R2["condB"]["se_item0"], math.sqrt(tot_c)))
P("  naive Var(condB) = %.6e   (HC0-diag part alone = %.6e)"
  % (Vn2[jc][jc], mm(mm(bread2, PARTS["diag"]), bread2)[jc][jc]))

# --------------------------------------------------- cluster bootstrap check
P("\n" + "=" * 104)
P("Nonparametric ITEM bootstrap of model (ii) condB (independent SE check)")
P("=" * 104)
rows_by_item = {}
for i, r in enumerate(long):
    rows_by_item.setdefault(r["item"], []).append(i)
uitems = sorted(rows_by_item)
rng = random.Random(20260731)
B = 600
bs = []
for b in range(B):
    pick = [uitems[rng.randrange(len(uitems))] for _ in range(len(uitems))]
    Xb, yb = [], []
    for it in pick:
        for i in rows_by_item[it]:
            Xb.append(X2[i]); yb.append(y2[i])
    try:
        fb = irls(Xb, yb, maxit=60)
        bs.append(fb["beta"][jc])
    except Exception:
        pass
mu = sum(bs) / len(bs)
sd = math.sqrt(sum((v - mu) ** 2 for v in bs) / (len(bs) - 1))
bs.sort()
lo = bs[int(0.025 * len(bs))]; hi = bs[int(0.975 * len(bs)) - 1]
P("  B=%d valid draws  mean=%.4f  bootstrap SD=%.4f  pct CI [%.4f, %.4f]"
  % (len(bs), mu, sd, lo, hi))
P("  point est=%.4f  naive SE=%.4f  CR1-item SE=%.4f  CR1-cluster SE=%.4f  boot SE=%.4f"
  % (f2["beta"][jc], R2["condB"]["se_naive"], R2["condB"]["se_item"],
     R2["condB"]["se_clus"], sd))
P("  boot/naive ratio = %.3f" % (sd / R2["condB"]["se_naive"]))

json.dump({"log": LOG, "R1": R1, "R2": R2, "R3": R3, "R4": R4,
           "boot_sd": sd, "icc_item": ii, "icc_cluster": ic},
          open(os.path.join(HERE, "prim_refute_se_struct_out.json"), "w"), indent=1)
P("\n[done]")

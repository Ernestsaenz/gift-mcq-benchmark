#!/usr/bin/env python3
"""mech_ref_negrec_01 -- independent recomputation of the 'negated-interaction'
recovery claim: P(B correct | A wrong), negated vs non-negated stems.

Everything re-implemented from scratch (no reuse of mech_stats.py) so the
numbers are an independent check, not a re-print.
"""
import json, math, random, collections

ANA = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
rows = [r for r in json.load(open(f"{ANA}/paired_clean.json")) if r["analysis_include"]]
lab = json.load(open(f"{ANA}/mech_labels.json"))
for r in rows:
    L = lab[r["question_id"]]
    r["neg_flag"] = bool(r["negated_stem"])
    r["neg_adj"] = bool(L["neg"])
    if not L["neg"]:
        r["subtype"] = "POS"
    elif any(t in L["hits"] for t in ("FALSO", "INCORRECTO", "ERRONEO", "INCIERTO")):
        r["subtype"] = "TRUTH-NEG"
    else:
        r["subtype"] = "SET-NEG"

MODELS = sorted({r["model"] for r in rows})
BAR = "=" * 96


# ------------------------------------------------------------------ stats kit
def lchoose(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher2x2(a, b, c, d):
    """Two-sided Fisher exact, exact hypergeometric, p<=p_obs rule."""
    r1, r2, c1, n = a + b, c + d, a + c, a + b + c + d

    def pr(x):
        y, z = r1 - x, c1 - x
        w = r2 - z
        if min(x, y, z, w) < 0:
            return 0.0
        return math.exp(lchoose(r1, x) + lchoose(r2, z) - lchoose(n, c1))

    po = pr(a)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    p = sum(pr(x) for x in range(lo, hi + 1) if pr(x) <= po * (1 + 1e-9))
    orr = float("inf") if (b == 0 or c == 0) else (a * d) / (b * c)
    return orr, min(1.0, p)


def wilson(k, n, z=1.959963985):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    cen = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, cen - half), min(1.0, cen + half)


def norm_sf2(z):
    return math.erfc(abs(z) / math.sqrt(2.0))


def t_sf2(t, df):
    """Two-sided Student-t tail via the regularized incomplete beta."""
    x = df / (df + t * t)
    return betainc(df / 2.0, 0.5, x)


def betainc(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(a * math.log(x) + b * math.log(1 - x) - lbeta) / a
    if x < (a + 1) / (a + b + 2):
        return front * _cf(a, b, x)
    lbeta2 = lbeta
    front2 = math.exp(b * math.log(1 - x) + a * math.log(x) - lbeta2) / b
    return 1.0 - front2 * _cf(b, a, 1 - x)


def _cf(a, b, x, itmax=300, eps=1e-14):
    f, c, d = 1.0, 1.0, 0.0
    for i in range(itmax + 1):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        if abs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < 1e-30:
            c = 1e-30
        f *= c * d
        if abs(1 - c * d) < eps:
            break
    return f - 1.0


def solve(A, bb):
    n = len(A)
    M = [row[:] + [bb[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-300:
            raise ZeroDivisionError
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        M[c] = [v / pv for v in M[c]]
        for r in range(n):
            if r != c and M[r][c] != 0.0:
                f = M[r][c]
                M[r] = [M[r][j] - f * M[c][j] for j in range(n + 1)]
    return [M[i][n] for i in range(n)]


def inv(A):
    n = len(A)
    return [[solve(A, [1.0 if r == j else 0.0 for r in range(n)])[i] for j in range(n)]
            for i in range(n)]


def logit_fit(X, y, iters=200, ridge=1e-9):
    n, k = len(X), len(X[0])
    beta = [0.0] * k
    for _ in range(iters):
        mu = []
        for i in range(n):
            e = sum(X[i][j] * beta[j] for j in range(k))
            mu.append(1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, e)))))
        W = [max(m * (1 - m), 1e-10) for m in mu]
        g = [sum(X[i][j] * (y[i] - mu[i]) for i in range(n)) for j in range(k)]
        H = [[sum(X[i][a] * W[i] * X[i][b] for i in range(n)) + (ridge if a == b else 0)
              for b in range(k)] for a in range(k)]
        st = solve(H, g)
        beta = [beta[j] + st[j] for j in range(k)]
        if max(abs(s) for s in st) < 1e-11:
            break
    return beta


def cr_se(X, y, beta, cl, kind="CR0"):
    n, k = len(X), len(X[0])
    mu = []
    for i in range(n):
        e = sum(X[i][j] * beta[j] for j in range(k))
        mu.append(1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, e)))))
    W = [max(m * (1 - m), 1e-10) for m in mu]
    B = [[sum(X[i][a] * W[i] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    Bi = inv(B)
    agg = {}
    for i in range(n):
        s = agg.setdefault(cl[i], [0.0] * k)
        r = y[i] - mu[i]
        for j in range(k):
            s[j] += X[i][j] * r
    M = [[sum(v[a] * v[b] for v in agg.values()) for b in range(k)] for a in range(k)]
    G = len(agg)
    if kind == "CR0":
        sc = 1.0
    elif kind == "CR0g":                       # G/(G-1) only  (what mech_stats does)
        sc = G / (G - 1)
    else:                                      # CR1: Stata-style G/(G-1) * (N-1)/(N-k)
        sc = (G / (G - 1)) * ((n - 1) / (n - k))
    V = [[sc * sum(Bi[a][x] * M[x][z] * Bi[z][b] for x in range(k) for z in range(k))
          for b in range(k)] for a in range(k)]
    return [math.sqrt(max(V[j][j], 0.0)) for j in range(k)], G


# ------------------------------------------------------------------- part 1
print(BAR)
print("PART 1 -- reproduce the headline recovery contrast (both polarity labels)")
print(BAR)


def rec_block(rs, key):
    neg = [r for r in rs if r[key] and not r["A_correct"]]
    pos = [r for r in rs if not r[key] and not r["A_correct"]]
    kn, kp = sum(r["B_correct"] for r in neg), sum(r["B_correct"] for r in pos)
    return neg, pos, kn, kp


for key, name, nit in (("neg_flag", "shipped negated_stem flag", 84),
                       ("neg_adj", "hand-adjudicated label (mech_labels.json)", 149)):
    neg, pos, kn, kp = rec_block(rows, key)
    o, p = fisher2x2(kn, len(neg) - kn, kp, len(pos) - kp)
    ln, lp = wilson(kn, len(neg)), wilson(kp, len(pos))
    print(f"  {name}  ({nit} items marked negated)")
    print(f"    negated     P(B+|A-) = {kn}/{len(neg)} = {kn/len(neg):.4f} [{ln[0]:.3f},{ln[1]:.3f}]"
          f"   items={len({r['question_id'] for r in neg})} clusters={len({r['cluster'] for r in neg})}")
    print(f"    non-negated P(B+|A-) = {kp}/{len(pos)} = {kp/len(pos):.4f} [{lp[0]:.3f},{lp[1]:.3f}]"
          f"   items={len({r['question_id'] for r in pos})} clusters={len({r['cluster'] for r in pos})}")
    print(f"    difference {kn/len(neg)-kp/len(pos):+.4f}  OR={o:.4f}"
          f"  Fisher exact (two-sided, p<=p_obs) p={p:.4f}   [treats cells as independent]")

print()
print("  PER MODEL (shipped flag), Fisher exact each:")
for m in MODELS:
    rs = [r for r in rows if r["model"] == m]
    neg, pos, kn, kp = rec_block(rs, "neg_flag")
    o, p = fisher2x2(kn, len(neg) - kn, kp, len(pos) - kp)
    print(f"    {m:28s} neg {kn}/{len(neg)}={kn/len(neg):.3f}  nonneg {kp}/{len(pos)}={kp/len(pos):.3f}"
          f"  OR={o:.3f}  p={p:.3f}")

# ------------------------------------------------------------------- part 2
print()
print(BAR)
print("PART 2 -- the Fisher p is the ONLY sub-0.05 test that ignores clustering.")
print("          Re-run the cluster-aware versions and the small-G correction.")
print(BAR)

KEY = "neg_flag"
neg, pos, kn, kp = rec_block(rows, KEY)
obs = kn / len(neg) - kp / len(pos)
aw = [r for r in rows if not r["A_correct"]]
print(f"  A-wrong cells n={len(aw)} from {len({r['question_id'] for r in aw})} items /"
      f" {len({r['cluster'] for r in aw})} clusters -> design effect is real")

# (a) cluster bootstrap over clusters
byc = collections.defaultdict(list)
for r in rows:
    byc[r["cluster"]].append(r)
keys = list(byc)
rng = random.Random(20260731)
bs = []
for _ in range(20000):
    samp = []
    for _ in range(len(keys)):
        samp.extend(byc[keys[rng.randrange(len(keys))]])
    a = [r for r in samp if r[KEY] and not r["A_correct"]]
    b = [r for r in samp if not r[KEY] and not r["A_correct"]]
    if len(a) < 5 or len(b) < 5:
        continue
    bs.append(sum(r["B_correct"] for r in a) / len(a) - sum(r["B_correct"] for r in b) / len(b))
bs.sort()
frac = sum(1 for v in bs if v <= 0) / len(bs)
print(f"  (a) cluster bootstrap (20000 resamples of {len(keys)} clusters): point {obs:+.4f}"
      f"  95% CI [{bs[int(.025*len(bs))]:+.4f},{bs[int(.975*len(bs))]:+.4f}]"
      f"  two-sided percentile p ~ {2*min(frac,1-frac):.4f}")

# (b) item-level permutation of the polarity label
items = collections.defaultdict(list)
for r in rows:
    items[r["question_id"]].append(r)
qs = list(items)
labs = [items[q][0][KEY] for q in qs]
rng2 = random.Random(11)
NP = 50000
cnt = 0
for _ in range(NP):
    rng2.shuffle(labs)
    a1 = a0 = b1 = b0 = 0
    for q, l in zip(qs, labs):
        for r in items[q]:
            if r["A_correct"]:
                continue
            if l:
                a1 += r["B_correct"]; a0 += 1
            else:
                b1 += r["B_correct"]; b0 += 1
    if a0 and b0 and abs(a1 / a0 - b1 / b0) >= abs(obs) - 1e-12:
        cnt += 1
print(f"  (b) item-level permutation of polarity label ({NP} perms, all model rows of an item"
      f" move together): p={(cnt+1)/(NP+1):.4f}")

# (c) logistic on A-wrong cells with covariates, CR0 vs CR1 vs t(G-1)
X, y, cl = [], [], []
mdix = {m: i for i, m in enumerate(MODELS)}
for r in aw:
    row = [1.0, 1.0 if r[KEY] else 0.0, 1.0 if r["has_context"] else 0.0,
           math.log(r["qlen"])]
    row += [1.0 if mdix[r["model"]] == j else 0.0 for j in range(1, len(MODELS))]
    X.append(row); y.append(float(r["B_correct"])); cl.append(r["question_id"])
beta = logit_fit(X, y)
for kind in ("CR0", "CR0g", "CR1"):
    se, G = cr_se(X, y, beta, cl, kind)
    z = beta[1] / se[1]
    print(f"  (c) logistic B_correct ~ negated + has_context + log qlen + model FE, {kind:4s}"
          f" cluster-robust (G={G} items): b={beta[1]:+.4f} se={se[1]:.4f} z={z:+.3f}"
          f"  normal p={norm_sf2(z):.4f}   t({G-1}) p={t_sf2(z, G-1):.4f}")
print("      NOTE: with G-1 df the t and normal references barely differ; the difference"
      "\n      between CR0 and CR1 is what moves the p-value, and CR0 (no finite-G correction)"
      "\n      is the anti-conservative choice reported in the claim.")

# (d) wild cluster bootstrap-t (Rademacher) on the negated coefficient, null imposed
print()
print("  (d) wild cluster bootstrap-t, Rademacher weights, null imposed (b_negated=0),"
      " 9999 reps:")
k = len(X[0])
Xr = [[v for j, v in enumerate(x) if j != 1] for x in X]      # restricted design
br = logit_fit(Xr, y)
mu0 = []
for i in range(len(Xr)):
    e = sum(Xr[i][j] * br[j] for j in range(len(br)))
    mu0.append(1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, e)))))
res = [y[i] - mu0[i] for i in range(len(y))]
se_obs, G = cr_se(X, y, beta, cl, "CR1")
t_obs = beta[1] / se_obs[1]
clusters = sorted(set(cl))
cidx = {c: i for i, c in enumerate(clusters)}
rng3 = random.Random(4242)
big = 0
NB = 9999
ok = 0
for _ in range(NB):
    w = [1.0 if rng3.random() < 0.5 else -1.0 for _ in clusters]
    ystar = []
    for i in range(len(y)):
        v = mu0[i] + w[cidx[cl[i]]] * res[i]
        ystar.append(1.0 if v > 0.5 else 0.0)          # binary projection
    try:
        bstar = logit_fit(X, ystar)
        sestar, _ = cr_se(X, ystar, bstar, cl, "CR1")
        t = bstar[1] / sestar[1]
    except Exception:
        continue
    ok += 1
    if abs(t) >= abs(t_obs) - 1e-12:
        big += 1
print(f"      t_obs={t_obs:+.3f}  wild-bootstrap p={(big+1)/(ok+1):.4f}  ({ok} usable reps)")

# ------------------------------------------------------------------- part 3
print()
print(BAR)
print("PART 3 -- RIVAL 1: conditioning on 'A wrong' is conditioning on a noisy baseline.")
print("          Negated items are HARDER in A, so the two A-wrong strata are not")
print("          comparable populations (differential selection / regression to the mean).")
print(BAR)
for key, name in (("neg_flag", "shipped flag"), ("neg_adj", "adjudicated")):
    n_ = [r for r in rows if r[key]]
    p_ = [r for r in rows if not r[key]]
    An, Ap = sum(r["A_correct"] for r in n_) / len(n_), sum(r["A_correct"] for r in p_) / len(p_)
    Bn, Bp = sum(r["B_correct"] for r in n_) / len(n_), sum(r["B_correct"] for r in p_) / len(p_)
    o, p = fisher2x2(sum(r["A_correct"] for r in n_), len(n_) - sum(r["A_correct"] for r in n_),
                     sum(r["A_correct"] for r in p_), len(p_) - sum(r["A_correct"] for r in p_))
    print(f"  {name:14s} A acc: neg {An:.4f} (n={len(n_)}) vs non-neg {Ap:.4f} (n={len(p_)})"
          f"   OR={o:.3f} Fisher p={p:.4g}")
    print(f"                 B acc: neg {Bn:.4f} vs non-neg {Bp:.4f}"
          f"   |  A-B delta: neg {An-Bn:+.4f} vs non-neg {Ap-Bp:+.4f}"
          f"   -> DELTA DIFFERENCE {(Ap-Bp)-(An-Bn):+.4f}")

print()
print("  The 'shortcut' hypothesis predicts a SMALLER A->B drop on negated stems.")
print("  That is the interaction. Test it directly (unconditional, no selection):")
for key, name in (("neg_flag", "shipped flag"), ("neg_adj", "adjudicated")):
    X2, y2, cl2 = [], [], []
    for r in rows:
        g = 1.0 if r[key] else 0.0
        X2.append([1.0, 0.0, g, 0.0]); y2.append(float(r["A_correct"])); cl2.append(r["question_id"])
        X2.append([1.0, 1.0, g, g]);   y2.append(float(r["B_correct"])); cl2.append(r["question_id"])
    b2 = logit_fit(X2, y2)
    se2, G2 = cr_se(X2, y2, b2, cl2, "CR1")
    z = b2[3] / se2[3]
    print(f"    {name:14s} condB x negated: b={b2[3]:+.4f} se={se2[3]:.4f} z={z:+.3f}"
          f"  CR1 p={norm_sf2(z):.4f}  t({G2-1}) p={t_sf2(z, G2-1):.4f}  OR={math.exp(b2[3]):.3f}")

print()
print("  Symmetry check the shortcut also predicts: LESS loss on negated stems.")
for key, name in (("neg_flag", "shipped flag"), ("neg_adj", "adjudicated")):
    out = []
    for tag, sel in (("neg", True), ("nonneg", False)):
        s = [r for r in rows if bool(r[key]) == sel and r["A_correct"]]
        loss = sum(1 for r in s if not r["B_correct"])
        out.append((tag, loss, len(s)))
    o, p = fisher2x2(out[0][1], out[0][2] - out[0][1], out[1][1], out[1][2] - out[1][1])
    print(f"    {name:14s} P(B-|A+) neg {out[0][1]}/{out[0][2]}={out[0][1]/out[0][2]:.4f}"
          f"   non-neg {out[1][1]}/{out[1][2]}={out[1][1]/out[1][2]:.4f}"
          f"   OR={o:.3f} Fisher p={p:.4g}")

# ------------------------------------------------------------------- part 4
print()
print(BAR)
print("PART 4 -- RIVAL 2: is the 'recovery' just where the NOTA slot sits?")
print("          B_correct == (B_selected == correct_letter). If negated items put the")
print("          answer in a letter models drift to under uncertainty, recovery rises")
print("          with no logic involved.")
print(BAR)
print("  correct_letter distribution by polarity (items):")
seen = {}
for r in rows:
    seen[r["question_id"]] = r
for key, name in (("neg_flag", "shipped flag"),):
    for sel, tag in ((True, "negated"), (False, "non-negated")):
        c = collections.Counter(v["correct_letter"] for v in seen.values() if bool(v[key]) == sel)
        tot = sum(c.values())
        print(f"    {tag:12s} " + "  ".join(f"{L}={c.get(L,0)}({c.get(L,0)/tot:.2f})"
                                            for L in "abcd"))
print()
print("  Among A-WRONG cells: where does B land?")
for sel, tag in ((True, "negated"), (False, "non-negated")):
    s = [r for r in aw if bool(r["neg_flag"]) == sel]
    c = collections.Counter(r["B_selected"] for r in s)
    tot = len(s)
    print(f"    {tag:12s} n={tot}  " + "  ".join(f"{L}={c.get(L,0)}({c.get(L,0)/tot:.2f})"
                                                 for L in sorted(c)))
print()
print("  Recovery within each correct_letter slot (A-wrong cells), neg vs non-neg:")
for L in "abcd":
    a = [r for r in aw if r["correct_letter"] == L and r["neg_flag"]]
    b = [r for r in aw if r["correct_letter"] == L and not r["neg_flag"]]
    if not a or not b:
        print(f"    letter {L}: insufficient (neg n={len(a)}, non-neg n={len(b)})")
        continue
    ka, kb = sum(r["B_correct"] for r in a), sum(r["B_correct"] for r in b)
    o, p = fisher2x2(ka, len(a) - ka, kb, len(b) - kb)
    print(f"    letter {L}: neg {ka}/{len(a)}={ka/len(a):.3f}  non-neg {kb}/{len(b)}={kb/len(b):.3f}"
          f"  OR={o:.3f} p={p:.3f}")
# Mantel-Haenszel over letter strata
num = den = 0.0
for L in "abcd":
    a = [r for r in aw if r["correct_letter"] == L and r["neg_flag"]]
    b = [r for r in aw if r["correct_letter"] == L and not r["neg_flag"]]
    if not a or not b:
        continue
    a11 = sum(r["B_correct"] for r in a); a12 = len(a) - a11
    a21 = sum(r["B_correct"] for r in b); a22 = len(b) - a21
    N = a11 + a12 + a21 + a22
    num += a11 * a22 / N
    den += a12 * a21 / N
print(f"    Mantel-Haenszel OR stratified on correct_letter = {num/den:.4f}"
      f"   (crude OR was {fisher2x2(kn, len(neg)-kn, kp, len(pos)-kp)[0]:.4f})")

# ------------------------------------------------------------------- part 5
print()
print(BAR)
print("PART 5 -- RIVAL 3: heterogeneity claim. 'consistent across all four models with")
print("          no detectable heterogeneity' -- check the power of that statement.")
print(BAR)
lors = []
for m in MODELS:
    rs = [r for r in rows if r["model"] == m]
    neg2, pos2, kn2, kp2 = rec_block(rs, "neg_flag")
    a, b, c, d = kn2 + .5, len(neg2) - kn2 + .5, kp2 + .5, len(pos2) - kp2 + .5
    lor = math.log(a * d / (b * c))
    v = 1 / a + 1 / b + 1 / c + 1 / d
    lors.append((m, lor, v, kn2, len(neg2), kp2, len(pos2)))
W = sum(1 / v for _, _, v, *_ in lors)
mu = sum(l / v for _, l, v, *_ in lors) / W
Q = sum((l - mu) ** 2 / v for _, l, v, *_ in lors)
print(f"  Woolf/DerSimonian Q={Q:.4f} df={len(lors)-1}")
print(f"  pooled log-OR (inverse variance) = {mu:+.4f}  OR={math.exp(mu):.3f}"
      f"  se={math.sqrt(1/W):.4f}  z={mu/math.sqrt(1/W):+.3f}  p={norm_sf2(mu/math.sqrt(1/W)):.4f}")
for m, l, v, kn2, nn2, kp2, np2 in lors:
    print(f"    {m:28s} logOR={l:+.4f} se={math.sqrt(v):.4f}"
          f"  95% CI OR [{math.exp(l-1.96*math.sqrt(v)):.2f},{math.exp(l+1.96*math.sqrt(v)):.2f}]"
          f"   ({kn2}/{nn2} vs {kp2}/{np2})")
print("  -> width of the per-model CIs is the point: the Woolf test cannot detect")
print("     heterogeneity it has no power to see. 'No detectable heterogeneity' is")
print("     not evidence of homogeneity.")
print()
print("  Leave-one-model-out pooled Fisher exact:")
for m in MODELS:
    rs = [r for r in rows if r["model"] != m]
    neg2, pos2, kn2, kp2 = rec_block(rs, "neg_flag")
    o, p = fisher2x2(kn2, len(neg2) - kn2, kp2, len(pos2) - kp2)
    print(f"    drop {m:28s} OR={o:.3f}  Fisher p={p:.4f}"
          f"  ({kn2}/{len(neg2)} vs {kp2}/{len(pos2)})")
print()
print("  Per-model sign test on the raw recovery difference (4 models, all positive):")
print(f"    exact two-sided sign-test p = {2*0.5**4:.4f}  (this is the true strength of"
      " 'consistent across all four models')")

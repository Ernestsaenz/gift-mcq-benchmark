#!/usr/bin/env python3
"""
INDEPENDENT REFUTATION SCRIPT for the "mixed-model" marginal (population-averaged)
logistic fits.  Standard library only.  Hand-rolled:
  - Gaussian elimination with partial pivoting (matrix inverse / solve)
  - IRLS / Fisher scoring for the canonical logit link
  - CR1 cluster-robust sandwich
  - Normal tail probabilities via math.erfc (exact to double precision)

Nothing here is copied from prim_linalg.py / prim_mixed_main.py.
"""
import json, math, collections

DATA = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json'

# ----------------------------------------------------------------------------
# linear algebra (dense, small k)
# ----------------------------------------------------------------------------
def matinv(Ain):
    n = len(Ain)
    A = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(Ain)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(A[r][col]))
        if abs(A[piv][col]) < 1e-14:
            raise ValueError('singular matrix at col %d' % col)
        A[col], A[piv] = A[piv], A[col]
        pv = A[col][col]
        A[col] = [x / pv for x in A[col]]
        for r in range(n):
            if r == col:
                continue
            f = A[r][col]
            if f != 0.0:
                A[r] = [a - f * b for a, b in zip(A[r], A[col])]
    return [row[n:] for row in A]

def matmul(A, B):
    n, m, p = len(A), len(B), len(B[0])
    return [[sum(A[i][k] * B[k][j] for k in range(m)) for j in range(p)] for i in range(n)]

def matvec(A, v):
    return [sum(a * b for a, b in zip(row, v)) for row in A]

# ----------------------------------------------------------------------------
# IRLS / Fisher scoring, canonical logit link
# ----------------------------------------------------------------------------
def irls_logit(X, y, tol=1e-12, maxit=200):
    n, k = len(X), len(X[0])
    beta = [0.0] * k
    dev_old = None
    it = 0
    for it in range(1, maxit + 1):
        eta = [sum(b * x for b, x in zip(beta, row)) for row in X]
        mu, w, z = [], [], []
        for i in range(n):
            e = max(-500.0, min(500.0, eta[i]))
            m = 1.0 / (1.0 + math.exp(-e))
            m = min(max(m, 1e-12), 1 - 1e-12)
            wi = m * (1 - m)
            mu.append(m); w.append(wi)
            z.append(e + (y[i] - m) / wi)
        XtWX = [[0.0] * k for _ in range(k)]
        XtWz = [0.0] * k
        for i in range(n):
            xi, wi, zi = X[i], w[i], z[i]
            for a in range(k):
                if xi[a] == 0.0:
                    continue
                wxa = wi * xi[a]
                XtWz[a] += wxa * zi
                for b in range(a, k):
                    XtWX[a][b] += wxa * xi[b]
        for a in range(k):
            for b in range(a):
                XtWX[a][b] = XtWX[b][a]
        beta = matvec(matinv(XtWX), XtWz)
        dev = 0.0
        for i in range(n):
            e = max(-500.0, min(500.0, sum(b * x for b, x in zip(beta, X[i]))))
            m = min(max(1.0 / (1.0 + math.exp(-e)), 1e-15), 1 - 1e-15)
            dev += -2.0 * (y[i] * math.log(m) + (1 - y[i]) * math.log(1 - m))
        if dev_old is not None and abs(dev - dev_old) < tol * (abs(dev) + 0.1):
            dev_old = dev
            break
        dev_old = dev
    # final weights / residuals at convergence
    eta = [sum(b * x for b, x in zip(beta, row)) for row in X]
    mu = [1.0 / (1.0 + math.exp(-max(-500.0, min(500.0, e)))) for e in eta]
    w = [m * (1 - m) for m in mu]
    XtWX = [[0.0] * k for _ in range(k)]
    for i in range(n):
        xi, wi = X[i], w[i]
        for a in range(k):
            if xi[a] == 0.0:
                continue
            wxa = wi * xi[a]
            for b in range(k):
                XtWX[a][b] += wxa * xi[b]
    bread = matinv(XtWX)
    return beta, mu, bread, dev_old, it

def naive_se(bread):
    return [math.sqrt(bread[j][j]) for j in range(len(bread))]

def cr1_se(X, y, mu, bread, groups):
    """CR1 cluster-robust sandwich: G/(G-1) * (N-1)/(N-k) * B (sum_g s_g s_g') B"""
    n, k = len(X), len(X[0])
    by = collections.defaultdict(list)
    for i, g in enumerate(groups):
        by[g].append(i)
    G = len(by)
    meat = [[0.0] * k for _ in range(k)]
    for g, idx in by.items():
        s = [0.0] * k
        for i in idx:
            e = y[i] - mu[i]
            for a in range(k):
                if X[i][a] != 0.0:
                    s[a] += X[i][a] * e
        for a in range(k):
            for b in range(k):
                meat[a][b] += s[a] * s[b]
    c = (G / (G - 1.0)) * ((n - 1.0) / (n - k))
    meat = [[c * v for v in row] for row in meat]
    V = matmul(matmul(bread, meat), bread)
    return [math.sqrt(V[j][j]) for j in range(k)], G

def two_sided_p(z):
    return math.erfc(abs(z) / math.sqrt(2.0))

# ----------------------------------------------------------------------------
# build long-form data
# ----------------------------------------------------------------------------
raw = json.load(open(DATA))
inc = [r for r in raw if r.get('analysis_include') is True]
models = sorted(set(r['model'] for r in inc))

rows = []   # (y, cond(0=A,1=B), model, cluster, item)
for r in inc:
    rows.append((r['A_correct'], 0, r['model'], r['cluster'], r['question_id']))
    rows.append((r['B_correct'], 1, r['model'], r['cluster'], r['question_id']))

N = len(rows)
print('=' * 78)
print('DATA: cells=%d  long-rows=%d  items=%d  clusters=%d  models=%d'
      % (len(inc), N, len(set(r['question_id'] for r in inc)),
         len(set(r['cluster'] for r in inc)), len(models)))

# ---- observed cell marginals -----------------------------------------------
print('\nOBSERVED per-model marginals (clean subset):')
cells = {}
for m in models:
    sub = [r for r in inc if r['model'] == m]
    nA = sum(r['A_correct'] for r in sub); nB = sum(r['B_correct'] for r in sub)
    n = len(sub)
    cells[m] = (nA, nB, n)
    print('  %-24s n=%3d  A %3d/%3d = %6.2f%%   B %3d/%3d = %6.2f%%   delta %+6.2f pp'
          % (m, n, nA, n, 100 * nA / n, nB, n, 100 * nB / n, 100 * (nB - nA) / n))
tA = sum(c[0] for c in cells.values()); tB = sum(c[1] for c in cells.values()); tn = sum(c[2] for c in cells.values())
print('  %-24s n=%3d  A %3d/%3d = %8.4f%% B %3d/%3d = %8.4f%%'
      % ('POOLED', tn, tA, tn, 100 * tA / tn, tB, tn, 100 * tB / tn))

y = [r[0] for r in rows]
cond = [r[1] for r in rows]
clus = [r[3] for r in rows]
item = [r[4] for r in rows]

def report(name, X, coefnames, focus):
    beta, mu, bread, dev, it = irls_logit(X, y)
    nse = naive_se(bread)
    rse_c, Gc = cr1_se(X, y, mu, bread, clus)
    rse_i, Gi = cr1_se(X, y, mu, bread, item)
    print('\n' + '-' * 78)
    print('%s   (k=%d, iterations=%d, deviance=%.6f)' % (name, len(coefnames), it, dev))
    for j, cn in enumerate(coefnames):
        print('   %-18s b=%+10.6f  naiveSE=%.6f  CR1[clus,G=%d]=%.6f  CR1[item,G=%d]=%.6f'
              % (cn, beta[j], nse[j], Gc, rse_c[j], Gi, rse_i[j]))
    j = coefnames.index(focus)
    b, se = beta[j], rse_c[j]
    z = b / se
    lo, hi = b - 1.959963985 * se, b + 1.959963985 * se
    print('   FOCUS %s: b=%.6f  robustSE(clus)=%.6f  OR=%.6f  95%%CI=[%.6f, %.6f]  z=%.4f  p=%.4e'
          % (focus, b, se, math.exp(b), math.exp(lo), math.exp(hi), z, two_sided_p(z)))
    return beta, coefnames, nse, rse_c, rse_i, it

# ---- model (i): condition only ---------------------------------------------
Xi = [[1.0, float(c)] for c in cond]
bi, ni, nsei, rsei_c, rsei_i, iti = report('MODEL (i)  y ~ condB', Xi, ['intercept', 'condB'], 'condB')

# closed form for saturated condition-only model
pA = tA / tn; pB = tB / tn
cf_int = math.log(tA / (tn - tA))
cf_cond = math.log(tB / (tn - tB)) - cf_int
cf_nse = math.sqrt(1/tA + 1/(tn-tA) + 1/tB + 1/(tn-tB))
print('   CLOSED FORM (saturated): intercept=%.10f  condB=%.10f  naiveSE(condB)=%.10f'
      % (cf_int, cf_cond, cf_nse))
print('   |IRLS - closed form|: intercept %.3e   condB %.3e' % (abs(bi[0]-cf_int), abs(bi[1]-cf_cond)))
print('   NOTE: logit(round(pA,4)=%.4f) = %.6f  <-- rounded-input value, NOT the true closed form'
      % (round(pA,4), math.log(round(pA,4)/(1-round(pA,4)))))

# ---- model (ii): condition + model FE ---------------------------------------
ref = models[0]
oth = models[1:]
Xii, names_ii = [], ['intercept', 'condB'] + ['M:' + m for m in oth]
for r in rows:
    row = [1.0, float(r[1])] + [1.0 if r[2] == m else 0.0 for m in oth]
    Xii.append(row)
bii, nii, nseii, rseii_c, rseii_i, itii = report('MODEL (ii) y ~ condB + model FE (ref=%s)' % ref,
                                                 Xii, names_ii, 'condB')

# ---- model (iii): condition * model (saturated in 8 cells) -------------------
Xiii, names_iii = [], ['intercept', 'condB'] + ['M:' + m for m in oth] + ['condB:' + m for m in oth]
for r in rows:
    d = [1.0 if r[2] == m else 0.0 for m in oth]
    Xiii.append([1.0, float(r[1])] + d + [float(r[1]) * x for x in d])
biii, niii, nseiii, rseiii_c, rseiii_i, itiii = report('MODEL (iii) y ~ condB * model (saturated)',
                                                       Xiii, names_iii, 'condB')

print('\n   SATURATION CHECK: model (iii) implied cell probabilities vs raw cell means')
maxerr = 0.0
for m in models:
    for c in (0, 1):
        d = [1.0 if m == mm else 0.0 for mm in oth]
        x = [1.0, float(c)] + d + [float(c) * v for v in d]
        eta = sum(b * v for b, v in zip(biii, x))
        p = 1 / (1 + math.exp(-eta))
        nA, nB, n = cells[m]
        obs = (nA if c == 0 else nB) / n
        maxerr = max(maxerr, abs(p - obs))
print('   max |fitted - observed| over the 8 cells = %.3e' % maxerr)

nA_ref, nB_ref, n_ref = cells[ref]
cf3 = math.log(nA_ref / (n_ref - nA_ref))
print('   reference cell = %s condition A: %d/%d correct' % (ref, nA_ref, n_ref))
print('   closed-form logit(%d/%d) = ln(%d/%d) = %.10f' % (nA_ref, n_ref, nA_ref, n_ref - nA_ref, cf3))
print('   IRLS intercept                       = %.10f' % biii[0])
print('   |diff| = %.3e' % abs(biii[0] - cf3))
print('   CLAIMED closed form in the claim text = 3.8180  -> |claim - truth| = %.4f'
      % abs(3.8180 - cf3))

# ---- claim comparison table --------------------------------------------------
print('\n' + '=' * 78)
print('CLAIM vs RECOMPUTED')
def cmp(label, claimed, got, tol):
    ok = abs(claimed - got) <= tol
    print('  %-46s claim=%-12s mine=%-14.6f %s' % (label, claimed, got, 'OK' if ok else '**MISMATCH**'))
    return ok

zi = bi[1] / rsei_c[1]
cmp('(i)   condB', -1.1140, bi[1], 5e-5)
cmp('(i)   naive SE', 0.1114, nsei[1], 5e-5)
cmp('(i)   robust SE [208 clusters]', 0.1177, rsei_c[1], 5e-5)
cmp('(i)   OR', 0.3282, math.exp(bi[1]), 5e-5)
cmp('(i)   CI lo', 0.2606, math.exp(bi[1] - 1.959963985 * rsei_c[1]), 5e-5)
cmp('(i)   CI hi', 0.4134, math.exp(bi[1] + 1.959963985 * rsei_c[1]), 5e-5)
cmp('(i)   z', -9.465, zi, 5e-4)
print('  %-46s claim=%-12s mine=%.4e' % ('(i)   p', '2.9e-21', two_sided_p(zi)))
cmp('(i)   intercept', 2.1710, bi[0], 5e-5)

zii = bii[1] / rseii_c[1]
cmp('(ii)  condB', -1.1747, bii[1], 5e-5)
cmp('(ii)  naive SE', 0.1145, nseii[1], 5e-5)
cmp('(ii)  robust SE [208 clusters]', 0.1223, rseii_c[1], 5e-5)
cmp('(ii)  robust SE [325 items]', 0.1237, rseii_i[1], 5e-5)
cmp('(ii)  OR', 0.3089, math.exp(bii[1]), 5e-5)
cmp('(ii)  CI lo', 0.2431, math.exp(bii[1] - 1.959963985 * rseii_c[1]), 5e-5)
cmp('(ii)  CI hi', 0.3926, math.exp(bii[1] + 1.959963985 * rseii_c[1]), 5e-5)
cmp('(ii)  z', -9.605, zii, 5e-4)
print('  %-46s claim=%-12s mine=%.4e' % ('(ii)  p', '7.6e-22', two_sided_p(zii)))
cmp('(iii) intercept', 3.8161, biii[0], 5e-5)
print('  iterations: (i)=%d (ii)=%d (iii)=%d   [claim: 6-8 Fisher-scoring iterations]'
      % (iti, itii, itiii))

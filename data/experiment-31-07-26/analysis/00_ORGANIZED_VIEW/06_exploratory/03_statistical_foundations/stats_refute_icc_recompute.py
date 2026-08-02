#!/usr/bin/env python3
"""
Independent recomputation of the 'item-level ICC dominates' claim.
Stdlib only.  No numpy/scipy/pandas.
"""
import json, math, random, statistics, collections, itertools, os

HERE = os.path.dirname(os.path.abspath(__file__))
D = [r for r in json.load(open(os.path.join(HERE, 'paired_clean.json')))
     if r['analysis_include']]

N = len(D)
items = sorted(set(r['question_id'] for r in D))
models = sorted(set(r['model'] for r in D))
clusters = sorted(set(r['cluster'] for r in D))
print(f"cells={N} items={len(items)} models={len(models)} clusters={len(clusters)}")

def col(field):
    return [float(r[field]) for r in D]

# ---------------------------------------------------------------- helpers
def pairwise_icc(vals, groups, centred_by=None, denom_df='n'):
    """Fleiss-Cuzick pairwise ICC.
    vals: list of floats; groups: list of group keys (the clustering unit)
    centred_by: optional list of keys -> residualise on that factor's mean first
    denom_df: 'n' -> s2 = SS/N ; 'n-1' -> s2 = SS/(N-1)
    """
    y = list(vals)
    if centred_by is not None:
        acc = collections.defaultdict(list)
        for v, k in zip(y, centred_by):
            acc[k].append(v)
        mu = {k: sum(v) / len(v) for k, v in acc.items()}
        y = [v - mu[k] for v, k in zip(y, centred_by)]
    n = len(y)
    gm = sum(y) / n
    e = [v - gm for v in y]
    ss = sum(v * v for v in e)
    s2 = ss / (n if denom_df == 'n' else n - 1)
    by = collections.defaultdict(list)
    for v, g in zip(e, groups):
        by[g].append(v)
    num = 0.0
    npairs = 0
    for g, vs in by.items():
        s = sum(vs)
        q = sum(v * v for v in vs)
        num += (s * s - q) / 2.0          # sum_{j<k} e_j e_k
        npairs += len(vs) * (len(vs) - 1) // 2
    return num / (npairs * s2), npairs

def anova_decomp(vals, groups, centred_by=None):
    """One-way random-effects decomposition; returns MSW, total var, rho."""
    y = list(vals)
    if centred_by is not None:
        acc = collections.defaultdict(list)
        for v, k in zip(y, centred_by):
            acc[k].append(v)
        mu = {k: sum(v) / len(v) for k, v in acc.items()}
        y = [v - mu[k] for v, k in zip(y, centred_by)]
    n = len(y)
    gm = sum(y) / n
    by = collections.defaultdict(list)
    for v, g in zip(y, groups):
        by[g].append(v)
    G = len(by)
    ssb = sum(len(vs) * (sum(vs) / len(vs) - gm) ** 2 for vs in by.values())
    ssw = sum(sum((v - sum(vs) / len(vs)) ** 2 for v in vs) for vs in by.values())
    sst = ssb + ssw
    msw = ssw / (n - G)
    msb = ssb / (G - 1)
    vtot = sst / n
    # n0 for unbalanced
    sizes = [len(vs) for vs in by.values()]
    n0 = (sum(sizes) - sum(s * s for s in sizes) / sum(sizes)) / (G - 1)
    var_b = (msb - msw) / n0
    rho_anova = var_b / (var_b + msw) if (var_b + msw) else float('nan')
    rho_1minus = 1 - msw / vtot
    return dict(MSW=msw, MSB=msb, Vtot=vtot, n0=n0, var_b=var_b,
                rho_varcomp=rho_anova, rho_1_minus_MSW_over_V=rho_1minus, G=G)

# ---------------------------------------------------------------- 1. reproduce
print("\n=== 1. ITEM-LEVEL PAIRWISE ICC of A_correct ===")
A = col('A_correct')
B = col('B_correct')
gi = [r['question_id'] for r in D]
gm_ = [r['model'] for r in D]
gc = [r['cluster'] for r in D]

for lab, cen in (("uncentred", None), ("model-centred", gm_)):
    for df in ('n', 'n-1'):
        rho, npr = pairwise_icc(A, gi, centred_by=cen, denom_df=df)
        print(f"  A_correct {lab:14s} s2 div {df:3s}: rho={rho:+.4f}  (pairs={npr})")

print("\n=== 2. NESTED / ONE-WAY ANOVA DECOMPOSITION (model effect removed) ===")
dec = anova_decomp(A, gi, centred_by=gm_)
for k, v in dec.items():
    print(f"  {k:26s} {v:.6f}")
dec_raw = anova_decomp(A, gi)
print("  --- uncentred (model effect NOT removed) ---")
for k, v in dec_raw.items():
    print(f"  {k:26s} {v:.6f}")

print("\n=== 2b. ALGEBRAIC IDENTITY CHECK ===")
rho_pair, _ = pairwise_icc(A, gi, centred_by=gm_, denom_df='n')
print(f"  pairwise (s2=SS/N)          = {rho_pair:+.6f}")
print(f"  1 - MSW/Vtot                = {dec['rho_1_minus_MSW_over_V']:+.6f}")
print(f"  difference                  = {rho_pair - dec['rho_1_minus_MSW_over_V']:+.3e}")
print(f"  varcomp form (MSB-MSW)/n0   = {dec['rho_varcomp']:+.6f}")

print("\n=== 3. B_correct ===")
for lab, cen in (("uncentred", None), ("model-centred", gm_)):
    rho, _ = pairwise_icc(B, gi, centred_by=cen, denom_df='n')
    print(f"  B_correct {lab:14s}: rho={rho:+.4f}")

# ---------------------------------------------------------------- 4. competing levels
print("\n=== 4. COMPETING DEPENDENCE LEVELS (A_correct) ===")
# model ICC: same model different item, item effect removed
rho_model, _ = pairwise_icc(A, gm_, centred_by=gi, denom_df='n')
rho_model_unc, _ = pairwise_icc(A, gm_, denom_df='n')
print(f"  rho(same MODEL, diff item) item-centred   = {rho_model:+.4f}")
print(f"  rho(same MODEL, diff item) uncentred      = {rho_model_unc:+.4f}")
rho_clu, _ = pairwise_icc(A, gc, centred_by=gm_, denom_df='n')
print(f"  rho(same CLUSTER cell-pairs) model-centred= {rho_clu:+.4f}")
# cluster ICC at ITEM-MEAN level (does cluster nesting survive item aggregation?)
byitem = collections.defaultdict(list)
itemcluster = {}
for r in D:
    byitem[r['question_id']].append(r['A_correct'])
    itemcluster[r['question_id']] = r['cluster']
item_mean = {k: sum(v) / len(v) for k, v in byitem.items()}
iv = [item_mean[k] for k in items]
ic = [itemcluster[k] for k in items]
rho_clu_item, npr_ci = pairwise_icc(iv, ic, denom_df='n')
print(f"  rho(items within CLUSTER, on item-means)  = {rho_clu_item:+.4f}  (pairs={npr_ci})")
sz = collections.Counter(collections.Counter(ic).values())
print(f"  cluster sizes (items per cluster): {dict(sorted(sz.items()))}")

# ---------------------------------------------------------------- 5. per model-pair rho
print("\n=== 5. PER-MODEL-PAIR phi CORRELATION of A_correct (heterogeneity) ===")
wide = collections.defaultdict(dict)
for r in D:
    wide[r['question_id']][r['model']] = r['A_correct']
for m1, m2 in itertools.combinations(models, 2):
    xs = [(wide[i][m1], wide[i][m2]) for i in items if m1 in wide[i] and m2 in wide[i]]
    n = len(xs)
    x = [a for a, b in xs]; yv = [b for a, b in xs]
    mx = sum(x) / n; my = sum(yv) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a in x) / n)
    sy = math.sqrt(sum((b - my) ** 2 for b in yv) / n)
    cov = sum((a - mx) * (b - my) for a, b in xs) / n
    phi = cov / (sx * sy) if sx > 0 and sy > 0 else float('nan')
    print(f"  {m1:26s} x {m2:26s} n={n} p1={mx:.3f} p2={my:.3f} phi={phi:+.4f}")

# max attainable phi given marginals (binary correlation bound)
print("\n  max attainable phi given the two marginals:")
for m1, m2 in itertools.combinations(models, 2):
    xs = [(wide[i][m1], wide[i][m2]) for i in items if m1 in wide[i] and m2 in wide[i]]
    n = len(xs)
    p1 = sum(a for a, b in xs) / n; p2 = sum(b for a, b in xs) / n
    pmin, pmax = min(p1, p2), max(p1, p2)
    phimax = math.sqrt(pmin * (1 - pmax) / (pmax * (1 - pmin)))
    print(f"  {m1[:22]:22s} x {m2[:22]:22s} phi_max={phimax:+.4f}")

# ---------------------------------------------------------------- 6. SE impact
print("\n=== 6. SE ON POOLED A ACCURACY: binomial vs clustered ===")
p = sum(A) / N
se_bin = math.sqrt(p * (1 - p) / N)
def cluster_robust_se(vals, groups):
    n = len(vals); m = sum(vals) / n
    by = collections.defaultdict(float)
    for v, g in zip(vals, groups):
        by[g] += (v - m)
    return math.sqrt(sum(s * s for s in by.values())) / n
se_item = cluster_robust_se(A, gi)
se_clu = cluster_robust_se(A, gc)
se_mod = cluster_robust_se(A, gm_)
print(f"  pooled p = {p:.4f}")
print(f"  binomial SE            = {se_bin:.5f}")
print(f"  item-clustered SE      = {se_item:.5f}  ratio {se_item/se_bin:.3f}")
print(f"  cluster-clustered SE   = {se_clu:.5f}  ratio {se_clu/se_bin:.3f}")
print(f"  model-clustered SE     = {se_mod:.5f}  ratio {se_mod/se_bin:.3f}  (models as random, k=4)")
# crossed random-effects SE of grand mean
var_item = dec['var_b']
var_e = dec['MSW']
dec_m = anova_decomp(A, gm_, centred_by=gi)
var_mod = max(dec_m['var_b'], 0.0)
I = len(items); M = len(models)
se_fixedmodel = math.sqrt(var_item / I + var_e / N)
se_randmodel = math.sqrt(var_item / I + var_mod / M + var_e / N)
print(f"  crossed RE, model FIXED  SE = {se_fixedmodel:.5f}  ratio {se_fixedmodel/se_bin:.3f}")
print(f"  crossed RE, model RANDOM SE = {se_randmodel:.5f}  ratio {se_randmodel/se_bin:.3f}")
print(f"  var components: item={var_item:.6f} model={var_mod:.6f} resid={var_e:.6f}")
print(f"  deff item = 1+(4-1)*rho = {1+3*dec['rho_varcomp']:.4f}  sqrt={math.sqrt(1+3*dec['rho_varcomp']):.4f}")

# SE on the 325 item-mean scores: iid vs cluster-clustered
im = [item_mean[k] for k in items]
mbar = sum(im) / len(im)
se_iid_items = math.sqrt(sum((v - mbar) ** 2 for v in im) / (len(im) - 1) / len(im))
se_clu_items = cluster_robust_se(im, ic)
print(f"\n  --- if analysis is run on the 325 item-mean scores (the recommendation) ---")
print(f"  iid SE over 325 item means      = {se_iid_items:.5f}")
print(f"  cluster-robust (208 clusters)   = {se_clu_items:.5f}  ratio {se_clu_items/se_iid_items:.3f}")

# ---------------------------------------------------------------- 7. bootstrap CI
print("\n=== 7. CLUSTER BOOTSTRAP CI for item-level model-centred rho (B=3000) ===")
random.seed(20260731)
byclu = collections.defaultdict(list)
for r in D:
    byclu[r['cluster']].append(r)
cl_keys = list(byclu.keys())
Bnum = 3000
boots = []
for b in range(Bnum):
    draw = [byclu[random.choice(cl_keys)] for _ in cl_keys]
    vals = []; gg = []; mm = []
    for ci_, blk in enumerate(draw):
        for r in blk:
            vals.append(float(r['A_correct']))
            gg.append((ci_, r['question_id']))
            mm.append(r['model'])
    try:
        rr, _ = pairwise_icc(vals, gg, centred_by=mm, denom_df='n')
        if rr == rr:
            boots.append(rr)
    except ZeroDivisionError:
        pass
boots.sort()
lo = boots[int(0.025 * len(boots))]
hi = boots[int(0.975 * len(boots)) - 1]
print(f"  B_eff={len(boots)}  percentile 95% CI = [{lo:+.4f}, {hi:+.4f}]  median={boots[len(boots)//2]:+.4f}")

# ---------------------------------------------------------------- 8. permutation
print("\n=== 8. PERMUTATION TEST (shuffle cells across items within model) ===")
random.seed(99)
obs = rho_pair
byM = collections.defaultdict(list)
for idx, r in enumerate(D):
    byM[r['model']].append(idx)
nulls = []
P = 5000
base_vals = A[:]
for b in range(P):
    perm = [0.0] * N
    for m, idxs in byM.items():
        vals = [base_vals[i] for i in idxs]
        random.shuffle(vals)
        for i, v in zip(idxs, vals):
            perm[i] = v
    rr, _ = pairwise_icc(perm, gi, centred_by=gm_, denom_df='n')
    nulls.append(rr)
ge = sum(1 for v in nulls if v >= obs)
pval = (ge + 1) / (P + 1)
print(f"  observed rho = {obs:+.6f}")
print(f"  null mean={statistics.mean(nulls):+.6f} sd={statistics.pstdev(nulls):.6f}"
      f" min={min(nulls):+.4f} max={max(nulls):+.4f}")
print(f"  #null >= obs = {ge};  p = (ge+1)/(B+1) = {pval:.6f}  (floor = {1/(P+1):.6f})")

# ---------------------------------------------------------------- 9. A-B within cell
print("\n=== 9. WITHIN-CELL A-B dependence (the other candidate 'dominant' structure) ===")
n = N
pa = sum(A) / n; pb = sum(B) / n
sa = math.sqrt(sum((v - pa) ** 2 for v in A) / n)
sb = math.sqrt(sum((v - pb) ** 2 for v in B) / n)
cov = sum((a - pa) * (b - pb) for a, b in zip(A, B)) / n
print(f"  phi(A_correct, B_correct) within the same cell = {cov/(sa*sb):+.4f}")

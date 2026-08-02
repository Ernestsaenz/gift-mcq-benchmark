#!/usr/bin/env python3
"""Follow-ups: estimator independence, pair heterogeneity, permutation-null
reproduction, variance-share of the grand mean.  Stdlib only."""
import json, math, random, statistics, collections, itertools, os

HERE = os.path.dirname(os.path.abspath(__file__))
D = [r for r in json.load(open(os.path.join(HERE, 'paired_clean.json')))
     if r['analysis_include']]
N = len(D)
items = sorted(set(r['question_id'] for r in D))
models = sorted(set(r['model'] for r in D))
A = [float(r['A_correct']) for r in D]
gi = [r['question_id'] for r in D]
gmod = [r['model'] for r in D]

def pairwise_icc(vals, groups, centred_by=None):
    y = list(vals)
    if centred_by is not None:
        acc = collections.defaultdict(list)
        for v, k in zip(y, centred_by): acc[k].append(v)
        mu = {k: sum(v)/len(v) for k, v in acc.items()}
        y = [v - mu[k] for v, k in zip(y, centred_by)]
    n = len(y); gmn = sum(y)/n
    e = [v - gmn for v in y]
    s2 = sum(v*v for v in e)/n
    by = collections.defaultdict(list)
    for v, g in zip(e, groups): by[g].append(v)
    num = 0.0; npairs = 0
    for vs in by.values():
        s = sum(vs); q = sum(v*v for v in vs)
        num += (s*s - q)/2.0
        npairs += len(vs)*(len(vs)-1)//2
    return num/(npairs*s2)

print("=" * 72)
print("A. ESTIMATOR INDEPENDENCE: are the 'two estimators' algebraically distinct?")
print("=" * 72)
print("""  For balanced groups of size k the Fleiss-Cuzick pairwise statistic is
      rho_pair = (k*SSB - SST) / ((k-1)*SST)
  and the ANOVA statistic quoted as the 'independent' check is
      1 - MSW/Vtot = 1 - [SSW/(G(k-1))] / [SST/(Gk)] = (k*SSB - SST)/((k-1)*SST)
  i.e. THE SAME FUNCTION of the SAME two sufficient statistics (SSB, SSW).""")
# numerical demonstration on synthetic balanced data
random.seed(1)
for trial in range(3):
    v = [random.choice([0.0, 1.0]) for _ in range(400)]
    g = [i // 4 for i in range(400)]
    n = len(v); gmn = sum(v)/n
    ssb = 0.0; ssw = 0.0
    byg = collections.defaultdict(list)
    for x, k in zip(v, g): byg[k].append(x)
    for vs in byg.values():
        m = sum(vs)/len(vs)
        ssb += len(vs)*(m-gmn)**2
        ssw += sum((x-m)**2 for x in vs)
    sst = ssb+ssw; G = len(byg); k = 4
    anova = 1 - (ssw/(n-G))/(sst/n)
    print(f"   synthetic trial {trial}: pairwise={pairwise_icc(v,g):+.10f}  "
          f"1-MSW/V={anova:+.10f}  diff={pairwise_icc(v,g)-anova:+.2e}")

print("\n  On the real (near-balanced) data:")
rp = pairwise_icc(A, gi, centred_by=gmod)
byg = collections.defaultdict(list)
ymc = []
acc = collections.defaultdict(list)
for v, m in zip(A, gmod): acc[m].append(v)
mu = {k: sum(v)/len(v) for k, v in acc.items()}
ymc = [v - mu[m] for v, m in zip(A, gmod)]
gmn = sum(ymc)/N
for v, g in zip(ymc, gi): byg[g].append(v)
ssb = sum(len(vs)*(sum(vs)/len(vs)-gmn)**2 for vs in byg.values())
ssw = sum(sum((x-sum(vs)/len(vs))**2 for x in vs) for vs in byg.values())
sst = ssb+ssw; G = len(byg)
print(f"   SSB={ssb:.6f} SSW={ssw:.6f} SST={sst:.6f}")
print(f"   MSW = SSW/(N-G) = {ssw/(N-G):.6f}   <-- claim's MS_cell=0.061735")
print(f"   Vtot = SST/N    = {sst/N:.6f}       <-- claim's 'total variance'=0.087656")
print(f"   Vtot = SST/(N-1)= {sst/(N-1):.6f}")
print(f"   var_item+var_resid (varcomp) = {(ssb/(G-1)-ssw/(N-G))/3.996921 + ssw/(N-G):.6f}")
print(f"   pairwise rho = {rp:+.6f}   1-MSW/Vtot = {1-(ssw/(N-G))/(sst/N):+.6f}")
print("   => the 'agreement' of 0.2924 and 0.2957 is a divisor convention, not")
print("      a second measurement.  Zero independent evidential content.")

print("\n" + "=" * 72)
print("B. VARIANCE SHARE OF THE POOLED-MEAN SAMPLING VARIANCE")
print("=" * 72)
# crossed decomposition: item, model, residual
def varcomp(vals, groups, centred_by):
    y = list(vals)
    acc = collections.defaultdict(list)
    for v, k in zip(y, centred_by): acc[k].append(v)
    mu = {k: sum(v)/len(v) for k, v in acc.items()}
    y = [v - mu[k] for v, k in zip(y, centred_by)]
    n = len(y); gmn = sum(y)/n
    by = collections.defaultdict(list)
    for v, g in zip(y, groups): by[g].append(v)
    G = len(by)
    ssb = sum(len(vs)*(sum(vs)/len(vs)-gmn)**2 for vs in by.values())
    ssw = sum(sum((x-sum(vs)/len(vs))**2 for x in vs) for vs in by.values())
    msb = ssb/(G-1); msw = ssw/(n-G)
    sizes = [len(vs) for vs in by.values()]
    n0 = (sum(sizes)-sum(s*s for s in sizes)/sum(sizes))/(G-1)
    return (msb-msw)/n0, msw, G
var_item, var_res, I = varcomp(A, gi, gmod)
var_mod, _, M = varcomp(A, gmod, gi)
c_item = var_item/I; c_mod = var_mod/M; c_res = var_res/N
tot = c_item + c_mod + c_res
print(f"  var_item={var_item:.6f} (I={I})  var_model={var_mod:.6f} (M={M})  var_resid={var_res:.6f}")
print(f"  contribution to Var(grand mean):")
print(f"    item   {c_item:.3e}  = {100*c_item/tot:5.1f}%")
print(f"    model  {c_mod:.3e}  = {100*c_mod/tot:5.1f}%")
print(f"    resid  {c_res:.3e}  = {100*c_res/tot:5.1f}%")
print(f"  => with models RANDOM the model term is {c_mod/c_item:.1f}x the item term.")
print(f"     With models FIXED the model term drops out and item dominates (that is")
print(f"     the unstated assumption the claim's 'dominant' rests on).")

print("\n" + "=" * 72)
print("C. HETEROGENEITY OF pairwise phi ACROSS MODEL PAIRS (cluster bootstrap)")
print("=" * 72)
wide = collections.defaultdict(dict)
icl = {}
for r in D:
    wide[r['question_id']][r['model']] = float(r['A_correct'])
    icl[r['question_id']] = r['cluster']
byclu = collections.defaultdict(list)
for it in items: byclu[icl[it]].append(it)
clkeys = list(byclu.keys())

def phi_pair(itemset, m1, m2):
    xs = [(wide[i][m1], wide[i][m2]) for i in itemset if m1 in wide[i] and m2 in wide[i]]
    n = len(xs)
    if n < 3: return float('nan')
    mx = sum(a for a, b in xs)/n; my = sum(b for a, b in xs)/n
    sx = math.sqrt(sum((a-mx)**2 for a, b in xs)/n)
    sy = math.sqrt(sum((b-my)**2 for a, b in xs)/n)
    if sx == 0 or sy == 0: return float('nan')
    return sum((a-mx)*(b-my) for a, b in xs)/n/(sx*sy)

pairs = list(itertools.combinations(models, 2))
obs = {p: phi_pair(items, *p) for p in pairs}
lo_p = min(obs, key=lambda p: obs[p]); hi_p = max(obs, key=lambda p: obs[p])
d_obs = obs[hi_p] - obs[lo_p]
print(f"  lowest  pair {lo_p[0]} x {lo_p[1]}: phi={obs[lo_p]:+.4f}")
print(f"  highest pair {hi_p[0]} x {hi_p[1]}: phi={obs[hi_p]:+.4f}")
print(f"  observed spread = {d_obs:+.4f}")
random.seed(7)
diffs = []; ranges = []
for b in range(3000):
    draw = []
    for _ in clkeys: draw.extend(byclu[random.choice(clkeys)])
    d = phi_pair(draw, *hi_p) - phi_pair(draw, *lo_p)
    if d == d: diffs.append(d)
    vals = [phi_pair(draw, *p) for p in pairs]
    vals = [v for v in vals if v == v]
    if len(vals) == len(pairs): ranges.append(max(vals)-min(vals))
diffs.sort()
print(f"  cluster-bootstrap 95% CI on that spread = "
      f"[{diffs[int(.025*len(diffs))]:+.4f}, {diffs[int(.975*len(diffs))-1]:+.4f}]  (B={len(diffs)})")
print(f"  fraction of bootstrap draws with spread <= 0: "
      f"{sum(1 for d in diffs if d <= 0)/len(diffs):.4f}")

print("\n" + "=" * 72)
print("D. PERMUTATION NULL: can the claim's null mean of -0.0159 be reproduced?")
print("=" * 72)
byM = collections.defaultdict(list)
for idx, r in enumerate(D): byM[r['model']].append(idx)

def perm_within_model():
    out = [0.0]*N
    for m, idxs in byM.items():
        vals = [A[i] for i in idxs]; random.shuffle(vals)
        for i, v in zip(idxs, vals): out[i] = v
    return out

def perm_multinomial_items():
    """cells reassigned to items at random WITHOUT preserving 4-per-item"""
    out_g = [random.choice(items) for _ in range(N)]
    return out_g

random.seed(11)
n1 = [pairwise_icc(perm_within_model(), gi, centred_by=gmod) for _ in range(2000)]
random.seed(12)
n2 = [pairwise_icc(A, perm_multinomial_items(), centred_by=gmod) for _ in range(2000)]
random.seed(13)
# variant: permute item labels globally (ignoring model) -> item groups keep size 4
n3 = []
for _ in range(2000):
    lab = gi[:]; random.shuffle(lab)
    n3.append(pairwise_icc(A, lab, centred_by=gmod))
for name, nn in (("within-model permutation (as described)", n1),
                 ("multinomial reassignment of cells to items", n2),
                 ("global shuffle of item labels", n3)):
    print(f"  {name:44s} mean={statistics.mean(nn):+.5f} sd={statistics.pstdev(nn):.5f}")
print("  claim reports                                mean=-0.01590 sd=0.02040")
print("  Theory: within-model permutation of model-centred residuals has")
print("  E[cross-product]=0 exactly, so the null mean must sit at ~0.")

print("\n" + "=" * 72)
print("E. IS ITEM-CLUSTERING SUFFICIENT?  (cluster level sits above item)")
print("=" * 72)
def crse(vals, groups):
    n = len(vals); m = sum(vals)/n
    by = collections.defaultdict(float)
    for v, g in zip(vals, groups): by[g] += (v-m)
    return math.sqrt(sum(s*s for s in by.values()))/n
gc = [r['cluster'] for r in D]
p = sum(A)/N
print(f"  binomial SE          {math.sqrt(p*(1-p)/N):.5f}   ratio 1.000")
print(f"  item-clustered SE    {crse(A,gi):.5f}   ratio {crse(A,gi)/math.sqrt(p*(1-p)/N):.3f}")
print(f"  cluster-clustered SE {crse(A,gc):.5f}   ratio {crse(A,gc)/math.sqrt(p*(1-p)/N):.3f}")
print(f"  cluster/item SE ratio = {crse(A,gc)/crse(A,gi):.4f}"
      f"  -> item-clustering still understates by "
      f"{100*(crse(A,gc)/crse(A,gi)-1):.1f}%")
sizes = collections.Counter(collections.Counter(icl[i] for i in items).values())
print(f"  items per cluster: {dict(sorted(sizes.items()))}  (max cluster = 20 items)")

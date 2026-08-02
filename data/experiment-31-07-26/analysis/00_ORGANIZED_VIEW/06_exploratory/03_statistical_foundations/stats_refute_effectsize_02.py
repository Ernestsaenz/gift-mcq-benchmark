"""Part 2: per-model CIs on g, and the cross-family AGREEMENT test the claim asserts."""
import json, math, random, collections

P = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json'
rows = [r for r in json.load(open(P)) if r.get('analysis_include')]

def lchoose(n, k): return math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)
def binom_cdf(k, n, p):
    if p <= 0: return 1.0
    if p >= 1: return 0.0 if k < n else 1.0
    return sum(math.exp(lchoose(n,i)+i*math.log(p)+(n-i)*math.log(1-p)) for i in range(k+1))
def binom_sf(k, n, p): return 1.0-binom_cdf(k-1,n,p) if k > 0 else 1.0
def bisect(f, target, incr=True):
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo+hi)/2
        if (f(mid) < target) == incr: lo = mid
        else: hi = mid
    return (lo+hi)/2
def cp(k, n):
    lo = 0.0 if k == 0 else bisect(lambda p: binom_sf(k,n,p), 0.025, True)
    hi = 1.0 if k == n else bisect(lambda p: binom_cdf(k,n,p), 0.025, False)
    return lo, hi
def cohen_h(p1,p2): return 2*math.asin(math.sqrt(p1))-2*math.asin(math.sqrt(p2))

bym = collections.defaultdict(list)
for r in rows: bym[r['model']].append(r)

print('PER-MODEL Cohen g with EXACT (Clopper-Pearson) CI, vs raw accuracy drop')
print(f'{"model":28s} {"n10":>4s} {"n01":>4s} {"disc":>5s} {"g":>8s} {"g 95% CI":>20s} {"RD":>8s} {"h":>8s}')
res = {}
for m in sorted(bym):
    rr = bym[m]
    a = sum(1 for r in rr if r['A_correct']==0 and r['B_correct']==1)
    b = sum(1 for r in rr if r['A_correct']==1 and r['B_correct']==0)
    d = a+b; n = len(rr)
    qA = sum(r['A_correct'] for r in rr)/n; qB = sum(r['B_correct'] for r in rr)/n
    g = a/d-0.5
    lo, hi = cp(a, d)
    res[m] = dict(g=g, RD=qB-qA, h=cohen_h(qB,qA), OR=a/b, disc=d, n=n, glo=lo-0.5, ghi=hi-0.5)
    print(f'{m:28s} {a:4d} {b:4d} {d:5d} {g:+8.4f} [{lo-0.5:+.4f},{hi-0.5:+.4f}] {qB-qA:+8.4f} {cohen_h(qB,qA):+8.4f}')

print('\n"all above the 0.25 large threshold" -- does the CI actually clear it?')
for m in sorted(res):
    v = res[m]
    clears = abs(v['ghi']) > 0.25   # ghi is the CI bound nearest zero
    print(f'  {m:28s} |g|={abs(v["g"]):.4f} CI-bound-nearest-0 = {abs(v["ghi"]):.4f} '
          f'-> excludes "large" boundary 0.25? {"YES" if clears else "NO"}')

print('\n--- DO THE FAMILIES AGREE? rank the 4 models by each effect size ---')
def ranks(key, absval=True):
    vals = {m: (abs(res[m][key]) if absval else res[m][key]) for m in res}
    order = sorted(vals, key=lambda m: -vals[m])
    return {m: i+1 for i, m in enumerate(order)}, vals

rk_g, v_g = ranks('g'); rk_rd, v_rd = ranks('RD'); rk_h, v_h = ranks('h')
print(f'{"model":28s} {"|g|":>8s} {"rank":>5s} {"|RD|":>8s} {"rank":>5s} {"|h|":>8s} {"rank":>5s}')
for m in sorted(res):
    print(f'{m:28s} {v_g[m]:8.4f} {rk_g[m]:5d} {v_rd[m]:8.4f} {rk_rd[m]:5d} {v_h[m]:8.4f} {rk_h[m]:5d}')

def spearman(r1, r2):
    ms = list(r1); n = len(ms)
    d2 = sum((r1[m]-r2[m])**2 for m in ms)
    return 1 - 6*d2/(n*(n*n-1))
print(f'\n  Spearman rank corr  |g| vs |RD| = {spearman(rk_g, rk_rd):+.3f}')
print(f'  Spearman rank corr  |g| vs |h|  = {spearman(rk_g, rk_h):+.3f}')
print(f'  Spearman rank corr  |RD| vs |h| = {spearman(rk_rd, rk_h):+.3f}')
print('  (n=4 models; Spearman on 4 points is descriptive only, no p-value computed)')

print('\n--- the concrete failure case ---')
gem = res['google/gemini-3.6-flash']; gma = res['google/gemma-4-26b-a4b-it']
print(f'  gemini : g={gem["g"]:+.4f} ("large" by Cohen) but accuracy fell only {abs(gem["RD"])*100:.2f} pp')
print(f'  gemma  : g={gma["g"]:+.4f} (smallest |g| of the four) but accuracy fell {abs(gma["RD"])*100:.2f} pp')
print(f'  -> g ranks gemini as the {rk_g["google/gemini-3.6-flash"]}nd-worst-hit model; RD ranks it '
      f'{rk_rd["google/gemini-3.6-flash"]}th (least hit). The families do NOT agree.')

print('\n--- why: g/OR discard the concordant cells entirely ---')
print('  Cohen g is a function of n10/(n10+n01) ONLY. Two runs with identical g:')
for (a, b, n) in [(45, 247, 1299), (4, 22, 1299), (2, 11, 1299)]:
    print(f'    n10={a:3d} n01={b:3d} of N={n}: g={a/(a+b)-0.5:+.4f}  OR={a/b:.4f}  '
          f'but RD={(a-b)/n:+.4f} ({abs(a-b)/n*100:.2f} pp)')
print('  => g/OR measure DIRECTION CONSISTENCY among discordants, not effect MAGNITUDE.')
print('     A "large" g is compatible with an arbitrarily small accuracy drop.')

# ---- bootstrap the pooled g under a hypothetical mid-range baseline, to isolate the ceiling ----
print('\n--- isolating the ceiling effect on h (pooled) ---')
n11 = sum(1 for r in rows if r['A_correct']==1 and r['B_correct']==1)
n10 = sum(1 for r in rows if r['A_correct']==0 and r['B_correct']==1)
n01 = sum(1 for r in rows if r['A_correct']==1 and r['B_correct']==0)
n00 = sum(1 for r in rows if r['A_correct']==0 and r['B_correct']==0)
N = len(rows)
pA = (n11+n01)/N; pB = (n11+n10)/N; RD = pB-pA
h_obs = cohen_h(pB, pA)
h_mid = cohen_h(0.5+RD, 0.5)
print(f'  observed pA={pA:.4f} -> |h|={abs(h_obs):.4f}')
print(f'  same RD={RD:+.4f} at a mid-range pA=0.50 -> |h|={abs(h_mid):.4f}')
print(f'  the 0.90 ceiling therefore INFLATES |h| by {(abs(h_obs)/abs(h_mid)-1)*100:.1f}%, not deflates it.')
print(f'  |h| is MINIMIZED near pA~0.6 for this RD; it grows monotonically toward either extreme.')

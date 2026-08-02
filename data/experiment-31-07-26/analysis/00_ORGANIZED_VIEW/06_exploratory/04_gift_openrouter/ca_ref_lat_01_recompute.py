#!/usr/bin/env python
"""Independent recomputation of the latency-cost cross-arm claim.
Stdlib only. Every estimator hand-rolled here; nothing imported from the analysis scripts.

Methods named inline:
  median   = order statistic, average of middle two for even n
  quantile = type-7 (linear interpolation on (n-1)p), same convention as numpy default
  CI       = cluster bootstrap over question clusters, B=20000, percentile interval
  sign test= exact two-sided binomial, method of small probabilities (sum of all
             outcomes with pmf <= pmf(observed))
"""
import json, math, random
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
rows = [r for r in json.load(open(BASE + 'cross_arm_A.json')) if r['analysis_include']]
MODELS = sorted({r['model'] for r in rows})

print('cells=%d items=%d clusters=%d models=%d' % (
    len(rows), len({r['question_id'] for r in rows}),
    len({r['cluster'] for r in rows}), len(MODELS)))

# ---------- estimators ----------
def median(xs):
    s = sorted(xs); n = len(s)
    return s[n//2] if n % 2 else 0.5*(s[n//2-1] + s[n//2])

def quant(xs, p):
    s = sorted(xs); n = len(s)
    if n == 1: return float(s[0])
    h = (n-1)*p; lo = int(math.floor(h)); hi = min(lo+1, n-1)
    return s[lo] + (h-lo)*(s[hi]-s[lo])

def logC(n, k):
    return math.lgamma(n+1) - math.lgamma(k+1) - math.lgamma(n-k+1)

def binom_two_sided(k, n, p=0.5):
    lp, lq = math.log(p), math.log(1-p)
    lpk = logC(n, k) + k*lp + (n-k)*lq
    tot = 0.0
    for i in range(n+1):
        li = logC(n, i) + i*lp + (n-i)*lq
        if li <= lpk + 1e-9:
            tot += math.exp(li)
    return min(1.0, tot)

def cluster_boot(cells, fn, B=20000, seed=777, alpha=0.05):
    byc = defaultdict(list)
    for r in cells: byc[r['cluster']].append(r)
    keys = list(byc.keys()); K = len(keys); rng = random.Random(seed)
    reps = []
    for _ in range(B):
        samp = []
        for _ in range(K): samp.extend(byc[keys[rng.randrange(K)]])
        reps.append(fn(samp))
    return quant(reps, alpha/2), quant(reps, 1-alpha/2)

med_ratio = lambda c: median([r['gift_latency_ms']/r['or_latency_ms'] for r in c])
med_diff  = lambda c: median([(r['gift_latency_ms']-r['or_latency_ms'])/1000.0 for r in c])

# ---------- headline table ----------
print('\n%-24s %5s %8s %8s %8s %-16s %8s %10s %9s' %
      ('model','n','medGIFT','medOR','ratio','ratio 95% CI','medDiff','g>o','p_sign'))
out = {}
for m in MODELS + ['POOLED']:
    c = rows if m == 'POOLED' else [r for r in rows if r['model'] == m]
    g = [r['gift_latency_ms']/1000.0 for r in c]
    o = [r['or_latency_ms']/1000.0 for r in c]
    ratios = [r['gift_latency_ms']/r['or_latency_ms'] for r in c]
    nb = sum(1 for x in ratios if x > 1)
    lo, hi = cluster_boot(c, med_ratio)
    dlo, dhi = cluster_boot(c, med_diff)
    p = binom_two_sided(nb, len(c))
    out[m] = dict(n=len(c), medG=median(g), medO=median(o), ratio=median(ratios),
                  ratio_ci=[lo,hi], medDiff=median([a-b for a,b in zip(g,o)]),
                  diff_ci=[dlo,dhi], n_slower=nb, frac_slower=nb/len(c), p_sign=p,
                  p10r=quant(ratios,.10), p25r=quant(ratios,.25), p75r=quant(ratios,.75),
                  p90r=quant(ratios,.90), minr=min(ratios), maxr=max(ratios),
                  p90G=quant(g,.90), maxG=max(g), p90O=quant(o,.90), maxO=max(o),
                  minG=min(g), minO=min(o),
                  iqrG=quant(g,.75)-quant(g,.25), iqrO=quant(o,.75)-quant(o,.25),
                  cvG=(sum(g)/len(g)) and (math.sqrt(sum((x-sum(g)/len(g))**2 for x in g)/(len(g)-1))/(sum(g)/len(g))),
                  cvO=math.sqrt(sum((x-sum(o)/len(o))**2 for x in o)/(len(o)-1))/(sum(o)/len(o)))
    print('%-24s %5d %8.2f %8.2f %8.2f [%6.2f,%6.2f] %8.2f %5d/%-4d %9.2g' %
          (m, len(c), out[m]['medG'], out[m]['medO'], out[m]['ratio'], lo, hi,
           out[m]['medDiff'], nb, len(c), p))

print('\nratio distribution within model (paired per-cell gift/or):')
print('%-24s %7s %7s %7s %7s %7s %7s %7s' % ('model','min','p10','p25','med','p75','p90','max'))
for m in MODELS + ['POOLED']:
    r = out[m]
    print('%-24s %7.2f %7.2f %7.2f %7.2f %7.2f %7.2f %7.2f' %
          (m, r['minr'], r['p10r'], r['p25r'], r['ratio'], r['p75r'], r['p90r'], r['maxr']))

print('\nspread WITHIN arm, per model (seconds):')
print('%-24s %8s %8s %8s %8s %8s | %8s %8s %8s %8s %8s' %
      ('model','G_min','G_med','G_p90','G_max','G_CV','O_min','O_med','O_p90','O_max','O_CV'))
for m in MODELS + ['POOLED']:
    r = out[m]
    print('%-24s %8.2f %8.2f %8.2f %8.2f %8.3f | %8.2f %8.2f %8.2f %8.2f %8.3f' %
          (m, r['minG'], r['medG'], r['p90G'], r['maxG'], r['cvG'],
           r['minO'], r['medO'], r['p90O'], r['maxO'], r['cvO']))

json.dump(out, open(BASE + 'ca_ref_lat_01_out.json','w'), indent=1)

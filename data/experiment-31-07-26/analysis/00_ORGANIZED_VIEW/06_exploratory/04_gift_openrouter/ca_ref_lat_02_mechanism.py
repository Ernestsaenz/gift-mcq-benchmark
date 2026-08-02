#!/usr/bin/env python
"""Test the CAUSAL half of the claim: is the model-to-model spread of the gift/or
multiplier driven by the OR denominator rather than by GIFT variation?

Counterfactual decomposition (deterministic, on median seconds):
  observed   ratio_m = G_m / O_m
  denom-only ratio_m = Gbar / O_m     (GIFT held at the pooled median)
  numer-only ratio_m = G_m / Obar     (OR   held at the pooled median)
Compare the between-model spread each generates (max/min, and sd of log).

Also: within-model dispersion of each arm, and per-cell rank correlation between
the two arms (does GIFT inherit the model's own speed?).
"""
import json, math
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
rows = [r for r in json.load(open(BASE + 'cross_arm_A.json')) if r['analysis_include']]
MODELS = sorted({r['model'] for r in rows})

def median(xs):
    s = sorted(xs); n = len(s)
    return s[n//2] if n % 2 else 0.5*(s[n//2-1]+s[n//2])

def sd(xs):
    m = sum(xs)/len(xs)
    return math.sqrt(sum((x-m)**2 for x in xs)/(len(xs)-1))

def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0.0]*len(v); i = 0
        while i < len(order):
            j = i
            while j+1 < len(order) and v[order[j+1]] == v[order[i]]: j += 1
            avg = (i+j)/2.0 + 1
            for k in range(i, j+1): rk[order[k]] = avg
            i = j+1
        return rk
    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx)/len(rx), sum(ry)/len(ry)
    num = sum((a-mx)*(b-my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry))
    return num/den if den else float('nan')

G = {m: median([r['gift_latency_ms']/1000. for r in rows if r['model']==m]) for m in MODELS}
O = {m: median([r['or_latency_ms']/1000.  for r in rows if r['model']==m]) for m in MODELS}
Gbar = median([r['gift_latency_ms']/1000. for r in rows])
Obar = median([r['or_latency_ms']/1000.  for r in rows])

print('pooled medians: GIFT %.2f s   OR %.2f s\n' % (Gbar, Obar))
print('%-24s %8s %8s %9s %11s %11s' % ('model','G_med','O_med','obs ratio','denom-only','numer-only'))
obs, den_only, num_only = [], [], []
for m in MODELS:
    o_r, d_r, n_r = G[m]/O[m], Gbar/O[m], G[m]/Obar
    obs.append(o_r); den_only.append(d_r); num_only.append(n_r)
    print('%-24s %8.2f %8.2f %9.2f %11.2f %11.2f' % (m, G[m], O[m], o_r, d_r, n_r))

def span(v): return max(v)/min(v)
def sdlog(v): return sd([math.log(x) for x in v])
print('\nbetween-model spread of the multiplier')
print('  observed                : span %6.2fx   sd(log) %.3f' % (span(obs), sdlog(obs)))
print('  if GIFT were constant   : span %6.2fx   sd(log) %.3f  <- denominator alone' % (span(den_only), sdlog(den_only)))
print('  if OR were constant     : span %6.2fx   sd(log) %.3f  <- numerator alone' % (span(num_only), sdlog(num_only)))
print('\nbetween-model spread of each ARM itself')
print('  GIFT medians : %.2f - %.2f s  span %.2fx  sd(log) %.3f' %
      (min(G.values()), max(G.values()), span(list(G.values())), sdlog(list(G.values()))))
print('  OR   medians : %.2f - %.2f s  span %.2fx  sd(log) %.3f' %
      (min(O.values()), max(O.values()), span(list(O.values())), sdlog(list(O.values()))))
print('  variance ratio sd(log O)^2 / sd(log G)^2 = %.1f' %
      ((sdlog(list(O.values()))**2)/(sdlog(list(G.values()))**2)))

# additive-overhead test: is GIFT = OR + constant?
print('\nadditive-overhead check (median paired difference, s):')
for m in MODELS:
    c = [r for r in rows if r['model']==m]
    d = median([(r['gift_latency_ms']-r['or_latency_ms'])/1000. for r in c])
    print('  %-24s  medG-medO %6.2f   median(G-O) %6.2f' % (m, G[m]-O[m], d))

print('\nper-cell rank correlation GIFT vs OR latency (Spearman, within model):')
for m in MODELS:
    c = [r for r in rows if r['model']==m]
    print('  %-24s rho=%+.3f  n=%d' % (m, spearman([r['gift_latency_ms'] for r in c],
                                                   [r['or_latency_ms'] for r in c]), len(c)))
c = rows
print('  %-24s rho=%+.3f  n=%d' % ('POOLED', spearman([r['gift_latency_ms'] for r in c],
                                                     [r['or_latency_ms'] for r in c]), len(c)))

# how many cells is GIFT faster, per model
print('\nGIFT faster than OR, per model:')
for m in MODELS + ['POOLED']:
    c = rows if m=='POOLED' else [r for r in rows if r['model']==m]
    f = sum(1 for r in c if r['gift_latency_ms'] < r['or_latency_ms'])
    print('  %-24s %4d/%d = %5.1f%% of cells GIFT is FASTER' % (m, f, len(c), 100.*f/len(c)))

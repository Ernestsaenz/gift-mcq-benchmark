#!/usr/bin/env python
"""ca_rtx_01: (1) replicate the claim's decomposition exactly; (2) redo the token
ledger on the MATCHED 1244-cell paired set instead of whole-arm attempt pools."""
import json, math, random
from collections import defaultdict
from math import lgamma, exp, log

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
rows = [r for r in json.load(open(BASE + 'cross_arm_A.json')) if r['analysis_include']]
M = json.load(open(BASE + 'ca_rtx_matched.json'))
MODELS = sorted(set(r['model'] for r in rows))
SHORT = {'google/gemini-3.6-flash': 'gemini', 'google/gemma-4-26b-a4b-it': 'gemma',
         'qwen/qwen3.6-35b-a3b': 'qwen', 'z-ai/glm-5.2': 'glm'}


def median(xs):
    s = sorted(xs); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def quant(xs, p):
    s = sorted(xs); n = len(s)
    if n == 1: return float(s[0])
    h = (n - 1) * p; lo = int(math.floor(h)); hi = min(lo + 1, n - 1)
    return s[lo] + (h - lo) * (s[hi] - s[lo])


def ols(x, y):
    n = len(x); mx = sum(x) / n; my = sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    b = sxy / sxx if sxx else 0.0
    a = my - b * mx
    ssr = sum((yy - (a + b * xx)) ** 2 for xx, yy in zip(x, y))
    sst = sum((yy - my) ** 2 for yy in y)
    return a, b, (1 - ssr / sst if sst else float('nan'))


print('=== 1. REPLICATION of ca_lat_03 decomposition (or_latency_s = a + b*or_COMPLETION_tokens) ===')
print('%-8s %8s %10s %8s %10s %10s %26s' % ('model', 'a_s', 'b_ms/tok', 'R2', 'medGcompl', 'medOcompl', 'med overhead_s [95%CI]'))
rep = {}
for m in MODELS:
    cells = [r for r in rows if r['model'] == m]
    a, b, r2 = ols([r['or_tokens'] for r in cells], [r['or_latency_ms'] / 1000.0 for r in cells])
    ovh = [r['gift_latency_ms'] / 1000.0 - (a + b * r['gift_tokens']) for r in cells]
    byc = defaultdict(list)
    for r, v in zip(cells, ovh): byc[r['cluster']].append(v)
    keys = list(byc); rng = random.Random(31337); reps = []
    for _ in range(5000):
        s = []
        for _ in range(len(keys)): s.extend(byc[keys[rng.randrange(len(keys))]])
        reps.append(median(s))
    ci = (quant(reps, .025), quant(reps, .975))
    print('%-8s %8.2f %10.3f %8.3f %10.0f %10.0f       %6.2f [%.2f, %.2f]'
          % (SHORT[m], a, b * 1000, r2, median([r['gift_tokens'] for r in cells]),
             median([r['or_tokens'] for r in cells]), median(ovh), ci[0], ci[1]))
    rep[SHORT[m]] = dict(a=a, b=b, r2=r2, med=median(ovh), ci=list(ci))

print('\n=== 2. TOKEN LEDGER, MATCHED 1244 PAIRED CELLS (same items, same models, both arms) ===')
print('%-8s %5s %11s %11s %7s %11s %11s %8s' % ('model', 'n', 'medP_GIFT', 'medP_OR', 'ratio', 'medC_GIFT', 'medC_OR', 'delta'))
led = {}
for m in MODELS + ['POOLED']:
    cc = M if m == 'POOLED' else [d for d in M if d['model'] == m]
    gp, op = median([d['g_prompt'] for d in cc]), median([d['o_prompt'] for d in cc])
    gc, oc = median([d['g_compl'] for d in cc]), median([d['o_compl'] for d in cc])
    print('%-8s %5d %11.0f %11.0f %7.2f %11.0f %11.0f %+8.0f'
          % (SHORT.get(m, m), len(cc), gp, op, gp / op, gc, oc, gc - oc))
    led[SHORT.get(m, m)] = dict(n=len(cc), medP_g=gp, medP_o=op, medC_g=gc, medC_o=oc,
                                sumC_g=sum(d['g_compl'] for d in cc),
                                sumC_o=sum(d['o_compl'] for d in cc),
                                sumP_g=sum(d['g_prompt'] for d in cc),
                                sumP_o=sum(d['o_prompt'] for d in cc))
p = led['POOLED']
print('\nMATCHED pooled COMPLETION tokens: GIFT %d vs OR %d  (ratio %.4f)'
      % (p['sumC_g'], p['sumC_o'], p['sumC_g'] / p['sumC_o']))
print('MATCHED pooled PROMPT     tokens: GIFT %d vs OR %d  (ratio %.4f)'
      % (p['sumP_g'], p['sumP_o'], p['sumP_g'] / p['sumP_o']))
for m in MODELS:
    d = led[SHORT[m]]
    print('   %-8s sum completion GIFT %8d vs OR %8d  (%+.1f%%)'
          % (SHORT[m], d['sumC_g'], d['sumC_o'], 100.0 * (d['sumC_g'] / d['sumC_o'] - 1)))

print('\npaired within-cell completion-token comparison (exact two-sided sign test, ties dropped):')


def binom_two_sided(k, n, pr=0.5):
    def lpmf(i):
        return (lgamma(n + 1) - lgamma(i + 1) - lgamma(n - i + 1)
                + i * log(pr) + (n - i) * log(1 - pr))
    obs = lpmf(k)
    return min(1.0, sum(exp(lpmf(i)) for i in range(n + 1) if lpmf(i) <= obs + 1e-9))


for m in MODELS + ['POOLED']:
    cc = M if m == 'POOLED' else [d for d in M if d['model'] == m]
    up = sum(1 for d in cc if d['g_compl'] > d['o_compl'])
    dn = sum(1 for d in cc if d['g_compl'] < d['o_compl'])
    ti = len(cc) - up - dn
    pv = binom_two_sided(up, up + dn) if up + dn else float('nan')
    print('   %-8s GIFT>OR %4d   GIFT<OR %4d   tie %4d   p=%.3g' % (SHORT.get(m, m), up, dn, ti, pv))

json.dump(dict(ledger=led, replication=rep), open(BASE + 'ca_rtx_01_out.json', 'w'), indent=1)

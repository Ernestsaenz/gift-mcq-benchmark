#!/usr/bin/env python
"""Independent re-computation of the latency-cost ratio claim.
Standard library only. Every p-value / CI names its method inline."""
import json, math, random, sqlite3
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
DB = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite'

rows = [r for r in json.load(open(BASE + 'cross_arm_A.json')) if r['analysis_include']]
MODELS = sorted(set(r['model'] for r in rows))
print('n cells', len(rows), 'items', len(set(r['question_id'] for r in rows)),
      'clusters', len(set(r['cluster'] for r in rows)), 'models', len(MODELS))


def median(xs):
    s = sorted(xs); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def quant(xs, p):
    s = sorted(xs); n = len(s)
    if n == 0: return float('nan')
    if n == 1: return float(s[0])
    h = (n - 1) * p; lo = int(math.floor(h)); hi = min(lo + 1, n - 1)
    return s[lo] + (h - lo) * (s[hi] - s[lo])


def cluster_boot_indices(cells, B, seed):
    byc = defaultdict(list)
    for r in cells:
        byc[r['cluster']].append(r)
    keys = list(byc); K = len(keys); rng = random.Random(seed)
    for _ in range(B):
        samp = []
        for _ in range(K):
            samp.extend(byc[keys[rng.randrange(K)]])
        yield samp


# ---------------------------------------------------------------- 1. reproduce
print('\n=== 1. POINT ESTIMATES (independent re-implementation) ===')
print('%-24s %6s %8s %8s %8s %9s %9s %9s %9s' %
      ('model', 'n', 'giftAcc', 'orAcc', 'dpp', 'medDiff_s', 'meanDiff_s', 'pp_per_s', 'net'))
pt = {}
for m in MODELS + ['POOLED']:
    cells = rows if m == 'POOLED' else [r for r in rows if r['model'] == m]
    n = len(cells)
    g = sum(r['gift_correct'] for r in cells); o = sum(r['or_correct'] for r in cells)
    d = 100.0 * (g - o) / n
    diffs = [(r['gift_latency_ms'] - r['or_latency_ms']) / 1000.0 for r in cells]
    md = median(diffs); mn = sum(diffs) / n
    pt[m] = dict(n=n, g=g, o=o, dpp=d, md=md, mn=mn, net=g - o,
                 tot_extra=sum(diffs))
    print('%-24s %6d %8.1f %8.1f %+8.3f %9.3f %9.3f %+9.4f %9d' %
          (m, n, 100.0 * g / n, 100.0 * o / n, d, md, mn, d / md, g - o))

print('\n=== 2. RATIO CIs, cluster bootstrap over 183 clusters, B=20000, percentile ===')
B = 20000
print('%-24s %10s %28s %10s | %10s %26s %10s' %
      ('model', 'pp_per_s', '95% CI', 'undef%', 's_per_corr', '95% CI', 'net<=0 %'))
ref = {}
for m in MODELS + ['POOLED']:
    cells = rows if m == 'POOLED' else [r for r in rows if r['model'] == m]
    v1 = []; u1 = 0; v2 = []; u2 = 0
    for samp in cluster_boot_indices(cells, B, seed=20260731):
        n = len(samp)
        net = sum(r['gift_correct'] for r in samp) - sum(r['or_correct'] for r in samp)
        d = 100.0 * net / n
        diffs = [(r['gift_latency_ms'] - r['or_latency_ms']) / 1000.0 for r in samp]
        md = median(diffs)
        if md <= 0: u1 += 1
        else: v1.append(d / md)
        if net <= 0: u2 += 1
        else: v2.append(sum(diffs) / net)
    p1 = pt[m]['dpp'] / pt[m]['md']
    p2 = (pt[m]['tot_extra'] / pt[m]['net']) if pt[m]['net'] > 0 else float('nan')
    ci1 = (quant(v1, .025), quant(v1, .975)); ci2 = (quant(v2, .025), quant(v2, .975))
    ref[m] = dict(pp_per_s=p1, pp_per_s_ci=list(ci1), undef1=100.0 * u1 / B,
                  s_per_corr=p2, s_per_corr_ci=list(ci2), pct_net_le0=100.0 * u2 / B)
    print('%-24s %+10.4f  [%+8.4f, %+8.4f] %9.2f%% | %10.1f [%9.1f,%9.1f] %9.2f%%' %
          (m, p1, ci1[0], ci1[1], 100.0 * u1 / B, p2, ci2[0], ci2[1], 100.0 * u2 / B))

json.dump(dict(point=pt, ratios=ref), open(BASE + 'ca_ref_lat_01_out.json', 'w'), indent=1)

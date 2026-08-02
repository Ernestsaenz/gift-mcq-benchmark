#!/usr/bin/env python
"""What is the GIFT 'extra latency' actually made of? If a large per-item component is
shared across models (retrieval), then charging it four times in the POOLED ratio, and
treating it as a per-model marginal cost, is wrong."""
import json, math, random
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
rows = [r for r in json.load(open(BASE + 'cross_arm_A.json')) if r['analysis_include']]
MODELS = sorted(set(r['model'] for r in rows))
by = defaultdict(dict)
for r in rows:
    by[r['model']][r['question_id']] = r
items = sorted(set(r['question_id'] for r in rows))


def median(xs):
    s = sorted(xs); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def pearson(x, y):
    n = len(x); mx = sum(x) / n; my = sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    return num / den if den else float('nan')


def rank(v):
    idx = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and v[idx[j + 1]] == v[idx[i]]: j += 1
        for k in range(i, j + 1): r[idx[k]] = (i + j) / 2.0 + 1
        i = j + 1
    return r


def spearman(x, y):
    return pearson(rank(x), rank(y))


print('=== GIFT per-item latency: how correlated across models? (Pearson / Spearman) ===')
print('%-26s %-26s %8s %8s' % ('model A', 'model B', 'pearson', 'spearman'))
for i in range(len(MODELS)):
    for j in range(i + 1, len(MODELS)):
        a, b = MODELS[i], MODELS[j]
        xs = [by[a][q]['gift_latency_ms'] / 1000.0 for q in items]
        ys = [by[b][q]['gift_latency_ms'] / 1000.0 for q in items]
        print('%-26s %-26s %8.3f %8.3f' % (a, b, pearson(xs, ys), spearman(xs, ys)))

print('\n=== same for OpenRouter (control: no shared retrieval step) ===')
for i in range(len(MODELS)):
    for j in range(i + 1, len(MODELS)):
        a, b = MODELS[i], MODELS[j]
        xs = [by[a][q]['or_latency_ms'] / 1000.0 for q in items]
        ys = [by[b][q]['or_latency_ms'] / 1000.0 for q in items]
        print('%-26s %-26s %8.3f %8.3f' % (a, b, pearson(xs, ys), spearman(xs, ys)))

print('\n=== GIFT latency decomposition: per-model median, and the item-level floor ===')
print('%-26s %10s %10s %10s %10s' % ('model', 'medGIFT_s', 'medOR_s', 'medExtra_s', 'medTok'))
for m in MODELS:
    v = [by[m][q] for q in items]
    print('%-26s %10.2f %10.2f %10.2f %10.0f' %
          (m, median([r['gift_latency_ms'] / 1000 for r in v]),
           median([r['or_latency_ms'] / 1000 for r in v]),
           median([(r['gift_latency_ms'] - r['or_latency_ms']) / 1000 for r in v]),
           median([r['gift_tokens'] for r in v])))
# per item: min GIFT latency across the 4 models = an upper bound on the model-independent floor
floor = [min(by[m][q]['gift_latency_ms'] for m in MODELS) / 1000.0 for q in items]
tot_gift = sum(by[m][q]['gift_latency_ms'] for m in MODELS for q in items) / 1000.0
print('\nmedian across items of min-over-models GIFT latency (shared-floor proxy): %.2f s' % median(floor))
print('total GIFT latency on 1244 cells: %.0f s' % tot_gift)
print('if the min-over-models component were paid ONCE per item, not 4x:')
shared = sum(floor)
print('  shared floor paid 4x  : %.0f s   (%.1f%% of GIFT total)' % (4 * shared, 400.0 * shared / tot_gift))
print('  shared floor paid 1x  : %.0f s' % shared)
print('  de-duplicated GIFT tot: %.0f s' % (tot_gift - 3 * shared))

print('\n=== GIFT latency vs question length (Spearman) and vs GIFT tokens ===')
for m in MODELS:
    v = [by[m][q] for q in items]
    print('%-26s rho(qlen)=%+.3f  rho(gift_tokens)=%+.3f  rho(or_latency)=%+.3f' %
          (m, spearman([r['qlen'] for r in v], [r['gift_latency_ms'] for r in v]),
           spearman([r['gift_tokens'] for r in v], [r['gift_latency_ms'] for r in v]),
           spearman([r['or_latency_ms'] for r in v], [r['gift_latency_ms'] for r in v])))

print('\n=== POOLED s-per-net-correct under the de-duplicated accounting ===')
extra_tot = sum((by[m][q]['gift_latency_ms'] - by[m][q]['or_latency_ms']) for m in MODELS for q in items) / 1000.0
net = sum(by[m][q]['gift_correct'] - by[m][q]['or_correct'] for m in MODELS for q in items)
or_tot = sum(by[m][q]['or_latency_ms'] for m in MODELS for q in items) / 1000.0
print('as reported          : extra=%.0f s  net=%d  -> %.0f s per net correct' % (extra_tot, net, extra_tot / net))
dedup_extra = (tot_gift - 3 * shared) - or_tot
print('shared floor once    : extra=%.0f s  net=%d  -> %.0f s per net correct' % (dedup_extra, net, dedup_extra / net))

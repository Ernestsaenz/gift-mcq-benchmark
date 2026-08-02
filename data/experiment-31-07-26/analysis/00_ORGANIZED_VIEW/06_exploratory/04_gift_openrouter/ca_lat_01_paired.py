#!/usr/bin/env python
"""ca_lat_01: paired latency GIFT vs OpenRouter, condition A, analysis_include cells.

Methods (all hand-rolled, stdlib only):
  * median ratio r_i = gift_latency_ms / or_latency_ms, paired within cell
  * CI: cluster bootstrap (resample the 183 question clusters with replacement, B=20000,
    percentile interval) -- clusters are the unit of independence in this design
  * paired sign test: exact two-sided binomial on #(gift>or)
  * accuracy-per-second: net extra correct answers / total extra latency seconds
"""
import json, random, math
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
rows = [r for r in json.load(open(BASE + 'cross_arm_A.json')) if r['analysis_include']]

MODELS = sorted(set(r['model'] for r in rows))
print('cells', len(rows), 'items', len(set(r['question_id'] for r in rows)),
      'clusters', len(set(r['cluster'] for r in rows)), 'models', len(MODELS))
assert all(r['gift_latency_ms'] is not None and r['or_latency_ms'] is not None for r in rows), 'missing latency'


def median(xs):
    s = sorted(xs); n = len(s)
    if n == 0: return float('nan')
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def quant(xs, p):
    s = sorted(xs); n = len(s)
    if n == 1: return float(s[0])
    h = (n - 1) * p
    lo = int(math.floor(h)); hi = min(lo + 1, n - 1)
    return s[lo] + (h - lo) * (s[hi] - s[lo])


def logC(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def binom_two_sided(k, n, p=0.5):
    """exact two-sided binomial p-value, method of small probabilities"""
    pk = math.exp(logC(n, k) + k * math.log(p) + (n - k) * math.log(1 - p))
    tot = 0.0
    for i in range(n + 1):
        pi = math.exp(logC(n, i) + i * math.log(p) + (n - i) * math.log(1 - p))
        if pi <= pk * (1 + 1e-9):
            tot += pi
    return min(1.0, tot)


def cluster_boot_ci(cells, stat_fn, B=20000, seed=20260731, alpha=0.05):
    """cells: list of dicts with 'cluster'. Resample clusters with replacement."""
    byc = defaultdict(list)
    for r in cells:
        byc[r['cluster']].append(r)
    keys = list(byc.keys())
    rng = random.Random(seed)
    K = len(keys)
    reps = []
    for _ in range(B):
        samp = []
        for _ in range(K):
            samp.extend(byc[keys[rng.randrange(K)]])
        reps.append(stat_fn(samp))
    reps.sort()
    return quant(reps, alpha / 2), quant(reps, 1 - alpha / 2), reps


def med_ratio(cells):
    return median([r['gift_latency_ms'] / r['or_latency_ms'] for r in cells])


def med_diff_s(cells):
    return median([(r['gift_latency_ms'] - r['or_latency_ms']) / 1000.0 for r in cells])


def acc_delta_pp(cells):
    g = sum(r['gift_correct'] for r in cells) / len(cells)
    o = sum(r['or_correct'] for r in cells) / len(cells)
    return 100.0 * (g - o)


def sec_per_extra_correct(cells):
    """total extra GIFT latency (s) divided by NET extra correct answers"""
    extra = sum(r['gift_latency_ms'] - r['or_latency_ms'] for r in cells) / 1000.0
    net = sum(r['gift_correct'] for r in cells) - sum(r['or_correct'] for r in cells)
    return extra / net if net != 0 else float('nan')


results = {}
print('\n%-24s %5s %8s %8s %8s %8s %8s %7s %7s' % ('model', 'n', 'medGIFT', 'medOR', 'ratio', 'p25r', 'p75r', 'g>o', 'p_sign'))
for m in MODELS + ['POOLED']:
    cells = rows if m == 'POOLED' else [r for r in rows if r['model'] == m]
    g = [r['gift_latency_ms'] / 1000.0 for r in cells]
    o = [r['or_latency_ms'] / 1000.0 for r in cells]
    ratios = [r['gift_latency_ms'] / r['or_latency_ms'] for r in cells]
    nb = sum(1 for x in ratios if x > 1)
    n = len(cells)
    p_sign = binom_two_sided(nb, n)
    lo, hi, _ = cluster_boot_ci(cells, med_ratio)
    dlo, dhi, _ = cluster_boot_ci(cells, med_diff_s)
    res = dict(
        n=n,
        med_gift_s=median(g), med_or_s=median(o),
        mean_gift_s=sum(g) / n, mean_or_s=sum(o) / n,
        p90_gift_s=quant(g, .9), p90_or_s=quant(o, .9),
        max_gift_s=max(g), max_or_s=max(o),
        med_ratio=median(ratios), ratio_ci=[lo, hi],
        p25_ratio=quant(ratios, .25), p75_ratio=quant(ratios, .75),
        n_gift_slower=nb, p_sign_exact=p_sign,
        med_diff_s=median([a - b for a, b in zip(g, o)]), diff_ci_s=[dlo, dhi],
        total_gift_s=sum(g), total_or_s=sum(o), total_extra_s=sum(g) - sum(o),
        gift_correct=sum(r['gift_correct'] for r in cells),
        or_correct=sum(r['or_correct'] for r in cells),
        acc_gift=100.0 * sum(r['gift_correct'] for r in cells) / n,
        acc_or=100.0 * sum(r['or_correct'] for r in cells) / n,
        acc_delta_pp=acc_delta_pp(cells),
        net_extra_correct=sum(r['gift_correct'] for r in cells) - sum(r['or_correct'] for r in cells),
        disc_gift_only=sum(1 for r in cells if r['gift_correct'] and not r['or_correct']),
        disc_or_only=sum(1 for r in cells if r['or_correct'] and not r['gift_correct']),
        med_gift_tokens=median([r['gift_tokens'] for r in cells if r['gift_tokens'] is not None]),
        med_or_tokens=median([r['or_tokens'] for r in cells if r['or_tokens'] is not None]),
        sum_gift_tokens=sum(r['gift_tokens'] or 0 for r in cells),
        sum_or_tokens=sum(r['or_tokens'] or 0 for r in cells),
    )
    res['sec_per_extra_correct'] = sec_per_extra_correct(cells)
    res['pp_per_extra_sec_per_item'] = (res['acc_delta_pp'] / res['med_diff_s']) if res['med_diff_s'] else float('nan')
    results[m] = res
    print('%-24s %5d %8.2f %8.2f %8.3f %8.2f %8.2f %4d/%d %8.3g  ratioCI[%.2f,%.2f]'
          % (m, n, res['med_gift_s'], res['med_or_s'], res['med_ratio'],
             res['p25_ratio'], res['p75_ratio'], nb, n, p_sign, lo, hi))

print('\n%-24s %9s %9s %8s %8s %9s %10s' % ('model', 'accGIFT', 'accOR', 'dpp', 'netcorr', 'extra_s', 's/extracorr'))
for m in MODELS + ['POOLED']:
    r = results[m]
    print('%-24s %8.2f%% %8.2f%% %+7.2f %8d %9.0f %10s'
          % (m, r['acc_gift'], r['acc_or'], r['acc_delta_pp'], r['net_extra_correct'],
             r['total_extra_s'],
             ('%.0f' % r['sec_per_extra_correct']) if r['net_extra_correct'] > 0 else 'n/a(<=0)'))

print('\n%-24s %8s %8s %8s %8s %10s %10s' % ('model', 'medGtok', 'medOtok', 'sumGtok', 'sumOtok', 'medDiff_s', 'diffCI'))
for m in MODELS + ['POOLED']:
    r = results[m]
    print('%-24s %8.0f %8.0f %8d %8d %10.2f  [%.2f,%.2f]'
          % (m, r['med_gift_tokens'], r['med_or_tokens'], r['sum_gift_tokens'], r['sum_or_tokens'],
             r['med_diff_s'], r['diff_ci_s'][0], r['diff_ci_s'][1]))

json.dump(results, open(BASE + 'ca_lat_01_paired.json', 'w'), indent=1)

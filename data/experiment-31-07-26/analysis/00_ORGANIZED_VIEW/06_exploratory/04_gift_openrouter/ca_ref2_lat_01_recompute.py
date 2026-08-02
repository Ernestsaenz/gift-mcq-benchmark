#!/usr/bin/env python
"""ca_ref2_lat_01: independent recompute of the two latency-cost ratio statistics.

Recomputes on the CANONICAL v2 export (306 items / 1224 cells / 178 clusters) and on the
SUPERSEDED v1 subset (311 / 1244 / 183) that the claim used, so the two can be compared.

Method: cluster bootstrap over clusters, B=20000, percentile CIs. Own RNG (seed 20260731),
independent of ca_lat_02_ratio_ci.py.
"""
import json, math, random
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
ALL = json.load(open(BASE + 'cross_arm_A.json'))
META = json.load(open(BASE + 'dataset_meta.json'))

# the 8 items that v2 added to the exclusion list; un-excluding them reconstructs v1
V1_EXTRA = set('b213 b293 b361 b396 b407 b433 b445 b451'.split())

V2 = [r for r in ALL if r['analysis_include']]
V1 = [r for r in ALL if r['analysis_include'] or r['question_id'] in V1_EXTRA]

MODELS = sorted(set(r['model'] for r in V2))


def median(xs):
    s = sorted(xs); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def quant(xs, p):
    s = sorted(xs); n = len(s)
    if n == 1: return float(s[0])
    h = (n - 1) * p; lo = int(math.floor(h)); hi = min(lo + 1, n - 1)
    return s[lo] + (h - lo) * (s[hi] - s[lo])


def dpp(cells):
    n = len(cells)
    return 100.0 * (sum(r['gift_correct'] for r in cells) - sum(r['or_correct'] for r in cells)) / n


def med_diff_s(cells):
    return median([(r['gift_latency_ms'] - r['or_latency_ms']) / 1000.0 for r in cells])


def mean_diff_s(cells):
    return sum((r['gift_latency_ms'] - r['or_latency_ms']) / 1000.0 for r in cells) / len(cells)


def pp_per_s_med(cells):
    md = med_diff_s(cells)
    if md <= 0: return None
    return dpp(cells) / md


def pp_per_s_mean(cells):
    md = mean_diff_s(cells)
    if md <= 0: return None
    return dpp(cells) / md


def net(cells):
    return sum(r['gift_correct'] for r in cells) - sum(r['or_correct'] for r in cells)


def extra_s(cells):
    return sum(r['gift_latency_ms'] - r['or_latency_ms'] for r in cells) / 1000.0


def sec_per_correct(cells):
    nt = net(cells)
    if nt <= 0: return None          # UNDEFINED -> should rank at +inf, not be dropped
    return extra_s(cells) / nt


def boot_vals(cells, fn, B=20000, seed=20260731):
    byc = defaultdict(list)
    for r in cells: byc[r['cluster']].append(r)
    keys = list(byc); K = len(keys); rng = random.Random(seed)
    vals = []; undef = 0
    for _ in range(B):
        samp = []
        for _ in range(K):
            samp.extend(byc[keys[rng.randrange(K)]])
        v = fn(samp)
        if v is None: undef += 1
        else: vals.append(v)
    return vals, undef, B


def pct_ci(vals, undef, B, undef_at_top=False):
    """Percentile CI. If undef_at_top, the `undef` replicates are treated as +inf and
    occupy the top of the ordering (the honest treatment for a ratio whose denominator
    crossed zero from above), so the ordering is over all B replicates."""
    if not vals: return (float('nan'), float('nan'))
    if not undef_at_top:
        return (quant(vals, .025), quant(vals, .975))
    s = sorted(vals)
    lo_i = 0.025 * (B - 1)
    hi_i = 0.975 * (B - 1)
    def at(i):
        if i >= len(s) - 1e-9: return float('inf')
        lo = int(math.floor(i)); hi = min(lo + 1, len(s) - 1)
        if lo >= len(s): return float('inf')
        return s[lo] + (i - lo) * (s[hi] - s[lo])
    return (at(lo_i), at(hi_i))


def run(rows, tag):
    print('\n' + '=' * 92)
    print('%s : %d cells, %d items, %d clusters' %
          (tag, len(rows), len(set(r['question_id'] for r in rows)),
           len(set(r['cluster'] for r in rows))))
    print('=' * 92)
    res = {}
    hdr = '%-24s %6s %7s %8s %9s %9s %22s'
    print(hdr % ('model', 'n', 'net', 'dpp', 'medDif_s', 'pp_per_s', '95% CI (cluster boot)'))
    for m in MODELS + ['POOLED']:
        cells = rows if m == 'POOLED' else [r for r in rows if r['model'] == m]
        d = dpp(cells); md = med_diff_s(cells); mn = mean_diff_s(cells)
        vals, undef, B = boot_vals(cells, pp_per_s_med)
        ci = pct_ci(vals, undef, B)
        vals2, u2, _ = boot_vals(cells, pp_per_s_mean)
        ci2 = pct_ci(vals2, u2, B)
        print(hdr % (m, len(cells), '%+d' % net(cells), '%+.3f' % d, '%.3f' % md,
                     '%+.4f' % (d / md), '[%+.4f, %+.4f]' % ci))
        print('%-24s %6s %7s %8s %9s %9s %22s   (MEAN denom, mean=%.3f s)' %
              ('', '', '', '', '%.3f' % mn, '%+.4f' % (d / mn),
               '[%+.4f, %+.4f]' % ci2, mn))
        res[m] = dict(n=len(cells), net=net(cells), dpp=d, med_diff_s=md, mean_diff_s=mn,
                      pp_per_s_med=d / md, ci_med=list(ci),
                      pp_per_s_mean=d / mn, ci_mean=list(ci2),
                      undef_med=undef / B)
    print('\n%-24s %8s %11s %26s %26s %10s' %
          ('model', 'net', 'point_s', '95% CI (drop undefined)', '95% CI (undef ranked +inf)', 'frac_undef'))
    for m in MODELS + ['POOLED']:
        cells = rows if m == 'POOLED' else [r for r in rows if r['model'] == m]
        pt = sec_per_correct(cells)
        vals, undef, B = boot_vals(cells, sec_per_correct)
        ci_drop = pct_ci(vals, undef, B, False)
        ci_inf = pct_ci(vals, undef, B, True)
        f = '%.0f' % pt if pt else 'undefined'
        print('%-24s %8d %11s   [%9.0f,%9.0f]     [%9.0f,%9s]  %9.2f%%' %
              (m, net(cells), f, ci_drop[0], ci_drop[1], ci_inf[0],
               ('inf' if math.isinf(ci_inf[1]) else '%.0f' % ci_inf[1]), 100.0 * undef / B))
        res[m].update(sec_per_correct=pt, ci_drop=list(ci_drop),
                      ci_inf=[ci_inf[0], None if math.isinf(ci_inf[1]) else ci_inf[1]],
                      frac_undef=undef / B)
    return res


out = {'v2_canonical': run(V2, 'v2 CANONICAL export'),
       'v1_superseded': run(V1, 'v1 SUPERSEDED export (what the claim used)')}

# ---- is the sign of pp_per_s ever anything but the sign of dpp? ----
print('\n' + '=' * 92)
print('TAUTOLOGY CHECK: does the median paired latency difference ever go <= 0?')
print('=' * 92)
for m in MODELS + ['POOLED']:
    cells = V2 if m == 'POOLED' else [r for r in V2 if r['model'] == m]
    vals, undef, B = boot_vals(cells, med_diff_s)
    print('%-24s med_diff_s point %8.3f  boot range [%.3f, %.3f]  reps with med<=0: %d/%d' %
          (m, med_diff_s(cells), min(vals), max(vals), undef, B))
    # fraction of cells where GIFT is faster than OR
    fr = sum(1 for r in cells if r['gift_latency_ms'] < r['or_latency_ms']) / len(cells)
    print('%-24s   per-cell: GIFT faster than OR on %.1f%% of cells' % ('', 100 * fr))

json.dump(out, open(BASE + 'ca_ref2_lat_01_out.json', 'w'), indent=1)
print('\nwrote ca_ref2_lat_01_out.json')

#!/usr/bin/env python
"""ca_ref3_lat_01 -- independent recomputation of the "latency-cost" ratio claim.

Own bootstrap implementation, own seed, own quantile function. Recomputes:
  R1 = (accuracy delta in pp) / (median paired latency difference, s)
  R2 = (total extra latency, s) / (net extra correct answers)
plus: mean-denominator variant, denominator-stability decomposition, sign-tautology check,
and the fraction of bootstrap replicates that are undefined for EACH statistic.
"""
import json, math, random
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
ALL = json.load(open(BASE + 'cross_arm_A.json'))
rows = [r for r in ALL if r['analysis_include']]
MODELS = sorted(set(r['model'] for r in rows))
B = 20000
SEED = 20260731          # deliberately different from ca_lat_02's 7761

print('=== EXPORT ACTUALLY ON DISK ===')
print('rows in file          : %d' % len(ALL))
print('analysis_include      : %d cells' % len(rows))
print('items                 : %d' % len(set(r['question_id'] for r in rows)))
print('clusters              : %d' % len(set(r['cluster'] for r in rows)))
print('(task brief said 1244 cells / 311 items / 183 clusters = RUN_STATUS v1, SUPERSEDED)')


def quant(xs, p):
    s = sorted(xs); n = len(s)
    if n == 0: return float('nan')
    if n == 1: return float(s[0])
    h = (n - 1) * p; lo = int(math.floor(h)); hi = min(lo + 1, n - 1)
    return s[lo] + (h - lo) * (s[hi] - s[lo])


def median(xs):
    s = sorted(xs); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def cells_for(m):
    return rows if m == 'POOLED' else [r for r in rows if r['model'] == m]


# ---------------------------------------------------------------- point estimates
print('\n=== POINT ESTIMATES (v2 export on disk) ===')
print('%-24s %5s %6s %6s %5s %5s %8s %9s %9s' %
      ('model', 'n', 'GIFT%', 'OR%', 'g_win', 'o_win', 'net', 'medDiff_s', 'meanDiff_s'))
pt = {}
for m in MODELS + ['POOLED']:
    c = cells_for(m); n = len(c)
    g = sum(r['gift_correct'] for r in c); o = sum(r['or_correct'] for r in c)
    gw = sum(1 for r in c if r['gift_correct'] and not r['or_correct'])
    ow = sum(1 for r in c if r['or_correct'] and not r['gift_correct'])
    dl = [(r['gift_latency_ms'] - r['or_latency_ms']) / 1000.0 for r in c]
    md = median(dl); mn = sum(dl) / n
    dpp = 100.0 * (g - o) / n
    pt[m] = dict(n=n, gacc=100.0 * g / n, oacc=100.0 * o / n, gw=gw, ow=ow, net=g - o,
                 dpp=dpp, med=md, mean=mn,
                 r1_med=dpp / md, r1_mean=dpp / mn,
                 extra_s=sum(dl),
                 r2=(sum(dl) / (g - o)) if (g - o) > 0 else None)
    print('%-24s %5d %6.2f %6.2f %5d %5d %8d %9.3f %9.3f' %
          (m, n, pt[m]['gacc'], pt[m]['oacc'], gw, ow, g - o, md, mn))


# ---------------------------------------------------------------- bootstrap
def boot_stats(cells, seed):
    """One pass; returns lists of replicate values for every statistic at once."""
    byc = defaultdict(list)
    for r in cells:
        byc[r['cluster']].append(r)
    keys = list(byc); K = len(keys); rng = random.Random(seed)
    out = dict(r1_med=[], r1_mean=[], r2=[], md=[], mn=[], dpp=[],
               n_md_le0=0, n_net_le0=0, n_mean_le0=0, sign_mismatch=0)
    for _ in range(B):
        samp = []
        for _ in range(K):
            samp.extend(byc[keys[rng.randrange(K)]])
        n = len(samp)
        g = 0; o = 0; s = 0.0; dl = []
        for r in samp:
            g += r['gift_correct']; o += r['or_correct']
            d = (r['gift_latency_ms'] - r['or_latency_ms']) / 1000.0
            s += d; dl.append(d)
        net = g - o
        dpp = 100.0 * net / n
        md = median(dl); mn = s / n
        out['dpp'].append(dpp); out['md'].append(md); out['mn'].append(mn)
        if md <= 0:
            out['n_md_le0'] += 1
        else:
            v = dpp / md
            out['r1_med'].append(v)
            if (v > 0) != (dpp > 0) and dpp != 0:
                out['sign_mismatch'] += 1
        if mn <= 0:
            out['n_mean_le0'] += 1
        else:
            out['r1_mean'].append(dpp / mn)
        if net <= 0:
            out['n_net_le0'] += 1
        else:
            out['r2'].append(s / net)
    return out


print('\n=== R1: pp of accuracy per extra SECOND (denominator = MEDIAN paired latency diff) ===')
print('%-24s %9s %26s %14s' % ('model', 'point', '95% pctl CI (B=20000)', 'reps md<=0'))
res = {}
for m in MODELS + ['POOLED']:
    c = cells_for(m)
    bs = boot_stats(c, SEED + hash(m) % 1000)
    res[m] = bs
    lo, hi = quant(bs['r1_med'], .025), quant(bs['r1_med'], .975)
    print('%-24s %+9.4f   [%+8.4f, %+8.4f] %13.2f%%' %
          (m, pt[m]['r1_med'], lo, hi, 100.0 * bs['n_md_le0'] / B))
    pt[m]['ci_r1_med'] = [lo, hi]

print('\n=== R1 SENSITIVITY: same statistic with denominator = MEAN paired latency diff ===')
print('%-24s %9s %26s %10s' % ('model', 'point', '95% pctl CI', 'shift'))
for m in MODELS + ['POOLED']:
    bs = res[m]
    lo, hi = quant(bs['r1_mean'], .025), quant(bs['r1_mean'], .975)
    a, b_ = pt[m]['r1_med'], pt[m]['r1_mean']
    print('%-24s %+9.4f   [%+8.4f, %+8.4f] %+9.1f%%' %
          (m, b_, lo, hi, 100.0 * (b_ - a) / abs(a) if a else float('nan')))
    pt[m]['ci_r1_mean'] = [lo, hi]

print('\n=== R2: seconds of extra latency per NET extra correct answer ===')
print('%-24s %9s %28s %14s' % ('model', 'point_s', '95% pctl CI (defined reps)', 'reps net<=0'))
for m in MODELS + ['POOLED']:
    bs = res[m]
    lo, hi = quant(bs['r2'], .025), quant(bs['r2'], .975)
    p = pt[m]['r2']
    print('%-24s %9s   [%9.0f, %9.0f] %13.2f%%' %
          (m, ('%.0f' % p) if p else 'UNDEF', lo, hi, 100.0 * bs['n_net_le0'] / B))
    pt[m]['ci_r2'] = [lo, hi]
    pt[m]['pct_net_le0'] = 100.0 * bs['n_net_le0'] / B

# ------------------------------------------------- where does R1's uncertainty come from?
print('\n=== DECOMPOSITION: is R1 anything more than the accuracy delta rescaled? ===')
print('%-24s %12s %12s %12s %12s %12s' %
      ('model', 'CV(dpp)', 'CV(medDiff)', 'CV(R1)', 'dpp CI(pp)', 'R1CI/den_pt'))
for m in MODELS + ['POOLED']:
    bs = res[m]
    def cv(v):
        mu = sum(v) / len(v)
        sd = math.sqrt(sum((x - mu) ** 2 for x in v) / (len(v) - 1))
        return sd / abs(mu) if mu else float('nan')
    dlo, dhi = quant(bs['dpp'], .025), quant(bs['dpp'], .975)
    den = pt[m]['med']
    print('%-24s %12.4f %12.4f %12.4f  [%+.2f,%+.2f]  [%+.4f,%+.4f]' %
          (m, cv(bs['dpp']), cv(bs['md']), cv(bs['r1_med']), dlo, dhi, dlo / den, dhi / den))
    pt[m]['ci_dpp'] = [dlo, dhi]

# ------------------------------------------------- sign tautology
print('\n=== SIGN TAUTOLOGY CHECK ===')
tot_mis = sum(res[m]['sign_mismatch'] for m in MODELS + ['POOLED'])
tot_md0 = sum(res[m]['n_md_le0'] for m in MODELS + ['POOLED'])
print('median paired latency diff > 0 in the point estimate for ALL 4 models: %s'
      % all(pt[m]['med'] > 0 for m in MODELS))
print('bootstrap replicates (5 x 20000 = 100000) with median latency diff <= 0 : %d' % tot_md0)
print('replicates where sign(R1) != sign(accuracy delta)                      : %d' % tot_mis)
print('=> R1 > 0  <=>  GIFT more accurate.  The "positive only where GIFT wins"')
print('   statement is an algebraic identity, not an empirical finding.')

json.dump({m: pt[m] for m in MODELS + ['POOLED']},
          open(BASE + 'ca_ref3_lat_01_out.json', 'w'), indent=1)

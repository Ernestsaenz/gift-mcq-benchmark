#!/usr/bin/env python
"""ca_lat_02: cluster-bootstrap CIs for the cost-effectiveness ratios, plus totals,
plus latency-vs-outcome decomposition, plus a drift check on the GIFT prefix."""
import json, random, math, sqlite3, datetime as dt
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
rows = [r for r in json.load(open(BASE + 'cross_arm_A.json')) if r['analysis_include']]
MODELS = sorted(set(r['model'] for r in rows))


def quant(xs, p):
    s = sorted(xs); n = len(s)
    if n == 1: return float(s[0])
    h = (n - 1) * p; lo = int(math.floor(h)); hi = min(lo + 1, n - 1)
    return s[lo] + (h - lo) * (s[hi] - s[lo])


def median(xs):
    s = sorted(xs); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def clusters_of(cells):
    byc = defaultdict(list)
    for r in cells:
        byc[r['cluster']].append(r)
    return byc


def boot(cells, fn, B=20000, seed=7761):
    byc = clusters_of(cells); keys = list(byc); K = len(keys); rng = random.Random(seed)
    vals = []; nan = 0
    for _ in range(B):
        samp = []
        for _ in range(K):
            samp.extend(byc[keys[rng.randrange(K)]])
        v = fn(samp)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            nan += 1
        else:
            vals.append(v)
    return vals, nan


out = {}
print('=== TOTAL LATENCY BUDGET on the analysed cells (n=1244) ===')
print('%-24s %10s %10s %10s %8s' % ('model', 'GIFT_tot_h', 'OR_tot_h', 'extra_h', 'x_total'))
for m in MODELS + ['POOLED']:
    cells = rows if m == 'POOLED' else [r for r in rows if r['model'] == m]
    G = sum(r['gift_latency_ms'] for r in cells) / 3.6e6
    O = sum(r['or_latency_ms'] for r in cells) / 3.6e6
    print('%-24s %10.3f %10.3f %10.3f %8.2f' % (m, G, O, G - O, G / O))
    out.setdefault(m, {}).update(gift_tot_h=G, or_tot_h=O, extra_h=G - O, x_total=G / O)

print('\n=== SECONDS OF EXTRA LATENCY PER NET EXTRA CORRECT ANSWER (cluster bootstrap, B=20000) ===')
print('%-24s %10s %10s %26s %10s' % ('model', 'net+', 'point_s', '95% CI (percentile)', 'pct_reps_net<=0'))


def secs_per_correct(cells):
    extra = sum(r['gift_latency_ms'] - r['or_latency_ms'] for r in cells) / 1000.0
    net = sum(r['gift_correct'] for r in cells) - sum(r['or_correct'] for r in cells)
    if net <= 0:
        return None
    return extra / net


for m in MODELS + ['POOLED']:
    cells = rows if m == 'POOLED' else [r for r in rows if r['model'] == m]
    net = sum(r['gift_correct'] for r in cells) - sum(r['or_correct'] for r in cells)
    pt = secs_per_correct(cells)
    vals, nan = boot(cells, secs_per_correct)
    frac_bad = nan / 20000.0
    ci = (quant(vals, .025), quant(vals, .975)) if vals else (float('nan'),) * 2
    print('%-24s %10d %10s   [%9.0f, %9.0f] %10.1f%%'
          % (m, net, ('%.0f' % pt) if pt else 'n/a', ci[0], ci[1], 100 * frac_bad))
    out.setdefault(m, {}).update(net_extra_correct=net, sec_per_extra_correct=pt,
                                 sec_per_correct_ci=list(ci), pct_reps_net_le0=100 * frac_bad)

print('\n=== ACCURACY GAINED PER EXTRA SECOND (pp per second of extra median latency) ===')
print('%-24s %10s %10s %10s %24s' % ('model', 'dpp', 'medDiff_s', 'pp_per_s', '95% CI on pp_per_s'))


def pp_per_s(cells):
    n = len(cells)
    d = 100.0 * (sum(r['gift_correct'] for r in cells) - sum(r['or_correct'] for r in cells)) / n
    md = median([(r['gift_latency_ms'] - r['or_latency_ms']) / 1000.0 for r in cells])
    if md <= 0:
        return None
    return d / md


for m in MODELS + ['POOLED']:
    cells = rows if m == 'POOLED' else [r for r in rows if r['model'] == m]
    n = len(cells)
    d = 100.0 * (sum(r['gift_correct'] for r in cells) - sum(r['or_correct'] for r in cells)) / n
    md = median([(r['gift_latency_ms'] - r['or_latency_ms']) / 1000.0 for r in cells])
    vals, nan = boot(cells, pp_per_s)
    ci = (quant(vals, .025), quant(vals, .975))
    print('%-24s %+10.2f %10.2f %+10.4f   [%+.4f, %+.4f]' % (m, d, md, d / md, ci[0], ci[1]))
    out.setdefault(m, {}).update(dpp=d, med_diff_s=md, pp_per_s=d / md, pp_per_s_ci=list(ci))

print('\n=== IS GIFT SLOW *BECAUSE* IT IS DOING SOMETHING USEFUL? latency by outcome pattern ===')
print('%-24s %8s %10s %10s %10s %10s' % ('model', 'pattern', 'n', 'medGIFT_s', 'medOR_s', 'medRatio'))
for m in MODELS + ['POOLED']:
    cells = rows if m == 'POOLED' else [r for r in rows if r['model'] == m]
    pats = {'both_ok': lambda r: r['gift_correct'] and r['or_correct'],
            'gift_win': lambda r: r['gift_correct'] and not r['or_correct'],
            'or_win': lambda r: r['or_correct'] and not r['gift_correct'],
            'both_bad': lambda r: not r['gift_correct'] and not r['or_correct']}
    for name, f in pats.items():
        sub = [r for r in cells if f(r)]
        if not sub:
            print('%-24s %8s %10d %10s %10s %10s' % (m, name, 0, '-', '-', '-')); continue
        print('%-24s %8s %10d %10.2f %10.2f %10.2f'
              % (m, name, len(sub),
                 median([r['gift_latency_ms'] / 1000 for r in sub]),
                 median([r['or_latency_ms'] / 1000 for r in sub]),
                 median([r['gift_latency_ms'] / r['or_latency_ms'] for r in sub])))

# ---- drift check: does GIFT latency degrade along the sequential prefix? ----
print('\n=== DRIFT: GIFT per-attempt latency across the 8h45m run (successful attempts only) ===')
DB = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite'
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)
att = list(c.execute('''select pa.created_at, pa.latency_ms, lc.model, pa.status_code
                        from provider_attempts pa join logical_calls lc on lc.id=pa.logical_call_id
                        join experiments e on e.id=lc.experiment_id
                        where e.name='expA_gift_310726' order by pa.created_at'''))
ok = [a for a in att if a[3] == 200]
t0 = dt.datetime.fromisoformat(ok[0][0])
elapsed = [( (dt.datetime.fromisoformat(a[0]) - t0).total_seconds()/3600.0, a[1]/1000.0) for a in ok]
nb = 8
per = len(elapsed) // nb
print('%6s %6s %10s %10s %10s' % ('bin', 'n', 'hrs_mid', 'medLat_s', 'meanLat_s'))
binmeds = []
for i in range(nb):
    seg = elapsed[i*per:(i+1)*per] if i < nb-1 else elapsed[i*per:]
    med = median([x[1] for x in seg]); binmeds.append(med)
    print('%6d %6d %10.2f %10.2f %10.2f' % (i+1, len(seg), median([x[0] for x in seg]), med,
                                            sum(x[1] for x in seg)/len(seg)))
# Spearman rho between elapsed hours and latency, permutation p
def rank(v):
    idx = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0]*len(v); i = 0
    while i < len(idx):
        j = i
        while j+1 < len(idx) and v[idx[j+1]] == v[idx[i]]: j += 1
        avg = (i+j)/2.0 + 1
        for k in range(i, j+1): r[idx[k]] = avg
        i = j+1
    return r
X = [x[0] for x in elapsed]; Y = [x[1] for x in elapsed]
rx, ry = rank(X), rank(Y)
n = len(rx); mx = sum(rx)/n; my = sum(ry)/n
num = sum((a-mx)*(b-my) for a, b in zip(rx, ry))
den = math.sqrt(sum((a-mx)**2 for a in rx) * sum((b-my)**2 for b in ry))
rho = num/den
rng = random.Random(99); cnt = 0; NP = 10000
sh = list(ry)
for _ in range(NP):
    rng.shuffle(sh)
    nu = sum((a-mx)*(b-my) for a, b in zip(rx, sh))
    if abs(nu/den) >= abs(rho): cnt += 1
print('Spearman rho(elapsed_hours, gift_latency) = %.4f  permutation p = %.4g (10k shuffles, two-sided)'
      % (rho, (cnt+1)/(NP+1)))
out['drift'] = dict(rho=rho, perm_p=(cnt+1)/(NP+1), bin_medians=binmeds, n=len(elapsed))

json.dump(out, open(BASE + 'ca_lat_02_ratio_ci.json', 'w'), indent=1)

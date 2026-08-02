#!/usr/bin/env python
"""ca_lat_03: (a) wall-clock throughput & failed-attempt accounting from provider_attempts,
(b) decomposition of the GIFT latency tax into generation time vs fixed retrieval overhead,
(c) coverage-caveat probe: does OpenRouter latency differ on covered vs uncovered items?"""
import sqlite3, json, math, random, datetime as dt
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
DB = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite'
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)
rows = [r for r in json.load(open(BASE + 'cross_arm_A.json')) if r['analysis_include']]
MODELS = sorted(set(r['model'] for r in rows))


def median(xs):
    s = sorted(xs); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def quant(xs, p):
    s = sorted(xs); n = len(s)
    if n == 1: return float(s[0])
    h = (n - 1) * p; lo = int(math.floor(h)); hi = min(lo + 1, n - 1)
    return s[lo] + (h - lo) * (s[hi] - s[lo])


# ---------------- (a) throughput / reliability ----------------
print('=== ARM-LEVEL OPERATIONAL ACCOUNTING (whole run, from provider_attempts) ===')
summary = {}
for exp, label in [('expA_gift_310726', 'GIFT'), ('expA_or_310726', 'OR')]:
    att = list(c.execute('''select pa.created_at, pa.latency_ms, pa.status_code, pa.error_type,
                                   pa.finish_reason, lc.id, lc.model
                            from provider_attempts pa join logical_calls lc on lc.id=pa.logical_call_id
                            join experiments e on e.id=lc.experiment_id where e.name=? order by pa.created_at''', (exp,)))
    times = [dt.datetime.fromisoformat(a[0]) for a in att]
    span = (times[-1] - times[0]).total_seconds()
    bursts = []; start = times[0]; prev = times[0]
    for t in times[1:]:
        if (t - prev).total_seconds() > 300:
            bursts.append((start, prev)); start = t
        prev = t
    bursts.append((start, prev))
    busy = sum((b - a).total_seconds() for a, b in bursts)
    ok = [a for a in att if a[2] == 200]
    bad = [a for a in att if a[2] != 200]
    done_calls = len(set(a[5] for a in ok))
    lat_ok = sum(a[1] for a in ok if a[1]) / 1000.0
    lat_bad = sum(a[1] for a in bad if a[1]) / 1000.0
    d = dict(label=label, attempts=len(att), ok=len(ok), failed=len(bad),
             fail_rate_pct=100.0 * len(bad) / len(att),
             logical_calls=len(set(a[5] for a in att)), completed_calls=done_calls,
             attempts_per_completed=len(att) / done_calls,
             span_h=span / 3600, busy_h=busy / 3600,
             model_time_h=(lat_ok + lat_bad) / 3600,
             effective_concurrency=(lat_ok + lat_bad) / busy,
             wallclock_s_per_completed_cell=busy / done_calls,
             burned_s_on_failures=lat_bad,
             median_ok_latency_s=median([a[1] / 1000 for a in ok if a[1]]),
             )
    summary[label] = d
    print('\n-- %s (%s)' % (label, exp))
    for k, v in d.items():
        if k == 'label': continue
        print('    %-32s %s' % (k, ('%.4g' % v) if isinstance(v, float) else v))
    et = defaultdict(int)
    for a in bad: et['%s/%s' % (a[2], a[3])] += 1
    print('    failure breakdown:', dict(et))

g, o = summary['GIFT'], summary['OR']
print('\nWALL-CLOCK PER COMPLETED CELL:  GIFT %.2f s   OR %.2f s   ratio %.1fx'
      % (g['wallclock_s_per_completed_cell'], o['wallclock_s_per_completed_cell'],
         g['wallclock_s_per_completed_cell'] / o['wallclock_s_per_completed_cell']))
print('EFFECTIVE CONCURRENCY:          GIFT %.2f  OR %.2f' % (g['effective_concurrency'], o['effective_concurrency']))
print('FAILED ATTEMPTS:                GIFT %d (%.1f%%)   OR %d (%.1f%%)'
      % (g['failed'], g['fail_rate_pct'], o['failed'], o['fail_rate_pct']))
print('SECONDS BURNED ON FAILED ATTEMPTS: GIFT %.0f s (%.1f%% of busy time)   OR %.0f s'
      % (g['burned_s_on_failures'], 100 * g['burned_s_on_failures'] / (g['busy_h'] * 3600), o['burned_s_on_failures']))

# projection to a complete GIFT arm
proj_h = g['wallclock_s_per_completed_cell'] * 1896 / 3600
print('PROJECTED wall-clock for a COMPLETE 1896-cell GIFT arm at the observed serial rate: %.2f h'
      % proj_h)
print('PROJECTED failed attempts for the same: %.0f' % (g['failed'] / g['completed_calls'] * 1896))

# cost attributable to the 1244 analysed cells
n_an = len(rows)
gift_wall_an = g['wallclock_s_per_completed_cell'] * n_an
or_wall_an = o['wallclock_s_per_completed_cell'] * n_an
net = sum(r['gift_correct'] for r in rows) - sum(r['or_correct'] for r in rows)
fails_an = g['failed'] / g['completed_calls'] * n_an
print('\n=== PRICE OF THE POOLED +%.2fpp (%d net extra correct answers over %d cells) ==='
      % (100.0 * net / n_an, net, n_an))
print('  GIFT wall-clock attributable to the 1244 analysed cells : %.0f s = %.2f h' % (gift_wall_an, gift_wall_an / 3600))
print('  OR   wall-clock attributable to the same 1244 cells     : %.0f s = %.2f h' % (or_wall_an, or_wall_an / 3600))
print('  extra wall-clock                                        : %.0f s = %.2f h' % (gift_wall_an - or_wall_an, (gift_wall_an - or_wall_an) / 3600))
print('  --> %.0f s = %.1f min of extra WALL-CLOCK per additional correct answer'
      % ((gift_wall_an - or_wall_an) / net, (gift_wall_an - or_wall_an) / net / 60))
print('  --> %.1f failed GIFT attempts per additional correct answer (%.0f failures / %d)'
      % (fails_an / net, fails_an, net))
summary['price'] = dict(gift_wall_an_s=gift_wall_an, or_wall_an_s=or_wall_an,
                        extra_wall_s=gift_wall_an - or_wall_an, net=net,
                        s_per_extra_correct_wall=(gift_wall_an - or_wall_an) / net,
                        fails_per_extra_correct=fails_an / net, proj_full_arm_h=proj_h)

# ---------------- (b) retrieval-overhead decomposition ----------------
print('\n=== DECOMPOSITION: is the GIFT tax generation time or a fixed retrieval overhead? ===')
print('OLS on the OpenRouter arm: or_latency_s = a + b*or_tokens (per model);')
print('then overhead_i = gift_latency_s - (a + b*gift_tokens_i).')
print('%-24s %8s %10s %10s %12s %12s %22s' % ('model', 'a_s', 'b_ms/tok', 'R2', 'medGtok', 'medOtok', 'med overhead_s [95% CI]'))
dec = {}


def ols(x, y):
    n = len(x); mx = sum(x) / n; my = sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    b = sxy / sxx if sxx else 0.0
    a = my - b * mx
    ss_res = sum((yy - (a + b * xx)) ** 2 for xx, yy in zip(x, y))
    ss_tot = sum((yy - my) ** 2 for yy in y)
    return a, b, (1 - ss_res / ss_tot if ss_tot else float('nan'))


for m in MODELS:
    cells = [r for r in rows if r['model'] == m and r['gift_tokens'] is not None and r['or_tokens'] is not None]
    a, b, r2 = ols([r['or_tokens'] for r in cells], [r['or_latency_ms'] / 1000.0 for r in cells])
    ovh = [r['gift_latency_ms'] / 1000.0 - (a + b * r['gift_tokens']) for r in cells]
    # cluster bootstrap CI on median overhead
    byc = defaultdict(list)
    for r, v in zip(cells, ovh): byc[r['cluster']].append(v)
    keys = list(byc); rng = random.Random(31337); reps = []
    for _ in range(5000):
        s = []
        for _ in range(len(keys)): s.extend(byc[keys[rng.randrange(len(keys))]])
        reps.append(median(s))
    ci = (quant(reps, .025), quant(reps, .975))
    print('%-24s %8.2f %10.3f %10.3f %12.0f %12.0f   %6.2f [%.2f, %.2f]'
          % (m, a, b * 1000, r2, median([r['gift_tokens'] for r in cells]),
             median([r['or_tokens'] for r in cells]), median(ovh), ci[0], ci[1]))
    dec[m] = dict(a_s=a, b_s_per_tok=b, r2=r2, med_overhead_s=median(ovh), overhead_ci=list(ci))
summary['decomposition'] = dec

# ---------------- (c) coverage caveat: OR latency covered vs uncovered ----------------
print('\n=== COVERAGE CAVEAT PROBE: OpenRouter latency, GIFT-covered vs GIFT-never-reached items ===')
_cv = json.load(open(BASE + 'gift_coverage.json'))
cov = set(_cv['complete_all_models'])
print('coverage file: n_complete=%s, set size=%d' % (_cv['n_complete'], len(cov)))
orl = list(c.execute('''select q.question_id, lc.model, pa.latency_ms, pa.total_tokens, s.strict_correct
                        from provider_attempts pa
                        join logical_calls lc on lc.id=pa.logical_call_id
                        join experiments e on e.id=lc.experiment_id
                        join questions q on q.id=lc.question_id
                        left join scores s on s.logical_call_id=lc.id
                        where e.name='expA_or_310726' and pa.status_code=200 and pa.finish_reason='stop' '''))
grp = defaultdict(list)
for qid, m, lat, tok, sc in orl:
    grp[(m, qid in cov)].append((lat / 1000.0, tok, sc))
print('%-24s %10s %6s %10s %10s %10s' % ('model', 'set', 'n', 'medLat_s', 'medTok', 'acc%'))
covprobe = {}
for m in MODELS:
    for flag, name in [(True, 'covered'), (False, 'uncovered')]:
        v = grp[(m, flag)]
        if not v: continue
        accs = [x[2] for x in v if x[2] is not None]
        print('%-24s %10s %6d %10.2f %10.0f %10.1f'
              % (m, name, len(v), median([x[0] for x in v]),
                 median([x[1] for x in v if x[1] is not None]),
                 100.0 * sum(accs) / len(accs) if accs else float('nan')))
        covprobe['%s|%s' % (m, name)] = dict(n=len(v), med_lat_s=median([x[0] for x in v]),
                                             med_tok=median([x[1] for x in v if x[1] is not None]),
                                             acc=100.0 * sum(accs) / len(accs) if accs else None)
# pooled two-sided permutation test on the difference in median OR latency
A = [x[0] for m in MODELS for x in grp[(m, True)]]
B = [x[0] for m in MODELS for x in grp[(m, False)]]
obs = median(A) - median(B)
allv = A + B; nA = len(A); rng = random.Random(4242); cnt = 0; NP = 10000
for _ in range(NP):
    rng.shuffle(allv)
    if abs(median(allv[:nA]) - median(allv[nA:])) >= abs(obs) - 1e-12: cnt += 1
print('pooled median OR latency: covered %.2f s (n=%d) vs uncovered %.2f s (n=%d); diff %+.2f s, '
      'permutation p = %.4g (10k label shuffles, two-sided)'
      % (median(A), len(A), median(B), len(B), obs, (cnt + 1) / (NP + 1)))
covprobe['pooled'] = dict(med_cov=median(A), med_unc=median(B), diff=obs, perm_p=(cnt + 1) / (NP + 1))
summary['coverage_probe'] = covprobe

json.dump(summary, open(BASE + 'ca_lat_03_reliability.json', 'w'), indent=1)

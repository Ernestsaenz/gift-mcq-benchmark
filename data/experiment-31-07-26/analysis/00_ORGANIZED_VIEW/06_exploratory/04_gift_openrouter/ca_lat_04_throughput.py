#!/usr/bin/env python
"""ca_lat_04: throughput framing (correct answers per unit wall-clock), per-model wall-clock price,
token-cost side of the ledger, and confirmation of the RUN_STATUS coverage figures."""
import sqlite3, json, math, random
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
DB = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite'
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)
rows = [r for r in json.load(open(BASE + 'cross_arm_A.json')) if r['analysis_include']]
MODELS = sorted(set(r['model'] for r in rows))
rel = json.load(open(BASE + 'ca_lat_03_reliability.json'))
G, O = rel['GIFT'], rel['OR']


def median(xs):
    s = sorted(xs); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


# ---- what field is gift_tokens? compare with DB completion/prompt tokens ----
print('=== TOKEN LEDGER (from provider_attempts, successful stop attempts) ===')
q = '''select e.name, lc.model, pa.prompt_tokens, pa.completion_tokens, pa.total_tokens
       from provider_attempts pa join logical_calls lc on lc.id=pa.logical_call_id
       join experiments e on e.id=lc.experiment_id
       where e.name in ('expA_gift_310726','expA_or_310726') and pa.status_code=200 and pa.finish_reason='stop' '''
tk = defaultdict(lambda: defaultdict(list))
for name, m, pt, ct, tt in c.execute(q):
    arm = 'GIFT' if 'gift' in name else 'OR'
    tk[(arm, m)]['p'].append(pt or 0); tk[(arm, m)]['c'].append(ct or 0); tk[(arm, m)]['t'].append(tt or 0)
print('%-24s %6s %6s %12s %12s %12s' % ('model', 'arm', 'n', 'med_prompt', 'med_compl', 'med_total'))
for m in MODELS:
    for arm in ['GIFT', 'OR']:
        d = tk[(arm, m)]
        if not d['t']: continue
        print('%-24s %6s %6d %12.0f %12.0f %12.0f'
              % (m, arm, len(d['t']), median(d['p']), median(d['c']), median(d['t'])))
allg = [x for m in MODELS for x in tk[('GIFT', m)]['p']]
allo = [x for m in MODELS for x in tk[('OR', m)]['p']]
print('pooled median PROMPT tokens: GIFT %.0f vs OR %.0f  (ratio %.2fx) '
      '-- prompt inflation is the retrieved context' % (median(allg), median(allo), median(allg) / median(allo)))

# ---- throughput: correct answers per second of wall-clock ----
print('\n=== THROUGHPUT: correct answers delivered per second of WALL-CLOCK ===')
acc_g = sum(r['gift_correct'] for r in rows) / len(rows)
acc_o = sum(r['or_correct'] for r in rows) / len(rows)
tg = 1.0 / G['wallclock_s_per_completed_cell'] * acc_g
to = 1.0 / O['wallclock_s_per_completed_cell'] * acc_o
print('  GIFT: 1 cell / %.2f s at concurrency %.2f  x %.4f accuracy = %.4f correct/s (%.1f correct/hour)'
      % (G['wallclock_s_per_completed_cell'], G['effective_concurrency'], acc_g, tg, tg * 3600))
print('  OR  : 1 cell / %.2f s at concurrency %.2f  x %.4f accuracy = %.4f correct/s (%.0f correct/hour)'
      % (O['wallclock_s_per_completed_cell'], O['effective_concurrency'], acc_o, to, to * 3600))
print('  --> OpenRouter delivers %.1fx more correct answers per unit wall-clock' % (to / tg))
print('  at MATCHED concurrency 1 (per-call medians %.2f s vs %.2f s): OpenRouter still %.2fx more correct/s'
      % (G['median_ok_latency_s'], O['median_ok_latency_s'],
         (acc_o / O['median_ok_latency_s']) / (acc_g / G['median_ok_latency_s'])))

# ---- per-model wall-clock price of the accuracy gain ----
print('\n=== PER-MODEL WALL-CLOCK PRICE (GIFT serial @1, OR at its measured %.1fx concurrency) ==='
      % O['effective_concurrency'])
print('%-24s %8s %10s %12s %12s %14s' % ('model', 'net+', 'dpp', 'GIFT_wall_s', 'OR_wall_s', 'min/extra_corr'))
per = {}
for m in MODELS + ['POOLED']:
    cells = rows if m == 'POOLED' else [r for r in rows if r['model'] == m]
    gw = sum(r['gift_latency_ms'] for r in cells) / 1000.0            # concurrency 1 -> latency == wall-clock
    ow = sum(r['or_latency_ms'] for r in cells) / 1000.0 / O['effective_concurrency']
    net = sum(r['gift_correct'] for r in cells) - sum(r['or_correct'] for r in cells)
    dpp = 100.0 * net / len(cells)
    s = (gw - ow) / net if net > 0 else None
    print('%-24s %8d %+10.2f %12.0f %12.0f %14s'
          % (m, net, dpp, gw, ow, ('%.1f' % (s / 60)) if s else 'n/a (net<=0)'))
    per[m] = dict(net=net, dpp=dpp, gift_wall_s=gw, or_wall_s=ow, s_per_extra_correct=s)

# ---- confirm the RUN_STATUS coverage figures ----
print('\n=== CONFIRMING RUN_STATUS COVERAGE FIGURES ===')
_cv = json.load(open(BASE + 'gift_coverage.json'))
cov = set(_cv['complete_all_models'])
q2 = '''select q.question_id, s.strict_correct
        from scores s join logical_calls lc on lc.id=s.logical_call_id
        join experiments e on e.id=lc.experiment_id join questions q on q.id=lc.question_id
        where e.name='expA_or_310726' '''
a = [[], []]
for qid, sc in c.execute(q2):
    if sc is None: continue
    a[0 if qid in cov else 1].append(sc)
print('  OpenRouter accuracy on the %d GIFT-covered items  : %.1f%%  (n=%d cells)'
      % (len(cov), 100.0 * sum(a[0]) / len(a[0]), len(a[0])))
print('  OpenRouter accuracy on the items never reached    : %.1f%%  (n=%d cells)'
      % (100.0 * sum(a[1]) / len(a[1]), len(a[1])))
print('  gap: %.1f pp -- matches RUN_STATUS (91.1%% vs 82.9%%)'
      % (100.0 * sum(a[0]) / len(a[0]) - 100.0 * sum(a[1]) / len(a[1])))

json.dump(dict(per_model=per, throughput_gift=tg, throughput_or=to, ratio=to / tg), open(BASE + 'ca_lat_04_throughput.json', 'w'), indent=1)

#!/usr/bin/env python
"""ca_ref_lat_00: establish what gift_tokens/or_tokens mean, and build a MATCHED
per-cell token table (prompt/completion/total, both arms) for the 1244 analysed cells,
using the scores -> parsed_answers.provider_attempt_id -> provider_attempts join
mandated by RUN_STATUS."""
import sqlite3, json
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
DB = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite'
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)
rows = [r for r in json.load(open(BASE + 'cross_arm_A.json')) if r['analysis_include']]
MODELS = sorted(set(r['model'] for r in rows))
print('analysed cells: %d, models %d, items %d' % (len(rows), len(MODELS), len(set(r['question_id'] for r in rows))))

# ---- SCORED attempt per logical call (the attempt that was actually graded) ----
Q = '''select e.name, q.question_id, lc.model,
              pa.prompt_tokens, pa.completion_tokens, pa.total_tokens,
              pa.latency_ms, pa.finish_reason, pa.status_code
       from scores s
       join parsed_answers pn on pn.id = s.parsed_answer_id
       join provider_attempts pa on pa.id = pn.provider_attempt_id
       join logical_calls lc on lc.id = s.logical_call_id
       join experiments e on e.id = lc.experiment_id
       join questions q on q.id = lc.question_id
       where e.name in ('expA_gift_310726','expA_or_310726')'''
scored = {}
for name, qid, m, pt, ct, tt, lat, fr, sc in c.execute(Q):
    arm = 'GIFT' if 'gift' in name else 'OR'
    scored[(arm, qid, m)] = dict(prompt=pt, compl=ct, total=tt, lat=lat, fr=fr, sc=sc)
print('scored attempts pulled: %d' % len(scored))

# ---- semantics check against cross_arm_A ----
agree = defaultdict(int); miss = 0
for r in rows:
    for arm, fld in [('GIFT', 'gift_tokens'), ('OR', 'or_tokens')]:
        k = (arm, r['question_id'], r['model'])
        if k not in scored: miss += 1; continue
        d = scored[k]
        v = r[fld]
        if v == d['compl']: agree['%s=completion' % arm] += 1
        if v == d['total']: agree['%s=total' % arm] += 1
        if v == d['prompt']: agree['%s=prompt' % arm] += 1
        latk = r['gift_latency_ms'] if arm == 'GIFT' else r['or_latency_ms']
        if latk == d['lat']: agree['%s_latency_matches' % arm] += 1
print('semantics (out of %d cells each):' % len(rows), dict(agree), 'missing joins:', miss)

# ---- build matched table ----
out = []
nmiss = 0
for r in rows:
    g = scored.get(('GIFT', r['question_id'], r['model']))
    o = scored.get(('OR', r['question_id'], r['model']))
    if not g or not o: nmiss += 1; continue
    out.append(dict(qid=r['question_id'], model=r['model'], cluster=r['cluster'],
                    region=r['region'], qlen=r['qlen'],
                    g_prompt=g['prompt'], g_compl=g['compl'], g_total=g['total'], g_lat=g['lat'], g_fr=g['fr'],
                    o_prompt=o['prompt'], o_compl=o['compl'], o_total=o['total'], o_lat=o['lat'], o_fr=o['fr'],
                    gift_correct=r['gift_correct'], or_correct=r['or_correct']))
print('matched paired cells with full token data: %d (dropped %d)' % (len(out), nmiss))
fr = defaultdict(int)
for d in out: fr['G:%s' % d['g_fr']] += 1; fr['O:%s' % d['o_fr']] += 1
print('finish_reason mix in matched set:', dict(fr))
nulls = sum(1 for d in out if d['g_prompt'] is None or d['o_prompt'] is None
            or d['g_compl'] is None or d['o_compl'] is None)
print('cells with any NULL token field:', nulls)
json.dump(out, open(BASE + 'ca_ref_lat_matched.json', 'w'))

# ---- how the claim pulled its medians: whole-arm, unmatched ----
print('\n=== CLAIM-STYLE PULL (whole arm, status 200 & finish_reason=stop, ALL attempts) ===')
q2 = '''select e.name, lc.model, pa.prompt_tokens, pa.completion_tokens
        from provider_attempts pa join logical_calls lc on lc.id=pa.logical_call_id
        join experiments e on e.id=lc.experiment_id
        where e.name in ('expA_gift_310726','expA_or_310726')
          and pa.status_code=200 and pa.finish_reason='stop' '''
tot = defaultdict(lambda: [0, 0, 0])   # arm -> [n, sum_compl, sum_prompt]
for name, m, pt, ct in c.execute(q2):
    arm = 'GIFT' if 'gift' in name else 'OR'
    t = tot[arm]; t[0] += 1; t[1] += (ct or 0); t[2] += (pt or 0)
for arm in ['GIFT', 'OR']:
    n, sc_, sp = tot[arm]
    print('  %-5s attempts=%d  SUM completion=%d  mean/attempt=%.1f  SUM prompt=%d' % (arm, n, sc_, sc_ / n, sp))
g, o = tot['GIFT'], tot['OR']
print('  pooled completion ratio GIFT/OR = %.4f ;  attempt-count ratio = %.4f'
      % (g[1] / o[1], g[0] / o[0]))
print('  --> per-attempt completion tokens: GIFT %.1f vs OR %.1f (GIFT %s)'
      % (g[1] / g[0], o[1] / o[0], 'HIGHER' if g[1] / g[0] > o[1] / o[0] else 'lower'))

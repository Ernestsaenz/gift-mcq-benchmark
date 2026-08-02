#!/usr/bin/env python
"""Does partial coverage bias the latency-cost ratio? Pull OR (full 474-item) and GIFT
(83% prefix) latencies straight from the DB and compare covered vs never-reached items.
Also audit what gift_latency_ms actually measures (retries? failed attempts?)."""
import json, math, sqlite3
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
DB = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite'
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)


def median(xs):
    s = sorted(xs); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


rows = [r for r in json.load(open(BASE + 'cross_arm_A.json')) if r['analysis_include']]
covered = set(r['question_id'] for r in rows)
MODELS = sorted(set(r['model'] for r in rows))
meta = json.load(open(BASE + 'dataset_meta.json'))
print('dataset_meta keys:', list(meta.keys())[:20])

# ---- 1. audit: attempts per logical call, and how much latency is NOT in the export
print('\n=== 1. ATTEMPT AUDIT (all attempts, incl. failures & superseded retries) ===')
for exp in ('expA_gift_310726', 'expA_or_310726'):
    q = list(c.execute('''select lc.model, pa.status_code, count(*), sum(pa.latency_ms)
                          from provider_attempts pa
                          join logical_calls lc on lc.id=pa.logical_call_id
                          join experiments e on e.id=lc.experiment_id
                          where e.name=? group by lc.model, pa.status_code''', (exp,)))
    tot_n = sum(x[2] for x in q); tot_s = sum((x[3] or 0) for x in q) / 1000.0
    okq = [x for x in q if x[1] == 200]
    print('%-20s attempts=%4d  total_latency=%9.1f s   (ok=%d, ok_latency=%.1f s)'
          % (exp, tot_n, tot_s, sum(x[2] for x in okq), sum((x[3] or 0) for x in okq) / 1000.0))
    for x in sorted(q):
        print('    %-26s status=%-6s n=%5d  sum_lat=%9.1f s' % (x[0], x[1], x[2], (x[3] or 0) / 1000.0))

# ---- 2. verify export latency == scored attempt latency
print('\n=== 2. EXPORT LATENCY PROVENANCE (scores -> parsed_answers -> provider_attempts) ===')
for exp, key in (('expA_gift_310726', 'gift_latency_ms'), ('expA_or_310726', 'or_latency_ms')):
    q = c.execute('''select q.question_id, lc.model, pa.latency_ms, pa.attempt_index
                     from scores s
                     join parsed_answers p on p.id=s.parsed_answer_id
                     join provider_attempts pa on pa.id=p.provider_attempt_id
                     join logical_calls lc on lc.id=s.logical_call_id
                     join questions q on q.id=lc.question_id
                     join experiments e on e.id=lc.experiment_id
                     where e.name=?''', (exp,))
    d = {(a, b): (lat, ai) for a, b, lat, ai in q}
    mism = 0; retried = 0
    for r in rows:
        k = (r['question_id'], r['model'])
        if k in d:
            if d[k][0] != r[key]: mism += 1
            if d[k][1] > 0: retried += 1
    print('  %-20s key=%-16s mismatches=%d  scored-attempt-was-a-retry=%d' % (exp, key, mism, retried))

# ---- 3. GIFT true wall-clock cost incl. failed attempts, on covered cells
print('\n=== 3. GIFT COST INCLUDING FAILED/SUPERSEDED ATTEMPTS (covered cells only) ===')
gall = defaultdict(float); gscored = defaultdict(float); gn = defaultdict(int)
for qid, model, lat, sc in c.execute('''select q.question_id, lc.model, pa.latency_ms, pa.status_code
                                        from provider_attempts pa
                                        join logical_calls lc on lc.id=pa.logical_call_id
                                        join questions q on q.id=lc.question_id
                                        join experiments e on e.id=lc.experiment_id
                                        where e.name='expA_gift_310726' '''):
    if qid in covered:
        gall[model] += (lat or 0) / 1000.0
        gn[model] += 1
for r in rows:
    gscored[r['model']] += r['gift_latency_ms'] / 1000.0
print('%-26s %12s %12s %8s' % ('model', 'scored_s', 'all_attempts_s', 'ratio'))
for m in MODELS:
    print('%-26s %12.1f %12.1f %8.3f' % (m, gscored[m], gall[m], gall[m] / gscored[m]))
print('%-26s %12.1f %12.1f %8.3f' % ('POOLED', sum(gscored.values()), sum(gall.values()),
                                     sum(gall.values()) / sum(gscored.values())))

# ---- 4. OR latency and accuracy: covered vs never-reached items
print('\n=== 4. OPENROUTER: covered (311 analysed) vs NOT covered, per model ===')
orfull = defaultdict(dict)
for qid, model, lat, corr in c.execute('''select q.question_id, lc.model, pa.latency_ms, s.strict_correct
                                          from scores s
                                          join parsed_answers p on p.id=s.parsed_answer_id
                                          join provider_attempts pa on pa.id=p.provider_attempt_id
                                          join logical_calls lc on lc.id=s.logical_call_id
                                          join questions q on q.id=lc.question_id
                                          join experiments e on e.id=lc.experiment_id
                                          where e.name='expA_or_310726' '''):
    orfull[model][qid] = (lat / 1000.0, corr)
defect = set()
try:
    defect = set(meta.get('excluded_item_defect_ids') or meta.get('item_defect_ids') or [])
except Exception:
    pass
print('defect ids from meta:', sorted(defect))
print('%-26s %6s %8s %10s %10s | %6s %8s %10s %10s' %
      ('model', 'n_cov', 'acc_cov', 'medLat_cov', 'meanLat_cov',
       'n_miss', 'acc_mis', 'medLat_mis', 'meanLat_mis'))
for m in MODELS:
    cov = [v for q, v in orfull[m].items() if q in covered]
    mis = [v for q, v in orfull[m].items() if q not in covered and q not in defect]
    def blk(x):
        return (len(x), 100.0 * sum(a[1] for a in x) / len(x), median([a[0] for a in x]),
                sum(a[0] for a in x) / len(x))
    a = blk(cov); b = blk(mis)
    print('%-26s %6d %8.1f %10.2f %10.2f | %6d %8.1f %10.2f %10.2f' % ((m,) + a + b))
allcov = [v for m in MODELS for q, v in orfull[m].items() if q in covered]
allmis = [v for m in MODELS for q, v in orfull[m].items() if q not in covered and q not in defect]
for nm, x in (('POOLED cov', allcov), ('POOLED miss', allmis)):
    print('%-26s %6d %8.1f %10.2f %10.2f' % (nm, len(x), 100.0 * sum(a[1] for a in x) / len(x),
                                             median([a[0] for a in x]), sum(a[0] for a in x) / len(x)))

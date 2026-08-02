#!/usr/bin/env python
"""Does the 83%-coverage prefix bias the paired latency ratio?

1. verify cross_arm_A.json latencies against the DB scored attempts
2. OR latency on GIFT-covered vs GIFT-missing items  (is the DENOMINATOR biased?)
3. counterfactual ratio on the missing items under an additive-overhead model
4. temporal drift of GIFT latency across the 8h45m run (is the prefix the fast part?)
5. unscored GIFT attempts (retries / load-shed) that the per-cell latency ignores
"""
import json, math, random
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
pull = json.load(open(BASE + 'ca_ref_lat_03_pull.json'))
rows = [r for r in json.load(open(BASE + 'cross_arm_A.json')) if r['analysis_include']]
MODELS = sorted({r['model'] for r in rows})
order = pull['order']

def median(xs):
    s = sorted(xs); n = len(s)
    return s[n//2] if n % 2 else 0.5*(s[n//2-1]+s[n//2])
def quant(xs, p):
    s = sorted(xs); n = len(s)
    if n == 1: return float(s[0])
    h = (n-1)*p; lo = int(math.floor(h)); hi = min(lo+1, n-1)
    return s[lo] + (h-lo)*(s[hi]-s[lo])

# ---------- 1. verify against DB ----------
db_or   = {(r['model'], r['qid']): r['latency_ms'] for r in pull['scored']['expA_or_310726']}
db_gift = {(r['model'], r['qid']): r['latency_ms'] for r in pull['scored']['expA_gift_310726']}
bad = 0
for r in rows:
    k = (r['model'], r['question_id'])
    if db_or.get(k) != r['or_latency_ms'] or db_gift.get(k) != r['gift_latency_ms']:
        bad += 1
print('[1] export-vs-DB latency mismatches: %d / %d cells' % (bad, len(rows)))

# ---------- 2. OR latency, covered vs missing ----------
covered = {r['question_id'] for r in rows}
gift_qids_any = {r['qid'] for r in pull['scored']['expA_gift_310726']}
print('\n[2] OpenRouter latency on GIFT-covered vs GIFT-missing items (scored OR attempts)')
print('%-24s %6s %8s %8s | %6s %8s %8s | %8s' %
      ('model','n_cov','med_cov','p90_cov','n_mis','med_mis','p90_mis','mis/cov'))
or_cov_med, or_mis_med = {}, {}
for m in MODELS:
    cov = [db_or[(m,q)]/1000. for q in covered if (m,q) in db_or]
    mis = [v/1000. for (mm,q), v in db_or.items() if mm == m and q not in covered]
    or_cov_med[m], or_mis_med[m] = median(cov), median(mis)
    print('%-24s %6d %8.2f %8.2f | %6d %8.2f %8.2f | %8.2f' %
          (m, len(cov), median(cov), quant(cov,.9), len(mis), median(mis), quant(mis,.9),
           median(mis)/median(cov)))
allcov = [db_or[(m,q)]/1000. for m in MODELS for q in covered if (m,q) in db_or]
allmis = [v/1000. for (mm,q), v in db_or.items() if q not in covered]
print('%-24s %6d %8.2f %8.2f | %6d %8.2f %8.2f | %8.2f' %
      ('POOLED', len(allcov), median(allcov), quant(allcov,.9), len(allmis),
       median(allmis), quant(allmis,.9), median(allmis)/median(allcov)))

# ---------- 3. counterfactual ratio on the missing items ----------
print('\n[3] counterfactual multiplier on the 155 uncovered items')
print('    model A: GIFT median is model-specific and constant across items')
print('    model B: GIFT = OR + median additive overhead measured on covered items')
print('%-24s %9s %9s %9s' % ('model','observed','cf A','cf B'))
for m in MODELS:
    c = [r for r in rows if r['model']==m]
    G = median([r['gift_latency_ms']/1000. for r in c])
    obs = median([r['gift_latency_ms']/r['or_latency_ms'] for r in c])
    ovh = median([(r['gift_latency_ms']-r['or_latency_ms'])/1000. for r in c])
    mis = [v/1000. for (mm,q), v in db_or.items() if mm==m and q not in covered]
    cfA = median([G/x for x in mis])
    cfB = median([(x+ovh)/x for x in mis])
    print('%-24s %9.2f %9.2f %9.2f' % (m, obs, cfA, cfB))
allmis_by = defaultdict(list)
for (mm,q), v in db_or.items():
    if q not in covered: allmis_by[mm].append(v/1000.)
obs_p = median([r['gift_latency_ms']/r['or_latency_ms'] for r in rows])
Gp = {m: median([r['gift_latency_ms']/1000. for r in rows if r['model']==m]) for m in MODELS}
ovhp = {m: median([(r['gift_latency_ms']-r['or_latency_ms'])/1000. for r in rows if r['model']==m]) for m in MODELS}
cfA_pool = median([Gp[m]/x for m in MODELS for x in allmis_by[m]])
cfB_pool = median([(x+ovhp[m])/x for m in MODELS for x in allmis_by[m]])
print('%-24s %9.2f %9.2f %9.2f' % ('POOLED', obs_p, cfA_pool, cfB_pool))

# ---------- 4. temporal drift of GIFT within the run ----------
print('\n[4] GIFT scored-attempt latency by position in the run (created_at order)')
gs = sorted(pull['scored']['expA_gift_310726'], key=lambda r: (r['created_at'] or ''))
print('   run spans %s .. %s  (n=%d)' % (gs[0]['created_at'], gs[-1]['created_at'], len(gs)))
Q = 6
for i in range(Q):
    a, b = i*len(gs)//Q, (i+1)*len(gs)//Q
    seg = [r['latency_ms']/1000. for r in gs[a:b]]
    print('   sextile %d  n=%3d  median %6.2f s  p90 %6.2f s' % (i+1, len(seg), median(seg), quant(seg,.9)))
# same for the analysed cells only, ordered by dataset position
print('   -- analysed cells only, by DATASET position (prefix vs late):')
an = sorted(rows, key=lambda r: order[r['question_id']])
for i in range(4):
    a, b = i*len(an)//4, (i+1)*len(an)//4
    seg = an[a:b]
    print('   quartile %d n=%3d  GIFT med %6.2f  OR med %6.2f  ratio med %5.2f  (dataset idx %d-%d)' %
          (i+1, len(seg), median([r['gift_latency_ms']/1000. for r in seg]),
           median([r['or_latency_ms']/1000. for r in seg]),
           median([r['gift_latency_ms']/r['or_latency_ms'] for r in seg]),
           order[seg[0]['question_id']], order[seg[-1]['question_id']]))

# ---------- 5. unscored GIFT attempts ----------
print('\n[5] attempts that the per-cell latency ignores')
for exp in ('expA_gift_310726','expA_or_310726'):
    att = pull['attempts'][exp]
    scored_ids = {(r['model'], r['qid'], r['attempt_index']) for r in pull['scored'][exp]}
    extra = [a for a in att if (a['model'], a['qid'], a['attempt_index']) not in scored_ids]
    lat = [a['latency_ms']/1000. for a in extra if a['latency_ms']]
    print('   %-18s attempts %4d  scored %4d  unscored %3d  their latency: n=%d sum %.0f s median %.2f s'
          % (exp, len(att), len(pull['scored'][exp]), len(extra), len(lat),
             sum(lat) if lat else 0, median(lat) if lat else float('nan')))
    errs = defaultdict(int)
    for a in extra: errs[a['error_type'] or ('http%s' % a['status_code'])] += 1
    print('      unscored breakdown:', dict(sorted(errs.items(), key=lambda kv: -kv[1])[:6]))

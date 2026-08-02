#!/usr/bin/env python
"""Coverage-bias sensitivity for the latency claim.

A. Is the covered/missing OR-latency gap an item property or a dataset-position artifact?
B. Region-reweighted multiplier: reweight covered items to the full 474-item region mix.
C. Full-dataset projected multiplier (mixture of observed covered + counterfactual missing),
   with a cluster bootstrap CI on the projected value.
D. The unscored-attempt asymmetry: whose hidden work is bigger?
E. Does the MECHANISM (denominator drives the spread) survive under every scenario?
"""
import json, math, random
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
pull = json.load(open(BASE + 'ca_ref_lat_03_pull.json'))
rows = [r for r in json.load(open(BASE + 'cross_arm_A.json')) if r['analysis_include']]
covfull = json.load(open(BASE + 'ca_cov_or_full.json'))
MODELS = sorted({r['model'] for r in rows})
order = pull['order']
items = covfull['items']
db_or = {(r['model'], r['qid']): r['latency_ms'] for r in pull['scored']['expA_or_310726']}
covered = {r['question_id'] for r in rows}

def median(xs):
    s = sorted(xs); n = len(s)
    return s[n//2] if n % 2 else 0.5*(s[n//2-1]+s[n//2])
def quant(xs, p):
    s = sorted(xs); n = len(s)
    if n == 1: return float(s[0])
    h = (n-1)*p; lo = int(math.floor(h)); hi = min(lo+1, n-1)
    return s[lo] + (h-lo)*(s[hi]-s[lo])
def wmedian(pairs):           # pairs = [(value, weight)]
    s = sorted(pairs); tot = sum(w for _, w in s); acc = 0.0
    for v, w in s:
        acc += w
        if acc >= tot/2.0: return v
    return s[-1][0]

# ---------- A. position vs item property ----------
print('[A] OR scored latency by DATASET position, all 474 items (median s)')
qs = sorted(order, key=lambda q: order[q])
print('%-24s %s' % ('model', '  '.join('d%d' % (i+1) for i in range(6))))
for m in MODELS:
    line = []
    for i in range(6):
        seg = qs[i*474//6:(i+1)*474//6]
        v = [db_or[(m,q)]/1000. for q in seg if (m,q) in db_or]
        line.append('%6.2f' % median(v))
    print('%-24s %s' % (m, '  '.join(line)))
print('  coverage rate by decile of dataset position:')
for i in range(10):
    seg = qs[i*474//10:(i+1)*474//10]
    c = sum(1 for q in seg if q in covered)
    print('    d%-2d idx %3d-%3d  covered %2d/%2d = %5.1f%%' % (i+1, order[seg[0]], order[seg[-1]], c, len(seg), 100.*c/len(seg)))

# ---------- B. region reweighting ----------
print('\n[B] region-reweighted multiplier (covered cells reweighted to the 474-item region mix)')
reg_full = defaultdict(int)
for q, it in items.items(): reg_full[it['region']] += 1
reg_cov = defaultdict(int)
for q in covered: reg_cov[items[q]['region']] += 1
print('   region                     full  covered   weight')
W = {}
for r in sorted(reg_full):
    w = (reg_full[r]/474.) / (reg_cov[r]/len(covered)) if reg_cov[r] else float('nan')
    W[r] = w
    print('   %-24s %5d %8d %8.3f' % (r, reg_full[r], reg_cov[r], w))
print('%-24s %10s %12s' % ('model','unweighted','reweighted'))
for m in MODELS + ['POOLED']:
    c = rows if m=='POOLED' else [r for r in rows if r['model']==m]
    unw = median([r['gift_latency_ms']/r['or_latency_ms'] for r in c])
    rew = wmedian([(r['gift_latency_ms']/r['or_latency_ms'], W.get(items[r['question_id']]['region'], 1.0)) for r in c])
    print('%-24s %10.2f %12.2f' % (m, unw, rew))

# ---------- C. projected full-dataset multiplier ----------
print('\n[C] projected FULL-dataset multiplier (observed covered + additive-overhead counterfactual missing)')
def project(cells):
    """cells = bootstrap sample of covered cells; returns pooled projected median ratio."""
    ov = {}
    for m in MODELS:
        cm = [r for r in cells if r['model']==m]
        if not cm: return float('nan')
        ov[m] = median([(r['gift_latency_ms']-r['or_latency_ms'])/1000. for r in cm])
    vals = [r['gift_latency_ms']/r['or_latency_ms'] for r in cells]
    for (mm,q), v in db_or.items():
        if q not in covered:
            vals.append((v/1000. + ov[mm])/(v/1000.))
    return median(vals)

byc = defaultdict(list)
for r in rows: byc[r['cluster']].append(r)
keys = list(byc.keys()); rng = random.Random(4242); reps = []
for _ in range(20000):
    samp = []
    for _ in range(len(keys)): samp.extend(byc[keys[rng.randrange(len(keys))]])
    reps.append(project(samp))
reps = [x for x in reps if x == x]
proj = project(rows)
print('   observed covered-only pooled median ratio : %.2f' % median([r['gift_latency_ms']/r['or_latency_ms'] for r in rows]))
print('   projected full-dataset pooled median ratio: %.2f  95%% CI [%.2f, %.2f]  (cluster bootstrap B=20000, percentile)'
      % (proj, quant(reps,.025), quant(reps,.975)))
print('   per-model projected:')
for m in MODELS:
    cm = [r for r in rows if r['model']==m]
    ov = median([(r['gift_latency_ms']-r['or_latency_ms'])/1000. for r in cm])
    vals = [r['gift_latency_ms']/r['or_latency_ms'] for r in cm]
    vals += [(v/1000.+ov)/(v/1000.) for (mm,q),v in db_or.items() if mm==m and q not in covered]
    print('     %-24s covered %6.2f  ->  projected %6.2f' % (m, median([r['gift_latency_ms']/r['or_latency_ms'] for r in cm]), median(vals)))

# ---------- D. unscored-attempt asymmetry ----------
print('\n[D] hidden (unscored) attempt cost, restricted to the 1244 analysed cells')
anal = {(r['model'], r['question_id']) for r in rows}
for exp, lab in (('expA_gift_310726','GIFT'), ('expA_or_310726','OR')):
    scored_ids = {(r['model'], r['qid'], r['attempt_index']) for r in pull['scored'][exp]}
    extra = [a for a in pull['attempts'][exp]
             if (a['model'], a['qid'], a['attempt_index']) not in scored_ids and (a['model'], a['qid']) in anal]
    lat = [a['latency_ms']/1000. for a in extra if a['latency_ms']]
    print('   %-5s unscored attempts on analysed cells: %3d   total hidden latency %8.0f s   median %7.2f s'
          % (lab, len(extra), sum(lat), median(lat) if lat else float('nan')))
tg = sum(r['gift_latency_ms'] for r in rows)/1000.
to = sum(r['or_latency_ms'] for r in rows)/1000.
print('   scored-only totals on 1244 cells: GIFT %.0f s   OR %.0f s   ratio %.2f' % (tg, to, tg/to))
gh = sum(a['latency_ms']/1000. for a in pull['attempts']['expA_gift_310726']
         if (a['model'],a['qid']) in anal and a['latency_ms'] and
         (a['model'],a['qid'],a['attempt_index']) not in {(r['model'],r['qid'],r['attempt_index']) for r in pull['scored']['expA_gift_310726']})
oh = sum(a['latency_ms']/1000. for a in pull['attempts']['expA_or_310726']
         if (a['model'],a['qid']) in anal and a['latency_ms'] and
         (a['model'],a['qid'],a['attempt_index']) not in {(r['model'],r['qid'],r['attempt_index']) for r in pull['scored']['expA_or_310726']})
print('   all-attempt totals              : GIFT %.0f s   OR %.0f s   ratio %.2f' % (tg+gh, to+oh, (tg+gh)/(to+oh)))

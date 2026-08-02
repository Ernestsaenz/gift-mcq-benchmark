#!/usr/bin/env python
"""Partial-coverage sensitivity for the latency-cost ratio.

Difficulty is defined LEAVE-ONE-MODEL-OUT so it is not derived from the same model's own
OpenRouter correctness (avoids regression-to-the-mean when we then look at GIFT-OR within
stratum). For cell (item i, model m): diff(i,m) = # of the OTHER 3 models that OpenRouter
got right on item i, in {0,1,2,3}. This is computable for all 474 items, so it gives the
full-dataset stratum distribution as well as the covered one.

Then: (a) how does the GIFT-OR accuracy delta and the pp-per-second ratio behave by
stratum, (b) reweight the covered cells to the full-dataset stratum mix and recompute the
ratio with a cluster bootstrap."""
import json, math, random, sqlite3
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
DB = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite'
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)
rows = [r for r in json.load(open(BASE + 'cross_arm_A.json')) if r['analysis_include']]
covered = set(r['question_id'] for r in rows)
MODELS = sorted(set(r['model'] for r in rows))


def median(xs):
    s = sorted(xs); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def wmedian(pairs):
    """weighted median of (value, weight)"""
    s = sorted(pairs); tot = sum(w for _, w in s); acc = 0.0
    for v, w in s:
        acc += w
        if acc >= tot / 2.0:
            return v
    return s[-1][0]


def quant(xs, p):
    s = sorted(xs); n = len(s)
    if n == 0: return float('nan')
    if n == 1: return float(s[0])
    h = (n - 1) * p; lo = int(math.floor(h)); hi = min(lo + 1, n - 1)
    return s[lo] + (h - lo) * (s[hi] - s[lo])


# ---- OR correctness for ALL 474 items x 4 models
orc = defaultdict(dict)
for qid, model, corr in c.execute('''select q.question_id, lc.model, s.strict_correct
                                     from scores s
                                     join parsed_answers p on p.id=s.parsed_answer_id
                                     join logical_calls lc on lc.id=s.logical_call_id
                                     join questions q on q.id=lc.question_id
                                     join experiments e on e.id=lc.experiment_id
                                     where e.name='expA_or_310726' '''):
    orc[model][qid] = corr
allq = sorted(set(q for m in MODELS for q in orc[m]))
full = [q for q in allq if all(q in orc[m] for m in MODELS)]
print('items with all 4 OR cells:', len(full), ' covered:', len(covered))


def loo(qid, m):
    return sum(orc[o][qid] for o in MODELS if o != m)


# ---- stratum shares
print('\n=== STRATUM SHARES (leave-one-out OR difficulty, 0..3 others correct) ===')
print('%-6s %10s %10s %10s' % ('stratum', 'covered', 'full474', 'weight'))
cov_n = defaultdict(int); full_n = defaultdict(int)
for m in MODELS:
    for q in full:
        full_n[loo(q, m)] += 1
for r in rows:
    cov_n[loo(r['question_id'], r['model'])] += 1
W = {}
NC = sum(cov_n.values()); NF = sum(full_n.values())
for s in range(4):
    W[s] = (full_n[s] / NF) / (cov_n[s] / NC) if cov_n[s] else 0.0
    print('%-6d %10d %10d %10.3f' % (s, cov_n[s], full_n[s], W[s]))

# ---- behaviour by stratum
print('\n=== GIFT-OR BEHAVIOUR BY DIFFICULTY STRATUM (pooled over 4 models) ===')
print('%-8s %6s %8s %8s %9s %10s %10s %10s' %
      ('stratum', 'n', 'giftAcc', 'orAcc', 'dpp', 'medDiff_s', 'pp_per_s', 'net'))
for s in range(4):
    sub = [r for r in rows if loo(r['question_id'], r['model']) == s]
    if not sub: continue
    n = len(sub); g = sum(r['gift_correct'] for r in sub); o = sum(r['or_correct'] for r in sub)
    d = 100.0 * (g - o) / n
    md = median([(r['gift_latency_ms'] - r['or_latency_ms']) / 1000.0 for r in sub])
    print('%-8d %6d %8.1f %8.1f %+9.3f %10.3f %+10.4f %10d' %
          (s, n, 100.0 * g / n, 100.0 * o / n, d, md, d / md if md else float('nan'), g - o))

print('\n=== same, per model, hard (loo<=1) vs easy (loo>=2) ===')
print('%-26s %8s %6s %9s %10s %10s' % ('model', 'band', 'n', 'dpp', 'medDiff_s', 'pp_per_s'))
for m in MODELS + ['POOLED']:
    cells = rows if m == 'POOLED' else [r for r in rows if r['model'] == m]
    for band, f in (('hard<=1', lambda r: loo(r['question_id'], r['model']) <= 1),
                    ('easy>=2', lambda r: loo(r['question_id'], r['model']) >= 2)):
        sub = [r for r in cells if f(r)]
        n = len(sub); g = sum(r['gift_correct'] for r in sub); o = sum(r['or_correct'] for r in sub)
        d = 100.0 * (g - o) / n
        md = median([(r['gift_latency_ms'] - r['or_latency_ms']) / 1000.0 for r in sub])
        print('%-26s %8s %6d %+9.3f %10.3f %+10.4f' % (m, band, n, d, md, d / md if md else float('nan')))

# ---- reweighted ratio + cluster bootstrap
print('\n=== REWEIGHTED TO FULL-474 DIFFICULTY MIX (cluster bootstrap B=20000, percentile) ===')
print('%-26s %10s %10s %28s %10s' % ('model', 'raw', 'reweighted', '95% CI (reweighted)', 'undef%'))
B = 20000
out = {}
for m in MODELS + ['POOLED']:
    cells = rows if m == 'POOLED' else [r for r in rows if r['model'] == m]
    # per-model weights (recompute so each model's own mix is matched)
    cn = defaultdict(int); fn = defaultdict(int)
    ms = MODELS if m == 'POOLED' else [m]
    for mm in ms:
        for q in full: fn[loo(q, mm)] += 1
    for r in cells: cn[loo(r['question_id'], r['model'])] += 1
    NCc = sum(cn.values()); NFf = sum(fn.values())
    w = {s: ((fn[s] / NFf) / (cn[s] / NCc) if cn[s] else 0.0) for s in range(4)}

    def stat(samp):
        num = 0.0; den = 0.0; pairs = []
        for r in samp:
            ww = w[loo(r['question_id'], r['model'])]
            num += ww * (r['gift_correct'] - r['or_correct']); den += ww
            pairs.append(((r['gift_latency_ms'] - r['or_latency_ms']) / 1000.0, ww))
        if den == 0: return None
        d = 100.0 * num / den
        md = wmedian(pairs)
        if md <= 0: return None
        return d / md
    raw_d = 100.0 * (sum(r['gift_correct'] for r in cells) - sum(r['or_correct'] for r in cells)) / len(cells)
    raw = raw_d / median([(r['gift_latency_ms'] - r['or_latency_ms']) / 1000.0 for r in cells])
    rw = stat(cells)
    byc = defaultdict(list)
    for r in cells: byc[r['cluster']].append(r)
    keys = list(byc); K = len(keys); rng = random.Random(4242)
    vals = []; und = 0
    for _ in range(B):
        samp = []
        for _ in range(K): samp.extend(byc[keys[rng.randrange(K)]])
        v = stat(samp)
        if v is None: und += 1
        else: vals.append(v)
    ci = (quant(vals, .025), quant(vals, .975))
    out[m] = dict(raw=raw, reweighted=rw, ci=list(ci), undef_pct=100.0 * und / B)
    print('%-26s %+10.4f %+10.4f  [%+8.4f, %+8.4f] %9.2f%%' % (m, raw, rw, ci[0], ci[1], 100.0 * und / B))

json.dump(out, open(BASE + 'ca_ref_lat_03_out.json', 'w'), indent=1)

#!/usr/bin/env python
"""ca_rtx_03: (A) honest CIs -- the claim's bootstrap holds the fitted (a,b) FIXED and only
resamples clusters, so it ignores the sampling error of the very regression it depends on.
Refit inside the bootstrap. (B) run-order drift of the 'fixed' tax. (C) retry contamination.
(D) the coverage caveat: are the covered items latency-atypical?"""
import json, math, random, sqlite3, datetime as dt
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
DB = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite'
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)
M = json.load(open(BASE + 'ca_rtx_matched.json'))
MODELS = sorted(set(d['model'] for d in M))
SHORT = {'google/gemini-3.6-flash': 'gemini', 'google/gemma-4-26b-a4b-it': 'gemma',
         'qwen/qwen3.6-35b-a3b': 'qwen', 'z-ai/glm-5.2': 'glm'}


def median(xs):
    s = sorted(xs); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def quant(xs, p):
    s = sorted(xs); n = len(s)
    if n == 1: return float(s[0])
    h = (n - 1) * p; lo = int(math.floor(h)); hi = min(lo + 1, n - 1)
    return s[lo] + (h - lo) * (s[hi] - s[lo])


def ols(x, y):
    n = len(x); mx = sum(x) / n; my = sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    b = sxy / sxx if sxx else 0.0
    a = my - b * mx
    ssr = sum((yy - (a + b * xx)) ** 2 for xx, yy in zip(x, y))
    sst = sum((yy - my) ** 2 for yy in y)
    n_ = len(x)
    se_b = math.sqrt(ssr / (n_ - 2) / sxx) if sxx and n_ > 2 else float('nan')
    return a, b, (1 - ssr / sst if sst else float('nan')), se_b


print('=== (A) DOES THE OVERHEAD CI SURVIVE REFITTING (a,b) INSIDE THE BOOTSTRAP? ===')
print('claim CI: cluster bootstrap of the median, (a,b) held at the point estimate.')
print('honest  : same cluster resample, but the OR regression is REFIT on each resample.')
print('%-8s %8s %10s %9s %22s %24s %8s' % ('model', 'b_ms/tok', 'se_b', 'R2',
                                           'CLAIM CI (a,b fixed)', 'HONEST CI (a,b refit)', 'width x'))
res = {}
for m in MODELS:
    cc = [d for d in M if d['model'] == m]
    a0, b0, r2, se = ols([d['o_compl'] for d in cc], [d['o_lat'] / 1000.0 for d in cc])
    med0 = median([d['g_lat'] / 1000.0 - (a0 + b0 * d['g_compl']) for d in cc])
    byc = defaultdict(list)
    for d in cc: byc[d['cluster']].append(d)
    keys = list(byc)
    r1, r2b = [], []
    rng = random.Random(31337)
    for _ in range(5000):
        s = []
        for _ in range(len(keys)): s.extend(byc[keys[rng.randrange(len(keys))]])
        r1.append(median([d['g_lat'] / 1000.0 - (a0 + b0 * d['g_compl']) for d in s]))
        aa, bb, _, _ = ols([d['o_compl'] for d in s], [d['o_lat'] / 1000.0 for d in s])
        r2b.append(median([d['g_lat'] / 1000.0 - (aa + bb * d['g_compl']) for d in s]))
    c1 = (quant(r1, .025), quant(r1, .975)); c2 = (quant(r2b, .025), quant(r2b, .975))
    w = (c2[1] - c2[0]) / (c1[1] - c1[0])
    print('%-8s %8.3f %10.4f %9.3f   [%6.2f, %6.2f]      [%6.2f, %6.2f]  %7.2fx'
          % (SHORT[m], b0 * 1000, se * 1000, r2, c1[0], c1[1], c2[0], c2[1], w))
    res[SHORT[m]] = dict(med=med0, ci_fixed=list(c1), ci_refit=list(c2), b=b0, se_b=se, r2=r2)

print('\n  sensitivity of the point estimate to b alone (b +/- 1.96*se, prediction at median GIFT compl):')
for m in MODELS:
    cc = [d for d in M if d['model'] == m]
    a0, b0, r2, se = ols([d['o_compl'] for d in cc], [d['o_lat'] / 1000.0 for d in cc])
    gt = median([d['g_compl'] for d in cc])
    swing = 1.96 * se * gt
    print('    %-8s med GIFT completion %6.0f tok -> +/- %.2f s of the reported %.2f s overhead (%.0f%%)'
          % (SHORT[m], gt, swing, res[SHORT[m]]['med'], 100 * swing / res[SHORT[m]]['med']))

print('\n=== (B) RUN-ORDER DRIFT: is the "fixed tax" stable across the 8.8 h GIFT run? ===')
ts = {}
q = '''select q.question_id, lc.model, pa.created_at, pa.attempt_index
       from scores s join parsed_answers pn on pn.id=s.parsed_answer_id
       join provider_attempts pa on pa.id=pn.provider_attempt_id
       join logical_calls lc on lc.id=s.logical_call_id
       join experiments e on e.id=lc.experiment_id join questions q on q.id=lc.question_id
       where e.name='expA_gift_310726' '''
for qid, m, ca, ai in c.execute(q):
    ts[(qid, m)] = (dt.datetime.fromisoformat(ca), ai)
t0 = min(v[0] for v in ts.values())
print('%-8s %7s %9s %9s %9s %9s %10s' % ('model', 'n', 'Q1_med', 'Q2_med', 'Q3_med', 'Q4_med', 'Q4-Q1'))
drift = {}
for m in MODELS:
    cc = [d for d in M if d['model'] == m]
    a0, b0, _, _ = ols([d['o_compl'] for d in cc], [d['o_lat'] / 1000.0 for d in cc])
    v = []
    for d in cc:
        k = (d['qid'], d['model'])
        if k not in ts: continue
        ov = d['g_lat'] / 1000.0 - (a0 + b0 * d['g_compl'])
        v.append(((ts[k][0] - t0).total_seconds(), ov, ts[k][1]))
    v.sort()
    n = len(v); qs = [v[i * n // 4:(i + 1) * n // 4] for i in range(4)]
    ms = [median([x[1] for x in qq]) for qq in qs]
    print('%-8s %7d %9.2f %9.2f %9.2f %9.2f %+10.2f' % (SHORT[m], n, ms[0], ms[1], ms[2], ms[3], ms[3] - ms[0]))
    drift[SHORT[m]] = dict(quartile_medians=ms, delta=ms[3] - ms[0], series=v)

# pooled permutation test: first-half vs second-half median overhead (within model, pooled)
allv = []
for m in MODELS:
    v = drift[SHORT[m]]['series']
    n = len(v)
    for i, x in enumerate(v): allv.append((0 if i < n // 2 else 1, x[1]))
obs = median([x[1] for x in allv if x[0] == 1]) - median([x[1] for x in allv if x[0] == 0])
lab = [x[0] for x in allv]; val = [x[1] for x in allv]
rng = random.Random(555); NP = 10000; cnt = 0
for _ in range(NP):
    rng.shuffle(lab)
    d1 = median([v for l, v in zip(lab, val) if l == 1]) - median([v for l, v in zip(lab, val) if l == 0])
    if abs(d1) >= abs(obs) - 1e-12: cnt += 1
print('pooled 2nd-half minus 1st-half median overhead: %+.2f s; permutation p = %.4g'
      % (obs, (cnt + 1) / (NP + 1)))
print('  [method: 10k shuffles of the half labels within the pooled per-cell overheads]')

print('\n=== (C) RETRY CONTAMINATION: GIFT had a 12.4%% attempt failure rate ===')
byai = defaultdict(list)
for m in MODELS:
    cc = [d for d in M if d['model'] == m]
    a0, b0, _, _ = ols([d['o_compl'] for d in cc], [d['o_lat'] / 1000.0 for d in cc])
    for d in cc:
        k = (d['qid'], d['model'])
        if k not in ts: continue
        byai[ts[k][1] > 0].append(d['g_lat'] / 1000.0 - (a0 + b0 * d['g_compl']))
for f, name in [(False, 'first attempt'), (True, 'after >=1 retry')]:
    if byai[f]:
        print('  %-16s n=%4d  median overhead %.2f s' % (name, len(byai[f]), median(byai[f])))
nfail = list(c.execute('''select count(*) from provider_attempts pa
    join logical_calls lc on lc.id=pa.logical_call_id join experiments e on e.id=lc.experiment_id
    where e.name='expA_gift_310726' and pa.status_code!=200'''))[0][0]
print('  GIFT non-200 attempts in the whole arm: %d' % nfail)

print('\n=== (D) COVERAGE CAVEAT: are the GIFT-covered items latency/token-atypical on OR? ===')
_cv = json.load(open(BASE + 'gift_coverage.json'))
cov = set(_cv['complete_all_models'])
q3 = '''select q.question_id, lc.model, pa.latency_ms, pa.prompt_tokens, pa.completion_tokens
        from scores s join parsed_answers pn on pn.id=s.parsed_answer_id
        join provider_attempts pa on pa.id=pn.provider_attempt_id
        join logical_calls lc on lc.id=s.logical_call_id
        join experiments e on e.id=lc.experiment_id join questions q on q.id=lc.question_id
        where e.name='expA_or_310726' '''
grp = defaultdict(list)
for qid, m, lat, pt, ct in c.execute(q3):
    grp[(m, qid in cov)].append((lat / 1000.0, pt, ct))
print('%-8s %10s %6s %10s %11s %11s' % ('model', 'set', 'n', 'medLat_s', 'medPrompt', 'medCompl'))
covp = {}
for m in MODELS:
    for flag, nm in [(True, 'covered'), (False, 'uncovered')]:
        v = grp[(m, flag)]
        if not v: continue
        print('%-8s %10s %6d %10.2f %11.0f %11.0f'
              % (SHORT[m], nm, len(v), median([x[0] for x in v]),
                 median([x[1] for x in v]), median([x[2] for x in v])))
        covp['%s|%s' % (SHORT[m], nm)] = dict(n=len(v), lat=median([x[0] for x in v]),
                                              p=median([x[1] for x in v]), ct=median([x[2] for x in v]))
    a = [x[2] for x in grp[(m, True)]]; b = [x[2] for x in grp[(m, False)]]
    obs2 = median(a) - median(b)
    allx = a + b; nA = len(a); rngp = random.Random(808); cc2 = 0; NP2 = 10000
    for _ in range(NP2):
        rngp.shuffle(allx)
        if abs(median(allx[:nA]) - median(allx[nA:])) >= abs(obs2) - 1e-12: cc2 += 1
    print('%-8s   completion-token gap covered-uncovered: %+.0f tok, permutation p = %.4g (10k shuffles)'
          % ('', obs2, (cc2 + 1) / (NP2 + 1)))

json.dump(dict(honest=res, drift={k: v['quartile_medians'] for k, v in drift.items()},
               coverage=covp), open(BASE + 'ca_rtx_03_out.json', 'w'), indent=1)

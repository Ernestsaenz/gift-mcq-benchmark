#!/usr/bin/env python
"""ca_rtx_04: THE DECISIVE TEST.
The claim's model predicts GIFT generation time with the OpenRouter arm's per-token slope,
i.e. it ASSUMES GIFT decodes at the same speed per output token. Everything that assumption
gets wrong lands in the residual and is then relabelled 'retrieval'.
Fit each arm's own decode slope and compare. A slower GIFT decode is GENERATION time, and it
scales with output length -- the opposite of a fixed pipeline tax.
Also: overhead as a share of latency, and how the coverage prefix biases that share.
"""
import json, math, random, sqlite3
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
DB = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite'
M = json.load(open(BASE + 'ca_rtx_matched.json'))
MODELS = sorted(set(d['model'] for d in M))
SHORT = {'google/gemini-3.6-flash': 'gemini', 'google/gemma-4-26b-a4b-it': 'gemma',
         'qwen/qwen3.6-35b-a3b': 'qwen', 'z-ai/glm-5.2': 'glm'}
CLAIM = {'gemini': 11.86, 'gemma': 13.17, 'qwen': 9.26, 'glm': 12.49}


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
    return my - b * mx, b


print('=== (1) PER-ARM DECODE SLOPE: seconds of latency per OUTPUT token, fitted separately ===')
print('    (simple OLS lat_s ~ completion_tokens inside each arm, same 311 items, same model)')
print('%-8s %12s %12s %8s %26s' % ('model', 'OR ms/tok', 'GIFT ms/tok', 'ratio', 'diff 95% cluster-boot CI'))
dec = {}
for m in MODELS:
    cc = [d for d in M if d['model'] == m]
    ao, bo = ols([d['o_compl'] for d in cc], [d['o_lat'] / 1000.0 for d in cc])
    ag, bg = ols([d['g_compl'] for d in cc], [d['g_lat'] / 1000.0 for d in cc])
    byc = defaultdict(list)
    for d in cc: byc[d['cluster']].append(d)
    keys = list(byc); rng = random.Random(2468); reps = []
    for _ in range(5000):
        s = []
        for _ in range(len(keys)): s.extend(byc[keys[rng.randrange(len(keys))]])
        _, b1 = ols([d['o_compl'] for d in s], [d['o_lat'] / 1000.0 for d in s])
        _, b2 = ols([d['g_compl'] for d in s], [d['g_lat'] / 1000.0 for d in s])
        reps.append((b2 - b1) * 1000)
    lo, hi = quant(reps, .025), quant(reps, .975)
    print('%-8s %12.3f %12.3f %8.2f   [%+7.3f, %+7.3f] %s'
          % (SHORT[m], bo * 1000, bg * 1000, bg / bo if bo else float('nan'), lo, hi,
             'EXCLUDES 0' if lo > 0 or hi < 0 else '(includes 0)'))
    dec[SHORT[m]] = dict(b_or=bo, b_gift=bg, diff_ci=[lo, hi],
                         med_g_compl=median([d['g_compl'] for d in cc]))

print('\n=== (2) HOW MUCH OF THE CLAIMED "RETRIEVAL TAX" IS JUST SLOWER DECODING? ===')
print('    extra decode seconds = (b_GIFT - b_OR) * median GIFT completion tokens')
print('%-8s %14s %16s %14s %12s' % ('model', 'med_G_compl', 'extra_decode_s', 'claimed_ovh_s', 'share'))
tot = {}
for m in MODELS:
    s = SHORT[m]; d = dec[s]
    ex = (d['b_gift'] - d['b_or']) * d['med_g_compl']
    print('%-8s %14.0f %16.2f %14.2f %11.0f%%' % (s, d['med_g_compl'], ex, CLAIM[s], 100 * ex / CLAIM[s]))
    tot[s] = ex

print('\n=== (3) SHARE OF GIFT LATENCY THE "TAX" ACCOUNTS FOR, AND THE COVERAGE PREFIX ===')
print('%-8s %12s %14s %14s' % ('model', 'med_G_lat_s', 'med_overhead_s', 'ovh/lat'))
for m in MODELS:
    cc = [d for d in M if d['model'] == m]
    ao, bo = ols([d['o_compl'] for d in cc], [d['o_lat'] / 1000.0 for d in cc])
    ov = [d['g_lat'] / 1000.0 - (ao + bo * d['g_compl']) for d in cc]
    gl = median([d['g_lat'] / 1000.0 for d in cc])
    print('%-8s %12.2f %14.2f %13.0f%%' % (SHORT[m], gl, median(ov), 100 * median(ov) / gl))

print('\n    The 311 analysed items are the GIFT-covered prefix. On OpenRouter those items need')
print('    FEWER output tokens than the 155 GIFT never reached (ca_rtx_03 D). Re-express the tax')
print('    as a share of latency at the uncovered items\' generation demand:')
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)
_cv = json.load(open(BASE + 'gift_coverage.json'))
cov = set(_cv['complete_all_models'])
q3 = '''select q.question_id, lc.model, pa.completion_tokens
        from scores s join parsed_answers pn on pn.id=s.parsed_answer_id
        join provider_attempts pa on pa.id=pn.provider_attempt_id
        join logical_calls lc on lc.id=s.logical_call_id
        join experiments e on e.id=lc.experiment_id join questions q on q.id=lc.question_id
        where e.name='expA_or_310726' '''
gg = defaultdict(list)
for qid, m, ct in c.execute(q3): gg[(m, qid in cov)].append(ct)
print('%-8s %14s %14s %12s %14s %14s' % ('model', 'medC_covered', 'medC_uncov', 'uplift', 'ovh/lat_cov', 'ovh/lat_proj'))
for m in MODELS:
    cc = [d for d in M if d['model'] == m]
    ao, bo = ols([d['o_compl'] for d in cc], [d['o_lat'] / 1000.0 for d in cc])
    ov = median([d['g_lat'] / 1000.0 - (ao + bo * d['g_compl']) for d in cc])
    gl = median([d['g_lat'] / 1000.0 for d in cc])
    mc, mu = median(gg[(m, True)]), median(gg[(m, False)])
    upl = mu / mc if mc else float('nan')
    # project GIFT latency on an uncovered-like item: same tax + GIFT decode scaled by uplift
    bg = dec[SHORT[m]]['b_gift']
    gl_proj = gl + bg * (mu - mc) * (dec[SHORT[m]]['med_g_compl'] / mc if mc else 1)
    print('%-8s %14.0f %14.0f %12.2fx %13.0f%% %13.0f%%'
          % (SHORT[m], mc, mu, upl, 100 * ov / gl, 100 * ov / gl_proj))

print('\n=== (4) UNMEASURABILITY: what fraction of the dataset has ANY GIFT latency at all? ===')
tot_items = 474
print('    items with GIFT latency on all 4 models : 319  (%.0f%% of %d)' % (100 * 319 / tot_items, tot_items))
print('    items in the analysed cross-arm set     : 311')
print('    items with NO GIFT timing whatsoever    : 155  (%.0f%%)' % (100 * 155 / tot_items))
print('    experiment B on GIFT                    : 0 cells -- the retrieval tax under the')
print('                                              NOTA rewrite is entirely unobserved')
json.dump(dict(decode=dec, extra_decode_s=tot), open(BASE + 'ca_rtx_04_out.json', 'w'), indent=1)

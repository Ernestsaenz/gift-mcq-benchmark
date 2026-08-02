#!/usr/bin/env python
"""ca_rtx_02: does the 'fixed retrieval tax, not generation' decomposition survive?
(A) The claim's model regresses OR latency on COMPLETION tokens only, so the intercept is
    pinned at OR's ~900-token prompt. Refit with prompt tokens included and see how much of
    the residual is prefill compute.
(B) Within the GIFT arm itself: if the tax were fixed, GIFT latency should not scale with
    GIFT prompt tokens. Test it.
(C) Is the 'overhead' fixed at all? dispersion, cross-model heterogeneity, drift over the run.
"""
import json, math, random, sqlite3
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
DB = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite'
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


def mlr(X, y):
    """OLS with intercept via normal equations + Gauss-Jordan. X: list of feature rows."""
    k = len(X[0]) + 1
    A = [[0.0] * k for _ in range(k)]; bvec = [0.0] * k
    for xi, yi in zip(X, y):
        row = [1.0] + list(xi)
        for i in range(k):
            bvec[i] += row[i] * yi
            for j in range(k): A[i][j] += row[i] * row[j]
    # gauss-jordan
    m = [A[i][:] + [bvec[i]] for i in range(k)]
    for col in range(k):
        piv = max(range(col, k), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12: return None
        m[col], m[piv] = m[piv], m[col]
        pv = m[col][col]
        m[col] = [v / pv for v in m[col]]
        for r in range(k):
            if r != col and m[r][col]:
                f = m[r][col]
                m[r] = [a - f * b for a, b in zip(m[r], m[col])]
    beta = [m[i][k] for i in range(k)]
    my = sum(y) / len(y)
    ssr = sum((yi - (beta[0] + sum(b * x for b, x in zip(beta[1:], xi)))) ** 2 for xi, yi in zip(X, y))
    sst = sum((yi - my) ** 2 for yi in y)
    return beta, 1 - ssr / sst


def boot_ci_stat(items, stat, B=5000, seed=31337, byc=None):
    """cluster bootstrap CI; items are (clusterkey, payload)."""
    g = defaultdict(list)
    for ck, p in items: g[ck].append(p)
    keys = list(g); rng = random.Random(seed); reps = []
    for _ in range(B):
        s = []
        for _ in range(len(keys)): s.extend(g[keys[rng.randrange(len(keys))]])
        v = stat(s)
        if v is not None: reps.append(v)
    return quant(reps, .025), quant(reps, .975)


print('=== (A) OR-arm latency model: completion-only (claim) vs completion+prompt ===')
print('OR prompt-token range constrains identification -- report it.')
print('%-8s %7s %7s %7s %8s %9s %9s %8s' % ('model', 'Pmin', 'Pmed', 'Pmax', 'R2_1var', 'R2_2var', 'b_prompt', 'R2gain'))
bp = {}
for m in MODELS:
    cc = [d for d in M if d['model'] == m]
    y = [d['o_lat'] / 1000.0 for d in cc]
    r1 = mlr([[d['o_compl']] for d in cc], y)
    r2 = mlr([[d['o_compl'], d['o_prompt']] for d in cc], y)
    P = [d['o_prompt'] for d in cc]
    print('%-8s %7d %7.0f %7d %8.3f %9.3f %9.5f %8.3f'
          % (SHORT[m], min(P), median(P), max(P), r1[1], r2[1], r2[0][2], r2[1] - r1[1]))
    bp[SHORT[m]] = dict(b_prompt_s_per_tok=r2[0][2], b_compl=r2[0][1], a=r2[0][0],
                        r2_1=r1[1], r2_2=r2[1], or_p_med=median(P),
                        gift_p_med=median([d['g_prompt'] for d in cc]))

print('\n  IMPLIED PREFILL TIME for the extra GIFT prompt tokens, at the OR-arm b_prompt:')
print('  (extrapolation: GIFT prompts sit ~5.6x beyond the fitted OR prompt range -- an')
print('   out-of-support extrapolation, so this is an ORDER-OF-MAGNITUDE probe, not an estimate)')
print('%-8s %14s %14s %12s %14s' % ('model', 'extra_P_tokens', 'implied_s', 'claimed_ovh', 'share_of_ovh'))
CLAIM = {'gemini': 11.86, 'gemma': 13.17, 'qwen': 9.26, 'glm': 12.49}
for m in MODELS:
    s = SHORT[m]; d = bp[s]
    extra = d['gift_p_med'] - d['or_p_med']
    imp = d['b_prompt_s_per_tok'] * extra
    print('%-8s %14.0f %14.2f %12.2f %13.0f%%' % (s, extra, imp, CLAIM[s], 100 * imp / CLAIM[s]))

print('\n=== (B) WITHIN THE GIFT ARM: does latency scale with the retrieved-prompt size? ===')
print('If the tax were a FIXED retrieval constant, b_prompt inside GIFT would be ~0.')
print('%-8s %8s %8s %8s %11s %13s %10s' % ('model', 'Pmin', 'Pmed', 'Pmax', 'b_compl_ms', 'b_prompt_ms', 'R2'))
gin = {}
for m in MODELS:
    cc = [d for d in M if d['model'] == m]
    y = [d['g_lat'] / 1000.0 for d in cc]
    r2 = mlr([[d['g_compl'], d['g_prompt']] for d in cc], y)
    P = [d['g_prompt'] for d in cc]
    print('%-8s %8d %8.0f %8d %11.4f %13.4f %10.3f'
          % (SHORT[m], min(P), median(P), max(P), r2[0][1] * 1000, r2[0][2] * 1000, r2[1]))
    gin[SHORT[m]] = dict(b_compl=r2[0][1], b_prompt=r2[0][2], r2=r2[1],
                         pmin=min(P), pmax=max(P), pmed=median(P))
    # cluster-bootstrap CI on b_prompt inside GIFT
    items = [(d['cluster'], d) for d in cc]

    def st(s, _m=m):
        r = mlr([[x['g_compl'], x['g_prompt']] for x in s], [x['g_lat'] / 1000.0 for x in s])
        return None if r is None else r[0][2] * 1000
    lo, hi = boot_ci_stat(items, st, B=2000, seed=777)
    print('%-8s   b_prompt 95%% cluster-bootstrap CI (B=2000): [%.4f, %.4f] ms/prompt-token%s'
          % ('', lo, hi, '   <-- EXCLUDES 0' if lo * hi > 0 else '   (includes 0)'))
    gin[SHORT[m]]['b_prompt_ci'] = [lo, hi]
    # what the fitted prompt slope implies across the observed GIFT prompt span
    print('%-8s   implied latency swing across observed GIFT prompt span (%d->%d tok): %.2f s'
          % ('', min(P), max(P), r2[0][2] * (max(P) - min(P))))

print('\n=== (C) IS THE OVERHEAD "FIXED"? dispersion and heterogeneity ===')
rows = [r for r in json.load(open(BASE + 'cross_arm_A.json')) if r['analysis_include']]
byqm = {(r['question_id'], r['model']): r for r in rows}


def ols1(x, y):
    n = len(x); mx = sum(x) / n; my = sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    b = sxy / sxx if sxx else 0.0
    return my - b * mx, b


print('%-8s %9s %9s %9s %9s %9s %11s' % ('model', 'p10', 'p25', 'median', 'p75', 'p90', 'IQR/median'))
ovh_all = {}
for m in MODELS:
    cc = [d for d in M if d['model'] == m]
    a, b = ols1([d['o_compl'] for d in cc], [d['o_lat'] / 1000.0 for d in cc])
    ov = [d['g_lat'] / 1000.0 - (a + b * d['g_compl']) for d in cc]
    ovh_all[SHORT[m]] = list(zip([d['cluster'] for d in cc], ov, [d['g_prompt'] for d in cc],
                                 [d['qid'] for d in cc]))
    print('%-8s %9.2f %9.2f %9.2f %9.2f %9.2f %11.2f'
          % (SHORT[m], quant(ov, .10), quant(ov, .25), median(ov), quant(ov, .75), quant(ov, .90),
             (quant(ov, .75) - quant(ov, .25)) / median(ov)))

# cross-model heterogeneity: permutation test on max-min of per-model median overhead
meds = {k: median([v[1] for v in ovh_all[k]]) for k in ovh_all}
obs = max(meds.values()) - min(meds.values())
pool = [(k, v[1]) for k in ovh_all for v in ovh_all[k]]
sizes = [len(ovh_all[k]) for k in ovh_all]
rng = random.Random(9001); NP = 10000; cnt = 0
vals = [v for _, v in pool]
for _ in range(NP):
    rng.shuffle(vals)
    i = 0; ms = []
    for s in sizes:
        ms.append(median(vals[i:i + s])); i += s
    if max(ms) - min(ms) >= obs - 1e-12: cnt += 1
print('\nper-model median overhead: %s' % {k: round(v, 2) for k, v in meds.items()})
print('spread max-min = %.2f s (%.0f%% of the smallest); permutation p = %.4g'
      % (obs, 100 * obs / min(meds.values()), (cnt + 1) / (NP + 1)))
print('  [method: 10k label shuffles of the pooled per-cell overheads, statistic = max-min of')
print('   the four group medians. A truly FIXED pipeline tax would be model-invariant.]')

# overhead vs GIFT prompt tokens (Spearman, permutation p)
print('\n=== overhead vs retrieved-context size (Spearman rho, 10k cluster-permutation) ===')


def spearman(x, y):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v); i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]: j += 1
            avg = (i + j) / 2.0 + 1
            for k2 in range(i, j + 1): r[order[k2]] = avg
            i = j + 1
        return r
    rx, ry = rank(x), rank(y)
    n = len(x); mx = sum(rx) / n; my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


for k in ['gemini', 'gemma', 'qwen', 'glm']:
    v = ovh_all[k]
    x = [t[2] for t in v]; y = [t[1] for t in v]
    rho = spearman(x, y)
    # cluster-preserving permutation: shuffle y across clusters
    byc = defaultdict(list)
    for t in v: byc[t[0]].append(t)
    ckeys = list(byc)
    rngp = random.Random(1234); c2 = 0; NP2 = 10000
    for _ in range(NP2):
        rngp.shuffle(ckeys)
        yy = [t[1] for ck in ckeys for t in byc[ck]]
        xx = [t[2] for ck in byc for t in byc[ck]]
        if abs(spearman(xx, yy)) >= abs(rho) - 1e-12: c2 += 1
    print('  %-8s rho = %+.3f   permutation p = %.4g   (n=%d)' % (k, rho, (c2 + 1) / (NP2 + 1), len(v)))

json.dump(dict(or_prefill=bp, gift_internal=gin,
               model_medians=meds, spread=obs), open(BASE + 'ca_rtx_02_out.json', 'w'), indent=1)

#!/usr/bin/env python
"""Addendum: does any analysis decision actually depend on the shape of the
binary outcome, and do the recommended tests really 'assume normality of
nothing'?  Stdlib only."""
import json, math, random, statistics
from collections import Counter, defaultdict

random.seed(4242)
P = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
d = [r for r in json.load(open(P + 'paired_clean.json')) if r.get('analysis_include') is True]
n = len(d)

print('=== A. WALD (NORMAL-APPROX) INTERVALS ON THE BINARY ENDPOINT ===')
print('If shape "carries no information" it still governs whether the normal')
print('approximation is usable. Check per-model accuracy Wald bounds.\n')
bym = defaultdict(list)
for r in d:
    bym[r['model']].append(r)
print('  %-26s %5s %7s %8s %8s   %s' % ('model', 'n', 'p_A', 'waldLo', 'waldHi', 'flag'))
for m in sorted(bym):
    rows = bym[m]
    k = sum(r['A_correct'] for r in rows)
    N = len(rows)
    p = k / N
    se = math.sqrt(p * (1 - p) / N)
    lo, hi = p - 1.96 * se, p + 1.96 * se
    flag = 'WALD EXCEEDS 1.0' if hi > 1 else ''
    print('  %-26s %5d %7.4f %8.4f %8.4f   %s' % (m, N, p, lo, hi, flag))

print('\n  Same for B_correct:')
for m in sorted(bym):
    rows = bym[m]
    k = sum(r['B_correct'] for r in rows)
    N = len(rows)
    p = k / N
    se = math.sqrt(p * (1 - p) / N)
    print('  %-26s %5d %7.4f %8.4f %8.4f' % (m, N, p, k / N - 1.96 * se, k / N + 1.96 * se))

print('\n=== B. CLUSTER-LEVEL RANDOMISATION TEST vs NAIVE McNEMAR ===')
print('McNemar / exact conditional binomial treat the 1299 cells as 1299')
print('independent pairs. They are not: 325 items x 4 models, 208 clusters.')
tab = Counter((r['A_correct'], r['B_correct']) for r in d)
b10, c01 = tab[(1, 0)], tab[(0, 1)]
obs_stat = (b10 - c01) / n
print('  observed RD = %.6f  (b=%d, c=%d, nd=%d)' % (obs_stat, b10, c01, b10 + c01))

# randomisation: under H0 of exchangeability of the A/B labels *within a
# cluster*, flip the whole cluster's A/B assignment together.
byclu = defaultdict(list)
for r in d:
    byclu[r['cluster']].append((r['A_correct'], r['B_correct']))
clusters = list(byclu.values())
REPS = 20000
cnt = 0
null = []
for _ in range(REPS):
    s = 0
    for cl in clusters:
        if random.random() < 0.5:
            s += sum(x - y for x, y in cl)
        else:
            s += sum(y - x for x, y in cl)
    st = s / n
    null.append(st)
    if abs(st) >= abs(obs_stat) - 1e-12:
        cnt += 1
p_perm = (cnt + 1) / (REPS + 1)
print('  cluster-flip randomisation p = %.3e  (%d/%d reps as extreme; null sd=%.5f)'
      % (p_perm, cnt, REPS, statistics.stdev(null)))
print('  -> monte-carlo floor is 1/(REPS+1) = %.2e, so this only shows p < that.'
      % (1 / (REPS + 1)))
print('  null sd under cluster-flip = %.5f  vs  naive paired SE = %.5f  (ratio %.2f)'
      % (statistics.stdev(null),
         math.sqrt(b10 + c01 - (b10 - c01) ** 2 / n) / n,
         statistics.stdev(null) / (math.sqrt(b10 + c01 - (b10 - c01) ** 2 / n) / n)))

print('\n=== C. DOES McNEMAR "ASSUME NORMALITY OF NOTHING"? ===')


def logbinom(k, N):
    return math.lgamma(N + 1) - math.lgamma(k + 1) - math.lgamma(N - k + 1)


def exact_two_sided(k, N):
    lp = [logbinom(i, N) - N * math.log(2) for i in range(N + 1)]
    obs = lp[k]
    mx = max(lp)
    tot = sum(math.exp(v - mx) for v in lp)
    sel = sum(math.exp(v - mx) for v in lp if v <= obs + 1e-7)
    return sel / tot


nd = b10 + c01
pe = exact_two_sided(min(b10, c01), nd)
chi2 = (abs(b10 - c01) - 1) ** 2 / nd
pa = math.erfc(math.sqrt(chi2 / 2))
print('  exact conditional binomial p      = %.4e' % pe)
print("  McNemar chi2(cc) p (normal approx)= %.4e" % pa)
print('  ratio approx/exact                = %.1f x' % (pa / pe))
print('  The asymptotic McNemar statistic IS a normal approximation to')
print('  Binom(nd, 1/2); the two disagree by that factor in the far tail.')

print('\n  Smaller-nd demo (where the approximation actually matters for a verdict):')
print('  %6s %6s %14s %14s' % ('nd', 'b', 'exact p', 'chi2(cc) p'))
for nd_, b_ in ((10, 9), (15, 12), (20, 15), (25, 18), (30, 22)):
    e = exact_two_sided(nd_ - b_, nd_)
    ch = (abs(b_ - (nd_ - b_)) - 1) ** 2 / nd_
    print('  %6d %6d %14.5f %14.5f' % (nd_, b_, e, math.erfc(math.sqrt(ch / 2))))

print('\n=== D. WITHIN-CLUSTER / WITHIN-ITEM DEPENDENCE, QUANTIFIED ===')
# ICC-ish: how concordant are the 4 models on the same item?
byitem = defaultdict(list)
for r in d:
    byitem[r['question_id']].append(r)
full = [v for v in byitem.values() if len(v) == 4]
print('  items with all 4 models present: %d / %d' % (len(full), len(byitem)))
for fld in ('A_correct', 'B_correct'):
    # pairwise agreement across models within an item vs chance
    agree = tot = 0
    for v in full:
        vals = [x[fld] for x in v]
        for i in range(len(vals)):
            for j in range(i + 1, len(vals)):
                tot += 1
                agree += (vals[i] == vals[j])
    pbar = sum(r[fld] for r in d) / n
    chance = pbar ** 2 + (1 - pbar) ** 2
    print('  %s: observed within-item pairwise agreement %.4f vs chance %.4f  (kappa=%.3f)'
          % (fld, agree / tot, chance, (agree / tot - chance) / (1 - chance)))
# between-cluster variance of A accuracy vs binomial expectation
byclu2 = defaultdict(list)
for r in d:
    byclu2[r['cluster']].append(r['A_correct'])
rates, sizes = [], []
for k, v in byclu2.items():
    rates.append(sum(v) / len(v))
    sizes.append(len(v))
pbar = sum(r['A_correct'] for r in d) / n
obsvar = statistics.pvariance(rates)
expvar = statistics.mean([pbar * (1 - pbar) / s for s in sizes])
print('  cluster-level accuracy variance: observed %.5f vs binomial-only %.5f (ratio %.2f)'
      % (obsvar, expvar, obsvar / expvar))

#!/usr/bin/env python
"""Independent recomputation of the 'normality-and-scale' claim.

Stdlib only. No numpy/scipy/pandas.
"""
import json, math, random, statistics
from collections import Counter, defaultdict

random.seed(20260731)

P = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
recs = json.load(open(P + 'paired_clean.json'))
meta = json.load(open(P + 'dataset_meta.json'))
print('meta:', json.dumps(meta, indent=1)[:800])

d = [r for r in recs if r.get('analysis_include') is True]
print('\n=== 0. SHAPE ===')
print('raw records         :', len(recs))
print('analysis_include    :', len(d))
print('distinct items      :', len({r['question_id'] for r in d}))
print('distinct clusters   :', len({r['cluster'] for r in d}))
print('distinct models     :', len({r['model'] for r in d}))
print('models              :', sorted({r['model'] for r in d}))

A = [r['A_correct'] for r in d]
B = [r['B_correct'] for r in d]
n = len(A)
print('value sets: A=%s B=%s' % (sorted(set(A)), sorted(set(B))))


# ---------- moment machinery ----------
def moments_population(x):
    """m2, m3, m4 about the mean with 1/n denominators (the 'population' /
    method-of-moments estimator, i.e. scipy.stats.skew(bias=True),
    kurtosis(fisher=True, bias=True))."""
    m = sum(x) / len(x)
    n_ = len(x)
    m2 = sum((v - m) ** 2 for v in x) / n_
    m3 = sum((v - m) ** 3 for v in x) / n_
    m4 = sum((v - m) ** 4 for v in x) / n_
    g1 = m3 / m2 ** 1.5
    g2 = m4 / m2 ** 2 - 3.0
    return m, m2, g1, g2


def moments_sample_corrected(x):
    """G1 (Fisher-Pearson adjusted, Excel SKEW) and G2 (Excel KURT) --
    the unbiased-ish estimators most software reports by default in R
    (e1071 type 2) / Excel."""
    n_ = len(x)
    m, m2, g1, g2 = moments_population(x)
    G1 = g1 * math.sqrt(n_ * (n_ - 1)) / (n_ - 2)
    G2 = ((n_ - 1) * ((n_ + 1) * g2 + 6)) / ((n_ - 2) * (n_ - 3))
    return G1, G2


def bern_theory(p):
    q = 1 - p
    return (1 - 2 * p) / math.sqrt(p * q), (1 - 6 * p * q) / (p * q)


print('\n=== 1. MOMENT IDENTITY (claim: observed == closed form to 4 dp) ===')
for name, x in (('A_correct', A), ('B_correct', B)):
    m, m2, g1, g2 = moments_population(x)
    tg1, tg2 = bern_theory(m)
    G1, G2 = moments_sample_corrected(x)
    print('\n%s  n=%d  successes=%d  p=%.10f' % (name, len(x), sum(x), m))
    print('  variance m2      = %.10f   theory p(1-p) = %.10f  absdiff=%.3e'
          % (m2, m * (1 - m), abs(m2 - m * (1 - m))))
    print('  skew   (pop g1)  = %.10f   theory        = %.10f  absdiff=%.3e'
          % (g1, tg1, abs(g1 - tg1)))
    print('  exkurt (pop g2)  = %.10f   theory        = %.10f  absdiff=%.3e'
          % (g2, tg2, abs(g2 - tg2)))
    print('  claim printed    : skew %.4f / exkurt %.4f' % (g1, g2))
    print('  sample-corrected : G1 = %.10f (diff from theory %.5f)' % (G1, G1 - tg1))
    print('                     G2 = %.10f (diff from theory %.5f)' % (G2, G2 - tg2))

print('\n=== 2. IS THE "VERIFICATION" CAPABLE OF FAILING? ===')
print('Test: run the same check on adversarial binary vectors -- wrong p, extreme')
print('clustering, deterministic patterns, tiny n. If the identity is algebraic it')
print('holds for ALL of them and the check has zero diagnostic content.')
worst = 0.0
cases = []
# (a) iid Bernoulli at many p
for p in (0.01, 0.1, 0.3, 0.5, 0.73, 0.9, 0.99):
    cases.append(('iid p=%.2f' % p, [1 if random.random() < p else 0 for _ in range(1299)]))
# (b) maximally clustered: 208 blocks each all-0 or all-1
blk = []
for _ in range(208):
    v = 1 if random.random() < 0.9 else 0
    blk += [v] * 6
cases.append(('perfectly clustered blocks', blk))
# (c) deterministic alternating
cases.append(('alternating 0101...', [i % 2 for i in range(1299)]))
# (d) pathological: 1 success in 1299
cases.append(('single success', [1] + [0] * 1298))
# (e) tiny n
cases.append(('n=5', [1, 1, 0, 1, 0]))
for label, x in cases:
    m, m2, g1, g2 = moments_population(x)
    if m in (0.0, 1.0):
        print('  %-28s p=%.4f  degenerate (m2=0), moments undefined' % (label, m))
        continue
    tg1, tg2 = bern_theory(m)
    dd = max(abs(g1 - tg1), abs(g2 - tg2))
    worst = max(worst, dd)
    print('  %-28s p=%.4f  max|observed-theory| = %.3e' % (label, m, dd))
print('  WORST DEVIATION ACROSS ALL ADVERSARIAL CASES: %.3e' % worst)

print('\n=== 3. PAIRED 2x2 ===')
tab = Counter((r['A_correct'], r['B_correct']) for r in d)
a11, b10, c01, d00 = tab[(1, 1)], tab[(1, 0)], tab[(0, 1)], tab[(0, 0)]
print('  (A=1,B=1)=%d  (1,0)=%d  (0,1)=%d  (0,0)=%d  total=%d'
      % (a11, b10, c01, d00, a11 + b10 + c01 + d00))
print('  p_A = %d/%d = %.6f ; p_B = %d/%d = %.6f' % (a11 + b10, n, (a11 + b10) / n,
                                                     a11 + c01, n, (a11 + c01) / n))
RD = (b10 - c01) / n
print('  risk difference A-B = %.6f' % RD)

print('\n=== 4. DOES THE *INDEPENDENCE* ASSUMPTION BIND? (the one actually at risk) ===')


def logbinom(k, N):
    return (math.lgamma(N + 1) - math.lgamma(k + 1) - math.lgamma(N - k + 1))


def exact_binom_two_sided_p(k, N, p=0.5):
    """Exact two-sided binomial test, small-p method (sum of all outcomes with
    likelihood <= observed). Computed in logs; no scipy."""
    lp = [logbinom(i, N) + i * math.log(p) + (N - i) * math.log(1 - p) for i in range(N + 1)]
    obs = lp[k]
    tol = 1e-7
    mx = max(lp)
    tot = sum(math.exp(v - mx) for v in lp)
    sel = sum(math.exp(v - mx) for v in lp if v <= obs + tol)
    return sel / tot


nd = b10 + c01
p_exact = exact_binom_two_sided_p(min(b10, c01), nd, 0.5)
print('  discordant pairs nd = %d (b=%d, c=%d)' % (nd, b10, c01))
print('  exact conditional binomial two-sided p = %.6e' % p_exact)
chi2_cc = (abs(b10 - c01) - 1) ** 2 / nd
print("  McNemar chi2 w/ continuity correction = %.2f (1 df)" % chi2_cc)
print('  -> chi2 p via erfc (normal approx to the binomial): %.3e'
      % math.erfc(math.sqrt(chi2_cc / 2)))

# naive (independent-cells) SE for the paired risk difference
se_naive = math.sqrt(b10 + c01 - (b10 - c01) ** 2 / n) / n
print('  naive paired SE(RD) assuming 1299 independent cells = %.6f' % se_naive)
print('    -> 95%% CI %.4f .. %.4f' % (RD - 1.96 * se_naive, RD + 1.96 * se_naive))

# cluster bootstrap: resample the 208 clusters with replacement, carrying all
# item x model rows in each cluster together (handles item nesting AND the
# fact that the same items are reused across the 4 models).
byclu = defaultdict(list)
for r in d:
    byclu[r['cluster']].append((r['A_correct'], r['B_correct']))
clusters = list(byclu.values())
K = len(clusters)
boot = []
for _ in range(4000):
    sa = sb = m_ = 0
    for _ in range(K):
        for (x, y) in clusters[random.randrange(K)]:
            sa += x
            sb += y
            m_ += 1
    boot.append((sa - sb) / m_)
se_clu = statistics.stdev(boot)
boot.sort()
lo = boot[int(0.025 * len(boot))]
hi = boot[int(0.975 * len(boot)) - 1]
print('  cluster bootstrap SE(RD) over %d clusters (4000 reps) = %.6f' % (K, se_clu))
print('    -> 95%% percentile CI %.4f .. %.4f' % (lo, hi))
print('  DESIGN-EFFECT on the SE = %.3f  (variance inflation %.3f)'
      % (se_clu / se_naive, (se_clu / se_naive) ** 2))

# how much of the dependence is the model crossing vs the clustering?
byitem = defaultdict(list)
for r in d:
    byitem[r['question_id']].append((r['A_correct'], r['B_correct']))
items = list(byitem.values())
I = len(items)
boot_i = []
for _ in range(4000):
    sa = sb = m_ = 0
    for _ in range(I):
        for (x, y) in items[random.randrange(I)]:
            sa += x
            sb += y
            m_ += 1
    boot_i.append((sa - sb) / m_)
se_item = statistics.stdev(boot_i)
print('  item bootstrap SE(RD) over %d items                    = %.6f (ratio %.3f)'
      % (I, se_item, se_item / se_naive))

print('\n=== 5. IS NORMALITY LIVE ANYWHERE IN THIS DATASET? (secondary endpoints) ===')
for key in ('A_tokens', 'B_tokens', 'A_latency_ms', 'B_latency_ms', 'qlen'):
    x = [r[key] for r in d if r.get(key) is not None]
    if not x:
        continue
    m, m2, g1, g2 = moments_population(x)
    xs = sorted(x)
    print('  %-13s n=%4d mean=%9.1f sd=%9.1f skew=%7.3f exkurt=%8.3f  min=%d med=%d max=%d'
          % (key, len(x), m, math.sqrt(m2), g1, g2, xs[0], xs[len(xs) // 2], xs[-1]))
print('  (these are continuous / count-valued: their skewness is NOT pinned by a')
print('   mean, so for THESE variables shape is a real, testable, decision-relevant')
print('   question -- the binary-endpoint argument does not transfer to them.)')

print('\n=== 6. CLUSTER-LEVEL / ITEM-LEVEL AGGREGATES ARE NOT BERNOULLI ===')
cl_rates = []
for k, v in byclu.items():
    cl_rates.append(sum(x for x, y in v) / len(v))
m, m2, g1, g2 = moments_population(cl_rates)
tg1, tg2 = bern_theory(m)
print('  cluster-mean A accuracy: n=%d mean=%.4f sd=%.4f skew=%.4f exkurt=%.4f'
      % (len(cl_rates), m, math.sqrt(m2), g1, g2))
print('  Bernoulli closed form at that mean would be skew=%.4f exkurt=%.4f'
      % (tg1, tg2))
print('  -> identity FAILS by %.3f / %.3f once you leave the 0/1 scale.'
      % (abs(g1 - tg1), abs(g2 - tg2)))
print('  distinct values taken by the cluster-level statistic: %d' % len(set(cl_rates)))

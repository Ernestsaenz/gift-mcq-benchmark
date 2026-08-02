"""
stats_normality_robust.py -- hardening the one finding where normality actually
changes a conclusion: the MEAN COMPLETION-TOKEN DELTA (B - A).

In stats_normality_main.py PART 3c the normal-theory CI excluded 0 while the
cluster-bootstrap percentile CI included it. That is a decision flip caused purely
by the distributional assumption, so it must be checked for stability and for
outlier dependence before being reported.
"""
import json
import math
import random
import statistics as st
from collections import defaultdict
from stats_normlib import moments, phi_sf

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis'
rows = json.load(open(f'{BASE}/paired_clean.json'))
D = [r for r in rows if r['analysis_include']]
Dt = [r['B_tokens'] - r['A_tokens'] for r in D]
N = len(Dt)

by_cluster = defaultdict(list)
for r in D:
    by_cluster[r['cluster']].append(r)
cl_list = list(by_cluster.values())
K = len(cl_list)


def sect(t):
    print('\n' + '=' * 80)
    print(t)
    print('=' * 80)


sect('A. STABILITY OF THE CI DISCREPANCY ACROSS SEEDS')
obsT = st.mean(Dt)
print(f'  observed mean token delta = {obsT:+.3f}   (n={N})')
print(f'\n  {"seed":>8} {"reps":>7} {"boot SE":>9} {"pctile lo":>11} {"pctile hi":>11} '
      f'{"normal lo":>11} {"normal hi":>11} {"pctile CI excl 0?":>18}')
for seed, reps in [(1, 20000), (2, 20000), (3, 20000), (4, 50000), (5, 50000)]:
    random.seed(seed)
    boot = []
    for _ in range(reps):
        s = 0
        cnt = 0
        for _ in range(K):
            g = cl_list[random.randrange(K)]
            for r in g:
                s += r['B_tokens'] - r['A_tokens']
                cnt += 1
        boot.append(s / cnt)
    sd = st.stdev(boot)
    bs = sorted(boot)
    lo, hi = bs[int(0.025 * reps)], bs[int(0.975 * reps)]
    nlo, nhi = obsT - 1.959963985 * sd, obsT + 1.959963985 * sd
    print(f'  {seed:>8} {reps:>7} {sd:9.2f} {lo:+11.2f} {hi:+11.2f} {nlo:+11.2f} {nhi:+11.2f} '
          f'{str(lo > 0):>18}')
print('\n  -> the normal-theory interval always excludes 0; the percentile interval')
print('     sits essentially ON 0. The two procedures disagree about the conclusion.')

sect('B. OUTLIER DEPENDENCE OF THE MEAN TOKEN DELTA')
srt = sorted(range(N), key=lambda i: abs(Dt[i]), reverse=True)
print(f'  mean = {obsT:+.2f}, median = {st.median(Dt):+.1f}')
print(f'\n  {"rank":>5} {"model":>28} {"A_tok":>8} {"B_tok":>8} {"delta":>9} '
      f'{"mean w/o it":>12} {"% shift":>9}')
for k in range(6):
    i = srt[k]
    r = D[i]
    rest = [Dt[j] for j in range(N) if j != i]
    mr = st.mean(rest)
    print(f'  {k+1:>5} {r["model"]:>28} {r["A_tokens"]:8d} {r["B_tokens"]:8d} '
          f'{Dt[i]:+9d} {mr:+12.2f} {100*(mr-obsT)/abs(obsT):+9.1f}%')
for k in (1, 3, 5, 10):
    drop = set(srt[:k])
    rest = [Dt[j] for j in range(N) if j not in drop]
    print(f'  dropping the {k:2d} largest-|delta| cells ({100*k/N:.2f}% of data): '
          f'mean = {st.mean(rest):+8.2f}  (from {obsT:+.2f})')
one = srt[0]
print(f'\n  A SINGLE cell ({D[one]["model"]}, {D[one]["question_id"]}) moves the mean by '
      f'{abs(st.mean([Dt[j] for j in range(N) if j != one]) - obsT):.1f} tokens '
      f'= {100*abs(st.mean([Dt[j] for j in range(N) if j != one]) - obsT)/abs(obsT):.0f}% of the estimate.')

sect('C. WHAT DO ASSUMPTION-FREE TESTS SAY ABOUT THE SAME QUESTION?')
pos = sum(1 for v in Dt if v > 0)
neg = sum(1 for v in Dt if v < 0)
tie = sum(1 for v in Dt if v == 0)


def exact_binom_two_sided(b, n):
    """Exact, in integer/rational arithmetic -- 2**1256 overflows a float."""
    from fractions import Fraction
    obs2 = abs(2 * b - n)          # work in halves to stay integral
    tot = sum(math.comb(n, k) for k in range(n + 1) if abs(2 * k - n) >= obs2)
    return min(1.0, float(Fraction(tot, 2 ** n)))


nsign = pos + neg
p_sign = exact_binom_two_sided(pos, nsign)
print(f'  Sign test (does B use more tokens than A?): B>A {pos}, B<A {neg}, ties {tie}')
print(f'    exact two-sided binomial p = {p_sign:.3e}   -- STRONGLY yes, in DIRECTION')
print('    (this test ignores magnitudes entirely, so no distributional assumption)')

# paired t-test on the mean, for contrast
sd_d = st.stdev(Dt)
se_d = sd_d / math.sqrt(N)
t = obsT / se_d
print(f'\n  Paired t-test on the MEAN delta: t = {t:.3f} (df={N-1}), '
      f'normal-approx two-sided p = {2*phi_sf(abs(t)):.4f}')
print(f'    naive SE = {se_d:.2f}. This is the test whose validity depends on normality')
print(f'    of the mean, and Cochran\'s rule said n>11624 was needed (we have {N}).')

# cluster sign-flip randomization test on the MEAN (assumption-light for the mean)
random.seed(99)
REP = 20000
cl_sums = []
for g in cl_list:
    cl_sums.append(sum(r['B_tokens'] - r['A_tokens'] for r in g))
tot_n = N
obs_mean = sum(cl_sums) / tot_n
cnt = 0
for _ in range(REP):
    s = 0.0
    for cs in cl_sums:
        s += cs if random.random() < 0.5 else -cs
    if abs(s / tot_n) >= abs(obs_mean) - 1e-12:
        cnt += 1
p_perm = (cnt + 1) / (REP + 1)
print(f'\n  Cluster-level sign-flip randomization test on the MEAN ({REP} reps): '
      f'p = {p_perm:.4f}')
print('    (flips the sign of each cluster\'s total delta; respects clustering,')
print('     makes no normality assumption, but still targets the fragile MEAN)')

# cell-level sign flip for contrast
random.seed(98)
cnt = 0
for _ in range(REP):
    s = 0.0
    for v in Dt:
        s += v if random.random() < 0.5 else -v
    if abs(s / N) >= abs(obs_mean) - 1e-12:
        cnt += 1
print(f'  Cell-level sign-flip randomization on the MEAN: p = {(cnt+1)/(REP+1):.4f}')

sect('D. THE MEDIAN / LOG SCALE -- A TARGET THAT IS NOT TAIL-FRAGILE')
# Hodges-Lehmann style: median of the paired differences, cluster-bootstrapped
random.seed(7)
REP = 10000
bmed = []
for _ in range(REP):
    vals = []
    for _ in range(K):
        g = cl_list[random.randrange(K)]
        vals.extend(r['B_tokens'] - r['A_tokens'] for r in g)
    bmed.append(st.median(vals))
bs = sorted(bmed)
print(f'  median paired token delta = {st.median(Dt):+.1f}')
print(f'  cluster-bootstrap 95% percentile CI for the MEDIAN: '
      f'[{bs[int(0.025*REP)]:+.1f}, {bs[int(0.975*REP)]:+.1f}]')
n_, m_, sd_, g1_, g2_ = moments(bmed)
print(f'  bootstrap dist of the median: skew={g1_:+.3f} exkurt={g2_:+.3f}')

# ratio scale: geometric mean ratio B/A
lr = [math.log(r['B_tokens'] / r['A_tokens']) for r in D]
n_, m_, sd_, g1_, g2_ = moments(lr)
print(f'\n  log-ratio log(B_tokens/A_tokens): n={n_} mean={m_:+.4f} sd={sd_:.4f} '
      f'skew={g1_:+.3f} exkurt={g2_:+.3f}')
print(f'  -> geometric mean ratio B/A = {math.exp(m_):.4f} '
      f'({100*(math.exp(m_)-1):+.1f}% tokens under B)')
random.seed(11)
blr = []
for _ in range(REP):
    s = 0.0
    cnt = 0
    for _ in range(K):
        g = cl_list[random.randrange(K)]
        for r in g:
            s += math.log(r['B_tokens'] / r['A_tokens'])
            cnt += 1
    blr.append(s / cnt)
bs = sorted(blr)
lo, hi = bs[int(0.025 * REP)], bs[int(0.975 * REP)]
sdb = st.stdev(blr)
n_b, m_b, _, g1b, g2b = moments(blr)
print(f'  cluster-bootstrap 95% CI for geometric mean ratio: '
      f'[{math.exp(lo):.4f}, {math.exp(hi):.4f}]')
print(f'  normal-theory CI on the log scale: '
      f'[{math.exp(m_-1.959963985*sdb):.4f}, {math.exp(m_+1.959963985*sdb):.4f}]')
print(f'  bootstrap dist on log scale: skew={g1b:+.4f} exkurt={g2b:+.4f}  '
      f'-> these two agree, so the log/ratio target is safe for normal-theory inference')

sect('E. SAME CHECK ON THE ACCURACY ENDPOINT (for contrast)')
print('  Repeat the outlier-influence check on the PRIMARY accuracy delta.')
A = [r['A_correct'] for r in D]
B = [r['B_correct'] for r in D]
obs = st.mean(B) - st.mean(A)
worst = 0.0
for i in range(N):
    d = (sum(B) - B[i]) / (N - 1) - (sum(A) - A[i]) / (N - 1)
    worst = max(worst, abs(d - obs))
print(f'  pooled accuracy delta = {obs:+.5f}')
print(f'  max leave-one-cell-out shift = {worst:.6f} = {100*worst/abs(obs):.3f}% of the estimate')
print('  -> a bounded 0/1 outcome has NO outliers by construction. This is exactly why')
print('     the primary endpoint is robust while the token endpoint is not.')

"""
stats_normlib_validate.py -- self-validation of the hand-rolled normality tests.

Three checks:
 (1) Analytic spot-checks of Phi and Phi^-1 against known values.
 (2) CALIBRATION: under a true normal H0, a valid test's p-values must be
     Uniform(0,1). We simulate and check the type-I error rate at 0.10/0.05/0.01
     and the mean p (should be ~0.5), at each sample size we will actually use.
 (3) POWER: under known non-normal alternatives (exponential, t3, uniform,
     lognormal) the tests must reject. A test that never rejects is broken.

If (2) is off, every p-value in the main analysis is untrustworthy, so this
runs first and its output is reported alongside the findings.
"""
import math
import random
import statistics as st
from stats_normlib import (phi_cdf, phi_ppf, shapiro_wilk, shapiro_francia,
                           dagostino_k2, anderson_darling, jarque_bera)

random.seed(20260731)


def sect(t):
    print('\n' + '=' * 78)
    print(t)
    print('=' * 78)


sect('(1) ANALYTIC SPOT-CHECKS')
# Known: Phi(1.959963985) = 0.975 ; Phi(0)=0.5 ; Phi(-2.5758293)=0.005
for z, known in [(0.0, 0.5), (1.959963984540054, 0.975), (-2.5758293035489004, 0.005),
                 (1.0, 0.8413447460685429), (-3.0, 0.0013498980316301)]:
    got = phi_cdf(z)
    print(f'  Phi({z:+.9f}) = {got:.12f}   known {known:.12f}   err {abs(got-known):.2e}')
for p, known in [(0.975, 1.959963984540054), (0.5, 0.0), (0.005, -2.5758293035489004),
                 (0.999, 3.090232306167813), (1e-8, -5.612001244174789)]:
    got = phi_ppf(p)
    print(f'  Phi^-1({p:g}) = {got:+.12f}  known {known:+.12f}  err {abs(got-known):.2e}')
# round-trip
worst = max(abs(phi_cdf(phi_ppf(p)) - p) for p in [i / 1000 for i in range(1, 1000)])
print(f'  round-trip max err over p=0.001..0.999: {worst:.3e}')

sect('(2) CALIBRATION UNDER TRUE NORMAL H0  (p-values must be ~Uniform(0,1))')
NS = [50, 208, 325, 1299]
REPS = 3000
print(f'  {REPS} normal samples per n. Expected rejection rates: .10 / .05 / .01')
print(f'  {"n":>5} {"test":>10} {"rej.10":>8} {"rej.05":>8} {"rej.01":>8} {"mean p":>8}')
calib = {}
for n in NS:
    reps = REPS if n <= 325 else 1200
    ps = {'SW': [], 'SF': [], 'K2': [], 'AD': [], 'JB': []}
    for _ in range(reps):
        x = [random.gauss(0, 1) for _ in range(n)]
        ps['SW'].append(shapiro_wilk(x)['p'])
        ps['SF'].append(shapiro_francia(x)['p'])
        ps['K2'].append(dagostino_k2(x)['p'])
        ps['AD'].append(anderson_darling(x)['p'])
        ps['JB'].append(jarque_bera(x)['p'])
    for k, v in ps.items():
        r10 = sum(1 for q in v if q < 0.10) / len(v)
        r05 = sum(1 for q in v if q < 0.05) / len(v)
        r01 = sum(1 for q in v if q < 0.01) / len(v)
        calib[(n, k)] = (r10, r05, r01, st.mean(v))
        print(f'  {n:>5} {k:>10} {r10:8.4f} {r05:8.4f} {r01:8.4f} {st.mean(v):8.4f}')
print('  (MC standard error on rej.05 at 3000 reps ~ 0.004; at 1200 reps ~ 0.006)')

sect('(3) POWER UNDER KNOWN NON-NORMAL ALTERNATIVES (n=325, 1000 reps)')


def gen(kind, n):
    if kind == 'exponential':
        return [random.expovariate(1.0) for _ in range(n)]
    if kind == 'lognormal':
        return [math.exp(random.gauss(0, 1)) for _ in range(n)]
    if kind == 'uniform':
        return [random.random() for _ in range(n)]
    if kind == 't3':
        out = []
        for _ in range(n):
            z = random.gauss(0, 1)
            c = sum(random.gauss(0, 1) ** 2 for _ in range(3))
            out.append(z / math.sqrt(c / 3))
        return out
    if kind == 'bernoulli.5':
        return [float(random.random() < 0.5) for _ in range(n)]


print(f'  {"alt":>14} {"SW":>8} {"SF":>8} {"K2":>8} {"AD":>8} {"JB":>8}   (rejection rate @ .05)')
for kind in ['exponential', 'lognormal', 'uniform', 't3']:
    cnt = {'SW': 0, 'SF': 0, 'K2': 0, 'AD': 0, 'JB': 0}
    R = 1000
    for _ in range(R):
        x = gen(kind, 325)
        if shapiro_wilk(x)['p'] < .05: cnt['SW'] += 1
        if shapiro_francia(x)['p'] < .05: cnt['SF'] += 1
        if dagostino_k2(x)['p'] < .05: cnt['K2'] += 1
        if anderson_darling(x)['p'] < .05: cnt['AD'] += 1
        if jarque_bera(x)['p'] < .05: cnt['JB'] += 1
    print(f'  {kind:>14} ' + ' '.join(f'{cnt[k]/R:8.3f}' for k in ['SW', 'SF', 'K2', 'AD', 'JB']))

sect('(4) SENSITIVITY: what deviation is detectable at each n?')
print('  SE(g1) under normality = sqrt(6/n) approx; |g1| beyond ~2*SE is flagged.')
for n in NS:
    se1 = math.sqrt(6.0 * n * (n - 1) / ((n - 2) * (n + 1) * (n + 3)))
    se2 = math.sqrt(24.0 * n * (n - 1) ** 2 / ((n - 3) * (n - 2) * (n + 3) * (n + 5)))
    print(f'  n={n:>5}  SE(skew)={se1:.4f} -> detects |skew|>{1.96*se1:.3f} ;'
          f'  SE(exkurt)={se2:.4f} -> detects |exkurt|>{1.96*se2:.3f}')

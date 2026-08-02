"""
stats_normality_main.py -- normality & scale audit for the A/B MCQ experiment.

Structure:
  PART 0  the primary outcome is Bernoulli -> normality is not a question you can ask
  PART 1  aggregated accuracy quantities (per-item, per-cluster, per-model)  -> discrete
  PART 2  genuinely continuous instrumentation quantities (tokens, latency)
  PART 3  the question that actually matters: is the SAMPLING DISTRIBUTION of the
          estimator normal enough to license a normal-theory test?
"""
import json
import math
import random
import statistics as st
from collections import defaultdict, Counter
from stats_normlib import (moments, se_skew, se_kurt, shapiro_wilk, shapiro_francia,
                           dagostino_k2, anderson_darling, jarque_bera,
                           qq_tail_report, n_distinct, tie_fraction, phi_ppf, phi_sf)

random.seed(20260731)
BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis'
rows = json.load(open(f'{BASE}/paired_clean.json'))
D = [r for r in rows if r['analysis_include']]


def sect(t):
    print('\n' + '=' * 84)
    print(t)
    print('=' * 84)


def sub(t):
    print('\n--- ' + t + ' ' + '-' * max(0, 78 - len(t)))


def battery(name, x, note=''):
    """Run every test on one vector and print a single tidy block."""
    n, m, sd, g1, g2 = moments(x)
    nd, tf = n_distinct(x), tie_fraction(x)
    print(f'\n  [{name}]  n={n}  mean={m:.6g}  sd={sd:.6g}')
    print(f'    distinct values={nd}  tied-obs fraction={tf:.4f}'
          + (f'   {note}' if note else ''))
    if nd < 3:
        print('    -> support has <3 distinct values; a continuous-distribution test'
              ' is undefined here. Skipping.')
        return None
    print(f'    skew g1={g1:+.4f} (SE {se_skew(n):.4f}, z={g1/se_skew(n):+.2f})   '
          f'excess kurt g2={g2:+.4f} (SE {se_kurt(n):.4f}, z={g2/se_kurt(n):+.2f})')
    res = {}
    sw = shapiro_wilk(x)
    if sw:
        res['SW'] = sw
        print(f'    Shapiro-Wilk    W ={sw["W"]:.5f}   p={sw["p"]:.3e}')
    sf = shapiro_francia(x)
    if sf:
        res['SF'] = sf
        print(f'    Shapiro-Francia W\'={sf["Wprime"]:.5f}   p={sf["p"]:.3e}   (QQ corr r={sf["r"]:.5f})')
    k2 = dagostino_k2(x)
    if k2:
        res['K2'] = k2
        print(f'    D\'Agostino K2   K2={k2["K2"]:.2f}  (Z_skew={k2["Z1"]:+.2f}, '
              f'Z_kurt={k2["Z2"]:+.2f})  p={k2["p"]:.3e}')
    ad = anderson_darling(x)
    if ad:
        res['AD'] = ad
        print(f'    Anderson-Darling A*2={ad["Astar2"]:.4f}  p={ad["p"]:.3e}')
    jb = jarque_bera(x)
    if jb:
        res['JB'] = jb
        print(f'    Jarque-Bera     JB={jb["JB"]:.2f}   p={jb["p"]:.3e}')
    qq = qq_tail_report(x)
    if qq:
        res['QQ'] = qq
        print(f'    QQ sup-gap = {qq["max_qq_dev_sd"]:.2f} SD;  z-range [{qq["min_z"]:.2f},{qq["max_z"]:.2f}]')
        print(f'    QQ tails: emp/theo  q01 {qq["emp_q1"]:+.2f}/{qq["thy_q1"]:+.2f}   '
              f'q05 {qq["emp_q5"]:+.2f}/{qq["thy_q5"]:+.2f}   '
              f'q95 {qq["emp_q95"]:+.2f}/{qq["thy_q95"]:+.2f}   '
              f'q99 {qq["emp_q99"]:+.2f}/{qq["thy_q99"]:+.2f}')
    # Cochran-style CLT adequacy for the MEAN of this variable
    if math.isfinite(g1) and g1 != 0:
        print(f'    CLT adequacy for the mean (Cochran 25*g1^2): need n>{25*g1*g1:.0f}, have n={n}'
              f'  -> {"OK" if n > 25*g1*g1 else "NOT MET"}')
    return res


# =========================================================================
sect('PART 0 -- THE PRIMARY OUTCOME IS BINARY: NORMALITY IS NOT A WELL-POSED QUESTION')
# =========================================================================
A = [r['A_correct'] for r in D]
B = [r['B_correct'] for r in D]
print(f'\n  A_correct: distinct values = {sorted(set(A))}, n={len(A)}, mean={st.mean(A):.4f}')
print(f'  B_correct: distinct values = {sorted(set(B))}, n={len(B)}, mean={st.mean(B):.4f}')
print('\n  A Bernoulli(p) variable has its skewness and kurtosis FORCED by p alone.')
print('  Theory:  g1 = (1-2p)/sqrt(p(1-p))    g2_excess = (1-6p(1-p))/(p(1-p))')
print(f'\n  {"var":>10} {"p":>8} {"g1 obs":>10} {"g1 theory":>10} {"g2 obs":>10} {"g2 theory":>10}')
for nm, v in (('A_correct', A), ('B_correct', B)):
    n, m, sd, g1, g2 = moments(v)
    p = m
    tg1 = (1 - 2 * p) / math.sqrt(p * (1 - p))
    tg2 = (1 - 6 * p * (1 - p)) / (p * (1 - p))
    print(f'  {nm:>10} {p:8.4f} {g1:10.4f} {tg1:10.4f} {g2:10.4f} {tg2:10.4f}')
print('\n  Observed == theory to 4 dp. So a "normality test" on the raw outcome would')
print('  only be re-measuring the accuracy p. It carries no information about model fit,')
print('  and no analysis decision can depend on it.')
mc = Counter((a, b) for a, b in zip(A, B))
print(f'\n  Paired 2x2 (A,B):  (1,1)={mc[(1,1)]}  (1,0)={mc[(1,0)]}  (0,1)={mc[(0,1)]}  (0,0)={mc[(0,0)]}')
print('  The paired binary structure -> McNemar / exact binomial / permutation.')
print('  None of those assume normality of anything.')

# =========================================================================
sect('PART 1 -- AGGREGATED ACCURACY QUANTITIES (the usual "but these are continuous" claim)')
# =========================================================================
by_item_A, by_item_B = defaultdict(list), defaultdict(list)
by_clu_A, by_clu_B = defaultdict(list), defaultdict(list)
by_mod_A, by_mod_B = defaultdict(list), defaultdict(list)
for r in D:
    by_item_A[r['question_id']].append(r['A_correct'])
    by_item_B[r['question_id']].append(r['B_correct'])
    by_clu_A[r['cluster']].append(r['A_correct'])
    by_clu_B[r['cluster']].append(r['B_correct'])
    by_mod_A[r['model']].append(r['A_correct'])
    by_mod_B[r['model']].append(r['B_correct'])

sub('1a. per-ITEM accuracy proportion (averaged over the 4 models), n=325 items')
itemA = [st.mean(by_item_A[q]) for q in sorted(by_item_A)]
itemB = [st.mean(by_item_B[q]) for q in sorted(by_item_B)]
itemD = [st.mean(by_item_B[q]) - st.mean(by_item_A[q]) for q in sorted(by_item_A)]
sizes = Counter(len(v) for v in by_item_A.values())
print(f'  models per item: {dict(sizes)}  -> support is essentially {{0,.25,.5,.75,1}}')
print(f'  value counts A: {dict(sorted(Counter(round(v,4) for v in itemA).items()))}')
print(f'  value counts B: {dict(sorted(Counter(round(v,4) for v in itemB).items()))}')
battery('per-item accuracy, condition A', itemA)
battery('per-item accuracy, condition B', itemB)
battery('per-item delta (B-A)', itemD)

sub('1b. IS THE REJECTION CAUSED BY SHAPE, OR JUST BY 5-POINT GRANULARITY?')
print('  Simulate the BEST CASE: items truly independent Binomial(4,p)/4 with p = observed mean.')
print('  If Shapiro-Wilk still rejects ~always, the rejection is about discreteness, not')
print('  about anything the study did. 2000 reps, n=325.')
for nm, obs in (('A', itemA), ('B', itemB)):
    p = st.mean(obs)
    rej = 0
    R = 2000
    for _ in range(R):
        sim = [sum(1 for _ in range(4) if random.random() < p) / 4 for _ in range(325)]
        s = shapiro_wilk(sim)
        if s and s['p'] < 0.05:
            rej += 1
    print(f'    condition {nm} (p={p:.4f}): SW rejects normality in {rej}/{R} = {rej/R:.3f} of'
          f' IDEALLY-BEHAVED simulated datasets')

sub('1c. per-CLUSTER accuracy (all cells in a clinical-context cluster), n=208 clusters')
cluA = [st.mean(by_clu_A[c]) for c in sorted(by_clu_A)]
cluB = [st.mean(by_clu_B[c]) for c in sorted(by_clu_B)]
cluD = [st.mean(by_clu_B[c]) - st.mean(by_clu_A[c]) for c in sorted(by_clu_A)]
csz = Counter(len(v) for v in by_clu_A.values())
print(f'  cells per cluster distribution: {dict(sorted(csz.items()))}')
print(f'  -> cluster sizes are UNEQUAL, so cluster means have unequal variance '
      f'(heteroscedastic by construction)')
battery('per-cluster accuracy, condition A', cluA)
battery('per-cluster accuracy, condition B', cluB)
battery('per-cluster delta (B-A)', cluD)

sub('1d. per-MODEL delta, n=4')
print(f'  {"model":>28} {"acc A":>8} {"acc B":>8} {"delta":>9} {"nA":>5}')
mdeltas = []
for mname in sorted(by_mod_A):
    a, b = st.mean(by_mod_A[mname]), st.mean(by_mod_B[mname])
    mdeltas.append(b - a)
    print(f'  {mname:>28} {a:8.4f} {b:8.4f} {b-a:+9.4f} {len(by_mod_A[mname]):5d}')
n, m, sd, g1, g2 = moments(mdeltas)
print(f'\n  n=4. mean delta={m:+.4f}, sd={sd:.4f}.')
print('  With n=4 no normality test has meaningful power: Shapiro-Wilk at n=4 cannot')
print('  reject below p=0.05 for many configurations, and the 4 models are a')
print('  CONVENIENCE SET, not a random sample from a population of models.')
print('  A one-sample t-test across 4 models is not defensible on distributional grounds')
print('  and is not defensible on sampling grounds either.')
sw4 = shapiro_wilk(mdeltas)
print(f'  (for completeness: SW on the 4 deltas W={sw4["W"]:.5f} p={sw4["p"]:.4f} -- uninformative)')

# =========================================================================
sect('PART 2 -- GENUINELY CONTINUOUS QUANTITIES: TOKENS AND LATENCY')
# =========================================================================
At = [r['A_tokens'] for r in D]
Bt = [r['B_tokens'] for r in D]
Dt = [r['B_tokens'] - r['A_tokens'] for r in D]
Al = [r['A_latency_ms'] for r in D]
Bl = [r['B_latency_ms'] for r in D]
Dl = [r['B_latency_ms'] - r['A_latency_ms'] for r in D]

sub('2a. completion tokens, pooled across models (n=1299 per condition)')
battery('A_tokens (raw)', At)
battery('B_tokens (raw)', Bt)
battery('paired delta B_tokens - A_tokens', Dt)
battery('log(A_tokens)', [math.log(v) for v in At])
battery('log(B_tokens)', [math.log(v) for v in Bt])

sub('2b. latency ms, pooled across models')
battery('A_latency_ms (raw)', Al)
battery('B_latency_ms (raw)', Bl)
battery('paired delta B_latency - A_latency', Dl)
battery('log(A_latency_ms)', [math.log(v) for v in Al])
battery('log(B_latency_ms)', [math.log(v) for v in Bl])

sub('2c. POOLING ACROSS MODELS CREATES A MIXTURE. Does within-model help?')
print('  If the 4 models have different token/latency locations, the pooled distribution is')
print('  a 4-component mixture and is non-normal even if each component were normal.')
tok_by_m, lat_by_m = defaultdict(list), defaultdict(list)
for r in D:
    tok_by_m[r['model']].append(r['A_tokens'])
    lat_by_m[r['model']].append(r['A_latency_ms'])
print(f'\n  {"model":>28} {"med tok":>9} {"mean tok":>9} {"max tok":>9} {"med lat":>9} {"max lat":>10}')
for mname in sorted(tok_by_m):
    t, l = tok_by_m[mname], lat_by_m[mname]
    print(f'  {mname:>28} {st.median(t):9.0f} {st.mean(t):9.1f} {max(t):9d} '
          f'{st.median(l):9.0f} {max(l):10d}')
for mname in sorted(tok_by_m):
    battery(f'A_tokens within {mname}', tok_by_m[mname])
for mname in sorted(lat_by_m):
    battery(f'log(A_latency) within {mname}', [math.log(v) for v in lat_by_m[mname]])

sub('2d. how much of the tail is driving this? trimming check on A_tokens')
srt = sorted(At)
for trim in (0.0, 0.01, 0.025, 0.05):
    k = int(len(srt) * trim)
    sub_x = srt[k:len(srt) - k] if k else srt
    n, m, sd, g1, g2 = moments(sub_x)
    sw = shapiro_wilk(sub_x)
    print(f'  trim {trim*100:4.1f}% each tail: n={n:5d} mean={m:8.1f} skew={g1:+8.3f} '
          f'exkurt={g2:+9.3f}  SW W={sw["W"]:.4f} p={sw["p"]:.2e}')

# =========================================================================
sect('PART 3 -- THE QUESTION THAT ACTUALLY MATTERS: IS THE ESTIMATOR NORMAL?')
# =========================================================================
print('\n  Normality of the DATA is not what licenses a z/t test -- normality of the')
print('  SAMPLING DISTRIBUTION of the estimator is. That is directly checkable here.')

sub('3a. McNemar: exact conditional binomial vs the normal/chi-square approximation')


def exact_binom_two_sided(b, c):
    """Exact two-sided p for H0: P(discordant is b-type)=0.5, conditional on n=b+c."""
    n = b + c
    if n == 0:
        return 1.0
    obs = abs(b - n / 2.0)
    tot = 0.0
    for k in range(n + 1):
        if abs(k - n / 2.0) >= obs - 1e-12:
            tot += math.comb(n, k)
    return min(1.0, tot / (2.0 ** n))


print(f'\n  {"model":>28} {"b(A1B0)":>8} {"c(A0B1)":>8} {"exact p":>12} {"normal p":>12} {"ratio":>9}')
for mname in sorted(by_mod_A):
    sel = [r for r in D if r['model'] == mname]
    b = sum(1 for r in sel if r['A_correct'] == 1 and r['B_correct'] == 0)
    c = sum(1 for r in sel if r['A_correct'] == 0 and r['B_correct'] == 1)
    pe = exact_binom_two_sided(b, c)
    nn = b + c
    z = (abs(b - c) - 0) / math.sqrt(nn) if nn else 0.0
    pn = 2 * phi_sf(z) if nn else 1.0
    print(f'  {mname:>28} {b:8d} {c:8d} {pe:12.3e} {pn:12.3e} '
          f'{(pn/pe if pe>0 else float("inf")):9.3f}')
allb = sum(1 for r in D if r['A_correct'] == 1 and r['B_correct'] == 0)
allc = sum(1 for r in D if r['A_correct'] == 0 and r['B_correct'] == 1)
pe = exact_binom_two_sided(allb, allc)
z = abs(allb - allc) / math.sqrt(allb + allc)
print(f'  {"POOLED (ignores clustering)":>28} {allb:8d} {allc:8d} {pe:12.3e} '
      f'{2*phi_sf(z):12.3e} {(2*phi_sf(z)/pe if pe>0 else 0):9.3f}')
print('\n  Note: the pooled row IGNORES item/cluster/model dependence and is shown only to')
print('  compare the exact vs normal tail, not as a valid study-level test.')

sub('3b. cluster bootstrap of the pooled accuracy delta -- is the BOOTSTRAP dist normal?')
clusters = sorted(set(r['cluster'] for r in D))
by_cluster = defaultdict(list)
for r in D:
    by_cluster[r['cluster']].append(r)
obs_delta = st.mean(B) - st.mean(A)
REP = 20000
boot = []
cl_list = [by_cluster[c] for c in clusters]
K = len(cl_list)
for _ in range(REP):
    sa = sb = 0
    cnt = 0
    for _ in range(K):
        grp = cl_list[random.randrange(K)]
        for r in grp:
            sa += r['A_correct']
            sb += r['B_correct']
            cnt += 1
    boot.append(sb / cnt - sa / cnt)
n, m, sd, g1, g2 = moments(boot)
print(f'\n  observed pooled delta (B-A) = {obs_delta:+.5f}')
print(f'  cluster bootstrap ({REP} reps, resampling {K} clusters): mean={m:+.5f} SE={sd:.5f}')
print(f'  bootstrap-distribution skew={g1:+.4f} (SE {se_skew(n):.4f})  '
      f'excess kurt={g2:+.4f} (SE {se_kurt(n):.4f})')
bs = sorted(boot)
lo_pct, hi_pct = bs[int(0.025 * REP)], bs[int(0.975 * REP)]
lo_nrm, hi_nrm = obs_delta - 1.959963985 * sd, obs_delta + 1.959963985 * sd
print(f'  95% percentile CI : [{lo_pct:+.5f}, {hi_pct:+.5f}]')
print(f'  95% normal-theory CI: [{lo_nrm:+.5f}, {hi_nrm:+.5f}]')
print(f'  endpoint disagreement: lo {abs(lo_pct-lo_nrm):.5f}  hi {abs(hi_pct-hi_nrm):.5f}'
      f'  ({100*abs(lo_pct-lo_nrm)/abs(obs_delta):.2f}% / '
      f'{100*abs(hi_pct-hi_nrm)/abs(obs_delta):.2f}% of the estimate)')
k2b = dagostino_k2(boot)
print(f'  D\'Agostino K2 on bootstrap replicates: K2={k2b["K2"]:.2f} p={k2b["p"]:.3e}')
print('  (with 20000 replicates this test detects even trivial departures; read the')
print('   skew/kurtosis magnitudes, not the p-value)')

sub('3c. same check for the MEAN TOKEN DELTA -- the quantity a paired t-test would target')
REP2 = 20000
bootT = []
for _ in range(REP2):
    s = 0
    cnt = 0
    for _ in range(K):
        grp = cl_list[random.randrange(K)]
        for r in grp:
            s += r['B_tokens'] - r['A_tokens']
            cnt += 1
    bootT.append(s / cnt)
n, m, sd, g1, g2 = moments(bootT)
obsT = st.mean(Dt)
print(f'\n  observed mean token delta = {obsT:+.2f}')
print(f'  cluster bootstrap: mean={m:+.2f} SE={sd:.2f}')
print(f'  bootstrap skew={g1:+.4f}  excess kurt={g2:+.4f}')
bt = sorted(bootT)
loP, hiP = bt[int(0.025 * REP2)], bt[int(0.975 * REP2)]
loN, hiN = obsT - 1.959963985 * sd, obsT + 1.959963985 * sd
print(f'  95% percentile CI  : [{loP:+.2f}, {hiP:+.2f}]')
print(f'  95% normal-theory CI: [{loN:+.2f}, {hiN:+.2f}]')
print(f'  endpoint disagreement: lo {abs(loP-loN):.2f}  hi {abs(hiP-hiN):.2f}')
# naive iid t-interval, for contrast
sd_iid = st.stdev(Dt) / math.sqrt(len(Dt))
print(f'  naive iid SE (ignores clustering) = {sd_iid:.2f} vs cluster-bootstrap SE = {sd:.2f}'
      f'   ratio {sd/sd_iid:.3f}')
print(f'  median token delta = {st.median(Dt):+.1f}  (vs mean {obsT:+.2f}) '
      f'-- mean and median disagree in magnitude, a signature of tail dominance')
sgn = sum(1 for v in Dt if v > 0)
tie = sum(1 for v in Dt if v == 0)
print(f'  sign split: B>A in {sgn}, B<A in {len(Dt)-sgn-tie}, tied in {tie}')

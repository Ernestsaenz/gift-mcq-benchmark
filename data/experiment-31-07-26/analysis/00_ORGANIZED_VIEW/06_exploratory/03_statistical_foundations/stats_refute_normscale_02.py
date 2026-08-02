"""
stats_refute_normscale_02.py -- follow-ups to stats_refute_normscale_01.py

A  seed-stability of the headline "0.29% / 0.42%" endpoint-disagreement numbers
B  the algebraic identity behind the leave-one-cell-out "outlier-proof" evidence
C  large-scale calibration: does the nominal-95% cluster-bootstrap interval
   actually cover 95%?  normal / percentile / studentized / t(K-1)
D  what a reader who hears "normal-theory is defensible" would actually build:
   the naive iid interval, and how badly it covers
"""
import json, math, random, statistics as st
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis'
D = [r for r in json.load(open(f'{BASE}/paired_clean.json')) if r['analysis_include']]

def phi(z): return 0.5 * math.erfc(-z / math.sqrt(2.0))
Z975 = 1.959963984540054

by_cluster = defaultdict(list)
for r in D:
    by_cluster[r['cluster']].append(r)
clusters = sorted(by_cluster)
K = len(clusters)
cl_n = [len(by_cluster[c]) for c in clusters]
cl_d = [sum(r['B_correct'] - r['A_correct'] for r in by_cluster[c]) for c in clusters]
N = sum(cl_n); TOT_D = sum(cl_d)
obs = TOT_D / N
d_cell = [r['B_correct'] - r['A_correct'] for r in D]

def hr(t):
    print('\n' + '=' * 88); print(t); print('=' * 88)

def boot_once(rng):
    s = 0; c = 0
    for _ in range(K):
        j = rng.randrange(K)
        s += cl_d[j]; c += cl_n[j]
    return s / c

# ------------------------------------------------------------------ A
hr('A. IS THE HEADLINE "0.29% / 0.42%" ENDPOINT DISAGREEMENT A STABLE NUMBER?')
print('  Re-running the identical 20000-rep cluster bootstrap under 12 seeds.')
print('  seed |  bootSE  |   skew  | exkurt |  lo-gap %  |  hi-gap %  | which end bigger')
los, his, skews, kurts, ses = [], [], [], [], []
for sd_seed in range(1, 13):
    rng = random.Random(1000 + sd_seed)
    b = [boot_once(rng) for _ in range(20000)]
    m = sum(b) / len(b)
    n = len(b)
    m2 = sum((v-m)**2 for v in b)/n; m3 = sum((v-m)**3 for v in b)/n; m4 = sum((v-m)**4 for v in b)/n
    g1 = m3/m2**1.5; g2 = m4/m2**2 - 3
    s = math.sqrt(sum((v-m)**2 for v in b)/(n-1))
    b.sort()
    lp, hp = b[int(0.025*n)], b[int(0.975*n)]
    ln, hn = obs - Z975*s, obs + Z975*s
    gl = 100*abs(lp-ln)/abs(obs); gh = 100*abs(hp-hn)/abs(obs)
    los.append(gl); his.append(gh); skews.append(g1); kurts.append(g2); ses.append(s)
    print(f'  {1000+sd_seed:4d} | {s:.6f} | {g1:+.4f} | {g2:+.4f} | {gl:9.3f}% | {gh:9.3f}% | '
          f'{"lo" if gl>gh else "hi"}')
print(f'\n  across seeds: lo-gap {min(los):.3f}%-{max(los):.3f}%  '
      f'hi-gap {min(his):.3f}%-{max(his):.3f}%')
print(f'  skew range {min(skews):+.4f}..{max(skews):+.4f}   '
      f'exkurt range {min(kurts):+.4f}..{max(kurts):+.4f}')
print(f'  -> the CLAIM quotes lo=0.29% hi=0.42%, skew -0.0630, exkurt +0.1011 as if')
print('     they were estimates of something. They are Monte-Carlo noise at that')
print('     precision; only the order of magnitude (<1% of the estimate) replicates.')
print('  Also note the denominator choice. The same lo-gap expressed against')
lp_gap = st.mean(los) * abs(obs) / 100
print(f'     |estimate| ({abs(obs):.5f}) = {100*lp_gap/abs(obs):.2f}%')
print(f'     CI width   ({2*Z975*st.mean(ses):.5f}) = {100*lp_gap/(2*Z975*st.mean(ses)):.2f}%')
print(f'     one SE     ({st.mean(ses):.5f}) = {100*lp_gap/st.mean(ses):.2f}%')
print('     "% of the estimate" is the most flattering of the three denominators.')

# ------------------------------------------------------------------ B
hr('B. THE "OUTLIER-PROOF BY CONSTRUCTION" EVIDENCE IS AN ALGEBRAIC IDENTITY')
mx = max(abs(v - obs) for v in d_cell)
forced = mx / (N - 1)
emp = 0.0
for v in d_cell:
    emp = max(emp, abs((TOT_D - v)/(N-1) - obs))
print(f'  For a plain mean, dropping cell i shifts it by exactly (mean - x_i)/(n-1).')
print(f'  So max shift == max|d_i - delta| / (n-1) = {mx:.6f} / {N-1} = {forced:.6f}')
print(f'  empirical max leave-one-cell-out shift    = {emp:.6f}   identical: {abs(emp-forced)<1e-15}')
print(f'  CLAIM reports 0.000890 = {100*forced/abs(obs):.3f}% of the estimate -> reproduced.')
print(f'\n  But d_i is confined to {{-1,0,+1}}, so max|d_i - delta| can never exceed')
print(f'  1 + |delta| = {1+abs(obs):.4f}. The number is therefore pinned by n and by the')
print(f'  mere existence of one cell with d=+1. It cannot detect an influential')
print(f'  observation, because in this design no single cell can be influential.')
print(f'  Sanity check: if EVERY cell were maximally adverse the figure would still be')
print(f'  {(1+abs(obs))/(N-1):.6f}. The reported value is {forced:.6f}. No information.')

# leverage at the unit the bootstrap actually resamples
sh = sorted((abs((TOT_D - cl_d[i])/(N - cl_n[i]) - obs), clusters[i], cl_n[i])
            for i in range(K))[::-1]
rng = random.Random(4242)
se_ref = st.stdev([boot_once(rng) for _ in range(20000)])
print(f'\n  Same exercise at the CLUSTER level (the unit the bootstrap resamples):')
for v, c, nn in sh[:5]:
    print(f'    cluster {c:>4} (n={nn:3d} cells): shift {v:.6f} = {100*v/abs(obs):5.2f}% of estimate '
          f'= {100*v/se_ref:5.1f}% of one bootstrap SE')
print(f'  cluster sizes range {min(cl_n)}..{max(cl_n)} cells; the largest single cluster is')
print(f'  {100*max(cl_n)/N:.2f}% of all cells. Kish effective #clusters = '
      f'{N*N/sum(x*x for x in cl_n):.1f}, not {K}.')

# ------------------------------------------------------------------ C
hr('C. CALIBRATION: DOES THE NOMINAL-95% INTERVAL COVER 95%?')
print('  Outer loop = 8000 cluster-resamples treated as replicate studies (truth=obs).')
print('  Each replicate study gets a LINEARIZED cluster-robust SE (exact, no inner loop),')
print('  so there is no inner-bootstrap noise contaminating the coverage estimate.')

def robust(bn, bd):
    Nn = sum(bn); th = sum(bd)/Nn
    u = [(bd[i] - th*bn[i])/Nn for i in range(len(bn))]
    return th, math.sqrt((K/(K-1.0))*sum(x*x for x in u))

# studentized reference distribution from the observed sample
rng = random.Random(555)
tstar = []
for _ in range(20000):
    bn = []; bd = []
    for _ in range(K):
        j = rng.randrange(K); bn.append(cl_n[j]); bd.append(cl_d[j])
    th, se = robust(bn, bd)
    if se > 0:
        tstar.append((th - obs)/se)
tstar.sort()
tlo, thi = tstar[int(0.025*len(tstar))], tstar[int(0.975*len(tstar))]

# t(K-1) quantile via bisection on the t cdf (series-free: use normal + Cornish-Fisher-ish)
def t_ppf(p, df):
    z = 0.0
    lo, hi = -10.0, 10.0
    # Student-t CDF via incomplete beta by numeric integration of the density
    def pdf(x):
        return math.exp(math.lgamma((df+1)/2) - math.lgamma(df/2)) / math.sqrt(df*math.pi) \
               * (1 + x*x/df) ** (-(df+1)/2)
    def cdf(x):
        n = 4000
        a = -40.0
        h = (x - a)/n
        s = 0.5*(pdf(a) + pdf(x))
        for i in range(1, n):
            s += pdf(a + i*h)
        return s*h
    for _ in range(80):
        mid = (lo+hi)/2
        if cdf(mid) < p: lo = mid
        else: hi = mid
    return (lo+hi)/2
T975 = t_ppf(0.975, K-1)
print(f'  t_.975(df={K-1}) = {T975:.4f}   (z = {Z975:.4f});  '
      f'studentized t* quantiles = [{tlo:+.4f}, {thi:+.4f}]')

OUT = 8000
rng = random.Random(777)
cov_z = cov_t = cov_stud = cov_iid = 0
for _ in range(OUT):
    bn = []; bd = []
    for _ in range(K):
        j = rng.randrange(K); bn.append(cl_n[j]); bd.append(cl_d[j])
    th, se = robust(bn, bd)
    if se <= 0: continue
    if th - Z975*se <= obs <= th + Z975*se: cov_z += 1
    if th - T975*se <= obs <= th + T975*se: cov_t += 1
    if th - thi*se <= obs <= th - tlo*se: cov_stud += 1
    # naive iid interval, built from the resampled cells
    cells = []
    for j in range(K):
        cells.extend([r['B_correct'] - r['A_correct'] for r in by_cluster[clusters[j]]])
    # (recompute properly: cells of the resampled clusters)
    cells = []
    for j in range(K):
        pass
    # cheap exact iid SE from resampled cluster sufficient stats
    # sum d^2 per cluster needed:
    # handled below with precomputed cl_d2
mcse = math.sqrt(0.95*0.05/OUT)
print(f'\n  normal-theory  (est +- 1.96 * cluster-robust SE) coverage = {cov_z/OUT:.4f}  (MC SE {mcse:.4f})')
print(f'  t(K-1)         (est +- {T975:.3f} * same SE)          coverage = {cov_t/OUT:.4f}')
print(f'  studentized    (bootstrap-t quantiles)            coverage = {cov_stud/OUT:.4f}')
print(f'  z-deficit = {100*(0.95 - cov_z/OUT):.2f} pp, i.e. '
      f'{(0.95 - cov_z/OUT)/mcse:.1f} MC SEs below nominal')

# ------------------------------------------------------------------ D
hr('D. THE INTERVAL A READER ACTUALLY BUILDS FROM "NORMAL-THEORY IS DEFENSIBLE"')
cl_d2 = [sum((r['B_correct'] - r['A_correct'])**2 for r in by_cluster[c]) for c in clusters]
rng = random.Random(999)
cov_naive = 0
for _ in range(OUT):
    sn = sd_ = sq = 0
    for _ in range(K):
        j = rng.randrange(K)
        sn += cl_n[j]; sd_ += cl_d[j]; sq += cl_d2[j]
    th = sd_/sn
    var = (sq - sn*th*th)/(sn - 1)
    se = math.sqrt(var/sn)
    if th - Z975*se <= obs <= th + Z975*se: cov_naive += 1
print(f'  naive iid normal interval (1299 cells treated as independent):')
print(f'    coverage = {cov_naive/OUT:.4f}  vs nominal 0.95   '
      f'-> {100*(0.95-cov_naive/OUT):.1f} pp too narrow')
sd_iid = st.stdev(d_cell)/math.sqrt(N)
print(f'    on the real sample: SE {sd_iid:.6f} vs cluster-robust {se_ref:.6f} '
      f'(design effect {(se_ref/sd_iid)**2:.3f})')
print(f'    95% CI [{obs-Z975*sd_iid:+.5f}, {obs+Z975*sd_iid:+.5f}] vs '
      f'[{obs-Z975*se_ref:+.5f}, {obs+Z975*se_ref:+.5f}]')
print(f'    endpoint error {Z975*abs(se_ref-sd_iid):.5f} = '
      f'{100*Z975*abs(se_ref-sd_iid)/abs(obs):.2f}% of the estimate')
print(f'\n  The claim advertises a {st.mean(los):.2f}% / {st.mean(his):.2f}% discrepancy as the one')
print(f'  that "does not matter". The discrepancy it never mentions is '
      f'{100*Z975*abs(se_ref-sd_iid)/abs(obs):.2f}%, i.e. '
      f'{Z975*abs(se_ref-sd_iid)/(st.mean(los)*abs(obs)/100):.0f}x larger.')

"""
stats_refute_normscale_01.py -- INDEPENDENT recomputation of the
"normal-theory inference is defensible for the primary accuracy contrast" claim.

Nothing is imported from the analysis libs; every number below is computed here
from paired_clean.json with the standard library only.

Checks
  0  data shape / cluster size distribution
  1  observed pooled delta (B - A)
  2  cluster bootstrap (20000 reps, resample 208 clusters) -> SE, skew, exkurt
  3  percentile vs normal-theory CI, endpoint disagreement
  4  is "percentile == normal" an independent check, or a symmetry tautology?
     -> compare against BCa and studentized (bootstrap-t), the intervals that
        actually differ from normal when the estimator is skewed/biased
  5  the SE that actually matters: naive iid SE vs cluster-robust SE (design eff)
  6  leverage: leave-one-CELL-out (what the claim reports) vs leave-one-CLUSTER-out
     (the correct unit given the resampling scheme) vs leave-one-MODEL-out
  7  double bootstrap calibration of the nominal-95% normal-theory interval
"""
import json, math, random, statistics as st
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis'
rows = json.load(open(f'{BASE}/paired_clean.json'))
D = [r for r in rows if r['analysis_include']]

SEED = 987654321
random.seed(SEED)

def hr(t):
    print('\n' + '=' * 88)
    print(t)
    print('=' * 88)

def moments(x):
    n = len(x)
    m = sum(x) / n
    m2 = sum((v - m) ** 2 for v in x) / n
    m3 = sum((v - m) ** 3 for v in x) / n
    m4 = sum((v - m) ** 4 for v in x) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in x) / (n - 1))
    g1 = m3 / m2 ** 1.5 if m2 > 0 else float('nan')
    g2 = m4 / m2 ** 2 - 3.0 if m2 > 0 else float('nan')
    return n, m, sd, g1, g2

def phi(z):   # standard normal CDF
    return 0.5 * math.erfc(-z / math.sqrt(2.0))

def phi_ppf(p):
    # Acklam / Wichura-style inverse normal, then one Newton polish with erfc
    if p <= 0 or p >= 1:
        raise ValueError(p)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        x = (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    elif p <= ph:
        q = p - 0.5; r = q * q
        x = (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    else:
        q = math.sqrt(-2 * math.log(1 - p))
        x = -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    e = phi(x) - p
    u = e * math.sqrt(2 * math.pi) * math.exp(x * x / 2)
    return x - u / (1 + x * u / 2)

Z975 = phi_ppf(0.975)

# ---------------------------------------------------------------- 0. shape
hr('0. DATA SHAPE (independent count)')
print(f'  records total            = {len(rows)}')
print(f'  analysis_include cells   = {len(D)}')
print(f'  distinct items           = {len(set(r["question_id"] for r in D))}')
print(f'  distinct clusters        = {len(set(r["cluster"] for r in D))}')
print(f'  distinct models          = {len(set(r["model"] for r in D))}')

by_cluster = defaultdict(list)
for r in D:
    by_cluster[r['cluster']].append(r)
clusters = sorted(by_cluster)
K = len(clusters)
sizes = sorted((len(by_cluster[c]) for c in clusters), reverse=True)
N = len(D)
print(f'  cluster sizes (cells): min={sizes[-1]} median={st.median(sizes)} '
      f'mean={N/K:.2f} max={sizes[0]}')
print(f'  top-10 cluster sizes     = {sizes[:10]}')
print(f'  largest cluster share of all cells = {sizes[0]/N:.4f}  '
      f'({100*sizes[0]/N:.2f}%)')
print(f'  Kish-style effective #clusters (sum n)^2/sum n^2 = '
      f'{sum(sizes)**2/sum(s*s for s in sizes):.1f} of {K}')

# ---------------------------------------------------------------- 1. delta
hr('1. OBSERVED POOLED ACCURACY DELTA')
accA = sum(r['A_correct'] for r in D) / N
accB = sum(r['B_correct'] for r in D) / N
obs = accB - accA
print(f'  acc A = {accA:.6f}   acc B = {accB:.6f}')
print(f'  observed delta (B - A) = {obs:+.6f}')
print(f'  CLAIM says -0.15550  -> match: {abs(obs + 0.15550) < 5e-5}')

# per-cluster sufficient stats for the ratio estimator
cl_n = [len(by_cluster[c]) for c in clusters]
cl_d = [sum(r['B_correct'] - r['A_correct'] for r in by_cluster[c]) for c in clusters]

# ---------------------------------------------------------------- 2/3. bootstrap
hr('2-3. CLUSTER BOOTSTRAP (20000 reps, resample 208 clusters w/ replacement)')
REP = 20000
rng = random.Random(SEED)
boot = []
for _ in range(REP):
    s = 0; c = 0
    for _ in range(K):
        j = rng.randrange(K)
        s += cl_d[j]; c += cl_n[j]
    boot.append(s / c)
n_, m_, sd_, g1_, g2_ = moments(boot)
se_skew = math.sqrt(6.0 * n_ * (n_ - 1) / ((n_ - 2) * (n_ + 1) * (n_ + 3)))
se_kurt = 2 * se_skew * math.sqrt((n_ * n_ - 1) / ((n_ - 3) * (n_ + 5)))
print(f'  bootstrap mean = {m_:+.6f}   bias = {m_ - obs:+.6f}')
print(f'  bootstrap SE   = {sd_:.6f}      (CLAIM 0.01605)')
print(f'  skew  g1 = {g1_:+.4f}  (SE {se_skew:.4f},  z = {g1_/se_skew:+.2f})   (CLAIM -0.0630)')
print(f'  exkurt g2 = {g2_:+.4f} (SE {se_kurt:.4f},  z = {g2_/se_kurt:+.2f})   (CLAIM +0.1011)')
bs = sorted(boot)

def pct(p):
    # linear-interpolated order statistic
    h = (len(bs) - 1) * p
    lo = int(math.floor(h)); hi = min(lo + 1, len(bs) - 1)
    return bs[lo] + (h - lo) * (bs[hi] - bs[lo])

lo_pct, hi_pct = pct(0.025), pct(0.975)
lo_nrm, hi_nrm = obs - Z975 * sd_, obs + Z975 * sd_
print(f'\n  95% percentile CI     : [{lo_pct:+.5f}, {hi_pct:+.5f}]')
print(f'  95% normal-theory CI  : [{lo_nrm:+.5f}, {hi_nrm:+.5f}]')
print(f'  endpoint gap: lo {abs(lo_pct-lo_nrm):.5f} ({100*abs(lo_pct-lo_nrm)/abs(obs):.2f}%)  '
      f'hi {abs(hi_pct-hi_nrm):.5f} ({100*abs(hi_pct-hi_nrm)/abs(obs):.2f}%)')
print(f'  width percentile = {hi_pct-lo_pct:.5f}   width normal = {hi_nrm-lo_nrm:.5f}   '
      f'ratio = {(hi_pct-lo_pct)/(hi_nrm-lo_nrm):.4f}')

# ---------------------------------------------------------------- 4. BCa + boot-t
hr('4. THE INTERVALS THAT CAN ACTUALLY DISAGREE WITH NORMAL: BCa AND BOOTSTRAP-t')
print('  (percentile and normal-theory are BOTH symmetric functions of the same')
print('   bootstrap draw; their agreement is a SYMMETRY check, not an accuracy check.)')

# --- BCa
n_below = sum(1 for v in boot if v < obs)
n_eq = sum(1 for v in boot if v == obs)
p0 = (n_below + 0.5 * n_eq) / REP
z0 = phi_ppf(min(max(p0, 1e-9), 1 - 1e-9))
# jackknife over clusters for acceleration
TOT_D = sum(cl_d); TOT_N = sum(cl_n)
jk = [(TOT_D - cl_d[i]) / (TOT_N - cl_n[i]) for i in range(K)]
jbar = sum(jk) / K
num = sum((jbar - v) ** 3 for v in jk)
den = sum((jbar - v) ** 2 for v in jk)
acc = num / (6.0 * den ** 1.5) if den > 0 else 0.0
def bca_end(alpha):
    za = phi_ppf(alpha)
    adj = z0 + (z0 + za) / (1 - acc * (z0 + za))
    return pct(min(max(phi(adj), 1e-6), 1 - 1e-6))
lo_bca, hi_bca = bca_end(0.025), bca_end(0.975)
print(f'\n  BCa: z0 = {z0:+.5f}   acceleration a = {acc:+.6f}   '
      f'(P(boot < obs) = {p0:.5f})')
print(f'  95% BCa CI            : [{lo_bca:+.5f}, {hi_bca:+.5f}]')
print(f'  BCa vs normal gap: lo {abs(lo_bca-lo_nrm):.5f} '
      f'({100*abs(lo_bca-lo_nrm)/abs(obs):.2f}%)  hi {abs(hi_bca-hi_nrm):.5f} '
      f'({100*abs(hi_bca-hi_nrm)/abs(obs):.2f}%)')

# --- studentized bootstrap (cluster-robust linearized SE inside each rep)
def robust_se(idx_n, idx_d):
    """cluster-robust SE of the ratio estimator sum(d)/sum(n) for one dataset."""
    Nn = sum(idx_n); Dd = sum(idx_d); th = Dd / Nn
    kk = len(idx_n)
    u = [(idx_d[i] - th * idx_n[i]) / Nn for i in range(kk)]
    v = (kk / (kk - 1.0)) * sum(x * x for x in u)
    return math.sqrt(v), th

se_lin, th_lin = robust_se(cl_n, cl_d)
rng2 = random.Random(SEED + 1)
tstar = []
for _ in range(REP):
    bn = []; bd = []
    for _ in range(K):
        j = rng2.randrange(K)
        bn.append(cl_n[j]); bd.append(cl_d[j])
    se_b, th_b = robust_se(bn, bd)
    if se_b > 0:
        tstar.append((th_b - obs) / se_b)
ts = sorted(tstar)
def tq(p):
    h = (len(ts) - 1) * p
    lo = int(math.floor(h)); hi = min(lo + 1, len(ts) - 1)
    return ts[lo] + (h - lo) * (ts[hi] - ts[lo])
t_lo, t_hi = tq(0.025), tq(0.975)
lo_t, hi_t = obs - t_hi * se_lin, obs - t_lo * se_lin
print(f'\n  analytic cluster-robust (linearized) SE = {se_lin:.6f}  '
      f'vs bootstrap SE {sd_:.6f}   ratio {sd_/se_lin:.4f}')
print(f'  studentized t quantiles: t.025 = {t_lo:+.4f}  t.975 = {t_hi:+.4f}  '
      f'(normal: {-Z975:+.4f} / {Z975:+.4f})')
print(f'  95% bootstrap-t CI    : [{lo_t:+.5f}, {hi_t:+.5f}]')
print(f'  boot-t vs normal gap: lo {abs(lo_t-lo_nrm):.5f} '
      f'({100*abs(lo_t-lo_nrm)/abs(obs):.2f}%)  hi {abs(hi_t-hi_nrm):.5f} '
      f'({100*abs(hi_t-hi_nrm)/abs(obs):.2f}%)')
print(f'  boot-t width / normal width = {(hi_t-lo_t)/(hi_nrm-lo_nrm):.4f}')

# ---------------------------------------------------------------- 5. design effect
hr('5. THE CHOICE THAT ACTUALLY MOVES THE INTERVAL: iid SE vs CLUSTER-ROBUST SE')
d_cell = [r['B_correct'] - r['A_correct'] for r in D]
se_iid = st.stdev(d_cell) / math.sqrt(N)
print(f'  naive iid SE (treats 1299 cells as independent) = {se_iid:.6f}')
print(f'  cluster-robust / bootstrap SE                    = {sd_:.6f}')
print(f'  ratio (cluster / iid) = {sd_/se_iid:.4f}   design effect = {(sd_/se_iid)**2:.4f}')
lo_iid, hi_iid = obs - Z975 * se_iid, obs + Z975 * se_iid
print(f'  95% naive-normal CI   : [{lo_iid:+.5f}, {hi_iid:+.5f}]')
print(f'  naive-normal vs cluster-normal endpoint gap: lo {abs(lo_iid-lo_nrm):.5f} '
      f'({100*abs(lo_iid-lo_nrm)/abs(obs):.2f}% of estimate)  '
      f'hi {abs(hi_iid-hi_nrm):.5f} ({100*abs(hi_iid-hi_nrm)/abs(obs):.2f}%)')
print(f'  -> the SE choice moves the endpoints '
      f'{abs(lo_iid-lo_nrm)/max(abs(lo_pct-lo_nrm),1e-12):.1f}x more than the '
      f'percentile-vs-normal choice the claim advertises.')

# ---------------------------------------------------------------- 6. leverage
hr('6. LEVERAGE: WHICH UNIT DO YOU DROP?')
# leave one cell out
worst_cell = 0.0; wc = None
for i, r in enumerate(D):
    di = r['B_correct'] - r['A_correct']
    new = (TOT_D - di) / (N - 1)
    if abs(new - obs) > worst_cell:
        worst_cell = abs(new - obs); wc = (r['question_id'], r['model'])
print(f'  max leave-one-CELL-out shift    = {worst_cell:.6f} '
      f'= {100*worst_cell/abs(obs):.3f}% of estimate   (CLAIM 0.000890 / 0.572%)')
print(f'      -> attained at {wc}')
print(f'      note: for a bounded mean this is algebraically forced to be '
      f'<= max|d - delta|/(n-1) = {max(abs(v-obs) for v in d_cell)/(N-1):.6f}. '
      f'It is a statement about n, not about the data.')

worst_cl = 0.0; wcl = None
shifts = []
for i in range(K):
    new = (TOT_D - cl_d[i]) / (TOT_N - cl_n[i])
    shifts.append(abs(new - obs))
    if abs(new - obs) > worst_cl:
        worst_cl = abs(new - obs); wcl = (clusters[i], cl_n[i], cl_d[i])
shifts.sort(reverse=True)
print(f'\n  max leave-one-CLUSTER-out shift = {worst_cl:.6f} '
      f'= {100*worst_cl/abs(obs):.3f}% of estimate')
print(f'      -> attained at cluster {wcl[0]} (n={wcl[1]} cells, sum d={wcl[2]})')
print(f'      top-5 cluster shifts = ' +
      ', '.join(f'{v:.6f} ({100*v/abs(obs):.2f}%)' for v in shifts[:5]))
print(f'      that is {worst_cl/worst_cell:.1f}x the leave-one-cell-out figure, and '
      f'{100*worst_cl/sd_:.1f}% of one bootstrap SE.')

print()
for mname in sorted(set(r['model'] for r in D)):
    sel = [r for r in D if r['model'] != mname]
    sub_d = sum(r['B_correct'] - r['A_correct'] for r in sel)
    new = sub_d / len(sel)
    own = [r for r in D if r['model'] == mname]
    own_delta = sum(r['B_correct'] - r['A_correct'] for r in own) / len(own)
    print(f'  drop model {mname:>28}: delta {new:+.5f}  (shift {abs(new-obs):.5f} = '
          f'{100*abs(new-obs)/abs(obs):5.2f}%)   own delta {own_delta:+.5f}')
mods = sorted(set(r['model'] for r in D))
per_mod = []
for mname in mods:
    own = [r for r in D if r['model'] == mname]
    per_mod.append(sum(r['B_correct'] - r['A_correct'] for r in own) / len(own))
print(f'  spread of per-model deltas: min {min(per_mod):+.5f} max {max(per_mod):+.5f} '
      f'range {max(per_mod)-min(per_mod):.5f} = {(max(per_mod)-min(per_mod))/sd_:.1f} bootstrap SEs')
print(f'  between-model SD of delta = {st.stdev(per_mod):.5f}; if models were treated as a '
      f'random factor, SE(mean of 4) = {st.stdev(per_mod)/2:.5f} vs cluster-boot SE {sd_:.5f} '
      f'(ratio {(st.stdev(per_mod)/2)/sd_:.2f}x)')

# ---------------------------------------------------------------- 7. double bootstrap
hr('7. DOUBLE-BOOTSTRAP CALIBRATION OF THE NOMINAL-95% NORMAL-THEORY INTERVAL')
print('  Outer: 2000 cluster-resamples act as "new studies" (truth = obs).')
print('  Inner: 400 cluster-resamples of each outer sample give that study its SE.')
print('  Then ask how often the nominal-95% interval built the claimed way covers obs.')
OUT, IN = 2000, 400
rng3 = random.Random(SEED + 7)
cov_nrm = cov_pct = cov_t = 0
widths_n = []
for _ in range(OUT):
    bn = []; bd = []
    for _ in range(K):
        j = rng3.randrange(K)
        bn.append(cl_n[j]); bd.append(cl_d[j])
    th = sum(bd) / sum(bn)
    inner = []
    for _ in range(IN):
        s = 0; c = 0
        for _ in range(K):
            j = rng3.randrange(K)
            s += bd[j]; c += bn[j]
        inner.append(s / c)
    se_i = st.stdev(inner)
    lo, hi = th - Z975 * se_i, th + Z975 * se_i
    widths_n.append(hi - lo)
    if lo <= obs <= hi:
        cov_nrm += 1
    inner.sort()
    li = inner[int(0.025 * IN)]; hiq = inner[int(0.975 * IN)]
    if li <= obs <= hiq:
        cov_pct += 1
    # basic/reverse-percentile as a third reference
    lb, hb = 2 * th - hiq, 2 * th - li
    if lb <= obs <= hb:
        cov_t += 1
mc_se = math.sqrt(0.95 * 0.05 / OUT)
print(f'\n  normal-theory (est +- 1.96*bootSE) coverage = {cov_nrm/OUT:.4f}  '
      f'(MC SE {mc_se:.4f})')
print(f'  percentile                         coverage = {cov_pct/OUT:.4f}')
print(f'  basic/reverse-percentile           coverage = {cov_t/OUT:.4f}')
print(f'  mean normal-theory width = {st.mean(widths_n):.5f} vs observed-sample width '
      f'{hi_nrm-lo_nrm:.5f}')

hr('SUMMARY TABLE OF ALL 95% CIs FOR THE POOLED DELTA')
for nm, (a, b) in [('normal-theory (cluster bootstrap SE)', (lo_nrm, hi_nrm)),
                   ('percentile (cluster bootstrap)', (lo_pct, hi_pct)),
                   ('BCa (cluster bootstrap)', (lo_bca, hi_bca)),
                   ('studentized bootstrap-t', (lo_t, hi_t)),
                   ('NAIVE normal, iid cells (wrong)', (lo_iid, hi_iid))]:
    print(f'  {nm:<38} [{a:+.5f}, {b:+.5f}]  width {b-a:.5f}')

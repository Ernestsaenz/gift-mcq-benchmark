"""
Independent recomputation of the "normality-and-scale" claim.

Stdlib only. Implements Shapiro-Wilk (Royston 1992, AS R94) from scratch,
plus the normal quantile function (Acklam rational approx + one Halley
refinement using math.erfc), and a Monte-Carlo null calibration.

Everything printed here was computed by this script. Nothing is quoted from
the claim under review.
"""
import json, math, random, statistics, collections

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"

# ---------------------------------------------------------------- normal cdf / ppf
def norm_cdf(z):
    return 0.5 * math.erfc(-z / math.sqrt(2.0))

def norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2.0))

_A = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
      1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
_B = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
      6.680131188771972e+01, -1.328068155288572e+01]
_C = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
      -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
_D = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
      3.754408661907416e+00]

def norm_ppf(p):
    """Acklam's inverse normal CDF + one Halley refinement."""
    if p <= 0.0 or p >= 1.0:
        raise ValueError(p)
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        x = (((((_C[0]*q+_C[1])*q+_C[2])*q+_C[3])*q+_C[4])*q+_C[5]) / \
            ((((_D[0]*q+_D[1])*q+_D[2])*q+_D[3])*q+1)
    elif p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        x = -(((((_C[0]*q+_C[1])*q+_C[2])*q+_C[3])*q+_C[4])*q+_C[5]) / \
             ((((_D[0]*q+_D[1])*q+_D[2])*q+_D[3])*q+1)
    else:
        q = p - 0.5
        r = q * q
        x = (((((_A[0]*r+_A[1])*r+_A[2])*r+_A[3])*r+_A[4])*r+_A[5])*q / \
            (((((_B[0]*r+_B[1])*r+_B[2])*r+_B[3])*r+_B[4])*r+1)
    e = norm_cdf(x) - p
    u = e * math.sqrt(2 * math.pi) * math.exp(x * x / 2)
    x = x - u / (1 + x * u / 2)
    return x

# ---------------------------------------------------------------- Shapiro-Wilk
def _sw_coeffs(n):
    """Royston (1992) AS R94 coefficients a_i."""
    m = [norm_ppf((i - 0.375) / (n + 0.25)) for i in range(1, n + 1)]
    ssm = sum(v * v for v in m)
    rsn = 1.0 / math.sqrt(n)
    a = [0.0] * n
    c_n = m[n-1] / math.sqrt(ssm)
    c_n1 = m[n-2] / math.sqrt(ssm)
    an = (-2.706056*rsn**5 + 4.434685*rsn**4 - 2.071190*rsn**3
          - 0.147981*rsn**2 + 0.221157*rsn + c_n)
    if n > 5:
        an1 = (-3.582633*rsn**5 + 5.682633*rsn**4 - 1.752461*rsn**3
               - 0.293762*rsn**2 + 0.042981*rsn + c_n1)
        phi = ((ssm - 2*m[n-1]**2 - 2*m[n-2]**2)
               / (1 - 2*an**2 - 2*an1**2))
        a[n-1] = an;  a[0] = -an
        a[n-2] = an1; a[1] = -an1
        for i in range(2, n - 2):
            a[i] = m[i] / math.sqrt(phi)
    else:
        phi = (ssm - 2*m[n-1]**2) / (1 - 2*an**2)
        a[n-1] = an; a[0] = -an
        for i in range(1, n - 1):
            a[i] = m[i] / math.sqrt(phi)
    return a

_COEF_CACHE = {}
def sw_coeffs(n):
    if n not in _COEF_CACHE:
        _COEF_CACHE[n] = _sw_coeffs(n)
    return _COEF_CACHE[n]

def shapiro(x):
    """Return (W, p). p from Royston's normalising transform, valid 12<=n<=5000.
    p far in the tail is an EXTRAPOLATION of that transform, not an exact p."""
    n = len(x)
    xs = sorted(x)
    a = sw_coeffs(n)
    xbar = sum(xs) / n
    ss = sum((v - xbar) ** 2 for v in xs)
    if ss == 0:
        return float('nan'), float('nan')
    num = sum(a[i] * xs[i] for i in range(n)) ** 2
    W = num / ss
    if W >= 1.0:
        W = 1.0 - 1e-15
    ln_n = math.log(n)
    if n < 12:
        raise ValueError("n<12 branch not implemented")
    mu = 0.0038915*ln_n**3 - 0.083751*ln_n**2 - 0.31082*ln_n - 1.5861
    sigma = math.exp(0.0030302*ln_n**2 - 0.082676*ln_n - 0.4803)
    z = (math.log(1 - W) - mu) / sigma
    return W, norm_sf(z)

# ---------------------------------------------------------------- data
recs = [r for r in json.load(open(PATH)) if r["analysis_include"]]
print("=" * 74)
print("0. DATA SHAPE")
print("=" * 74)
per_item_n = collections.Counter(r["question_id"] for r in recs)
print(f"cells={len(recs)}  items={len(per_item_n)}  "
      f"clusters={len(set(r['cluster'] for r in recs))}  "
      f"models={len(set(r['model'] for r in recs))}")
print("models-per-item distribution:", dict(collections.Counter(per_item_n.values())))
odd = [(k, v) for k, v in per_item_n.items() if v != 4]
print("items NOT observed under all 4 models:", odd)

def per_group(key, field):
    num = collections.Counter(); den = collections.Counter()
    for r in recs:
        num[r[key]] += r[field]; den[r[key]] += 1
    return {k: num[k] / den[k] for k in den}, den

itemA, itemden = per_group("question_id", "A_correct")
itemB, _ = per_group("question_id", "B_correct")
clusA, clusden = per_group("cluster", "A_correct")
clusB, _ = per_group("cluster", "B_correct")

def describe(vals, label, show_counts=True):
    v = list(vals)
    n = len(v)
    cnt = collections.Counter(round(x, 6) for x in v)
    singletons = sum(1 for k, c in cnt.items() if c == 1)
    tied = (n - singletons) / n
    W, p = shapiro(v)
    print(f"\n{label}: n={n}  mean={sum(v)/n:.6f}  sd={statistics.stdev(v):.6f}")
    print(f"  distinct values = {len(cnt)}   tied fraction = {tied:.4f}")
    if show_counts:
        print("  value counts:", dict(sorted(cnt.items())))
    print(f"  Shapiro-Wilk  W={W:.6f}  p={p:.4g}")
    return W, p, len(cnt), tied

print("\n" + "=" * 74)
print("1. PER-ITEM ACCURACY  (recomputed)")
print("=" * 74)
WA, pA, kA, tA = describe(itemA.values(), "condition A")
WB, pB, kB, tB = describe(itemB.values(), "condition B")

print("\n" + "=" * 74)
print("2. PER-CLUSTER ACCURACY  (recomputed)")
print("=" * 74)
print("cluster size (cells) distribution:",
      dict(sorted(collections.Counter(clusden.values()).items())))
WcA, pcA, kcA, tcA = describe(clusA.values(), "condition A")
WcB, pcB, kcB, tcB = describe(clusB.values(), "condition B")

# ---------------------------------------------------------------- validation of my SW
print("\n" + "=" * 74)
print("3. VALIDATION OF MY SHAPIRO-WILK IMPLEMENTATION")
print("=" * 74)
rng = random.Random(20260731)
rej = 0; REPS = 2000
for _ in range(REPS):
    s = [rng.gauss(0, 1) for _ in range(325)]
    if shapiro(s)[1] < 0.05:
        rej += 1
print(f"  truly-Gaussian N(0,1), n=325, {REPS} reps: "
      f"type-I rate at 0.05 = {rej}/{REPS} = {rej/REPS:.4f}  (nominal 0.05)")
rng = random.Random(99)
rej2 = 0
for _ in range(500):
    s = [rng.expovariate(1.0) for _ in range(60)]
    if shapiro(s)[1] < 0.05:
        rej2 += 1
print(f"  Exponential(1), n=60, 500 reps: power at 0.05 = {rej2/500:.3f} "
      "(should be ~1.0)")

# ---------------------------------------------------------------- null calibration
print("\n" + "=" * 74)
print("4. NULL CALIBRATION: does SW reject IDEAL Binomial(4,p)/4 data?")
print("=" * 74)

def binom_draw(rng, k, p):
    return sum(1 for _ in range(k) if rng.random() < p)

def calib(p, n, k, reps, seed, label, hetero_sd=None):
    rng = random.Random(seed)
    rej = 0; Ws = []
    for _ in range(reps):
        vals = []
        for _ in range(n):
            pi = p
            if hetero_sd:
                lo = math.log(p / (1 - p)) + rng.gauss(0, hetero_sd)
                pi = 1 / (1 + math.exp(-lo))
            vals.append(binom_draw(rng, k, pi) / k)
        W, pv = shapiro(vals)
        Ws.append(W)
        if pv < 0.05:
            rej += 1
    print(f"  {label}: p={p:.4f} n={n} k={k} reps={reps}"
          + (f" logit-sd={hetero_sd}" if hetero_sd else ""))
    print(f"    rejects at 0.05: {rej}/{reps} = {rej/reps*100:.1f}%   "
          f"median W={statistics.median(Ws):.4f}  max W={max(Ws):.4f}")
    return rej / reps

mA = sum(itemA.values()) / len(itemA)
mB = sum(itemB.values()) / len(itemB)
print(f"  observed per-item means: A={mA:.4f}  B={mB:.4f}")
calib(mA, 325, 4, 2000, 11, "ideal homogeneous, cond A")
calib(mB, 325, 4, 2000, 22, "ideal homogeneous, cond B")
calib(mA, 325, 4, 1000, 33, "ideal + item heterogeneity, cond A", hetero_sd=1.5)
calib(mB, 325, 4, 1000, 44, "ideal + item heterogeneity, cond B", hetero_sd=1.5)
print("\n  --- how far does the granularity artefact extend? ---")
for p0 in (0.5, 0.7, 0.9):
    calib(p0, 325, 4, 500, 100 + int(p0 * 100), f"k=4  p={p0}")
for k in (4, 8, 20, 50):
    calib(0.5, 325, k, 500, 200 + k, f"p=0.5  k={k} (draws per item)")

# ------------------------------------------------- is discreteness the WHOLE story?
print("\n" + "=" * 74)
print("5. DOES SW STILL REJECT AFTER REMOVING TIES? (jitter check)")
print("=" * 74)
for label, vals in (("item A", list(itemA.values())), ("item B", list(itemB.values())),
                    ("cluster A", list(clusA.values())), ("cluster B", list(clusB.values()))):
    rng = random.Random(7)
    j = [v + rng.uniform(-1e-6, 1e-6) for v in vals]
    W, p = shapiro(j)
    print(f"    {label}: jittered W={W:.4f} p={p:.3g}  (0 ties, W ~unchanged)")

print("\n" + "=" * 74)
print("6. SHAPE: observed vs ideal-binomial reference distribution")
print("=" * 74)
def moments(v):
    n = len(v); m = sum(v)/n
    s = statistics.pstdev(v)
    g1 = sum((x-m)**3 for x in v)/n/s**3
    g2 = sum((x-m)**4 for x in v)/n/s**4 - 3
    return m, s, g1, g2
obs = {}
for label, v in (("A", list(itemA.values())), ("B", list(itemB.values()))):
    m, s, g1, g2 = moments(v)
    obs[label] = (m, s, g1, g2, shapiro(v)[0])
    print(f"  observed item {label}: sd={s:.4f} skew={g1:+.3f} exkurt={g2:+.3f} W={obs[label][4]:.4f}")
for label, p, seed in (("A", mA, 5), ("B", mB, 6)):
    rng = random.Random(seed)
    sk = []; ku = []; sds = []; ws = []
    for _ in range(2000):
        v = [binom_draw(rng, 4, p)/4 for _ in range(325)]
        _, s, g1, g2 = moments(v)
        sds.append(s); sk.append(g1); ku.append(g2); ws.append(shapiro(v)[0])
    for arr in (sk, ku, sds, ws): arr.sort()
    print(f"  ideal    item {label}: sd 95%CI=[{sds[50]:.4f},{sds[1949]:.4f}] "
          f"skew 95%CI=[{sk[50]:+.3f},{sk[1949]:+.3f}] "
          f"exkurt 95%CI=[{ku[50]:+.3f},{ku[1949]:+.3f}]")
    o = obs[label]
    print(f"      -> observed sd {'INSIDE' if sds[50]<=o[1]<=sds[1949] else 'OUTSIDE'} ideal band; "
          f"skew {'INSIDE' if sk[50]<=o[2]<=sk[1949] else 'OUTSIDE'}; "
          f"exkurt {'INSIDE' if ku[50]<=o[3]<=ku[1949] else 'OUTSIDE'}")
    print(f"      -> ideal W 95%CI=[{ws[50]:.4f},{ws[1949]:.4f}]; observed W={o[4]:.4f} "
          f"{'INSIDE' if ws[50]<=o[4]<=ws[1949] else 'OUTSIDE'}")
    # MC p-value for observed W under the ideal-binomial null
    cnt = sum(1 for w in ws if w <= o[4])
    print(f"      -> MC p(W_ideal <= W_obs) = {(cnt+1)/(len(ws)+1):.4f}  "
          "(calibrated 'is it binomial-shaped?' test)")
print("\ndone.")

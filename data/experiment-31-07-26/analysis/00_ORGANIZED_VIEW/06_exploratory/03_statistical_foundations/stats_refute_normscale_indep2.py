"""
Follow-up probes on the "normality-and-scale" claim.

Q1. The claim says its simulation "demonstrates the test cannot distinguish the
    observed data from an ideally-behaved binomial." Test that directly by using
    the simulation as a CALIBRATED reference distribution for W.
Q2. If W does discriminate, what dependence structure does the departure point to?
Q3. Is the departure driven by the single 3-model item?
Q4. The claim says the per-item/per-cluster aggregation "rescue does not work."
    Test whether the CLT rescue (t-interval on n=325 item means) actually works.
"""
import json, math, random, statistics, collections
import importlib.util, sys

spec = importlib.util.spec_from_file_location(
    "indep",
    "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/stats_refute_normscale_indep.py")
# avoid re-running the whole first script: re-declare what we need instead.

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"

def norm_cdf(z): return 0.5 * math.erfc(-z / math.sqrt(2.0))
def norm_sf(z):  return 0.5 * math.erfc(z / math.sqrt(2.0))

_A = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
      1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
_B = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
      6.680131188771972e+01, -1.328068155288572e+01]
_C = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
      -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
_D = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
      3.754408661907416e+00]

def norm_ppf(p):
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2*math.log(p))
        x = (((((_C[0]*q+_C[1])*q+_C[2])*q+_C[3])*q+_C[4])*q+_C[5]) / ((((_D[0]*q+_D[1])*q+_D[2])*q+_D[3])*q+1)
    elif p > phigh:
        q = math.sqrt(-2*math.log(1-p))
        x = -(((((_C[0]*q+_C[1])*q+_C[2])*q+_C[3])*q+_C[4])*q+_C[5]) / ((((_D[0]*q+_D[1])*q+_D[2])*q+_D[3])*q+1)
    else:
        q = p-0.5; r = q*q
        x = (((((_A[0]*r+_A[1])*r+_A[2])*r+_A[3])*r+_A[4])*r+_A[5])*q / (((((_B[0]*r+_B[1])*r+_B[2])*r+_B[3])*r+_B[4])*r+1)
    e = norm_cdf(x) - p
    u = e*math.sqrt(2*math.pi)*math.exp(x*x/2)
    return x - u/(1 + x*u/2)

def _sw_coeffs(n):
    m = [norm_ppf((i-0.375)/(n+0.25)) for i in range(1, n+1)]
    ssm = sum(v*v for v in m); rsn = 1.0/math.sqrt(n); a = [0.0]*n
    c_n, c_n1 = m[n-1]/math.sqrt(ssm), m[n-2]/math.sqrt(ssm)
    an  = (-2.706056*rsn**5 + 4.434685*rsn**4 - 2.071190*rsn**3 - 0.147981*rsn**2 + 0.221157*rsn + c_n)
    an1 = (-3.582633*rsn**5 + 5.682633*rsn**4 - 1.752461*rsn**3 - 0.293762*rsn**2 + 0.042981*rsn + c_n1)
    phi = (ssm - 2*m[n-1]**2 - 2*m[n-2]**2) / (1 - 2*an**2 - 2*an1**2)
    a[n-1]=an; a[0]=-an; a[n-2]=an1; a[1]=-an1
    for i in range(2, n-2): a[i] = m[i]/math.sqrt(phi)
    return a

_CC = {}
def sw_coeffs(n):
    if n not in _CC: _CC[n] = _sw_coeffs(n)
    return _CC[n]

def shapiro(x):
    n = len(x); xs = sorted(x); a = sw_coeffs(n)
    xbar = sum(xs)/n; ss = sum((v-xbar)**2 for v in xs)
    if ss == 0: return float('nan'), float('nan')
    W = sum(a[i]*xs[i] for i in range(n))**2 / ss
    if W >= 1.0: W = 1.0 - 1e-15
    ln_n = math.log(n)
    mu = 0.0038915*ln_n**3 - 0.083751*ln_n**2 - 0.31082*ln_n - 1.5861
    sigma = math.exp(0.0030302*ln_n**2 - 0.082676*ln_n - 0.4803)
    return W, norm_sf((math.log(1-W)-mu)/sigma)

recs = [r for r in json.load(open(PATH)) if r["analysis_include"]]
num = collections.Counter(); den = collections.Counter()
numB = collections.Counter()
for r in recs:
    num[r["question_id"]] += r["A_correct"]
    numB[r["question_id"]] += r["B_correct"]
    den[r["question_id"]] += 1
itemA = {k: num[k]/den[k] for k in den}
itemB = {k: numB[k]/den[k] for k in den}
mA = sum(itemA.values())/len(itemA)
mB = sum(itemB.values())/len(itemB)

def binom_draw(rng, k, p):
    return sum(1 for _ in range(k) if rng.random() < p)

print("="*74)
print("Q1. USE THE CLAIM'S OWN SIMULATION AS A CALIBRATED REFERENCE FOR W")
print("="*74)
print("   The alpha=0.05 DECISION is degenerate (100% rejection) -- agreed.")
print("   But is the STATISTIC uninformative? Compare observed W to the null band.")
REPS = 20000
for label, obsvals, p in (("A", list(itemA.values()), mA), ("B", list(itemB.values()), mB)):
    Wobs = shapiro(obsvals)[0]
    rng = random.Random(1234 + ord(label))
    ws = []
    for _ in range(REPS):
        ws.append(shapiro([binom_draw(rng, 4, p)/4 for _ in range(325)])[0])
    ws.sort()
    lo, hi = ws[int(0.025*REPS)], ws[int(0.975*REPS)]
    cnt = sum(1 for w in ws if w <= Wobs)
    print(f"\n  condition {label}: W_obs = {Wobs:.5f}")
    print(f"    ideal Binomial(4,{p:.4f})/4 null: W 95% band = [{lo:.5f}, {hi:.5f}]  "
          f"min over {REPS} reps = {min(ws):.5f}")
    print(f"    MC p-value  P(W_null <= W_obs) = {(cnt+1)/(REPS+1):.5f}   (reps={REPS})")
    print(f"    -> observed is {'MORE non-normal than' if Wobs < lo else 'compatible with'} the ideal binomial")

print("\n" + "="*74)
print("Q2. WHAT DEPENDENCE STRUCTURE MOVES W TOWARD THE OBSERVED VALUE?")
print("="*74)
print("  Exchangeable within-item model agreement: with prob rho all 4 models")
print("  share one Bernoulli(p) outcome; else 4 independent Bernoulli(p).")
for label, obsvals, p in (("A", list(itemA.values()), mA), ("B", list(itemB.values()), mB)):
    Wobs = shapiro(obsvals)[0]
    print(f"\n  condition {label} (W_obs={Wobs:.4f}, sd_obs={statistics.pstdev(obsvals):.4f}):")
    for rho in (0.0, 0.2, 0.4, 0.6, 0.8):
        rng = random.Random(777 + int(rho*100) + ord(label))
        ws = []; sds = []
        for _ in range(1000):
            v = []
            for _ in range(325):
                if rng.random() < rho:
                    v.append(1.0 if rng.random() < p else 0.0)
                else:
                    v.append(binom_draw(rng, 4, p)/4)
            ws.append(shapiro(v)[0]); sds.append(statistics.pstdev(v))
        ws.sort(); sds.sort()
        flag = "  <== brackets W_obs" if ws[25] <= Wobs <= ws[974] else ""
        print(f"    rho={rho:.1f}: W 95%band=[{ws[25]:.4f},{ws[974]:.4f}] "
              f"sd 95%band=[{sds[25]:.4f},{sds[974]:.4f}]{flag}")

print("\n" + "="*74)
print("Q3. IS ANY OF THIS DRIVEN BY THE ONE 3-MODEL ITEM (b320)?")
print("="*74)
for label, d in (("A", itemA), ("B", itemB)):
    full = list(d.values())
    drop = [v for k, v in d.items() if k != "b320"]
    print(f"  cond {label}: with b320 n={len(full)} W={shapiro(full)[0]:.5f} | "
          f"without b320 n={len(drop)} W={shapiro(drop)[0]:.5f} | "
          f"distinct without = {len(set(round(x,6) for x in drop))}")

print("\n" + "="*74)
print("Q4. DOES THE AGGREGATION 'RESCUE' ACTUALLY FAIL FOR ITS PURPOSE?")
print("="*74)
print("  The rescue's purpose is CLT validity for a t-interval on the MEAN of")
print("  n=325 item proportions -- not marginal normality of the observations.")
print("  Coverage check: resample 325 item values from the observed empirical")
print("  distribution, build a 95% t-interval, count how often it covers the")
print("  true (= observed empirical) mean.  Iid bootstrap; ignores clustering.")

def tcrit_975(df):
    # Cornish-Fisher / Peizer-Pratt style expansion for t quantile, df large.
    z = norm_ppf(0.975)
    g1 = (z**3 + z)/4
    g2 = (5*z**5 + 16*z**3 + 3*z)/96
    g3 = (3*z**7 + 19*z**5 + 17*z**3 - 15*z)/384
    return z + g1/df + g2/df**2 + g3/df**3

for label, d in (("A", itemA), ("B", itemB)):
    vals = list(d.values()); n = len(vals)
    truth = sum(vals)/n
    tc = tcrit_975(n-1)
    rng = random.Random(31337 + ord(label))
    cov = 0; lo_miss = 0; hi_miss = 0; REP = 20000
    for _ in range(REP):
        s = [vals[int(rng.random()*n)] for _ in range(n)]
        m = sum(s)/n
        sd = statistics.stdev(s)
        half = tc*sd/math.sqrt(n)
        if m - half <= truth <= m + half: cov += 1
        elif truth < m - half: lo_miss += 1
        else: hi_miss += 1
    print(f"  cond {label}: t_crit(df={n-1})={tc:.4f}  nominal 95%  "
          f"empirical coverage = {cov/REP:.4f}  "
          f"(miss low {lo_miss/REP:.4f} / miss high {hi_miss/REP:.4f})")

print("\n  Same check on per-CLUSTER means (n=208, unequal cluster sizes):")
cn = collections.Counter(); cd = collections.Counter(); cnB = collections.Counter()
for r in recs:
    cn[r["cluster"]] += r["A_correct"]; cnB[r["cluster"]] += r["B_correct"]; cd[r["cluster"]] += 1
clus = {"A": {k: cn[k]/cd[k] for k in cd}, "B": {k: cnB[k]/cd[k] for k in cd}}
for label in ("A", "B"):
    vals = list(clus[label].values()); n = len(vals)
    truth = sum(vals)/n; tc = tcrit_975(n-1)
    rng = random.Random(4242 + ord(label))
    cov = 0; REP = 20000
    for _ in range(REP):
        s = [vals[int(rng.random()*n)] for _ in range(n)]
        m = sum(s)/n; sd = statistics.stdev(s)
        half = tc*sd/math.sqrt(n)
        if m - half <= truth <= m + half: cov += 1
    print(f"    cond {label}: n={n} empirical coverage = {cov/REP:.4f}")

print("\n" + "="*74)
print("Q5. HOW EXTREME IS THE REPORTED SW p? (transform-range sanity)")
print("="*74)
for label, vals in (("item A", list(itemA.values())), ("item B", list(itemB.values()))):
    W, p = shapiro(vals)
    ln_n = math.log(len(vals))
    mu = 0.0038915*ln_n**3 - 0.083751*ln_n**2 - 0.31082*ln_n - 1.5861
    sigma = math.exp(0.0030302*ln_n**2 - 0.082676*ln_n - 0.4803)
    z = (math.log(1-W)-mu)/sigma
    print(f"  {label}: W={W:.5f} -> Royston z={z:.3f} -> p={p:.3g}")
print("  Royston's normalising transform was fitted to the body of the null")
print("  distribution; z of this size is far outside the fitted range, so the")
print("  exponent of these p-values is an EXTRAPOLATION, not a calibrated tail area.")
print("\ndone.")

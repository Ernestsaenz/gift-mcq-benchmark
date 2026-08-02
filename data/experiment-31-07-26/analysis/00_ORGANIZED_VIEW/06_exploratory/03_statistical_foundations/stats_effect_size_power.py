#!/usr/bin/env python3
"""
Effect size + precision analysis for the A(verbatim) vs B(NOTA-swap) paired MCQ design.

Stdlib only. Everything computed from data; no library p-values.

Outputs:
  1. per-model and pooled: pA, pB, raw risk difference RD = pB - pA
  2. odds ratio from discordant pairs (McNemar OR = n10/n01)
  3. Cohen's g (paired/sign-test effect size, = p10 - 0.5) and Cohen's h (arcsine)
  4. 95% CI by cluster bootstrap (resample the 208 clusters w/ replacement, 10000 reps)
  5. 95% CI by exact binomial (Clopper-Pearson) on the discordant pairs
  6. retrospective precision: MDE at 80% power, alpha=.05 two-sided, given this
     cluster structure, both analytically (from the cluster-robust SE) and by
     Monte-Carlo simulation with a beta-binomial cluster model calibrated to data.

Coding of the discordant cells:
  n10 = A wrong -> B correct   (B better)
  n01 = A correct -> B wrong   (B worse)
  RD = (n10 - n01)/N
"""
import json, math, random, statistics
from collections import defaultdict, Counter

random.seed(20260731)

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
B_REPS = 10000
Z975 = 1.959963984540054
Z80 = 0.8416212335729143

# ---------------------------------------------------------------- math helpers
def betacf(a, b, x):
    MAXIT, EPS, FPMIN = 300, 3e-16, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN: d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN: d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN: c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN: d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN: c = FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS: break
    return h

def betai(a, b, x):
    """Regularised incomplete beta I_x(a,b)."""
    if x <= 0.0: return 0.0
    if x >= 1.0: return 1.0
    lbeta = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
             + a * math.log(x) + b * math.log(1.0 - x))
    bt = math.exp(lbeta)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * betacf(a, b, x) / a
    return 1.0 - bt * betacf(b, a, 1.0 - x) / b

def beta_quantile(p, a, b):
    """Inverse of I_x(a,b) by bisection."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if betai(a, b, mid) < p: lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)

def clopper_pearson(k, n, alpha=0.05):
    """Exact binomial CI for k/n."""
    lo = 0.0 if k == 0 else beta_quantile(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta_quantile(1 - alpha / 2, k + 1, n - k)
    return lo, hi

def binom_two_sided_exact_p(k, n, p0=0.5):
    """Exact two-sided binomial (sign / McNemar exact) p-value, small-p method."""
    def pmf(i):
        return math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                        + i * math.log(p0) + (n - i) * math.log(1 - p0))
    if n == 0: return 1.0
    obs = pmf(k)
    tot = 0.0
    for i in range(n + 1):
        v = pmf(i)
        if v <= obs * (1 + 1e-9): tot += v
    return min(1.0, tot)

def norm_p_two(z):
    return math.erfc(abs(z) / math.sqrt(2.0))

def pct(sorted_vals, q):
    """Percentile of a sorted list, linear interpolation."""
    n = len(sorted_vals)
    if n == 0: return float("nan")
    idx = q * (n - 1)
    lo = int(math.floor(idx)); hi = int(math.ceil(idx))
    if lo == hi: return sorted_vals[lo]
    return sorted_vals[lo] + (idx - lo) * (sorted_vals[hi] - sorted_vals[lo])

def cohen_h(p1, p2):
    return 2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2))

# ---------------------------------------------------------------- data
raw = json.load(open(PATH))
rows = [r for r in raw if r["analysis_include"]]
MODELS = sorted(set(r["model"] for r in rows))

def stats_from_cells(cells):
    """cells = list of (A_correct, B_correct)."""
    N = len(cells)
    a = sum(c[0] for c in cells); b = sum(c[1] for c in cells)
    n11 = sum(1 for c in cells if c[0] == 1 and c[1] == 1)
    n10 = sum(1 for c in cells if c[0] == 0 and c[1] == 1)   # B better
    n01 = sum(1 for c in cells if c[0] == 1 and c[1] == 0)   # B worse
    n00 = sum(1 for c in cells if c[0] == 0 and c[1] == 0)
    pA, pB = a / N, b / N
    nd = n10 + n01
    return dict(N=N, pA=pA, pB=pB, RD=pB - pA, n11=n11, n10=n10, n01=n01, n00=n00,
                nd=nd, p10=(n10 / nd if nd else float("nan")))

def eff_or(n10, n01, haldane=False):
    if haldane: return (n10 + 0.5) / (n01 + 0.5)
    if n01 == 0: return float("inf")
    if n10 == 0: return 0.0
    return n10 / n01

# cluster -> cells, keyed per model and pooled
def build(model=None):
    byclu = defaultdict(list)
    for r in rows:
        if model is not None and r["model"] != model: continue
        byclu[r["cluster"]].append((r["A_correct"], r["B_correct"]))
    return byclu

# ---------------------------------------------------------------- bootstrap
def cluster_bootstrap(byclu, reps=B_REPS):
    keys = list(byclu.keys())
    K = len(keys)
    pools = [byclu[k] for k in keys]
    RDs, ORs, Gs, PAs, PBs, HS = [], [], [], [], [], []
    for _ in range(reps):
        cells = []
        for _ in range(K):
            cells.extend(pools[random.randrange(K)])
        s = stats_from_cells(cells)
        RDs.append(s["RD"])
        # Haldane-corrected OR inside replicates so zero cells don't kill the CI
        ORs.append(eff_or(s["n10"], s["n01"], haldane=True))
        Gs.append((s["n10"] + 0.5) / (s["nd"] + 1.0) - 0.5 if s["nd"] >= 0 else float("nan"))
        PAs.append(s["pA"]); PBs.append(s["pB"])
        HS.append(cohen_h(s["pB"], s["pA"]))
    out = {}
    for name, arr in (("RD", RDs), ("OR", ORs), ("g", Gs), ("pA", PAs), ("pB", PBs), ("h", HS)):
        a = sorted(arr)
        out[name] = dict(lo=pct(a, 0.025), hi=pct(a, 0.975), se=statistics.pstdev(arr),
                         med=pct(a, 0.5))
    out["_RD_draws"] = RDs
    return out

def cluster_robust_se_rd(byclu):
    """Cluster-robust SE of RD = mean(d), d = B - A, clusters independent."""
    N = sum(len(v) for v in byclu.values())
    S = {k: sum(b - a for a, b in v) for k, v in byclu.items()}
    rd = sum(S.values()) / N
    var = sum((S[k] - len(byclu[k]) * rd) ** 2 for k in byclu) / (N ** 2)
    return rd, math.sqrt(var)

def iid_se_rd(cells):
    d = [b - a for a, b in cells]
    n = len(d)
    m = sum(d) / n
    v = sum((x - m) ** 2 for x in d) / (n - 1)
    return math.sqrt(v / n)

# ---------------------------------------------------------------- ICC helpers
def icc_oneway(groups):
    """One-way random-effects ICC(1) for a list of lists of numbers."""
    groups = [g for g in groups if len(g) > 0]
    k = len(groups)
    N = sum(len(g) for g in groups)
    if k < 2 or N <= k: return 0.0, 0.0
    grand = sum(sum(g) for g in groups) / N
    msb = sum(len(g) * (sum(g) / len(g) - grand) ** 2 for g in groups) / (k - 1)
    msw = sum(sum((x - sum(g) / len(g)) ** 2 for x in g) for g in groups) / (N - k)
    m0 = (N - sum(len(g) ** 2 for g in groups) / N) / (k - 1)
    if msb + (m0 - 1) * msw == 0: return 0.0, m0
    return (msb - msw) / (msb + (m0 - 1) * msw), m0

# ---------------------------------------------------------------- report core
def analyse(label, byclu):
    cells = [c for v in byclu.values() for c in v]
    s = stats_from_cells(cells)
    N, n10, n01, nd = s["N"], s["n10"], s["n01"], s["nd"]

    # point effect sizes
    OR = eff_or(n10, n01)
    OR_h = eff_or(n10, n01, haldane=True)
    p10 = s["p10"]
    g = p10 - 0.5 if nd else float("nan")
    h = cohen_h(s["pB"], s["pA"])

    # exact binomial on discordant pairs -> CI for p10, then OR and RD
    if nd > 0:
        lo_p, hi_p = clopper_pearson(n10, nd)
        ex = dict(p10=(lo_p, hi_p),
                  g=(lo_p - 0.5, hi_p - 0.5),
                  OR=(lo_p / (1 - lo_p) if lo_p < 1 else float("inf"),
                      hi_p / (1 - hi_p) if hi_p < 1 else float("inf")),
                  RD=((nd / N) * (2 * lo_p - 1), (nd / N) * (2 * hi_p - 1)))
        p_exact = binom_two_sided_exact_p(n10, nd, 0.5)
    else:
        ex, p_exact = None, 1.0

    boot = cluster_bootstrap(byclu)
    rd_pt, se_cl = cluster_robust_se_rd(byclu)
    se_iid = iid_se_rd(cells)

    # ICCs on the paired difference
    d_groups = [[b - a for a, b in v] for v in byclu.values()]
    icc_d, m0 = icc_oneway(d_groups)
    deff_icc = 1 + (m0 - 1) * max(icc_d, 0.0)
    deff_emp = (se_cl / se_iid) ** 2
    deff_boot = (boot["RD"]["se"] / se_iid) ** 2

    # bootstrap p-value for RD (fraction of draws on the other side of 0, doubled)
    dr = boot["_RD_draws"]
    frac = sum(1 for x in dr if x >= 0) / len(dr)
    p_boot = min(1.0, 2 * min(frac, 1 - frac))

    return dict(label=label, s=s, OR=OR, OR_h=OR_h, g=g, h=h, ex=ex, boot=boot,
                se_cl=se_cl, se_iid=se_iid, icc_d=icc_d, m0=m0, deff_icc=deff_icc,
                deff_emp=deff_emp, deff_boot=deff_boot, p_exact=p_exact, p_boot=p_boot,
                z_cl=(rd_pt / se_cl if se_cl > 0 else float("nan")))

def fmt(x, n=4):
    if x != x: return "nan"
    if x == float("inf"): return "inf"
    return f"{x:.{n}f}"

results = {}
print("=" * 100)
print("EFFECT SIZE + PRECISION :: A (verbatim) vs B (NOTA text swap), paired, runs=1")
print(f"cells={len(rows)}  items={len(set(r['question_id'] for r in rows))}  "
      f"clusters={len(set(r['cluster'] for r in rows))}  models={len(MODELS)}")
print(f"bootstrap reps={B_REPS} (clusters resampled with replacement); seed=20260731")
print("=" * 100)

for label, model in [("POOLED", None)] + [(m, m) for m in MODELS]:
    byclu = build(model)
    res = analyse(label, byclu)
    results[label] = res
    s = res["s"]; b = res["boot"]; ex = res["ex"]
    print(f"\n--- {label} ---")
    print(f"  N cells={s['N']}  clusters={len(byclu)}  "
          f"table: n11={s['n11']} n10(A wrong->B right)={s['n10']} "
          f"n01(A right->B wrong)={s['n01']} n00={s['n00']}  discordant={s['nd']} "
          f"({100*s['nd']/s['N']:.1f}%)")
    print(f"  pA={fmt(s['pA'])}  pB={fmt(s['pB'])}")
    print(f"  RD (B-A)          = {fmt(s['RD'])}   "
          f"cluster-boot 95% CI [{fmt(b['RD']['lo'])}, {fmt(b['RD']['hi'])}]  "
          f"bootSE={fmt(b['RD']['se'])}")
    if ex:
        print(f"                       exact-binomial (conditional on {s['nd']} discordant) "
              f"95% CI [{fmt(ex['RD'][0])}, {fmt(ex['RD'][1])}]")
    print(f"  OR (n10/n01)      = {fmt(res['OR'],3)}  (Haldane {fmt(res['OR_h'],3)})  "
          f"cluster-boot 95% CI [{fmt(b['OR']['lo'],3)}, {fmt(b['OR']['hi'],3)}]")
    if ex:
        print(f"                       exact-binomial 95% CI "
              f"[{fmt(ex['OR'][0],3)}, {fmt(ex['OR'][1],3)}]")
    print(f"  Cohen g (p10-.5)  = {fmt(res['g'])}   "
          f"cluster-boot 95% CI [{fmt(b['g']['lo'])}, {fmt(b['g']['hi'])}]")
    if ex:
        print(f"                       exact-binomial 95% CI "
              f"[{fmt(ex['g'][0])}, {fmt(ex['g'][1])}]")
    print(f"  Cohen h (arcsine, marginals) = {fmt(res['h'])}   "
          f"cluster-boot 95% CI [{fmt(b['h']['lo'])}, {fmt(b['h']['hi'])}]")
    print(f"  SE(RD): iid={fmt(res['se_iid'],5)}  cluster-robust={fmt(res['se_cl'],5)}  "
          f"cluster-bootstrap={fmt(b['RD']['se'],5)}")
    print(f"  ICC(d) within cluster={fmt(res['icc_d'],4)}  mean cluster size m0={fmt(res['m0'],2)}  "
          f"DEFF: 1+(m0-1)ICC={fmt(res['deff_icc'],3)}  empirical(robust/iid)^2={fmt(res['deff_emp'],3)}  "
          f"bootstrap^2={fmt(res['deff_boot'],3)}")
    print(f"  p (exact McNemar/binomial on discordants) = {res['p_exact']:.3g}   "
          f"p (cluster-bootstrap percentile) = {res['p_boot']:.3g}   "
          f"p (cluster-robust normal z={fmt(res['z_cl'],2)}) = {norm_p_two(res['z_cl']):.3g}")

# ---------------------------------------------------------------- power / MDE
print("\n" + "=" * 100)
print("RETROSPECTIVE PRECISION / MDE")
print("=" * 100)

def mde_analytic(se):
    return (Z975 + Z80) * se

def power_analytic(delta, se):
    lam = abs(delta) / se
    # P(|Z| > 1.96) with Z ~ N(lam,1); upper tail dominates
    up = 0.5 * math.erfc((Z975 - lam) / math.sqrt(2))
    lo = 0.5 * math.erfc((Z975 + lam) / math.sqrt(2))
    return up + lo

# --- beta-binomial simulation calibrated to the pooled cluster structure
def beta_params(mu, rho):
    if rho <= 1e-6 or mu <= 1e-9 or mu >= 1 - 1e-9: return None
    rho = min(rho, 0.95)
    s = (1 - rho) / rho
    a, b = mu * s, (1 - mu) * s
    if a <= 1e-9 or b <= 1e-9: return None
    return a, b

def draw_beta(a, b):
    x = random.gammavariate(a, 1.0); y = random.gammavariate(b, 1.0)
    t = x + y
    return x / t if t > 0 else 0.5

def simulate_power(cluster_sizes, pi_d, delta, rho_d, rho_dir, nsim=4000, want_se=False):
    """Beta-binomial cluster model.
       pi_d = P(cell is discordant); direction P(B better | discordant) = p from delta.
       delta = pi_d*(2p-1)  ->  p = (1 + delta/pi_d)/2
    """
    p = (1 + delta / pi_d) / 2.0
    p = min(max(p, 1e-4), 1 - 1e-4)
    bp_d = beta_params(pi_d, rho_d)
    bp_dir = beta_params(p, rho_dir)
    N = sum(cluster_sizes)
    rej_cl = rej_iid = 0
    ses = []
    for _ in range(nsim):
        Ssum = 0; Ss = []; n10t = 0; n01t = 0
        for nc in cluster_sizes:
            pic = draw_beta(*bp_d) if bp_d else pi_d
            pdc = draw_beta(*bp_dir) if bp_dir else p
            nd = 0
            for _ in range(nc):
                if random.random() < pic: nd += 1
            n10 = 0
            for _ in range(nd):
                if random.random() < pdc: n10 += 1
            n01 = nd - n10
            n10t += n10; n01t += n01
            Sc = n10 - n01
            Ss.append((Sc, nc)); Ssum += Sc
        rd = Ssum / N
        var = sum((Sc - nc * rd) ** 2 for Sc, nc in Ss) / (N ** 2)
        se_cl = math.sqrt(var)
        if want_se: ses.append(se_cl)
        nd_t = n10t + n01t
        se_id = math.sqrt(max(nd_t - (n10t - n01t) ** 2 / N, 0.0)) / N
        if se_cl > 0 and abs(rd / se_cl) > Z975: rej_cl += 1
        if se_id > 0 and abs(rd / se_id) > Z975: rej_iid += 1
    if want_se:
        return rej_cl / nsim, rej_iid / nsim, (sum(ses) / len(ses) if ses else float("nan"))
    return rej_cl / nsim, rej_iid / nsim

def calibrate_rho_dir(cluster_sizes, pi_d, delta_obs, rho_d, se_target, nsim=1500):
    """Pick the cluster-level ICC of the *direction* process so that the simulated
    mean cluster-robust SE at the observed effect reproduces the empirical one.
    Returns (rho_dir, simulated_SE_at_that_rho)."""
    lo, hi = 0.0, 0.90
    _, _, se_lo = simulate_power(cluster_sizes, pi_d, delta_obs, rho_d, 0.0,
                                 nsim=nsim, want_se=True)
    if se_lo >= se_target:      # even zero direction-ICC over-shoots
        return 0.0, se_lo
    best = (0.0, se_lo)
    for _ in range(10):
        mid = 0.5 * (lo + hi)
        _, _, se = simulate_power(cluster_sizes, pi_d, delta_obs, rho_d, mid,
                                  nsim=nsim, want_se=True)
        best = (mid, se)
        if se < se_target: lo = mid
        else: hi = mid
    return best

def find_mde_sim(cluster_sizes, pi_d, rho_d, rho_dir, nsim=4000, target=0.80,
                 lo=0.0005, hi=None):
    if hi is None: hi = 0.95 * pi_d
    for _ in range(13):
        mid = 0.5 * (lo + hi)
        pw, _ = simulate_power(cluster_sizes, pi_d, mid, rho_d, rho_dir, nsim=nsim)
        if pw < target: lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)

# ICC of discordance indicator and of direction, pooled
byclu_pool = build(None)
disc_groups, dir_groups, sizes_pool = [], [], []
for k, v in byclu_pool.items():
    dd = [1 if a != b else 0 for a, b in v]
    disc_groups.append(dd)
    dirs = [1 if (a == 0 and b == 1) else 0 for a, b in v if a != b]
    if dirs: dir_groups.append(dirs)
    sizes_pool.append(len(v))
icc_disc, m0_disc = icc_oneway(disc_groups)
icc_dir, m0_dir = icc_oneway(dir_groups)
pool = results["POOLED"]["s"]
pi_d_pool = pool["nd"] / pool["N"]
print(f"\ncalibration (pooled): pi_discordant={fmt(pi_d_pool)}  "
      f"ICC(discordance)={fmt(icc_disc)}  ICC(direction|discordant)={fmt(icc_dir)}  "
      f"mean cluster size (cells)={fmt(m0_disc,2)}")

rho_d = max(icc_disc, 0.0); rho_dir = max(icc_dir, 0.0)

print("\n-- analytic MDE at 80% power, alpha=.05 two-sided, MDE = (1.96+0.842)*SE --")
print(f"{'stratum':<28}{'SE_iid':>10}{'SE_cluster':>12}{'MDE_iid':>10}{'MDE_cluster':>13}"
      f"{'MDE_boot':>11}{'power@obs':>11}")
for label in ["POOLED"] + MODELS:
    r = results[label]
    se_b = r["boot"]["RD"]["se"]
    print(f"{label:<28}{fmt(r['se_iid'],5):>10}{fmt(r['se_cl'],5):>12}"
          f"{fmt(mde_analytic(r['se_iid'])):>10}{fmt(mde_analytic(r['se_cl'])):>13}"
          f"{fmt(mde_analytic(se_b)):>11}"
          f"{fmt(power_analytic(r['s']['RD'], se_b),3):>11}")

print("\n-- simulation MDE (beta-binomial cluster model, exact observed cluster sizes) --")
print("   the direction-ICC is calibrated so the simulated cluster-robust SE at the")
print("   OBSERVED effect reproduces the empirical cluster-robust SE (variance match)")
print(f"pooled cluster sizes: {len(sizes_pool)} clusters, "
      f"sizes(count) {sorted(Counter(sizes_pool).items())}")

sim_rows = []
for label in ["POOLED"] + MODELS:
    r = results[label]
    byc = build(None if label == "POOLED" else label)
    sizes_m = [len(v) for v in byc.values()]
    pi_d_m = r["s"]["nd"] / r["s"]["N"]
    dg = [[1 if a != b else 0 for a, b in v] for v in byc.values()]
    ic_d, _ = icc_oneway(dg)
    rd_obs = r["s"]["RD"]
    se_emp = r["se_cl"]
    rho_dir_cal, se_sim = calibrate_rho_dir(sizes_m, pi_d_m, rd_obs, max(ic_d, 0.0),
                                            se_emp, nsim=1500)
    m = find_mde_sim(sizes_m, pi_d_m, max(ic_d, 0.0), rho_dir_cal,
                     nsim=4000 if label == "POOLED" else 3000)
    pw_cl, pw_iid = simulate_power(sizes_m, pi_d_m, m, max(ic_d, 0.0), rho_dir_cal,
                                   nsim=4000)
    sim_rows.append((label, pi_d_m, ic_d, rho_dir_cal, se_emp, se_sim, m, pw_cl, pw_iid))
    print(f"{label:<28} pi_d={fmt(pi_d_m,3)} ICC_disc={fmt(ic_d,3)} "
          f"rho_dir(calibrated)={fmt(rho_dir_cal,3)} "
          f"SE_emp={fmt(se_emp,5)} SE_sim={fmt(se_sim,5)} "
          f"-> MDE={fmt(m)} ({100*m:.2f} pp)  "
          f"power@MDE: cluster-robust {pw_cl:.3f} / naive {pw_iid:.3f}")

# power curve at plausible smaller effects, pooled + single model
print("\n-- power at plausible smaller true effects (analytic, cluster-bootstrap SE) --")
grid = [0.01, 0.02, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20]
hdr = f"{'stratum':<28}" + "".join(f"{100*d:>8.1f}pp" for d in grid)
print(hdr)
for label in ["POOLED"] + MODELS:
    se_b = results[label]["boot"]["RD"]["se"]
    print(f"{label:<28}" + "".join(f"{power_analytic(d, se_b):>10.3f}" for d in grid))

# how many items would be needed for 80% power at smaller effects (pooled, single model)
print("\n-- items required for 80% power vs true RD (scaling the observed cluster-robust SE) --")
print("   (SE scales as sqrt(n0/n); n0 = observed cells; assumes same discordance + ICC)")
for label in ["POOLED", MODELS[0]]:
    r = results[label]
    se0, n0 = r["boot"]["RD"]["se"], r["s"]["N"]
    line = []
    for d in [0.02, 0.03, 0.05, 0.075, 0.10]:
        n_need = n0 * ((Z975 + Z80) * se0 / d) ** 2
        line.append(f"{100*d:.1f}pp:{n_need:,.0f} cells")
    print(f"   {label:<26}" + "   ".join(line))

json.dump({k: dict(N=v["s"]["N"], pA=v["s"]["pA"], pB=v["s"]["pB"], RD=v["s"]["RD"],
                   n10=v["s"]["n10"], n01=v["s"]["n01"], nd=v["s"]["nd"],
                   OR=v["OR"], g=v["g"], h=v["h"],
                   boot_RD=[v["boot"]["RD"]["lo"], v["boot"]["RD"]["hi"]],
                   boot_OR=[v["boot"]["OR"]["lo"], v["boot"]["OR"]["hi"]],
                   boot_g=[v["boot"]["g"]["lo"], v["boot"]["g"]["hi"]],
                   exact_RD=list(v["ex"]["RD"]) if v["ex"] else None,
                   exact_OR=list(v["ex"]["OR"]) if v["ex"] else None,
                   exact_g=list(v["ex"]["g"]) if v["ex"] else None,
                   se_iid=v["se_iid"], se_cl=v["se_cl"], se_boot=v["boot"]["RD"]["se"],
                   p_exact=v["p_exact"], p_boot=v["p_boot"])
           for k, v in results.items()},
          open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
               "experiment-31-07-26/analysis/stats_effect_size_power_out.json", "w"), indent=1)
print("\n[wrote stats_effect_size_power_out.json]")

#!/usr/bin/env python3
"""
Independent coverage simulations for the exact (Clopper-Pearson-on-discordants)
RD interval vs cluster-robust / cluster-bootstrap intervals.

Three questions the original left open:
  Q1. Pure-iid (NO clustering): how badly does the CP-derived RD interval cover?
      This isolates the 'conditioning on n_d' defect, which is the part the claim
      quantifies analytically as '18-34% too narrow before clustering'.
  Q2. Clustered: reproduce the claim's 0.743 / per-model numbers.
  Q3. Robustness: the original put ALL cluster heterogeneity in the DIRECTION
      probability p and none in the discordance rate pi_d.  Redo with the
      heterogeneity in pi_d instead (same calibrated design effect).  Does the
      verdict survive?
Standard library only.
"""
import json, math, random
from collections import defaultdict

random.seed(20260731)
Z975 = 1.959963984540054
BASE = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/"
rows = [r for r in json.load(open(BASE + "paired_clean.json")) if r["analysis_include"]]
MODELS = sorted({r["model"] for r in rows})


# ---- fast regularized incomplete beta (validated against stats_refute_exactci_01 tail inversion)
def betacf(a, b, x):
    MAXIT, EPS, FPMIN = 300, 3e-16, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < FPMIN: d = FPMIN
    d = 1.0 / d; h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d; d = FPMIN if abs(d) < FPMIN else d; d = 1.0 / d
        c = 1.0 + aa / c; c = FPMIN if abs(c) < FPMIN else c
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d; d = FPMIN if abs(d) < FPMIN else d; d = 1.0 / d
        c = 1.0 + aa / c; c = FPMIN if abs(c) < FPMIN else c
        de = d * c; h *= de
        if abs(de - 1.0) < EPS: break
    return h


def betai(a, b, x):
    if x <= 0.0: return 0.0
    if x >= 1.0: return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                  + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0): return bt * betacf(a, b, x) / a
    return 1.0 - bt * betacf(b, a, 1.0 - x) / b


def beta_q(pr, a, b):
    lo, hi = 0.0, 1.0
    for _ in range(70):
        mid = 0.5 * (lo + hi)
        if betai(a, b, mid) < pr: lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)


def cp(k, n, alpha=0.05):
    if n == 0: return 0.0, 1.0
    lo = 0.0 if k == 0 else beta_q(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta_q(1 - alpha / 2, k + 1, n - k)
    return lo, hi


def beta_ab(mu, rho):
    if rho <= 1e-9 or mu <= 1e-12 or mu >= 1 - 1e-12: return None
    rho = min(rho, 0.95)
    s = (1 - rho) / rho
    a, b = mu * s, (1 - mu) * s
    return (a, b) if a > 1e-9 and b > 1e-9 else None


def rbeta(ab):
    a, b = ab
    x = random.gammavariate(a, 1.0); y = random.gammavariate(b, 1.0)
    t = x + y
    return x / t if t > 0 else 0.5


# ---------------------------------------------------------------- strata setup
def setup(sub):
    byclu = defaultdict(int)
    for r in sub: byclu[r["cluster"]] += 1
    sizes = sorted(byclu.values(), reverse=True)
    N = sum(sizes)
    n10 = sum(1 for r in sub if r["A_correct"] == 0 and r["B_correct"] == 1)
    n01 = sum(1 for r in sub if r["A_correct"] == 1 and r["B_correct"] == 0)
    nd = n10 + n01
    pi_d, p = nd / N, n10 / nd
    delta = (n10 - n01) / N
    Q = sum(s * s for s in sizes)
    return dict(sizes=sizes, N=N, Q=Q, pi_d=pi_d, p=p, delta=delta,
                V0=pi_d * (1 - pi_d * (2 * p - 1) ** 2))


STRATA = [("POOLED", rows)] + [(m, [r for r in rows if r["model"] == m]) for m in MODELS]
CFG = {lab: setup(sub) for lab, sub in STRATA}
SENS = json.load(open(BASE + "stats_mde_sensitivity_out.json"))
for lab in CFG:
    CFG[lab]["deff_obs"] = max(SENS[lab]["deff"], 1.0)   # target design effect


def one_dataset(cfg, mode, rho):
    """mode 'dir' -> heterogeneity in direction p; 'dis' -> heterogeneity in pi_d."""
    pi_d, p = cfg["pi_d"], cfg["p"]
    ab = beta_ab(p if mode == "dir" else pi_d, rho)
    n10t = n01t = 0; Ss = []
    for nc in cfg["sizes"]:
        if mode == "dir":
            pc, pdc = pi_d, (rbeta(ab) if ab else p)
        else:
            pc, pdc = (rbeta(ab) if ab else pi_d), p
        ndc = sum(1 for _ in range(nc) if random.random() < pc)
        a = sum(1 for _ in range(ndc) if random.random() < pdc)
        b = ndc - a
        n10t += a; n01t += b
        Ss.append((a - b, nc))
    return n10t, n01t, Ss


def run(cfg, mode, rho, nsim, label):
    N, delta = cfg["N"], cfg["delta"]
    ce = cw = cn = 0; we = ww = 0.0; sds = []
    for _ in range(nsim):
        n10t, n01t, Ss = one_dataset(cfg, mode, rho)
        tot = n10t - n01t
        rd = tot / N
        sds.append(rd)
        ndt = n10t + n01t
        lo_p, hi_p = cp(n10t, ndt)
        lo_e = (ndt / N) * (2 * lo_p - 1); hi_e = (ndt / N) * (2 * hi_p - 1)
        se_c = math.sqrt(sum((Sc - nc * rd) ** 2 for Sc, nc in Ss)) / N
        lo_w, hi_w = rd - Z975 * se_c, rd + Z975 * se_c
        se_n = math.sqrt(max(ndt - tot * tot / N, 0.0)) / N
        lo_n, hi_n = rd - Z975 * se_n, rd + Z975 * se_n
        ce += lo_e <= delta <= hi_e
        cw += lo_w <= delta <= hi_w
        cn += lo_n <= delta <= hi_n
        we += hi_e - lo_e; ww += hi_w - lo_w
    mu = sum(sds) / nsim
    sd = math.sqrt(sum((x - mu) ** 2 for x in sds) / (nsim - 1))
    f = lambda c: c / nsim
    mcse = lambda c: math.sqrt(f(c) * (1 - f(c)) / nsim)
    print(f"{label:<40}{f(ce):>9.3f}{mcse(ce):>8.3f}{f(cw):>9.3f}{f(cn):>9.3f}"
          f"{we/nsim:>9.4f}{ww/nsim:>9.4f}{sd:>10.5f}")
    return f(ce), f(cw), f(cn), sd


NSIM = 6000
hdr = f"{'':<40}{'cov_exact':>9}{'mcse':>8}{'cov_rob':>9}{'cov_iid':>9}{'w_exact':>9}{'w_rob':>9}{'sd(RD)':>10}"

# ------------------------------------------------- Q1: pure iid, no clustering
print("=" * 104)
print("Q1. PURE IID TRINOMIAL (rho = 0, NO clustering). Isolates the conditioning defect alone.")
print("    Analytic prediction for a Wald interval with SE too small by factor r: cov = 2*Phi(1.96/r)-1")
print("=" * 104)
print(hdr)
q1 = {}
for lab, _ in STRATA:
    c = CFG[lab]
    r_an = math.sqrt((1 - c["pi_d"] * (2 * c["p"] - 1) ** 2) / (1 - (2 * c["p"] - 1) ** 2))
    pred = math.erf(Z975 / r_an / math.sqrt(2))
    q1[lab] = run(c, "dir", 0.0, NSIM, f"{lab}  [analytic-Wald pred {pred:.3f}]")

# ------------------------------------------------- Q2/Q3: clustered
def rho_for(cfg, mode, deff):
    N, Q, V0, pi_d, p = cfg["N"], cfg["Q"], cfg["V0"], cfg["pi_d"], cfg["p"]
    if Q <= N or deff <= 1.0: return 0.0
    if mode == "dir":
        g = (deff - 1) * N * V0 / (pi_d ** 2 * (Q - N))
        return min(g / (4 * p * (1 - p)), 0.95)
    g = (deff - 1) * N * V0 / ((2 * p - 1) ** 2 * pi_d * (1 - pi_d) * (Q - N))
    return min(g, 0.95)


for mode, title in (("dir", "Q2. CLUSTERED, heterogeneity in DIRECTION p (the original's generative model)"),
                    ("dis", "Q3. CLUSTERED, heterogeneity in DISCORDANCE RATE pi_d (alternative, same DEFF)")):
    print("\n" + "=" * 104)
    print(title)
    print("=" * 104)
    print(hdr)
    for lab, _ in STRATA:
        c = CFG[lab]
        rho = rho_for(c, mode, c["deff_obs"])
        run(c, mode, rho, NSIM, f"{lab}  rho={rho:.3f} deff_tgt={c['deff_obs']:.2f}")

# ------------------------------------------------- Q4: does the BOOTSTRAP itself cover?
print("\n" + "=" * 104)
print("Q4. Coverage of the actual CLUSTER PERCENTILE BOOTSTRAP (not the robust-Wald proxy),")
print("    POOLED design, direction-ICC model, 1200 sims x 600 bootstrap resamples")
print("=" * 104)
c = CFG["POOLED"]; rho = rho_for(c, "dir", c["deff_obs"])
NS, NB = 1200, 600
cb = cw = 0
for _ in range(NS):
    n10t, n01t, Ss = one_dataset(c, "dir", rho)
    N = c["N"]; rd = (n10t - n01t) / N
    K = len(Ss)
    est = []
    for _ in range(NB):
        t = n = 0
        for _ in range(K):
            sc, nc = Ss[random.randrange(K)]
            t += sc; n += nc
        est.append(t / n)
    est.sort()
    lo, hi = est[int(0.025 * NB)], est[int(math.ceil(0.975 * NB)) - 1]
    cb += lo <= c["delta"] <= hi
    se_c = math.sqrt(sum((Sc - nc * rd) ** 2 for Sc, nc in Ss)) / N
    cw += rd - Z975 * se_c <= c["delta"] <= rd + Z975 * se_c
print(f"  cluster percentile bootstrap: coverage = {cb/NS:.3f} (MC SE {math.sqrt((cb/NS)*(1-cb/NS)/NS):.3f})")
print(f"  cluster-robust Wald (proxy) : coverage = {cw/NS:.3f} (MC SE {math.sqrt((cw/NS)*(1-cw/NS)/NS):.3f})")
print("  nominal = 0.950")

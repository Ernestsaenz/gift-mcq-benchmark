#!/usr/bin/env python3
"""
Retrospective precision (MDE at 80% power) under three ways of carrying the observed
cluster structure to a smaller hypothetical effect. Stdlib only.

The observed cluster-robust SE of RD is a fact of the data. What is NOT determined by
the data is how much of that clustering survives when the true effect shrinks, because
the paired difference d in {-1,0,+1} can only be cluster-correlated through
  (i)  cluster-level heterogeneity in the DISCORDANCE rate, whose contribution to
       Cov(d_i,d_j) is proportional to (2p-1)^2 and therefore vanishes as delta -> 0, or
  (ii) cluster-level heterogeneity in the DIRECTION of discordance, whose contribution
       is proportional to Var(p_c) and survives as delta -> 0.
Both models are calibrated to reproduce the OBSERVED cluster-robust SE at the OBSERVED
effect, then extrapolated down. They bracket the truth. A third, model-free option holds
the empirical design effect constant.
"""
import json, math, random
from collections import defaultdict, Counter

random.seed(11071977)
Z975 = 1.959963984540054
Z80 = 0.8416212335729143
PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"

rows = [r for r in json.load(open(PATH)) if r["analysis_include"]]
MODELS = sorted(set(r["model"] for r in rows))

def build(model=None):
    byclu = defaultdict(list)
    for r in rows:
        if model is not None and r["model"] != model: continue
        byclu[r["cluster"]].append((r["A_correct"], r["B_correct"]))
    return byclu

def emp(byclu):
    cells = [c for v in byclu.values() for c in v]
    N = len(cells)
    n10 = sum(1 for a, b in cells if a == 0 and b == 1)
    n01 = sum(1 for a, b in cells if a == 1 and b == 0)
    rd = (n10 - n01) / N
    S = {k: sum(b - a for a, b in v) for k, v in byclu.items()}
    var_cl = sum((S[k] - len(byclu[k]) * rd) ** 2 for k in byclu) / N ** 2
    d = [b - a for a, b in cells]
    m = sum(d) / N
    var_iid = sum((x - m) ** 2 for x in d) / (N - 1) / N
    sizes = [len(v) for v in byclu.values()]
    m_eff = sum(n * n for n in sizes) / N          # variance-weighted mean cluster size
    return dict(N=N, n10=n10, n01=n01, pi_d=(n10 + n01) / N, rd=rd,
                se_cl=math.sqrt(var_cl), se_iid=math.sqrt(var_iid),
                deff=var_cl / var_iid, sizes=sizes, m_eff=m_eff)

def beta_ab(mu, rho):
    if rho <= 1e-6 or mu <= 1e-9 or mu >= 1 - 1e-9: return None
    rho = min(rho, 0.95); s = (1 - rho) / rho
    a, b = mu * s, (1 - mu) * s
    return (a, b) if a > 1e-9 and b > 1e-9 else None

def rbeta(ab):
    a, b = ab
    x = random.gammavariate(a, 1.0); y = random.gammavariate(b, 1.0)
    t = x + y
    return x / t if t > 0 else 0.5

def sim(sizes, pi_d, delta, rho_d, rho_dir, nsim, collect_se=False):
    """Returns (power_cluster_robust, power_naive, mean_se_cluster_robust)."""
    p = min(max((1 + delta / pi_d) / 2.0, 1e-4), 1 - 1e-4)
    ab_d = beta_ab(pi_d, rho_d)
    ab_p = beta_ab(p, rho_dir)
    N = sum(sizes)
    rej_c = rej_n = 0; se_sum = 0.0
    for _ in range(nsim):
        tot = 0; Ss = []; n10t = 0; n01t = 0
        for nc in sizes:
            pic = rbeta(ab_d) if ab_d else pi_d
            pdc = rbeta(ab_p) if ab_p else p
            nd = 0
            for _ in range(nc):
                if random.random() < pic: nd += 1
            n10 = 0
            for _ in range(nd):
                if random.random() < pdc: n10 += 1
            n01 = nd - n10
            n10t += n10; n01t += n01
            Sc = n10 - n01
            Ss.append((Sc, nc)); tot += Sc
        rd = tot / N
        se_c = math.sqrt(sum((Sc - nc * rd) ** 2 for Sc, nc in Ss)) / N
        ndt = n10t + n01t
        se_n = math.sqrt(max(ndt - (n10t - n01t) ** 2 / N, 0.0)) / N
        se_sum += se_c
        if se_c > 0 and abs(rd / se_c) > Z975: rej_c += 1
        if se_n > 0 and abs(rd / se_n) > Z975: rej_n += 1
    return rej_c / nsim, rej_n / nsim, se_sum / nsim

def calibrate(sizes, pi_d, delta_obs, se_target, which, nsim=2000):
    """Find the ICC (of discordance if which=='disc', of direction if 'dir') that makes
    the simulated cluster-robust SE at the observed effect equal the empirical one."""
    lo, hi = 0.0, 0.90
    def f(rho):
        return sim(sizes, pi_d, delta_obs, rho if which == "disc" else 0.0,
                   0.0 if which == "disc" else rho, nsim)[2]
    if f(0.0) >= se_target: return 0.0, f(0.0)   # even ICC=0 overshoots
    if f(hi) <= se_target: return hi, f(hi)
    for _ in range(11):
        mid = 0.5 * (lo + hi)
        if f(mid) < se_target: lo = mid
        else: hi = mid
    r = 0.5 * (lo + hi)
    return r, f(r)

def mde_sim(sizes, pi_d, rho_d, rho_dir, nsim=3000, target=0.80):
    lo, hi = 0.0005, 0.95 * pi_d
    for _ in range(12):
        mid = 0.5 * (lo + hi)
        if sim(sizes, pi_d, mid, rho_d, rho_dir, nsim)[0] < target: lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)

def mde_fixed_deff(N, pi_d, deff):
    """Self-consistent: MDE = k*sqrt(deff*(pi_d - MDE^2)/N), k = z.975 + z.80."""
    k = Z975 + Z80
    x = 0.05
    for _ in range(200):
        x = k * math.sqrt(deff * max(pi_d - x * x, 1e-9) / N)
    return x

print("=" * 104)
print("MDE SENSITIVITY  (alpha=.05 two-sided, 80% power, cluster-aware test)")
print("seed=11071977; sim reps: calibration 2000, MDE bisection 3000/step, verification 6000")
print("=" * 104)
print(f"\n{'stratum':<26}{'N':>6}{'pi_d':>7}{'RD_obs':>9}{'SE_iid':>9}{'SE_clu':>9}"
      f"{'DEFF':>7}{'N_eff':>8}{'m_eff':>7}")
E = {}
for label in ["POOLED"] + MODELS:
    e = emp(build(None if label == "POOLED" else label)); E[label] = e
    print(f"{label:<26}{e['N']:>6}{e['pi_d']:>7.3f}{e['rd']:>9.4f}{e['se_iid']:>9.5f}"
          f"{e['se_cl']:>9.5f}{e['deff']:>7.3f}{e['N']/e['deff']:>8.0f}{e['m_eff']:>7.1f}")

print("\nMDE (percentage points) by method")
print(f"{'stratum':<26}{'A: empSE':>10}{'B: fixDEFF':>12}{'C: dir-ICC':>12}{'D: disc-ICC':>13}"
      f"{'  calibrated ICCs (dir / disc)':>32}")
out = {}
for label in ["POOLED"] + MODELS:
    e = E[label]
    A = (Z975 + Z80) * e["se_cl"]                       # MDE at the observed SE
    B = mde_fixed_deff(e["N"], e["pi_d"], e["deff"])    # DEFF held, var(d) at delta->MDE
    rdir, se_dir = calibrate(e["sizes"], e["pi_d"], e["rd"], e["se_cl"], "dir")
    rdis, se_dis = calibrate(e["sizes"], e["pi_d"], e["rd"], e["se_cl"], "disc")
    C = mde_sim(e["sizes"], e["pi_d"], 0.0, rdir)
    D = mde_sim(e["sizes"], e["pi_d"], rdis, 0.0)
    out[label] = dict(A=A, B=B, C=C, D=D, rdir=rdir, rdis=rdis,
                      se_dir=se_dir, se_dis=se_dis, **{k: e[k] for k in
                      ("N", "pi_d", "rd", "se_iid", "se_cl", "deff")})
    print(f"{label:<26}{100*A:>10.2f}{100*B:>12.2f}{100*C:>12.2f}{100*D:>13.2f}"
          f"{'':>6}{rdir:>8.3f} / {rdis:.3f}")

print("\nverification of the two simulation models at their own MDE (6000 reps):")
for label in ["POOLED"] + MODELS:
    e = E[label]; o = out[label]
    pc, pn, _ = sim(e["sizes"], e["pi_d"], o["C"], 0.0, o["rdir"], 6000)
    pc2, pn2, _ = sim(e["sizes"], e["pi_d"], o["D"], o["rdis"], 0.0, 6000)
    print(f"  {label:<24} model C: power={pc:.3f} (naive {pn:.3f})   "
          f"model D: power={pc2:.3f} (naive {pn2:.3f})")
    print(f"  {'':<24} calibration check at RD_obs: SE_emp={e['se_cl']:.5f}  "
          f"SE_sim(C)={o['se_dir']:.5f}  SE_sim(D)={o['se_dis']:.5f}")

print("\nheadline bracket (pp):")
for label in ["POOLED"] + MODELS:
    o = out[label]
    vals = [100 * o[k] for k in ("A", "B", "C", "D")]
    print(f"  {label:<24} MDE in [{min(vals):.2f}, {max(vals):.2f}] pp   "
          f"(model-free anchor A={vals[0]:.2f}, B={vals[1]:.2f})")

# observed effects vs the bracket
print("\nobserved |RD| vs MDE:")
for label in ["POOLED"] + MODELS:
    o = out[label]
    hi = max(100 * o[k] for k in ("A", "B", "C", "D"))
    print(f"  {label:<24} |RD_obs|={100*abs(o['rd']):.2f} pp  = {abs(o['rd'])/(hi/100):.1f}x "
          f"the most conservative MDE ({hi:.2f} pp)")

json.dump(out, open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
                    "experiment-31-07-26/analysis/stats_mde_sensitivity_out.json", "w"), indent=1)
print("\n[wrote stats_mde_sensitivity_out.json]")

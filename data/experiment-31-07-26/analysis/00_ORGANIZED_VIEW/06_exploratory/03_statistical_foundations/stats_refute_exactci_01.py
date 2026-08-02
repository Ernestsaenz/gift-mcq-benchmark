#!/usr/bin/env python3
"""
REFUTE-CHECK of the effect-size-and-power claim about the exact (Clopper-Pearson on
discordant pairs) interval for the paired risk difference.

Everything recomputed from paired_clean.json with independent implementations:
  * Clopper-Pearson by DIRECT inversion of the binomial tail (math.comb sums),
    not via an incomplete-beta continued fraction (the route the original used).
  * cluster bootstrap resampling the 208 clinical-context clusters.
  * analytic variance ratio  Var(RD)_true / Var(RD)_conditional.
  * the ACTUAL width deficiency of the CP-derived interval (CP is conservative,
    so the Wald-vs-Wald analytic ratio is NOT the interval's real narrowness).
Standard library only.
"""
import json, math, random
from collections import defaultdict

random.seed(1977_07_30)
Z975 = 1.959963984540054
BASE = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/"

rows = [r for r in json.load(open(BASE + "paired_clean.json")) if r["analysis_include"]]
MODELS = sorted({r["model"] for r in rows})
print(f"loaded {len(rows)} analysis cells, "
      f"{len({r['question_id'] for r in rows})} items, "
      f"{len({r['cluster'] for r in rows})} clusters, {len(MODELS)} models")


# ---------------------------------------------------------------- Clopper-Pearson
def binom_cdf(k, n, p):
    """P(X <= k). Direct summation of exact binomial pmf terms in log space."""
    if k < 0:  return 0.0
    if k >= n: return 1.0
    if p <= 0.0: return 1.0
    if p >= 1.0: return 0.0
    lp, lq = math.log(p), math.log1p(-p)
    tot = 0.0
    for i in range(0, k + 1):
        lt = math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq
        tot += math.exp(lt)
    return min(tot, 1.0)


def binom_sf(k, n, p):
    """P(X >= k)."""
    return 1.0 - binom_cdf(k - 1, n, p)


def cp_direct(k, n, alpha=0.05):
    """Clopper-Pearson by bisecting the binomial tail equations directly."""
    a = alpha / 2.0
    if k == 0:
        lo = 0.0
    else:
        f = lambda p: binom_sf(k, n, p) - a          # increasing in p
        x0, x1 = 0.0, 1.0
        for _ in range(200):
            m = 0.5 * (x0 + x1)
            if f(m) < 0: x0 = m
            else:        x1 = m
        lo = 0.5 * (x0 + x1)
    if k == n:
        hi = 1.0
    else:
        f = lambda p: binom_cdf(k, n, p) - a          # decreasing in p
        x0, x1 = 0.0, 1.0
        for _ in range(200):
            m = 0.5 * (x0 + x1)
            if f(m) > 0: x0 = m
            else:        x1 = m
        hi = 0.5 * (x0 + x1)
    return lo, hi


# ---------------------------------------------------------------- strata
def table(sub):
    N = len(sub)
    n10 = sum(1 for r in sub if r["A_correct"] == 0 and r["B_correct"] == 1)
    n01 = sum(1 for r in sub if r["A_correct"] == 1 and r["B_correct"] == 0)
    nd = n10 + n01
    return N, n10, n01, nd


STRATA = [("POOLED", rows)] + [(m, [r for r in rows if r["model"] == m]) for m in MODELS]

print("\n" + "=" * 104)
print("1. RAW TABLES + ANALYTIC VARIANCE RATIO  [1 - pi_d(2p-1)^2] / [1 - (2p-1)^2]")
print("=" * 104)
print(f"{'stratum':<26}{'N':>5}{'n10':>5}{'n01':>5}{'nd':>5}{'pi_d':>9}{'2p-1':>9}"
      f"{'RD':>10}{'varratio':>10}{'SEratio':>9}{'narrow%':>9}")
S = {}
for lab, sub in STRATA:
    N, n10, n01, nd = table(sub)
    pi_d = nd / N
    p = n10 / nd
    tp = 2 * p - 1
    rd = (n10 - n01) / N
    vr = (1 - pi_d * tp ** 2) / (1 - tp ** 2)
    ser = math.sqrt(vr)
    S[lab] = dict(N=N, n10=n10, n01=n01, nd=nd, pi_d=pi_d, p=p, rd=rd, vr=vr, ser=ser)
    print(f"{lab:<26}{N:>5}{n10:>5}{n01:>5}{nd:>5}{pi_d:>9.4f}{tp:>9.4f}"
          f"{rd:>10.4f}{vr:>10.3f}{ser:>9.3f}{100*(1-1/ser):>8.1f}%")

# ---------------------------------------------------------------- exact interval
print("\n" + "=" * 104)
print("2. CP-DERIVED EXACT RD INTERVAL (my own tail inversion) vs the reported one")
print("=" * 104)
MAIN = json.load(open(BASE + "stats_effect_size_power_out.json"))
print(f"{'stratum':<26}{'my exact RD CI':>26}{'reported':>26}{'max abs diff':>14}")
for lab, _ in STRATA:
    s = S[lab]
    lo_p, hi_p = cp_direct(s["n10"], s["nd"])
    lo = s["pi_d"] * (2 * lo_p - 1)
    hi = s["pi_d"] * (2 * hi_p - 1)
    s["ex"] = (lo, hi)
    rep = MAIN[lab]["exact_RD"]
    print(f"{lab:<26}[{lo:>11.5f},{hi:>11.5f}][{rep[0]:>11.5f},{rep[1]:>11.5f}]"
          f"{max(abs(lo-rep[0]), abs(hi-rep[1])):>14.2e}")

# ---------------------------------------------------------------- cluster bootstrap
print("\n" + "=" * 104)
print("3. CLUSTER BOOTSTRAP (independent, B=20000, percentile) vs reported")
print("=" * 104)
B = 20000
print(f"{'stratum':<26}{'my boot RD CI':>26}{'reported':>26}{'my se':>9}{'w_b/w_e':>9}")
for lab, sub in STRATA:
    byclu = defaultdict(list)
    for r in sub:
        byclu[r["cluster"]].append(1 if (r["A_correct"] == 0 and r["B_correct"] == 1)
                                   else (-1 if (r["A_correct"] == 1 and r["B_correct"] == 0) else 0))
    keys = list(byclu)
    agg = {k: (sum(v), len(v)) for k, v in byclu.items()}
    K = len(keys)
    est = []
    for _ in range(B):
        tot = n = 0
        for _ in range(K):
            sc, nc = agg[keys[random.randrange(K)]]
            tot += sc; n += nc
        est.append(tot / n)
    est.sort()
    lo = est[int(math.floor(0.025 * B))]
    hi = est[int(math.ceil(0.975 * B)) - 1]
    mu = sum(est) / B
    se = math.sqrt(sum((e - mu) ** 2 for e in est) / (B - 1))
    s = S[lab]; s["boot"] = (lo, hi); s["se_boot"] = se
    rep = MAIN[lab]["boot_RD"]
    we = s["ex"][1] - s["ex"][0]
    print(f"{lab:<26}[{lo:>11.5f},{hi:>11.5f}][{rep[0]:>11.5f},{rep[1]:>11.5f}]"
          f"{se:>9.5f}{(hi-lo)/we:>9.2f}")

# ------------------------------------------- ACTUAL narrowness of the CP interval
print("\n" + "=" * 104)
print("4. THE POINT THE CLAIM GLOSSES: analytic SE ratio is Wald-vs-Wald, but the")
print("   interval actually quoted is CLOPPER-PEARSON, which is conservative.")
print("   'correct iid' halfwidth = z * sqrt(pi_d - RD^2)/sqrt(N)   (unconditional trinomial)")
print("=" * 104)
print(f"{'stratum':<26}{'claimed narrow%':>16}{'ACTUAL narrow% vs iid':>23}{'vs cluster-boot':>17}")
for lab, _ in STRATA:
    s = S[lab]
    se_iid = math.sqrt(s["pi_d"] - s["rd"] ** 2) / math.sqrt(s["N"])
    hw_correct = Z975 * se_iid
    hw_ex = 0.5 * (s["ex"][1] - s["ex"][0])
    hw_boot = 0.5 * (s["boot"][1] - s["boot"][0])
    s["se_iid"] = se_iid
    print(f"{lab:<26}{100*(1-1/s['ser']):>15.1f}%{100*(1-hw_ex/hw_correct):>22.1f}%"
          f"{100*(1-hw_ex/hw_boot):>16.1f}%")

json.dump({k: {kk: vv for kk, vv in v.items()} for k, v in S.items()},
          open(BASE + "stats_refute_exactci_01_out.json", "w"), indent=1)
print("\nwrote stats_refute_exactci_01_out.json")

"""(i) Does the NOTA swap increase deliberation?  A_tokens vs B_tokens, paired.

Per cell we have a matched pair (same item, same model, condition A vs B).
Statistic of interest: median of the per-cell ratio B_tokens / A_tokens.
CI: nonparametric CLUSTER bootstrap (resample the 208 clusters with
replacement), percentile interval, B=4000.
Also: exact-conditional sign test (binomial, p=0.5) on the direction of the
paired difference, and Wilcoxon signed-rank with a normal approximation.
"""
import math
from mech_lib_effort import (load, MODELS, SHORT, median, mean, quantile,
                             cluster_bootstrap, boot_p_two_sided, rank_avg,
                             two_sided_z_p)

rows = load()


def med_ratio(rs):
    return median([r["B_tokens"] / r["A_tokens"] for r in rs])


def med_diff(rs):
    return median([r["B_tokens"] - r["A_tokens"] for r in rs])


def sign_test(rs):
    """Exact two-sided sign test: #(B>A) ~ Binom(n_nonties, 0.5)."""
    pos = sum(1 for r in rs if r["B_tokens"] > r["A_tokens"])
    neg = sum(1 for r in rs if r["B_tokens"] < r["A_tokens"])
    n = pos + neg
    if n == 0:
        return pos, neg, 1.0
    lo = min(pos, neg)
    # log-space to avoid overflow of math.comb for large n
    tail = sum(math.exp(math.lgamma(n + 1) - math.lgamma(k + 1)
                        - math.lgamma(n - k + 1) - n * math.log(2.0))
               for k in range(lo + 1))
    return pos, neg, min(1.0, 2 * tail)


def wilcoxon_sr(rs):
    """Wilcoxon signed-rank on B-A, normal approximation with tie correction."""
    d = [r["B_tokens"] - r["A_tokens"] for r in rs if r["B_tokens"] != r["A_tokens"]]
    n = len(d)
    if n < 10:
        return float("nan"), float("nan")
    ad = [abs(x) for x in d]
    rk = rank_avg(ad)
    Wp = sum(rk[i] for i in range(n) if d[i] > 0)
    mu = n * (n + 1) / 4.0
    # tie correction
    from collections import Counter
    tc = Counter(ad)
    tie_term = sum(t ** 3 - t for t in tc.values())
    var = n * (n + 1) * (2 * n + 1) / 24.0 - tie_term / 48.0
    z = (Wp - mu) / math.sqrt(var)
    return z, two_sided_z_p(z)


print("=" * 96)
print("(i) GENERATION EFFORT: A_tokens vs B_tokens, paired within (item, model)")
print("=" * 96)
print(f"{'model':<18} {'n':>4} {'medA':>7} {'medB':>7} {'medDiff':>8} "
      f"{'medRatio':>9} {'boot95 CI':>18} {'p_boot':>8} {'B>A':>5} {'B<A':>5} "
      f"{'p_sign':>10} {'p_wilcox':>10}")
allrows = rows
for m in MODELS + ["__ALL__"]:
    rs = allrows if m == "__ALL__" else [r for r in rows if r["model"] == m]
    pt, lo, hi, reps = cluster_bootstrap(rs, med_ratio, B=4000, seed=11)
    p_b = boot_p_two_sided(reps, 1.0)
    pos, neg, p_s = sign_test(rs)
    z, p_w = wilcoxon_sr(rs)
    md = med_diff(rs)
    name = "ALL POOLED" if m == "__ALL__" else SHORT[m]
    print(f"{name:<18} {len(rs):>4} {median([r['A_tokens'] for r in rs]):>7.0f} "
          f"{median([r['B_tokens'] for r in rs]):>7.0f} {md:>8.0f} "
          f"{pt:>9.3f} [{lo:>7.3f},{hi:>7.3f}] {p_b:>8.4f} {pos:>5} {neg:>5} "
          f"{p_s:>10.3g} {p_w:>10.3g}")

print()
print("-" * 96)
print("Token distribution detail (per model, per condition)")
print("-" * 96)
print(f"{'model':<18} {'cond':<4} {'mean':>9} {'p10':>7} {'p25':>7} {'p50':>7} "
      f"{'p75':>8} {'p90':>9} {'p99':>9} {'max':>9}")
for m in MODELS:
    for c in "AB":
        v = [r[c + "_tokens"] for r in rows if r["model"] == m]
        print(f"{SHORT[m]:<18} {c:<4} {mean(v):>9.1f} {quantile(v,.10):>7.0f} "
              f"{quantile(v,.25):>7.0f} {quantile(v,.50):>7.0f} "
              f"{quantile(v,.75):>8.0f} {quantile(v,.90):>9.0f} "
              f"{quantile(v,.99):>9.0f} {max(v):>9.0f}")

print()
print("-" * 96)
print("Mean of log2(B/A) per model  (geometric mean ratio), cluster bootstrap CI")
print("-" * 96)


def mean_log2ratio(rs):
    return mean([math.log2(r["B_tokens"] / r["A_tokens"]) for r in rs])


for m in MODELS:
    rs = [r for r in rows if r["model"] == m]
    pt, lo, hi, reps = cluster_bootstrap(rs, mean_log2ratio, B=4000, seed=12)
    print(f"{SHORT[m]:<18} mean log2 ratio = {pt:+.4f}  "
          f"geo-mean ratio = {2**pt:.3f}x  95% CI [{2**lo:.3f}, {2**hi:.3f}]  "
          f"p_boot={boot_p_two_sided(reps,0.0):.4g}")

print()
print("-" * 96)
print("Does the token increase depend on whether B was answered correctly?")
print("(split each model's cells by B_correct; median ratio in each)")
print("-" * 96)
print(f"{'model':<18} {'B_corr':>7} {'n':>5} {'medA':>7} {'medB':>7} {'medRatio':>9} {'95% CI':>20}")
for m in MODELS:
    for bc in (1, 0):
        rs = [r for r in rows if r["model"] == m and r["B_correct"] == bc]
        if len(rs) < 15:
            print(f"{SHORT[m]:<18} {bc:>7} {len(rs):>5}   (too few)")
            continue
        pt, lo, hi, _ = cluster_bootstrap(rs, med_ratio, B=2000, seed=13)
        print(f"{SHORT[m]:<18} {bc:>7} {len(rs):>5} "
              f"{median([r['A_tokens'] for r in rs]):>7.0f} "
              f"{median([r['B_tokens'] for r in rs]):>7.0f} "
              f"{pt:>9.3f}  [{lo:>7.3f},{hi:>7.3f}]")

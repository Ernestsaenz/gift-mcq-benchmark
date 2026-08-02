"""(ii-corrected) Does DELIBERATION (reasoning tokens) predict correctness?

Same two estimators as mech_02 but on reasoning_tokens instead of raw
completion_tokens, so the option-text echo cannot drive the result.

  * point-biserial r = Pearson r(correct, log2(reasoning_tokens+1));
    p from the t approximation, df = n-2, with a cluster-bootstrap 95% CI
    (208 clusters, 4000 reps, percentile) as the interval to trust.
  * logistic regression MLE (own Newton-Raphson), coefficient per 1 SD of
    log2(reasoning_tokens+1); Wald p from inverse observed information.

gemma-4-26b emits 0 reasoning tokens on every cell, so it is undefined there
and is reported as such rather than silently pooled.
"""
import math
from mech_merge import load_merged
from mech_lib_effort import (MODELS, SHORT, mean, sd, median, pearson,
                             logistic_fit, cluster_bootstrap, t_sf2, quantile)

rows = load_merged()
REAS = [m for m in MODELS if m != "google/gemma-4-26b-a4b-it"]


def lg(r, cond):
    return math.log2(r[cond + "_reason"] + 1)


print("=" * 104)
print("(ii-corrected) REASONING TOKENS vs CORRECTNESS, within model x condition")
print("=" * 104)
print(f"{'model':<18} {'cond':<5} {'n':>5} {'acc':>6} {'r_pb':>7} {'p_t':>10} "
      f"{'r_pb 95% CI (cluster boot)':>27} {'logit b/SD':>11} {'p_wald':>10} "
      f"{'b 95% CI (cluster boot)':>25}")
for m in REAS:
    rs_all = [r for r in rows if r["model"] == m]
    for cond in "AB":
        v = [lg(r, cond) for r in rs_all]
        mu, s = mean(v), sd(v)
        y = [float(r[cond + "_correct"]) for r in rs_all]
        n = len(rs_all)
        r = pearson(v, y)
        t = r * math.sqrt((n - 2) / max(1e-12, 1 - r * r))
        _, rlo, rhi, _ = cluster_bootstrap(
            rs_all, lambda z, c=cond: pearson([lg(x, c) for x in z],
                                              [float(x[c + "_correct"]) for x in z]),
            B=4000, seed=51)
        X = [[(lg(x, cond) - mu) / s] for x in rs_all]
        b, se = logistic_fit(X, y)
        zw = b[1] / se[1]

        def fit(z, c=cond, M=mu, S=s):
            XX = [[(lg(x, c) - M) / S] for x in z]
            yy = [float(x[c + "_correct"]) for x in z]
            if len(set(yy)) < 2:
                return None
            bb, _ = logistic_fit(XX, yy)
            return None if bb is None else bb[1]

        _, blo, bhi, _ = cluster_bootstrap(rs_all, fit, B=2000, seed=52)
        print(f"{SHORT[m]:<18} {cond:<5} {n:>5} {mean(y):>6.3f} {r:>7.3f} "
              f"{t_sf2(t, n-2):>10.3g} [{rlo:>+7.3f},{rhi:>+7.3f}]{'':>9} "
              f"{b[1]:>11.3f} {math.erfc(abs(zw)/math.sqrt(2)):>10.3g} "
              f"[{blo:>+7.3f},{bhi:>+7.3f}]")
print(f"{'gemma-4-26b':<18} {'A/B':<5} {'--':>5}   0 reasoning tokens on 650/650 "
      f"cells -> predictor is constant, coefficient undefined")

print()
print("-" * 104)
print("Same fact model-free: median reasoning tokens by outcome")
print("-" * 104)
print(f"{'model':<18} {'cond':<5} {'med | correct':>14} {'med | wrong':>12} "
      f"{'ratio wrong/correct':>20} {'n_wrong':>8}")
for m in REAS:
    rs_all = [r for r in rows if r["model"] == m]
    for cond in "AB":
        cor = [r[cond + "_reason"] for r in rs_all if r[cond + "_correct"] == 1]
        wro = [r[cond + "_reason"] for r in rs_all if r[cond + "_correct"] == 0]
        print(f"{SHORT[m]:<18} {cond:<5} {median(cor):>14.0f} {median(wro):>12.0f} "
              f"{median(wro)/max(1,median(cor)):>20.3f} {len(wro):>8}")

print()
print("=" * 104)
print("Does spending MORE extra thinking in B protect the answer?")
print("Cells with A_correct == 1 only.  logistic B_correct ~ 1 + dlog2reason,")
print("dlog2reason = log2((B_reason+1)/(A_reason+1))")
print("=" * 104)
print(f"{'model':<18} {'n(A=1)':>7} {'kept':>6} {'med dlog2 | kept':>17} "
      f"{'med dlog2 | lost':>17} {'logit b':>9} {'p_wald':>10} "
      f"{'b 95% CI (cluster boot)':>25}")


def dl(r):
    return math.log2((r["B_reason"] + 1) / (r["A_reason"] + 1))


for m in REAS:
    rs = [r for r in rows if r["model"] == m and r["A_correct"] == 1]
    kept = [dl(r) for r in rs if r["B_correct"] == 1]
    lost = [dl(r) for r in rs if r["B_correct"] == 0]
    X = [[dl(r)] for r in rs]
    y = [float(r["B_correct"]) for r in rs]
    b, se = logistic_fit(X, y)
    zw = b[1] / se[1]

    def fit(z):
        XX = [[dl(x)] for x in z]
        yy = [float(x["B_correct"]) for x in z]
        if len(set(yy)) < 2:
            return None
        bb, _ = logistic_fit(XX, yy)
        return None if bb is None else bb[1]

    _, lo, hi, _ = cluster_bootstrap(rs, fit, B=2000, seed=53)
    print(f"{SHORT[m]:<18} {len(rs):>7} {len(kept):>6} {median(kept):>17.3f} "
          f"{median(lost):>17.3f} {b[1]:>9.3f} "
          f"{math.erfc(abs(zw)/math.sqrt(2)):>10.3g} [{lo:>+7.3f},{hi:>+7.3f}]")

print()
print("=" * 104)
print("Absolute reasoning budget in B, split by whether B was answered correctly")
print("=" * 104)
print(f"{'model':<18} {'B correct':>10} {'n':>5} {'p25':>7} {'p50':>7} {'p75':>7} {'p90':>8}")
for m in REAS:
    for bc in (1, 0):
        v = [r["B_reason"] for r in rows if r["model"] == m and r["B_correct"] == bc]
        print(f"{SHORT[m]:<18} {bc:>10} {len(v):>5} {quantile(v,.25):>7.0f} "
              f"{quantile(v,.50):>7.0f} {quantile(v,.75):>7.0f} {quantile(v,.90):>8.0f}")

"""(ii) Within model, does token count predict correctness in A and in B?

Two estimators, both from scratch:
  * point-biserial r  = Pearson r between the binary outcome and log2(tokens);
    p from the t approximation t = r*sqrt((n-2)/(1-r^2)), df = n-2.
    NOTE: cells are nested in 208 clusters, so the t p-value is anticonservative;
    a CLUSTER bootstrap 95% CI (4000 reps, percentile) is reported alongside and
    is the interval to trust.
  * logistic regression (Newton-Raphson MLE, own implementation) of
    correct ~ 1 + z, z = (log2(tokens) - mean)/sd within model x condition,
    so the coefficient is "log-odds per 1 SD of log2 tokens".
    Wald p from the inverse observed information, plus a cluster-bootstrap CI.

Also:
  * the paired question -- does the SIZE of the token increase predict whether
    the model survives the swap?  Model B_correct ~ 1 + dlog2tok among the
    cells the model already got right in A.
"""
import math
from mech_lib_effort import (load, MODELS, SHORT, mean, sd, median, pearson,
                             logistic_fit, cluster_bootstrap, boot_p_two_sided,
                             t_sf2, quantile)

rows = load()

print("=" * 100)
print("(ii) DOES GENERATION LENGTH PREDICT CORRECTNESS?  (within model, within condition)")
print("=" * 100)
print(f"{'model':<18} {'cond':<5} {'n':>5} {'acc':>6} {'r_pb':>7} {'p_t':>10} "
      f"{'r_pb 95%CI (cluster boot)':>28} {'logit b/SD':>11} {'p_wald':>9} "
      f"{'b 95%CI (cluster boot)':>26}")


def rpb(rs, cond):
    x = [math.log2(r[cond + "_tokens"]) for r in rs]
    y = [float(r[cond + "_correct"]) for r in rs]
    return pearson(x, y)


def logit_b(rs, cond, mu, s):
    X = [[(math.log2(r[cond + "_tokens"]) - mu) / s] for r in rs]
    y = [float(r[cond + "_correct"]) for r in rs]
    if len(set(y)) < 2:
        return None
    b, se = logistic_fit(X, y)
    return None if b is None else b[1]


summary = {}
for m in MODELS:
    rs_all = [r for r in rows if r["model"] == m]
    for cond in "AB":
        lg = [math.log2(r[cond + "_tokens"]) for r in rs_all]
        mu, s = mean(lg), sd(lg)
        n = len(rs_all)
        r = rpb(rs_all, cond)
        t = r * math.sqrt((n - 2) / max(1e-12, 1 - r * r))
        p_t = t_sf2(t, n - 2)
        _, rlo, rhi, _ = cluster_bootstrap(rs_all, lambda z, c=cond: rpb(z, c),
                                           B=4000, seed=21)
        b = logit_b(rs_all, cond, mu, s)
        X = [[(math.log2(x[cond + "_tokens"]) - mu) / s] for x in rs_all]
        y = [float(x[cond + "_correct"]) for x in rs_all]
        bb, se = logistic_fit(X, y)
        z = bb[1] / se[1]
        p_w = math.erfc(abs(z) / math.sqrt(2.0))
        _, blo, bhi, breps = cluster_bootstrap(
            rs_all, lambda zz, c=cond, M=mu, S=s: logit_b(zz, c, M, S),
            B=2000, seed=22)
        summary[(m, cond)] = (b, blo, bhi)
        print(f"{SHORT[m]:<18} {cond:<5} {n:>5} "
              f"{mean(y):>6.3f} {r:>7.3f} {p_t:>10.3g} "
              f"[{rlo:>+7.3f},{rhi:>+7.3f}]{'':>10} {b:>11.3f} {p_w:>9.3g} "
              f"[{blo:>+7.3f},{bhi:>+7.3f}]")

print()
print("-" * 100)
print("Median tokens by outcome (raw, not logged) -- the same fact without a model")
print("-" * 100)
print(f"{'model':<18} {'cond':<5} {'med tok | correct':>18} {'med tok | wrong':>17} "
      f"{'ratio wrong/correct':>20} {'n_wrong':>8}")
for m in MODELS:
    rs_all = [r for r in rows if r["model"] == m]
    for cond in "AB":
        cor = [r[cond + "_tokens"] for r in rs_all if r[cond + "_correct"] == 1]
        wro = [r[cond + "_tokens"] for r in rs_all if r[cond + "_correct"] == 0]
        if not wro or not cor:
            continue
        print(f"{SHORT[m]:<18} {cond:<5} {median(cor):>18.0f} {median(wro):>17.0f} "
              f"{median(wro)/median(cor):>20.3f} {len(wro):>8}")

print()
print("=" * 100)
print("Does the SIZE of the extra effort in B predict surviving the swap?")
print("Restricted to cells with A_correct == 1 (the cells that can drop).")
print("logistic  B_correct ~ 1 + dlog2tok,  dlog2tok = log2(B_tokens/A_tokens)")
print("=" * 100)
print(f"{'model':<18} {'n(A=1)':>7} {'B ok':>6} {'med dlog2 | kept':>17} "
      f"{'med dlog2 | lost':>17} {'logit b':>9} {'p_wald':>10} "
      f"{'b 95%CI (cluster boot)':>26}")


def dlog(r):
    return math.log2(r["B_tokens"] / r["A_tokens"])


def fit_d(rs):
    X = [[dlog(r)] for r in rs]
    y = [float(r["B_correct"]) for r in rs]
    if len(set(y)) < 2:
        return None
    b, se = logistic_fit(X, y)
    return None if b is None else b[1]


for m in MODELS:
    rs = [r for r in rows if r["model"] == m and r["A_correct"] == 1]
    kept = [dlog(r) for r in rs if r["B_correct"] == 1]
    lost = [dlog(r) for r in rs if r["B_correct"] == 0]
    X = [[dlog(r)] for r in rs]
    y = [float(r["B_correct"]) for r in rs]
    b, se = logistic_fit(X, y)
    z = b[1] / se[1]
    p = math.erfc(abs(z) / math.sqrt(2.0))
    _, lo, hi, _ = cluster_bootstrap(rs, fit_d, B=2000, seed=23)
    print(f"{SHORT[m]:<18} {len(rs):>7} {len(kept):>6} {median(kept):>17.3f} "
          f"{median(lost):>17.3f} {b[1]:>9.3f} {p:>10.3g} "
          f"[{lo:>+7.3f},{hi:>+7.3f}]")

print()
print("=" * 100)
print("Cross-model descriptive: effort response vs accuracy drop (n = 4 models,")
print("too few for inference -- reported as a pattern only)")
print("=" * 100)
print(f"{'model':<18} {'medA tok':>9} {'median B/A tok':>15} {'accA':>7} "
      f"{'accB':>7} {'drop (pp)':>10}")
pts = []
for m in MODELS:
    rs = [r for r in rows if r["model"] == m]
    ratio = median([r["B_tokens"] / r["A_tokens"] for r in rs])
    a, b = mean([r["A_correct"] for r in rs]), mean([r["B_correct"] for r in rs])
    pts.append((ratio, (a - b) * 100))
    print(f"{SHORT[m]:<18} {median([r['A_tokens'] for r in rs]):>9.0f} "
          f"{ratio:>15.3f} {a:>7.3f} {b:>7.3f} {(a-b)*100:>10.1f}")
print(f"  Pearson r(median token ratio, drop) over 4 models = "
      f"{pearson([p[0] for p in pts], [p[1] for p in pts]):+.3f}  (n=4, no p reported)")

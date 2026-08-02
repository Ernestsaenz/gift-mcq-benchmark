"""Step 2: closed-form candidates.
  (a) McNemar exact (binomial, conditional on discordants)
  (b) McNemar chi-square WITH Yates continuity correction
  (c) McNemar chi-square WITHOUT correction (= score test = conditional-logistic score)
  (d) naive two-proportion z-test on pooled independent proportions
  (e) conditional (fixed-effects) logistic MLE -> shows equivalence with McNemar OR
  (f) Cochran Q across the 4 models
All p-values computed here; chi-square tails via regularised incomplete gamma,
normal tails via math.erfc.
"""
import sys, math
from collections import defaultdict
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from stats_lib import *

rows = load()

def tab(rs):
    a = sum(1 for r in rs if r["A_correct"] == 1 and r["B_correct"] == 1)
    b = sum(1 for r in rs if r["A_correct"] == 1 and r["B_correct"] == 0)
    c = sum(1 for r in rs if r["A_correct"] == 0 and r["B_correct"] == 1)
    d = sum(1 for r in rs if r["A_correct"] == 0 and r["B_correct"] == 0)
    return a, b, c, d

strata = [("POOLED", rows)] + sorted(
    ((m.split("/")[-1], rs) for m, rs in group(rows, lambda r: r["model"]).items()))

print("=== (a)(b)(c) McNemar variants ===")
print("%-20s %5s %5s %6s | %12s %12s %12s | %10s" %
      ("stratum", "b", "c", "n_disc", "exact p", "Yates p", "uncorr p", "OR=b/c"))
res = {}
for name, rs in strata:
    a, b, c, d = tab(rs)
    n = b + c
    p_ex = mcnemar_exact_p(b, c)
    if n > 0:
        chi_y = (abs(b - c) - 1) ** 2 / n if abs(b - c) >= 1 else 0.0
        chi_u = (b - c) ** 2 / n
    else:
        chi_y = chi_u = 0.0
    p_y = chi2_sf(chi_y, 1)
    p_u = chi2_sf(chi_u, 1)
    orr = (b / c) if c else float("inf")
    res[name] = dict(a=a, b=b, c=c, d=d, n=n, p_ex=p_ex, p_y=p_y, p_u=p_u,
                     chi_y=chi_y, chi_u=chi_u, orr=orr)
    print("%-20s %5d %5d %6d | %12.3e %12.3e %12.3e | %10.3f" %
          (name, b, c, n, p_ex, p_y, p_u, orr))

# relative difference between exact and corrected/uncorrected, on the log10 scale
P = res["POOLED"]
print("\npooled chi2 uncorrected = %.4f ; Yates = %.4f ; difference in chi2 = %.4f"
      % (P["chi_u"], P["chi_y"], P["chi_u"] - P["chi_y"]))
print("pooled p exact/Yates ratio = %.4f ; exact/uncorrected ratio = %.4f"
      % (P["p_ex"] / P["p_y"], P["p_ex"] / P["p_u"]))

# Where does Yates vs exact actually matter? Sweep small discordant tables.
print("\n--- how much do the three McNemar variants disagree as n_disc shrinks? ---")
print("%6s %6s | %11s %11s %11s" % ("b", "c", "exact", "Yates", "uncorr"))
for (b, c) in [(31, 4), (12, 3), (10, 2), (8, 2), (6, 1), (5, 1), (9, 3), (7, 2), (4, 0)]:
    n = b + c
    chi_y = (abs(b - c) - 1) ** 2 / n
    chi_u = (b - c) ** 2 / n
    print("%6d %6d | %11.5f %11.5f %11.5f" %
          (b, c, mcnemar_exact_p(b, c), chi2_sf(chi_y, 1), chi2_sf(chi_u, 1)))

print("\n=== (d) NAIVE two-proportion z (treats 2*1299 obs as independent) ===")
a, b, c, d = tab(rows)
n = a + b + c + d
xA, xB = a + b, a + c
pA, pB = xA / n, xB / n
pbar = (xA + xB) / (2 * n)
se_naive = math.sqrt(pbar * (1 - pbar) * (1 / n + 1 / n))
z_naive = (pB - pA) / se_naive
print("pA=%.4f pB=%.4f delta=%+.4f" % (pA, pB, pB - pA))
print("naive SE(delta) = %.5f  z = %.3f  two-sided p = %.3e" %
      (se_naive, z_naive, two_sided_z_p(z_naive)))
# correct paired SE (McNemar / within-cell), still ignoring clustering
se_paired = math.sqrt((b + c) - (b - c) ** 2 / n) / n
print("paired SE(delta) ignoring clusters = %.5f  (ratio naive/paired = %.3f)" %
      (se_paired, se_naive / se_paired))
z_paired = (pB - pA) / se_paired
print("paired z = %.3f  two-sided p = %.3e" % (z_paired, two_sided_z_p(z_paired)))

print("\n=== (e) conditional (fixed-effects-per-cell) logistic ===")
# Conditioning on each cell's total, only discordant cells contribute.
# loglik = b*beta - (b+c)*log(1+exp(beta))  -> MLE beta = log(b/c)
beta = math.log(b / c)
se_beta = math.sqrt(1.0 / b + 1.0 / c)
print("beta_hat = log(b/c) = %.4f  (OR = %.3f)  model-based SE = %.4f" % (beta, math.exp(beta), se_beta))
print("Wald z = %.3f  p = %.3e" % (beta / se_beta, two_sided_z_p(beta / se_beta)))
print("score statistic at beta=0 = (b-c)^2/(b+c) = %.4f == uncorrected McNemar chi2 %.4f"
      % ((b - c) ** 2 / (b + c), P["chi_u"]))
lo_or = math.exp(beta - 1.96 * se_beta); hi_or = math.exp(beta + 1.96 * se_beta)
print("model-based 95%% CI for OR (assumes cells independent): %.3f to %.3f" % (lo_or, hi_or))

print("\n=== (f) Cochran Q across the 4 models (same items) ===")
# Cochran Q needs complete blocks; 1 item has only 3 models -> drop it for Q.
models = sorted({r["model"] for r in rows})
by_item = defaultdict(dict)
for r in rows:
    by_item[r["question_id"]][r["model"]] = r
complete = {q: v for q, v in by_item.items() if len(v) == len(models)}
print("complete items for Q: %d (dropped %d incomplete)" % (len(complete), len(by_item) - len(complete)))

def cochran_q(field):
    k = len(models)
    L = [[complete[q][m][field] for m in models] for q in sorted(complete)]
    Nrows = len(L)
    Tj = [sum(row[j] for row in L) for j in range(k)]     # column (model) totals
    Bi = [sum(row) for row in L]                          # row (item) totals
    N = sum(Tj)
    num = (k - 1) * (k * sum(t * t for t in Tj) - N * N)
    den = k * N - sum(bb * bb for bb in Bi)
    if den == 0:
        return float("nan"), float("nan"), Tj, Nrows
    Q = num / den
    return Q, chi2_sf(Q, k - 1), Tj, Nrows

for field in ("A_correct", "B_correct"):
    Q, p, Tj, Nr = cochran_q(field)
    print("%s: Q = %.3f  df=%d  p = %.3e ; per-model accuracy = %s" %
          (field, Q, len(models) - 1, p,
           ["%.4f" % (t / Nr) for t in Tj]))

# Cochran Q on the DIFFERENCE is not defined (d is trichotomous), demonstrate why:
dvals = set()
for q, v in complete.items():
    for m in models:
        dvals.add(v[m]["B_correct"] - v[m]["A_correct"])
print("support of d = %s -> not binary, so Cochran Q cannot test heterogeneity of the A->B effect"
      % sorted(dvals))

# Heterogeneity of the A->B effect across models, model-based (ignores item pairing across models)
print("\n--- heterogeneity of the A->B log-OR across models (model-based, Woolf/Q_het) ---")
ws, bs = [], []
for name, rs in strata[1:]:
    a2, b2, c2, d2 = tab(rs)
    lb = math.log(b2 / c2)
    w = 1.0 / (1.0 / b2 + 1.0 / c2)
    ws.append(w); bs.append(lb)
    print("%-20s logOR=%.4f  se=%.4f  w=%.3f" % (name, lb, math.sqrt(1/b2 + 1/c2), w))
bbar = sum(w * bb for w, bb in zip(ws, bs)) / sum(ws)
Qhet = sum(w * (bb - bbar) ** 2 for w, bb in zip(ws, bs))
print("pooled logOR = %.4f ; Q_het = %.4f df=3 p = %.4f (model-based; ignores that the SAME items feed all 4 models)"
      % (bbar, Qhet, chi2_sf(Qhet, 3)))

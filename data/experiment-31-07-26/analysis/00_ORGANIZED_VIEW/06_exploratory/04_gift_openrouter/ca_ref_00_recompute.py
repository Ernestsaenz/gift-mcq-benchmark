"""Independent recompute of the PRIMARY cross-arm McNemar claim.

Written from scratch (no import of ca_prim_lib) so nothing is inherited.
Stdlib only.
"""
import json
import math
from fractions import Fraction
from collections import defaultdict

P = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/"
rows = json.load(open(P + "cross_arm_A.json"))
print("raw cells:", len(rows))
D = [r for r in rows if r["analysis_include"] is True]
print("analysis_include cells:", len(D))
print("items:", len(set(r["question_id"] for r in D)))
print("clusters:", len(set(r["cluster"] for r in D)))
print("models:", sorted(set(r["model"] for r in D)))

# ---- sanity: any missing/None outcomes?
bad = [r for r in D if r["gift_correct"] not in (0, 1) or r["or_correct"] not in (0, 1)]
print("cells with non-binary outcome:", len(bad))

# ---- per-model 2x2
def tab(sub):
    a = sum(1 for r in sub if r["gift_correct"] == 1 and r["or_correct"] == 1)
    b = sum(1 for r in sub if r["gift_correct"] == 1 and r["or_correct"] == 0)
    c = sum(1 for r in sub if r["gift_correct"] == 0 and r["or_correct"] == 1)
    d = sum(1 for r in sub if r["gift_correct"] == 0 and r["or_correct"] == 0)
    return a, b, c, d

print("\n%-28s %5s %6s %6s %8s %8s %7s  %s" %
      ("model", "n", "GIFT%", "OR%", "diff_pp", "b(G>O)", "c(O>G)", "(a,d)"))
for m in sorted(set(r["model"] for r in D)) + ["POOLED"]:
    sub = D if m == "POOLED" else [r for r in D if r["model"] == m]
    a, b, c, d = tab(sub)
    n = len(sub)
    g = (a + b) / n
    o = (a + c) / n
    print("%-28s %5d %6.2f %6.2f %8.2f %8d %7d  (%d,%d)" %
          (m, n, 100 * g, 100 * o, 100 * (g - o), b, c, a, d))

A, B, C, Dd = tab(D)
n_disc = B + C

# ---- exact conditional binomial McNemar, independently coded
def exact_mcnemar(b, c):
    n = b + c
    # P(X <= b) and P(X >= b) under Bin(n, 1/2), exact rationals
    num_le = sum(math.comb(n, i) for i in range(0, b + 1))
    num_ge = sum(math.comb(n, i) for i in range(b, n + 1))
    den = 1 << n
    lo = Fraction(num_le, den)
    hi = Fraction(num_ge, den)
    p2 = min(Fraction(1), 2 * min(lo, hi))
    # cross-check: sum of all outcomes with pmf <= pmf(b)  (point-probability method)
    pb = math.comb(n, b)
    num_pp = sum(math.comb(n, i) for i in range(0, n + 1) if math.comb(n, i) <= pb)
    p_pp = Fraction(num_pp, den)
    return p2, p_pp, lo, hi

p2, p_pp, lo, hi = exact_mcnemar(B, C)
print("\n=== POOLED exact McNemar ===")
print("b=%d c=%d n_disc=%d" % (B, C, n_disc))
print("two-sided p (2*min tail)  = %.10g   frac = %d/%d" % (float(p2), p2.numerator, p2.denominator))
print("two-sided p (point-prob)  = %.10g   frac = %d/%d" % (float(p_pp), p_pp.numerator, p_pp.denominator))
print("claim frac 850498915931112407/73786976294838206464 = %.10g" %
      (850498915931112407 / 73786976294838206464))
print("match claim frac:", p2 == Fraction(850498915931112407, 73786976294838206464))
print("one-sided P(X>=b) = %.10g" % float(hi))

# ---- asymptotic versions for context
chi2 = (B - C) ** 2 / n_disc
chi2_cc = (abs(B - C) - 1) ** 2 / n_disc
sf = lambda x: math.erfc(math.sqrt(x / 2.0))
print("chi2 (no cc) = %.4f  p=%.6g" % (chi2, sf(chi2)))
print("chi2 (cc)    = %.4f  p=%.6g" % (chi2_cc, sf(chi2_cc)))

# ---- Clopper-Pearson on pi = b/(b+c), independent implementation via
#      the exact Beta-quantile relation using bisection on the regularized
#      incomplete beta computed by continued fraction.
def betacf(a, b, x):
    MAXIT, EPS, FPMIN = 300, 3e-16, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS:
            break
    return h

def betai(a, b, x):
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    bt = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * betacf(a, b, x) / a
    return 1.0 - bt * betacf(b, a, 1.0 - x) / b

def beta_quantile(a, b, q):
    lo_, hi_ = 0.0, 1.0
    for _ in range(300):
        m = 0.5 * (lo_ + hi_)
        if betai(a, b, m) < q:
            lo_ = m
        else:
            hi_ = m
    return 0.5 * (lo_ + hi_)

def cp(k, n, alpha=0.05):
    lo_ = 0.0 if k == 0 else beta_quantile(k, n - k + 1, alpha / 2)
    hi_ = 1.0 if k == n else beta_quantile(k + 1, n - k, 1 - alpha / 2)
    return lo_, hi_

# validate the CP implementation on textbook values
print("\nCP validation  8/10 ->", ["%.4f" % v for v in cp(8, 10)], "(expect 0.4439 0.9748)")
print("CP validation  1/20 ->", ["%.4f" % v for v in cp(1, 20)], "(expect 0.0013 0.2487)")
print("CP validation  0/10 ->", ["%.4f" % v for v in cp(0, 10)], "(expect 0.0000 0.3085)")

pl, ph = cp(B, n_disc)
pi = B / n_disc
tr = lambda p: math.inf if p >= 1 else p / (1 - p)
print("\npi = %.6f  CP95 = (%.6f, %.6f)   [claim 0.6571 (0.5340,0.7665)]" % (pi, pl, ph))
print("OR = %.6f  CI  = (%.6f, %.6f)   [claim 1.9167 (1.1459,3.2830)]" % (B / C, tr(pl), tr(ph)))

json.dump({"b": B, "c": C, "a": A, "d": Dd, "n_disc": n_disc,
           "p_exact": float(p2), "p_exact_frac": [p2.numerator, p2.denominator],
           "p_pointprob": float(p_pp),
           "or": B / C, "or_ci": [tr(pl), tr(ph)], "pi": pi, "pi_ci": [pl, ph],
           "chi2": chi2, "chi2_p": sf(chi2), "chi2_cc": chi2_cc, "chi2_cc_p": sf(chi2_cc)},
          open(P + "ca_ref_00_out.json", "w"), indent=1)

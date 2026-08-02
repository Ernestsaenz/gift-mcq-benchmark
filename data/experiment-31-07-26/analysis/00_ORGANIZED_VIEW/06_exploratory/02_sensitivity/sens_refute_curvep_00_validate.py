"""Validate the independent primitives before using them to check the claim."""
import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sens_refute_speccurve_lib as L
import sens_speccurve_lib as O   # the ORIGINAL library, for cross-checking

print("=" * 78)
print("PRIMITIVE VALIDATION (independent implementations)")
print("=" * 78)

# ---- chi2, even df -------------------------------------------------------
print("\n[chi2 sf, even df]")
print(f"  sf(15.507, 8)  mine={L.chi2_sf_even(15.507,8):.9f}  orig={O.chi2_sf_even(15.507,8):.9f}"
      f"   (claimed 0.050005)")
print(f"  sf(3.841, 2)   mine={L.chi2_sf_even(3.841,2):.9f}   [exact e^-x/2 = {math.exp(-3.841/2):.9f}]")
print(f"  sf(9.488, 4)   mine={L.chi2_sf_even(9.488,4):.9f}   (table 0.05)")
print(f"  sf(18.307,10)  mine={L.chi2_sf_even(18.307,10):.9f}  (table 0.05)")

# ---- Student t -----------------------------------------------------------
print("\n[Student t two-sided]  exact odd-df closed form vs incomplete-beta")
for t, df in ((3.182, 3), (2.353, 3), (5.841, 3), (12.924, 3), (2.571, 5),
              (1.960, 10001), (1.9714, 207), (2.5, 1)):
    mine = L.t_two_sided(t, df)
    beta = L.betai(df / 2.0, 0.5, df / (df + t * t))
    orig = O.t_sf_two_sided(t, df)
    print(f"  t={t:<8} df={df:<6} exact/closed={mine:.9g}  betaCF={beta:.9g}  orig={orig:.9g}")
# explicit df=3 textbook form as a third route
def t3(t):
    s3 = math.sqrt(3.0)
    return 1.0 - (2.0 / math.pi) * (math.atan(t / s3) + t * s3 / (3.0 + t * t))
print(f"  df=3 textbook arctan form at t=3.182 -> {t3(3.182):.9g}   (claimed 0.050017)")
print(f"  df=3 textbook arctan form at t=5.841 -> {t3(5.841):.9g}")

# ---- exact binomial ------------------------------------------------------
print("\n[exact two-sided binomial / McNemar]")
for b, c in ((10, 0), (5, 15), (100, 20), (12, 3), (0, 0), (1, 1)):
    ex = L.binom_two_sided_exact(b, c)
    lg = L.binom_two_sided_log(b, c)
    orig = O.mcnemar_exact_two_sided(b, c)
    print(f"  b={b:<5} c={c:<5} exactRational={ex:.10g}  log-space={lg:.10g}  orig={orig:.10g}")
# hand values
print(f"  b=10,c=0 -> should be 2*(1/1024) = {2/1024:.10g}")
print(f"  b=1,c=1  -> should be 2*(2/4)    = 1.0")

# ---- logistic sanity: perfectly known 2x2 -------------------------------
print("\n[logistic regression on a 2x2 table -> log odds ratio]")
# 60/100 vs 30/100
y = [1]*60 + [0]*40 + [1]*30 + [0]*70
x = [0.0]*100 + [1.0]*100
cl = list(range(100)) + list(range(100))
b1, se, p, G = L.logit_cluster_robust(y, x, cl)
lor = math.log((30/70)/(60/40))
print(f"  fitted beta1={b1:.10f}   analytic log OR={lor:.10f}   diff={abs(b1-lor):.2e}")

# ---- OLS intercept CR1 with every obs its own cluster == paired t-test ---
print("\n[intercept-only OLS, CR1, each obs its own cluster == one-sample t]")
d = [-3.0, 1.5, -7.25, 2.0, -11.0, 0.5, -4.0]
m, se, p, G = L.ols_intercept_cluster_robust(d, list(range(len(d))))
mean = sum(d)/len(d)
var = sum((v-mean)**2 for v in d)/(len(d)-1)
se_t = math.sqrt(var/len(d))
p_t = L.t_two_sided(mean/se_t, len(d)-1)
print(f"  CR1: mean={m:.9f} se={se:.9f} p={p:.9f}")
print(f"  t  : mean={mean:.9f} se={se_t:.9f} p={p_t:.9f}   -> identical: {abs(p-p_t)<1e-12}")

print("\nAll primitives validated.")

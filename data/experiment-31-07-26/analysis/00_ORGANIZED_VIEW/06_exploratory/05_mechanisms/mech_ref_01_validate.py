"""Validate mech_ref_lib against closed-form results before trusting anything."""
import math, random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mech_ref_lib import logit, sandwich, jackknife_cluster, t_sf, norm_p, betainc, t_crit

print("=" * 78)
print("V1. 2x2 table: logistic slope must equal log OR, SE must equal sqrt(sum 1/n_ij)")
# counts: exposed/unexposed x event/no-event
n11, n10, n01, n00 = 37, 63, 21, 79
X, y = [], []
for _ in range(n11): X.append([1.0, 1.0]); y.append(1.0)
for _ in range(n10): X.append([1.0, 1.0]); y.append(0.0)
for _ in range(n01): X.append([1.0, 0.0]); y.append(1.0)
for _ in range(n00): X.append([1.0, 0.0]); y.append(0.0)
f = logit(X, y)
logor = math.log((n11 * n00) / (n10 * n01))
se = math.sqrt(1 / n11 + 1 / n10 + 1 / n01 + 1 / n00)
print(f"   beta  fitted {f['beta'][1]:.10f}   closed form {logor:.10f}")
print(f"   SE    fitted {math.sqrt(f['bread'][1][1]):.10f}   closed form {se:.10f}")
assert abs(f['beta'][1] - logor) < 1e-8 and abs(math.sqrt(f['bread'][1][1]) - se) < 1e-8
print("   PASS")

print()
print("=" * 78)
print("V2. singleton clusters: CR1 sandwich ~ HC1 robust; with correct model it must")
print("    track the model SE closely on a large simulated sample")
random.seed(7)
n = 6000
X, y, cl = [], [], []
for i in range(n):
    x1 = random.gauss(0, 1)
    x2 = 1.0 if random.random() < .4 else 0.0
    eta = -1.0 + 0.8 * x1 - 0.6 * x2
    p = 1 / (1 + math.exp(-eta))
    X.append([1.0, x1, x2]); y.append(1.0 if random.random() < p else 0.0); cl.append(i)
f = logit(X, y)
V, G = sandwich(f, cl, "CR1")
print(f"   true beta = [-1.0, 0.8, -0.6]; fitted = {[round(b,3) for b in f['beta']]}")
print(f"   model SE  = {[round(math.sqrt(f['bread'][j][j]),4) for j in range(3)]}")
print(f"   CR1 SE    = {[round(math.sqrt(V[j][j]),4) for j in range(3)]}")
ok = all(abs(math.sqrt(V[j][j]) / math.sqrt(f['bread'][j][j]) - 1) < 0.06 for j in range(3))
print("   PASS" if ok else "   FAIL")

print()
print("=" * 78)
print("V3. clustered data: CR1 must be materially LARGER than the naive model SE when a")
print("    cluster-level covariate drives a cluster random effect")
random.seed(11)
X, y, cl = [], [], []
for g in range(220):
    u = random.gauss(0, 1.2)              # cluster random intercept
    xg = random.gauss(0, 1)               # cluster-level covariate
    for _ in range(6):
        eta = -1.0 + 0.5 * xg + u
        p = 1 / (1 + math.exp(-eta))
        X.append([1.0, xg]); y.append(1.0 if random.random() < p else 0.0); cl.append(g)
f = logit(X, y)
V, G = sandwich(f, cl, "CR1")
print(f"   model SE(x) = {math.sqrt(f['bread'][1][1]):.4f}   CR1 SE(x) = {math.sqrt(V[1][1]):.4f} "
      f"(ratio {math.sqrt(V[1][1])/math.sqrt(f['bread'][1][1]):.2f}x)")
Vj, Gj, bj = jackknife_cluster(X, y, cl)
print(f"   cluster jackknife SE(x) = {math.sqrt(Vj[1][1]):.4f}")
print("   PASS" if math.sqrt(V[1][1]) > 1.15 * math.sqrt(f['bread'][1][1]) else "   FAIL")

print()
print("=" * 78)
print("V4. t and beta functions")
# t(10) two-sided p at t=2.228 is 0.05
print(f"   t_sf(2.228, 10) = {t_sf(2.228,10):.5f}  (expect 0.0500)")
print(f"   t_sf(1.96, 1e6) = {t_sf(1.96,1000000):.5f}  normal = {norm_p(1.96):.5f}")
print(f"   t_crit(204)     = {t_crit(204):.4f}  (expect ~1.9714)")
print(f"   t_crit(1e6)     = {t_crit(1000000):.4f}  (expect ~1.9600)")
assert abs(t_sf(2.228, 10) - 0.05) < 1e-3
print("   PASS")

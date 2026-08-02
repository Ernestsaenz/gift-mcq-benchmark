"""Step 5: put every procedure on the SAME estimand (the paired risk difference
delta = P(correct|B) - P(correct|A)) so the standard errors are comparable.

  (j) GEE with identity link (linear probability), independence working corr,
      cluster-robust sandwich  == cluster-robust one-sample test on d
  (k) cluster-robust paired z / t (CR0, CR1, CR3-jackknife) on d
  (l) studentized cluster permutation (fixes the conservatism of the raw
      cluster sign-flip under unequal cluster sizes)
  (m) cluster-weighted vs cell-weighted estimand
"""
import sys, math, random
from collections import defaultdict
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from stats_lib import *

random.seed(20260731)
rows = load()
for r in rows:
    r["d"] = r["B_correct"] - r["A_correct"]
models = sorted({r["model"] for r in rows})
MSHORT = {m: m.split("/")[-1] for m in models}
by_cluster = group(rows, lambda r: r["cluster"])
by_item = group(rows, lambda r: r["question_id"])
n = len(rows)
dbar = sum(r["d"] for r in rows) / n
print("delta_hat (cell-weighted) = %+.6f   n cells = %d" % (dbar, n))

# ---------------------------------------------------- cluster-robust variance
def cr_se(groups, dbar, n, kind="CR0"):
    """Cluster-robust SE of the mean of d.
    Score for cluster c: u_c = sum_{i in c} (d_i - dbar).  Var(dbar) = sum u_c^2 / n^2.
    CR1 applies the usual K/(K-1) * (n-1)/(n-p) finite-sample scale-up.
    CR3 is the cluster-jackknife."""
    K = len(groups)
    us = [sum(r["d"] - dbar for r in g) for g in groups]
    v0 = sum(u * u for u in us) / (n * n)
    if kind == "CR0":
        return math.sqrt(v0), K
    if kind == "CR1":
        c = (K / (K - 1.0)) * ((n - 1.0) / (n - 1.0))
        return math.sqrt(v0 * c), K
    if kind == "CR3":  # delete-one-cluster jackknife
        ests = []
        tot = sum(r["d"] for r in rows)
        for g in groups:
            s = sum(r["d"] for r in g); m = len(g)
            ests.append((tot - s) / (n - m))
        mj = sum(ests) / K
        v = (K - 1.0) / K * sum((e - mj) ** 2 for e in ests)
        return math.sqrt(v), K
    raise ValueError

gs_cluster = list(by_cluster.values())
gs_item = list(by_item.values())
gs_cell = [[r] for r in rows]

print("\n=== (j)/(k) SE of the SAME delta under different independence assumptions ===")
print("%-42s %8s %10s %9s %12s" % ("variance assumption", "K", "SE", "z", "two-sided p"))
def show(name, se, K, df=None):
    z = dbar / se
    p = two_sided_z_p(z)
    print("%-42s %8s %10.5f %9.3f %12.3e" % (name, K, se, z, p))
    return se, z, p

se_cell, _, _ = show("i.i.d. cells (= McNemar / paired)", math.sqrt(sum((r["d"] - dbar) ** 2 for r in rows) / n) / math.sqrt(n), n)
se_i0, _, _ = show("item-robust CR0", *cr_se(gs_item, dbar, n, "CR0"))
se_c0, z_c0, p_c0 = show("CLUSTER-robust CR0", *cr_se(gs_cluster, dbar, n, "CR0"))
se_c1, _, _ = show("CLUSTER-robust CR1", *cr_se(gs_cluster, dbar, n, "CR1"))
se_c3, _, _ = show("CLUSTER-robust CR3 (jackknife)", *cr_se(gs_cluster, dbar, n, "CR3"))
print("cluster bootstrap SE from step 3 = 0.01625 (for comparison)")
print("SE ratio cluster-robust / iid-cell = %.3f  -> variance inflation %.3f"
      % (se_c0 / se_cell, (se_c0 / se_cell) ** 2))

K = len(gs_cluster)
# t reference with K-1 df instead of z: p via the t distribution, computed from
# the incomplete beta -> use the relation t -> chi2? implement t tail directly.
def t_sf(t, df):
    """Two-sided t tail via the regularised incomplete beta, continued fraction."""
    x = df / (df + t * t)
    a, b = df / 2.0, 0.5
    # continued fraction for I_x(a,b)  (Numerical Recipes betacf)
    def betacf(a, b, x, itmax=300, eps=3e-16, fpmin=1e-300):
        qab, qap, qam = a + b, a + 1.0, a - 1.0
        c = 1.0
        d = 1.0 - qab * x / qap
        if abs(d) < fpmin: d = fpmin
        d = 1.0 / d
        h = d
        for m in range(1, itmax + 1):
            m2 = 2 * m
            aa = m * (b - m) * x / ((qam + m2) * (a + m2))
            d = 1.0 + aa * d
            if abs(d) < fpmin: d = fpmin
            c = 1.0 + aa / c
            if abs(c) < fpmin: c = fpmin
            d = 1.0 / d
            h *= d * c
            aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
            d = 1.0 + aa * d
            if abs(d) < fpmin: d = fpmin
            c = 1.0 + aa / c
            if abs(c) < fpmin: c = fpmin
            d = 1.0 / d
            dl = d * c
            h *= dl
            if abs(dl - 1.0) < eps: break
        return h
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    if x < (a + 1.0) / (a + b + 2.0):
        ib = math.exp(a * math.log(x) + b * math.log(1 - x) - lbeta) * betacf(a, b, x) / a
    else:
        ib = 1.0 - math.exp(b * math.log(1 - x) + a * math.log(x) - lbeta) * betacf(b, a, 1 - x) / b
    return ib  # this IS the two-sided p for the t statistic

print("\nt(K-1=%d) reference instead of z: p = %.3e (CR0), %.3e (CR3)"
      % (K - 1, t_sf(dbar / se_c0, K - 1), t_sf(dbar / se_c3, K - 1)))
print("95%% CI (CR0, normal):    [%+.5f, %+.5f]" % (dbar - 1.96 * se_c0, dbar + 1.96 * se_c0))
print("95%% CI (CR3, t_%d=%.3f): [%+.5f, %+.5f]"
      % (K - 1, 1.9714, dbar - 1.9714 * se_c3, dbar + 1.9714 * se_c3))

print("\n=== (l) STUDENTIZED cluster permutation (sign-flip of the A/B label per cluster) ===")
NP = 50000
sums = [sum(r["d"] for r in g) for g in gs_cluster]
sizes = [len(g) for g in gs_cluster]
def studentized(sgn):
    tot = sum(s * v for s, v in zip(sgn, sums))
    db = tot / n
    us = []
    for s, v, m in zip(sgn, sums, sizes):
        us.append(s * v - m * db)
    var = sum(u * u for u in us) / (n * n)
    return db / math.sqrt(var) if var > 0 else 0.0
obs_t = studentized([1] * K)
raw_obs = dbar
ge_t = 0; ge_raw = 0
raw_null_sd2 = 0.0
for _ in range(NP):
    sg = [1 if random.random() < 0.5 else -1 for _ in range(K)]
    if abs(studentized(sg)) >= abs(obs_t) - 1e-12:
        ge_t += 1
    tot = sum(s * v for s, v in zip(sg, sums)) / n
    if abs(tot) >= abs(raw_obs) - 1e-12:
        ge_raw += 1
print("observed studentized t = %.3f" % obs_t)
print("STUDENTIZED cluster permutation p = %.5f  (%d/%d)" % ((ge_t + 1) / (NP + 1), ge_t, NP))
print("RAW (unstudentized) cluster permutation p = %.5f  (%d/%d)" % ((ge_raw + 1) / (NP + 1), ge_raw, NP))
print("raw cluster-flip null SD = %.5f vs cluster-robust SE of the estimate = %.5f  (ratio %.2f)"
      % (math.sqrt(sum(s * s for s in sums)) / n, se_c0,
         (math.sqrt(sum(s * s for s in sums)) / n) / se_c0))
print("-> the raw sign-flip null SD is inflated because S_c carries the real effect")
print("   (large clusters get large |S_c| from the effect itself), so the raw")
print("   cluster permutation is CONSERVATIVE with unequal cluster sizes.")

print("\n=== (m) estimand: cell-weighted vs cluster-weighted vs model-then-item weighted ===")
cw = mean([mean([r["d"] for r in g]) for g in gs_cluster])
iw = mean([mean([r["d"] for r in g]) for g in gs_item])
mw = mean([mean([r["d"] for r in rows if r["model"] == m]) for m in models])
print("cell-weighted   delta = %+.5f" % dbar)
print("cluster-weighted delta = %+.5f (each of the %d clusters counts once)" % (cw, K))
print("item-weighted    delta = %+.5f" % iw)
print("model-weighted   delta = %+.5f" % mw)
# cluster bootstrap CI for the cluster-weighted estimand
B = 20000
bs = []
for _ in range(B):
    s = 0.0
    for _ in range(K):
        g = gs_cluster[random.randrange(K)]
        s += sum(r["d"] for r in g) / len(g)
    bs.append(s / K)
bs.sort()
mb = mean(bs)
sdb = math.sqrt(sum((x - mb) ** 2 for x in bs) / (B - 1))
print("cluster-weighted: cluster-boot SE %.5f  95%% CI [%+.5f, %+.5f]"
      % (sdb, quantile(bs, 0.025), quantile(bs, 0.975)))

print("\n=== per-model cluster-robust tests on the same scale ===")
print("%-22s %8s %9s %9s %9s %11s" % ("model", "delta", "SE_iid", "SE_clu", "z_clu", "p_clu"))
for m in models:
    rs = [r for r in rows if r["model"] == m]
    nm = len(rs)
    dm = sum(r["d"] for r in rs) / nm
    se_iid = math.sqrt(sum((r["d"] - dm) ** 2 for r in rs) / nm) / math.sqrt(nm)
    gsm = defaultdict(list)
    for r in rs:
        gsm[r["cluster"]].append(r)
    us = [sum(r["d"] - dm for r in g) for g in gsm.values()]
    se_cl = math.sqrt(sum(u * u for u in us)) / nm
    z = dm / se_cl
    print("%-22s %+8.4f %9.5f %9.5f %9.3f %11.3e"
          % (MSHORT[m], dm, se_iid, se_cl, z, two_sided_z_p(z)))

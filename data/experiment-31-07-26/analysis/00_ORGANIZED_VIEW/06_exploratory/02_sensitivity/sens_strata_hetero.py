"""Strata-robustness: within-stratum A->B deltas + heterogeneity tests.

METHODS (all implemented here, stdlib only)
-------------------------------------------
Cell = (question_id, model). delta = B_correct - A_correct in {-1,0,+1}.
d_k   = mean(delta | stratum k)  = acc(B|k) - acc(A|k).

(1) PERMUTATION Q  [primary for heterogeneity]
    Statistic Q = sum_k S_k^2/n_k - S^2/n  (between-level sum of squares of the
    cell-level delta; a size-weighted Cochran-Q analogue).
    Null: level label is exchangeable across PERMUTATION BLOCKS, where a block
    is the maximal subset of one clinical-context CLUSTER that is homogeneous in
    the stratifier. For region/year/has_context a block == a whole cluster.
    This preserves (a) within-cluster correlation, (b) the fact that some levels
    are carried by a few very large clusters. B = 20000 shuffles.
    p = (#{Q_perm >= Q_obs} + 1)/(B+1).

(2) RANGE (max-min delta) permutation test, same null, reported both over all
    levels and over levels with >= 40 cells (small levels otherwise dominate).

(3) COCHRAN Q_W with CLUSTER-ROBUST variances [cross-check]
    v_k = G_k/(G_k-1) * (1/n_k^2) * sum_{clusters c} ( sum_{i in c,k}(delta_i-d_k) )^2
    Q_W = sum_k (d_k - d_IV)^2 / v_k , d_IV = inverse-variance-weighted mean.
    p from chi-square (K-1) via a series/continued-fraction incomplete gamma.
    Also I^2 = max(0, (Q_W-(K-1))/Q_W).

(4) NAIVE item-level permutation, shown only to quantify how badly ignoring the
    cluster structure inflates significance.

(5) MULTIPLICITY over the 6 pre-specified stratifications: Holm-Bonferroni on
    the permutation-Q p-values, plus Westfall-Young min-P computed from
    INDEPENDENT permutation streams per stratifier. Independence is the
    conservative choice here: the six stratifiers are positively dependent (they
    are near-collinear with exam blocks), and positive dependence would license
    a *less* strict threshold, so the reported min-P adjusted values are upper
    bounds on the dependence-aware ones.

(6) Per-level 95% CI for d_k by CLUSTER bootstrap (resample the 208 clusters
    with replacement, 10000 reps, percentile interval).
"""
import math
import random
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/"
                   "tier1_mcq/data/experiment-31-07-26/analysis")
from sens_strata_lib import (load, stratifiers, delta, stratum_table,  # noqa
                             cluster_bootstrap_levels, holm, perm_p)

B_PERM = 20000
B_BOOT = 10000
SEED = 20260731


# ------------------------------------------------------------ chi-square tail
def _lower_gamma_reg(s, x):
    if x < 0:
        return 0.0
    if x < s + 1.0:
        term = 1.0 / s
        total = term
        n = 1
        while n < 5000:
            term *= x / (s + n)
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
            n += 1
        return total * math.exp(-x + s * math.log(x) - math.lgamma(s))
    # continued fraction for upper
    tiny = 1e-300
    b = x + 1.0 - s
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 5000):
        an = -i * (i - s)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-15:
            break
    q = math.exp(-x + s * math.log(x) - math.lgamma(s)) * h
    return 1.0 - q


def chi2_sf(x, df):
    if x <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - _lower_gamma_reg(df / 2.0, x / 2.0)))


# ------------------------------------------------------- permutation blocks
def blocks_for(rows, key):
    """Maximal covariate-homogeneous subsets of clusters.
    Returns (S list, n list, label list, n_whole_clusters_split)."""
    agg = defaultdict(lambda: [0.0, 0])
    lab = {}
    for r in rows:
        k = (r["cluster"], key(r))
        agg[k][0] += delta(r)
        agg[k][1] += 1
        lab[k] = key(r)
    keys = list(agg)
    per_cluster = Counter(c for c, _ in keys)
    split = sum(1 for c, v in per_cluster.items() if v > 1)
    return ([agg[k][0] for k in keys], [agg[k][1] for k in keys],
            [lab[k] for k in keys], split)


def items_for(rows, key):
    agg = defaultdict(lambda: [0.0, 0])
    lab = {}
    for r in rows:
        k = r["question_id"]
        agg[k][0] += delta(r)
        agg[k][1] += 1
        lab[k] = key(r)
    keys = list(agg)
    return ([agg[k][0] for k in keys], [agg[k][1] for k in keys],
            [lab[k] for k in keys], 0)


def Q_range(S, N, labels, levels, big=None):
    ss = defaultdict(float)
    nn = defaultdict(int)
    ts = 0.0
    tn = 0
    for s, n, l in zip(S, N, labels):
        ss[l] += s
        nn[l] += n
        ts += s
        tn += n
    Q = -ts * ts / tn
    ds = []
    dsb = []
    for l in levels:
        n = nn[l]
        if n:
            Q += ss[l] * ss[l] / n
            ds.append(ss[l] / n)
            if big is None or n >= big:
                dsb.append(ss[l] / n)
    rng = (max(ds) - min(ds)) if len(ds) > 1 else 0.0
    rngb = (max(dsb) - min(dsb)) if len(dsb) > 1 else 0.0
    return Q, rng, rngb


def cochran_Q(rows, key):
    """Cluster-robust Cochran Q + I^2."""
    g = defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    d = {}
    v = {}
    for lev, rs in g.items():
        n = len(rs)
        dk = sum(delta(r) for r in rs) / n
        byc = defaultdict(float)
        for r in rs:
            byc[r["cluster"]] += delta(r) - dk
        G = len(byc)
        if G < 2 or n == 0:
            continue
        s = sum(x * x for x in byc.values())
        vk = (G / (G - 1.0)) * s / (n * n)
        if vk <= 0:
            continue
        d[lev] = dk
        v[lev] = vk
    if len(d) < 2:
        return None
    W = sum(1.0 / v[l] for l in d)
    dIV = sum(d[l] / v[l] for l in d) / W
    Q = sum((d[l] - dIV) ** 2 / v[l] for l in d)
    df = len(d) - 1
    I2 = max(0.0, (Q - df) / Q) if Q > 0 else 0.0
    return dict(Q=Q, df=df, p=chi2_sf(Q, df), I2=I2, dIV=dIV,
                K_used=len(d), K_all=len(g),
                dropped=[l for l in g if l not in d])


def main():
    subset = sys.argv[1] if len(sys.argv) > 1 else "analysis"
    rows = load(subset)
    strats, cuts = stratifiers(rows)
    NC = len(set(r["cluster"] for r in rows))
    print("#" * 100)
    print("STRATA ROBUSTNESS  subset=%s   cells=%d  items=%d  clusters=%d"
          % (subset, len(rows), len(set(r["question_id"] for r in rows)), NC))
    print("qlen tertile cutpoints over unique items: T1<=%d, T2 %d-%d, T3>%d"
          % (cuts[0], cuts[0] + 1, cuts[1], cuts[1]))
    print("#" * 100)

    # ---------------- overall
    n = len(rows)
    A = sum(r["A_correct"] for r in rows) / n
    Bv = sum(r["B_correct"] for r in rows) / n
    boot_all = cluster_bootstrap_levels(rows, lambda r: "ALL", B_BOOT, SEED)
    lo, hi, _ = boot_all["__ALL__"]
    n10 = sum(1 for r in rows if r["A_correct"] and not r["B_correct"])
    n01 = sum(1 for r in rows if not r["A_correct"] and r["B_correct"])
    print("\nOVERALL: acc(A)=%.4f  acc(B)=%.4f  delta=%+.4f  "
          "95%% cluster-bootstrap CI [%+.4f, %+.4f]" % (A, Bv, Bv - A, lo, hi))
    print("         discordant: A-right/B-wrong=%d, A-wrong/B-right=%d" % (n10, n01))

    # ---------------- per stratification
    rnd_master = random.Random(SEED)
    results = {}
    perm_null_store = {}
    # shared cluster permutation stream for the cluster-constant stratifiers
    cluster_constant = []
    for name, key, unit in strats:
        S, N, L, split = blocks_for(rows, key)
        cluster_constant.append((name, key, S, N, L, split))

    for si, (name, key, S, N, L, split) in enumerate(cluster_constant):
        levels = sorted(set(L))
        Qo, Ro, Rob = Q_range(S, N, L, levels, big=40)
        # deterministic seed: str.__hash__ is salted per process, never use it
        rnd = random.Random(SEED + 1000 * si)
        perm = list(L)
        Qn, Rn, Rbn = [], [], []
        for _ in range(B_PERM):
            rnd.shuffle(perm)
            q, r1, r2 = Q_range(S, N, perm, levels, big=40)
            Qn.append(q)
            Rn.append(r1)
            Rbn.append(r2)
        # naive item-level permutation
        Si, Ni, Li, _ = items_for(rows, key)
        levi = sorted(set(Li))
        Qoi, _, _ = Q_range(Si, Ni, Li, levi)
        rnd2 = random.Random(SEED + 7)
        pi = list(Li)
        Qni = []
        for _ in range(B_PERM // 4):
            rnd2.shuffle(pi)
            Qni.append(Q_range(Si, Ni, pi, levi)[0])
        cq = cochran_Q(rows, key)
        results[name] = dict(
            Q=Qo, pQ=perm_p(Qo, Qn), R=Ro, pR=perm_p(Ro, Rn),
            Rbig=Rob, pRbig=perm_p(Rob, Rbn),
            pQ_naive_item=perm_p(Qoi, Qni),
            n_blocks=len(S), split_clusters=split, K=len(levels), cq=cq)
        perm_null_store[name] = Qn

    # ---------------- Westfall-Young min-P over the family of 6
    names = [s[0] for s in strats]
    Bmin = B_PERM
    # column-wise permutation p for every replicate
    colp = {}
    for nm in names:
        null = sorted(perm_null_store[nm])
        Bn = len(null)
        # p of each null value within its own column
        # rank: number of values >= v
        colp[nm] = []
        # binary search
        import bisect
        for v in perm_null_store[nm]:
            ge = Bn - bisect.bisect_left(null, v - 1e-12)
            colp[nm].append((ge + 1) / (Bn + 1))
    minp = [min(colp[nm][b] for nm in names) for b in range(Bmin)]
    minp.sort()
    import bisect
    wy = {}
    for nm in names:
        pobs = results[nm]["pQ"]
        cnt = bisect.bisect_right(minp, pobs + 1e-12)
        wy[nm] = (cnt + 1) / (Bmin + 1)
    hol = holm({nm: results[nm]["pQ"] for nm in names})

    # ---------------- print
    for name, key, unit in strats:
        r = results[name]
        tab = stratum_table(rows, key)
        boot = cluster_bootstrap_levels(rows, key, B_BOOT, SEED + 1)
        print("\n" + "=" * 100)
        print("STRATIFIER: %s   (%d levels, %d permutation blocks, "
              "%d clusters split by this stratifier)"
              % (name, r["K"], r["n_blocks"], r["split_clusters"]))
        print("=" * 100)
        print("  %-26s %6s %5s %5s %7s %7s %8s %-20s %5s %5s"
              % ("level", "cells", "item", "clst", "acc(A)", "acc(B)", "delta",
                 "95% cluster-boot CI", "n10", "n01"))
        for lev in sorted(tab, key=lambda l: tab[l]["d"]):
            t = tab[lev]
            lo, hi, nb = boot[lev]
            ci = ("[%+.3f,%+.3f]" % (lo, hi)) if lo is not None else "[   n/a    ]"
            print("  %-26s %6d %5d %5d %7.4f %7.4f %+8.4f %-20s %5d %5d"
                  % (str(lev)[:26], t["n_cells"], t["n_items"], t["n_clusters"],
                     t["A"], t["B"], t["d"], ci, t["n10"], t["n01"]))
        print("  ---- heterogeneity ----")
        print("  Permutation Q (block-exchangeable, B=%d): Q=%.4f  p=%.5f"
              % (B_PERM, r["Q"], r["pQ"]))
        print("  Range max-min delta (all levels)   : %.4f  p=%.5f"
              % (r["R"], r["pR"]))
        print("  Range max-min delta (levels>=40 cells): %.4f  p=%.5f"
              % (r["Rbig"], r["pRbig"]))
        cq = r["cq"]
        if cq:
            print("  Cochran Q (cluster-robust var, chi2_%d): Q=%.3f  p=%.5f  "
                  "I2=%.3f  [%d/%d levels usable, need >=2 clusters]"
                  % (cq["df"], cq["Q"], cq["p"], cq["I2"], cq["K_used"], cq["K_all"]))
            if cq["dropped"]:
                print("     dropped (single cluster): %s"
                      % ", ".join(sorted(map(str, cq["dropped"]))[:8]))
        print("  NAIVE item-level permutation Q p (ignores clusters): %.5f"
              % r["pQ_naive_item"])
        print("  Multiplicity over the 6 stratifications: Holm p=%.4f   "
              "Westfall-Young min-P p=%.4f" % (hol[name], wy[name]))

    print("\n" + "#" * 100)
    print("SUMMARY over the pre-specified family of 6 stratifications (subset=%s)"
          % subset)
    print("#" * 100)
    print("  %-14s %8s %10s %10s %10s %10s %8s"
          % ("stratifier", "K", "perm-Q p", "Holm", "WY min-P", "CochranQ p", "I2"))
    for name, key, unit in strats:
        r = results[name]
        cq = r["cq"]
        print("  %-14s %8d %10.5f %10.4f %10.4f %10.5f %8.3f"
              % (name, r["K"], r["pQ"], hol[name], wy[name],
                 cq["p"] if cq else float("nan"), cq["I2"] if cq else float("nan")))


if __name__ == "__main__":
    main()

"""INDEPENDENT refutation pass #3.

(a) Re-verify the reported overall cluster-bootstrap CI with my own bootstrap.
(b) Stress the YEAR TREND signal found in pass 2: multiple seeds, B, weightings,
    scales, and a cluster-bootstrap slope CI.
(c) Check whether year is confounded with region / exam_part / has_context
    (i.e. whether 'year heterogeneity' is really 'Illes Balears heterogeneity').
(d) Repeat the whole six-stratifier omnibus family on the three alternative
    exclusion sets, since the claim is billed as a *robustness* claim.
"""
import json
import math
import random
from collections import defaultdict, Counter

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")
ROWS = json.load(open(DATA))


def subset(name):
    if name == "analysis":
        return [r for r in ROWS if r["analysis_include"]]
    if name == "all":
        return list(ROWS)
    if name == "plus_nota_a":
        return [r for r in ROWS if not r["excl_item_defect"]]
    if name == "plus_defect":
        return [r for r in ROWS if not r["excl_nota_position_a"]]
    raise ValueError(name)


def d(r):
    return r["B_correct"] - r["A_correct"]


def perm_p(obs, null):
    return (sum(1 for v in null if v >= obs - 1e-12) + 1) / (len(null) + 1)


# ------------------------------------------------------------------ (a) CI
def cluster_boot_overall(rows, B, seed):
    byc = defaultdict(list)
    for r in rows:
        byc[r["cluster"]].append(d(r))
    cl = list(byc)
    n = len(cl)
    rnd = random.Random(seed)
    out = []
    for _ in range(B):
        s = 0.0
        c = 0
        for _ in range(n):
            v = byc[cl[rnd.randrange(n)]]
            s += sum(v)
            c += len(v)
        out.append(s / c)
    out.sort()
    return out[int(0.025 * B)], out[min(B - 1, int(0.975 * B))]


# ------------------------------------------------ (b) year trend machinery
def trend_test(rows, score, yfun, B, seed):
    S = defaultdict(float)
    N = defaultdict(int)
    X = {}
    for r in rows:
        y = yfun(r)
        if y is None:
            continue
        k = (r["cluster"], score(r))
        S[k] += y
        N[k] += 1
        X[k] = score(r)
    ks = list(S)
    Sv = [S[k] for k in ks]
    Nv = [N[k] for k in ks]
    Xv = [X[k] for k in ks]
    tn = sum(Nv)
    xb = sum(x * n for x, n in zip(Xv, Nv)) / tn
    obs = abs(sum((x - xb) * s for x, s in zip(Xv, Sv)))
    rnd = random.Random(seed)
    perm = list(Xv)
    null = []
    for _ in range(B):
        rnd.shuffle(perm)
        xx = sum(x * n for x, n in zip(perm, Nv)) / tn
        null.append(abs(sum((x - xx) * s for x, s in zip(perm, Sv))))
    return obs, perm_p(obs, null), len(ks)


def wls_slope(rows, score, yfun):
    """Cell-weighted OLS slope of y on score (each cell one observation)."""
    n = sx = sy = sxx = sxy = 0.0
    for r in rows:
        y = yfun(r)
        if y is None:
            continue
        x = score(r)
        n += 1
        sx += x
        sy += y
        sxx += x * x
        sxy += x * y
    den = n * sxx - sx * sx
    if den == 0:
        return None
    return (n * sxy - sx * sy) / den


def cluster_boot_slope(rows, score, yfun, B, seed):
    byc = defaultdict(list)
    for r in rows:
        byc[r["cluster"]].append(r)
    cl = list(byc)
    n = len(cl)
    rnd = random.Random(seed)
    out = []
    for _ in range(B):
        samp = []
        for _ in range(n):
            samp.extend(byc[cl[rnd.randrange(n)]])
        s = wls_slope(samp, score, yfun)
        if s is not None:
            out.append(s)
    out.sort()
    m = len(out)
    return out[int(0.025 * m)], out[min(m - 1, int(0.975 * m))], m


def main():
    A = subset("analysis")
    print("#" * 96)
    print("(a) OVERALL CLUSTER-BOOTSTRAP CI, my own implementation")
    print("#" * 96)
    n = len(A)
    delta = sum(d(r) for r in A) / n
    for seed in (1, 2, 3):
        lo, hi = cluster_boot_overall(A, 10000, 10_000 + seed)
        print("  seed=%d  delta=%+.4f  95%% CI [%+.4f, %+.4f]"
              % (seed, delta, lo, hi))
    print("  claimed: delta=-0.1555  CI [-0.1881, -0.1242]")

    print("\n" + "#" * 96)
    print("(b) YEAR TREND -- stress test")
    print("#" * 96)
    yrs = sorted(set(r["year"] for r in A))
    print("  years present: %s" % yrs)
    print("  %-6s %6s %6s %6s %9s %9s %9s"
          % ("year", "cells", "items", "clust", "accA", "accB", "delta"))
    for y in yrs:
        rs = [r for r in A if r["year"] == y]
        print("  %-6d %6d %6d %6d %9.4f %9.4f %+9.4f"
              % (y, len(rs), len(set(r["question_id"] for r in rs)),
                 len(set(r["cluster"] for r in rs)),
                 sum(r["A_correct"] for r in rs) / len(rs),
                 sum(r["B_correct"] for r in rs) / len(rs),
                 sum(d(r) for r in rs) / len(rs)))

    print("\n  block-permutation two-sided trend p, raw delta scale:")
    for seed in (991, 4242, 777771, 20260731, 5150):
        obs, p, nb = trend_test(A, lambda r: float(r["year"]), d, 20000, seed)
        print("     seed=%-9d B=20000  |T|=%.3f  p=%.5f" % (seed, obs, p))
    obs, p, nb = trend_test(A, lambda r: float(r["year"]), d, 200000, 13131)
    print("     seed=13131     B=200000 |T|=%.3f  p=%.5f  (blocks=%d)" % (obs, p, nb))

    print("\n  same trend test on other scales:")
    obs, p, _ = trend_test(A, lambda r: float(r["year"]),
                           lambda r: (1 - r["B_correct"]) if r["A_correct"] == 1 else None,
                           20000, 991)
    print("     P(B wrong | A right)  |T|=%.3f  p=%.5f" % (obs, p))
    obs, p, _ = trend_test(A, lambda r: float(r["year"]),
                           lambda r: r["A_correct"], 20000, 991)
    print("     A_correct alone       |T|=%.3f  p=%.5f  <- is the trend just baseline drift?"
          % (obs, p))
    obs, p, _ = trend_test(A, lambda r: float(r["year"]),
                           lambda r: r["B_correct"], 20000, 991)
    print("     B_correct alone       |T|=%.3f  p=%.5f" % (obs, p))

    print("\n  cell-weighted OLS slope of delta on year, cluster-bootstrap CI:")
    sl = wls_slope(A, lambda r: float(r["year"]), d)
    lo, hi, m = cluster_boot_slope(A, lambda r: float(r["year"]), d, 5000, 909)
    print("     slope=%+.5f delta-per-year   95%% CI [%+.5f, %+.5f]  (reps=%d)"
          % (sl, lo, hi, m))
    print("     -> CI %s zero" % ("EXCLUDES" if lo * hi > 0 else "includes"))

    print("\n  rank-based (Spearman-style) year trend, block permutation:")
    rankmap = {y: i + 1 for i, y in enumerate(yrs)}
    obs, p, _ = trend_test(A, lambda r: float(rankmap[r["year"]]), d, 20000, 991)
    print("     |T|=%.3f  p=%.5f" % (obs, p))

    print("\n  leave-one-year-out: does any single year carry the trend?")
    for y in yrs:
        sub = [r for r in A if r["year"] != y]
        obs, p, _ = trend_test(sub, lambda r: float(r["year"]), d, 20000, 991)
        print("     drop %d (n=%4d left): trend p=%.5f"
              % (y, len(sub), p))

    print("\n" + "#" * 96)
    print("(c) IS 'year' CONFOUNDED WITH region / exam_part / has_context?")
    print("#" * 96)
    for other in ("region", "exam_part", "has_context"):
        ct = defaultdict(Counter)
        for r in A:
            ct[r["year"]][str(r[other])] += 1
        print("\n  year x %s (cells):" % other)
        for y in yrs:
            tot = sum(ct[y].values())
            top = ct[y].most_common(3)
            print("     %d n=%4d  top: %s" % (y, tot,
                  ", ".join("%s=%d(%.0f%%)" % (k, v, 100.0 * v / tot) for k, v in top)))
        # Cramer's V on the cell-level contingency table
        rows_l = sorted(set(r["year"] for r in A))
        cols_l = sorted(set(str(r[other]) for r in A))
        N = len(A)
        chi = 0.0
        rtot = {y: sum(ct[y].values()) for y in rows_l}
        ctot = {c: sum(ct[y][c] for y in rows_l) for c in cols_l}
        for y in rows_l:
            for c in cols_l:
                e = rtot[y] * ctot[c] / N
                if e > 0:
                    chi += (ct[y][c] - e) ** 2 / e
        V = math.sqrt(chi / (N * (min(len(rows_l), len(cols_l)) - 1)))
        print("     Cramer's V = %.3f  (1.0 = perfectly collinear)" % V)

    print("\n  year trend WITHIN Illes Balears only, and EXCLUDING it:")
    ib = [r for r in A if r["region"] == "Illes Balears"]
    nib = [r for r in A if r["region"] != "Illes Balears"]
    print("     Illes Balears: n=%d years=%s" % (len(ib), sorted(set(r["year"] for r in ib))))
    obs, p, _ = trend_test(nib, lambda r: float(r["year"]), d, 20000, 991)
    print("     excluding Illes Balears: n=%d  trend p=%.5f" % (len(nib), p))

    print("\n" + "#" * 96)
    print("(d) OMNIBUS FAMILY ON ALTERNATIVE EXCLUSION SETS")
    print("#" * 96)
    import sens_ref_strata_02_perm as P
    for nm in ("analysis", "plus_defect", "plus_nota_a", "all"):
        rs = subset(nm)
        res = P.run_family(rs, "  subset=%s" % nm, d, "delta", B=20000,
                           seed=333, verbose=False)
        ps = {k: v["pQ"] for k, v in res.items()}
        h = P.holm(ps)
        ob, pt, _ = trend_test(rs, lambda r: float(r["year"]), d, 20000, 991)
        print("\n  subset=%-12s cells=%4d clusters=%3d" % (nm, len(rs),
              len(set(r["cluster"] for r in rs))))
        print("     %-14s %10s %10s" % ("stratifier", "perm-Q p", "Holm"))
        for k in ("region", "year", "exam_part", "has_context", "negated_stem",
                  "qlen_tertile"):
            print("     %-14s %10.5f %10.4f" % (k, ps[k], h[k]))
        print("     year TREND p = %.5f" % pt)


if __name__ == "__main__":
    main()

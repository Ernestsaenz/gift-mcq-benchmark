"""REFUTATION of the "detectability floor" trichotomy in strata-robustness.

CLAIM UNDER TEST
----------------
"Only three of the six nulls are informative. has_context / negated_stem /
qlen_tertile sit at 6-11% of the smallest spread this design could have called
significant -> genuine homogeneity. region / year / exam_part sit at 64-87% of
that floor -> 'not significant' means 'underpowered', not 'homogeneous'."

Floor := 95th percentile of the block-permutation null of
    R = max_k d_k - min_k d_k     over levels with >= 40 CELLS.

SECTIONS
--------
 S0  Exact reproduction of the six (obs, floor, ratio) triples.
 S2  obs/floor is a monotone recoding of the permutation p-value; also report
     the null MEAN/SD and the percentile of obs inside its own null.
 S1b The floor scales with K (number of qualifying levels) under pure noise.
 S3  Common footing: same K=2 statistic for all six stratifiers.
 S4  Sensitivity of every ratio to the arbitrary >=40-cell rule.
 S5  Permutation-unit audit for the two item-level stratifiers.
 S6  Real MDE: power at the floor, MDE50, MDE80.
 S7  Cluster-bootstrap bound on the maximal true contrast (the only quantity
     that can support an invariance claim).

Stdlib only. Every p-value / interval method stated inline.
"""
import json
import math
import random
import sys
from collections import defaultdict

sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/"
                   "tier1_mcq/data/experiment-31-07-26/analysis")
from sens_strata_lib import load, stratifiers, delta, qlen_tertile_map  # noqa

B_PERM = 20000
SEED = 20260731
MINC = 40

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")

# The 14 items excluded by the dataset revision that the CLAIM was computed on
# (dataset_meta.json as of 2026-07-31 10:30: 11 admin-law + 3 adjudicated keys).
# The file was regenerated at 10:47:46 with 19 admin-law items and a relabelled
# negated_stem, so `analysis_include` now selects 1271 cells, not the 1299 the
# claim's brief specifies. Reconstructing the old rule lets us test the claim on
# its own dataset.
CLAIM_DEFECT_14 = set("b205 b238 b331 b341 b343 b378 b385 b391 b401 b420 b430 "
                      "b178 b197 b496".split())


def load_mode(mode):
    if mode == "current":
        return load("analysis")
    if mode == "claim":
        rows = json.load(open(DATA))
        return [r for r in rows
                if r["question_id"] not in CLAIM_DEFECT_14
                and r["correct_letter"] != "a"]
    raise ValueError(mode)


def cl_blocks(rows, key):
    """EXACT block construction of sens_strata_conditional.py's floor section:
    permutation unit = (cluster, level) aggregate."""
    agg = defaultdict(lambda: [0.0, 0])
    for r in rows:
        k = (r["cluster"], key(r))
        agg[k][0] += delta(r)
        agg[k][1] += 1
    ks = list(agg)
    return ([agg[k][0] for k in ks], [agg[k][1] for k in ks], [k[1] for k in ks])


def rng_stat(S, N, labels, levels, minc=MINC):
    ss = defaultdict(float)
    nn = defaultdict(int)
    for s, n, l in zip(S, N, labels):
        ss[l] += s
        nn[l] += n
    ds = [ss[l] / nn[l] for l in levels if nn[l] >= minc]
    return (max(ds) - min(ds)) if len(ds) > 1 else 0.0


def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))]


def pct_of(obs, null):
    return sum(1 for x in null if x < obs) / float(len(null))


def perm_p(obs, null):
    """one-sided permutation p with the +1 (Phipson-Smyth) correction."""
    return (sum(1 for x in null if x >= obs - 1e-12) + 1) / (len(null) + 1.0)


def sep(t):
    print("\n" + "=" * 104)
    print(t)
    print("=" * 104)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "claim"
    rows = load_mode(mode)
    strats, cuts = stratifiers(rows)
    names = [s[0] for s in strats]
    overall = sum(delta(r) for r in rows) / len(rows)
    print("MODE=%s   cells=%d items=%d clusters=%d   overall d = %+.4f  "
          "qlen cuts=%s"
          % (mode, len(rows), len(set(r["question_id"] for r in rows)),
             len(set(r["cluster"] for r in rows)), overall, cuts))

    # =========================================================== S0 + S2
    sep("S0/S2  REPRODUCTION, AND WHAT obs/floor ACTUALLY IS")
    print("  %-13s %3s %9s %9s %7s | %9s %9s %8s %9s"
          % ("stratifier", "K", "obs", "floor95", "ratio",
             "null MEAN", "null SD", "obs pct", "perm p"))
    store = {}
    for name, key, unit in strats:
        S, N, L = cl_blocks(rows, key)
        levels = sorted(set(L))
        ss = defaultdict(float)
        nn = defaultdict(int)
        for s, n, l in zip(S, N, L):
            ss[l] += s
            nn[l] += n
        keep = [l for l in levels if nn[l] >= MINC]
        obs = rng_stat(S, N, L, levels)
        rnd = random.Random(SEED + 5)                 # original seed, verbatim
        perm = list(L)
        null, nlev = [], []
        for _ in range(B_PERM):
            rnd.shuffle(perm)
            null.append(rng_stat(S, N, perm, levels))
            c = defaultdict(int)
            for n, l in zip(N, perm):
                c[l] += n
            nlev.append(sum(1 for l in levels if c[l] >= MINC))
        fl = q(null, 0.95)
        mu = sum(null) / len(null)
        sd = math.sqrt(sum((x - mu) ** 2 for x in null) / (len(null) - 1))
        print("  %-13s %3d %9.4f %9.4f %7.2f | %9.4f %9.4f %8.3f %9.4f"
              % (name, len(keep), obs, fl, obs / fl, mu, sd,
                 pct_of(obs, null), perm_p(obs, null)))
        store[name] = dict(S=S, N=N, L=L, levels=levels, keep=keep, obs=obs,
                           floor=fl, null=null, nn=dict(nn), ss=dict(ss),
                           nlev=nlev, key=key, unit=unit, mu=mu, sd=sd)

    print("\n  Monotonicity check (is the ratio anything but the p-value?):")
    by_ratio = sorted(names, key=lambda n: store[n]["obs"] / store[n]["floor"])
    by_p = sorted(names, key=lambda n: -perm_p(store[n]["obs"], store[n]["null"]))
    print("    rank by obs/floor ascending : " + " < ".join(by_ratio))
    print("    rank by perm p  descending  : " + " < ".join(by_p))
    print("    identical ordering: %s" % (by_ratio == by_p))

    print("\n  Levels entering R under the null (K is not even held fixed):")
    for name in names:
        v = store[name]["nlev"]
        print("    %-13s observed K=%2d | null K mean %.2f, range %d-%d"
              % (name, len(store[name]["keep"]), sum(v) / len(v), min(v), max(v)))

    # =========================================================== S1b
    sep("S1b  THE FLOOR IS A FUNCTION OF K AND OF LEVEL IMBALANCE, NOT OF POWER")
    print("  The floor is computed entirely under the null -- no signal enters")
    print("  it. Below, the SAME 208 clusters are split into K pure-noise")
    print("  pseudo-levels (no real covariate at all) and the floor recomputed.")
    Sc = defaultdict(float)
    Nc = defaultdict(int)
    for r in rows:
        Sc[r["cluster"]] += delta(r)
        Nc[r["cluster"]] += 1
    cls = list(Sc)
    Sv = [Sc[c] for c in cls]
    Nv = [Nc[c] for c in cls]
    print("\n  (a) equal-size pseudo-levels, sample size per level matched by K:")
    print("      %5s %11s %14s" % ("K", "floor95", "vs floor(K=2)"))
    base = None
    for K in (2, 3, 5, 8, 11, 15):
        rnd = random.Random(SEED + 991 + K)
        lab = [i % K for i in range(len(cls))]
        levs = list(range(K))
        perm = list(lab)
        null = []
        for _ in range(6000):
            rnd.shuffle(perm)
            null.append(rng_stat(Sv, Nv, perm, levs))
        f = q(null, 0.95)
        base = f if base is None else base
        print("      %5d %11.4f %14.2fx" % (K, f, f / base))
    print("      (B=6000 whole-cluster permutations per row.)")

    print("\n  (b) pseudo-levels with each real stratifier's OWN size profile,")
    print("      labels assigned at random to clusters (covariate = pure noise):")
    print("      %-13s %3s %11s %11s" % ("size profile of", "K", "floor95",
                                         "reported floor"))
    for name in names:
        st = store[name]
        rnd = random.Random(SEED + 77)
        lab = list(st["L"])
        rnd.shuffle(lab)                      # destroy any real association
        S, N = st["S"], st["N"]
        levels = st["levels"]
        perm = list(lab)
        null = []
        for _ in range(6000):
            rnd.shuffle(perm)
            null.append(rng_stat(S, N, perm, levels))
        print("      %-13s %3d %11.4f %11.4f"
              % (name, len(st["keep"]), q(null, 0.95), st["floor"]))
    print("      -> identical by construction: the 'floor' contains ZERO")
    print("         information about the covariate; it is a noise scale set by")
    print("         K and the level-size profile.")

    # =========================================================== S3
    sep("S3  COMMON FOOTING: THE SAME K=2 STATISTIC FOR ALL SIX")
    print("  Statistic = |d(L1) - d(L2)| for the two LARGEST qualifying levels,")
    print("  fixed from the observed data; null = same whole-cluster block")
    print("  permutation, B=%d. Removes the max-over-K inflation." % B_PERM)
    print("\n  %-13s %-30s %9s %9s %7s"
          % ("stratifier", "contrast", "obs", "floor95", "ratio"))
    k2 = {}
    for name in names:
        st = store[name]
        a, b = sorted(st["keep"], key=lambda l: -st["nn"][l])[:2]
        S, N, L = st["S"], st["N"], st["L"]

        def gap(labels):
            ss = defaultdict(float)
            nn = defaultdict(int)
            for s, n, l in zip(S, N, labels):
                ss[l] += s
                nn[l] += n
            if not nn[a] or not nn[b]:
                return 0.0
            return abs(ss[a] / nn[a] - ss[b] / nn[b])

        obs = gap(L)
        rnd = random.Random(SEED + 7)
        perm = list(L)
        null = []
        for _ in range(B_PERM):
            rnd.shuffle(perm)
            null.append(gap(perm))
        f = q(null, 0.95)
        k2[name] = (obs, f, obs / f)
        print("  %-13s %-30s %9.4f %9.4f %7.2f"
              % (name, ("%s / %s" % (a, b))[:30], obs, f, obs / f))
    print("\n  ordering by ORIGINAL obs/floor : "
          + " > ".join(sorted(names, key=lambda n: -store[n]["obs"] / store[n]["floor"])))
    print("  ordering by K=2      obs/floor : "
          + " > ".join(sorted(names, key=lambda n: -k2[n][2])))

    # =========================================================== S4
    sep("S4  THE >=40-CELL RULE IS ARBITRARY AND MOVES EVERY RATIO")
    ths = (20, 40, 60, 80, 100, 150)
    print("  %-13s" % "stratifier" + "".join("%15s" % ("minc=%d" % m) for m in ths))
    print("  cell = obs/floor  (K)")
    for name, key, unit in strats:
        st = store[name]
        S, N, L, levels = st["S"], st["N"], st["L"], st["levels"]
        line = "  %-13s" % name
        for m in ths:
            obs = rng_stat(S, N, L, levels, m)
            K = sum(1 for l in levels if st["nn"][l] >= m)
            rnd = random.Random(SEED + 5)
            perm = list(L)
            null = []
            for _ in range(6000):
                rnd.shuffle(perm)
                null.append(rng_stat(S, N, perm, levels, m))
            f = q(null, 0.95)
            line += "%15s" % ("%.2f (%d)" % ((obs / f) if f else float("nan"), K))
        print(line)
    print("\n  (B=6000 per cell.)  A conclusion that flips with an undeclared")
    print("  nuisance threshold is not a robustness result.")

    # =========================================================== S5
    sep("S5  PERMUTATION-UNIT AUDIT (negated_stem, qlen_tertile)")
    print("  The claim says 'same block-permutation null as the Q test'. The Q")
    print("  test permutes ITEMS for item-level covariates (sens_strata_lib")
    print("  _units(..., unit='item')); the floor code permutes (cluster x")
    print("  level) aggregates. Consequences:\n")
    lab, _ = qlen_tertile_map(rows)
    itemvars = [("negated_stem", lambda r: str(r["negated_stem"])),
                ("qlen_tertile", lambda r: lab(r["qlen"]))]
    print("  %-13s %-32s %6s %9s %9s %7s"
          % ("stratifier", "permutation unit", "units", "obs", "floor95", "ratio"))
    for name, key in itemvars:
        st = store[name]
        print("  %-13s %-32s %6d %9.4f %9.4f %7.2f"
              % (name, "(cluster x level) block [used]", len(st["S"]),
                 st["obs"], st["floor"], st["obs"] / st["floor"]))
        agg = defaultdict(lambda: [0.0, 0])
        clu, lb = {}, {}
        for r in rows:
            qid = r["question_id"]
            agg[qid][0] += delta(r)
            agg[qid][1] += 1
            clu[qid] = r["cluster"]
            lb[qid] = key(r)
        qs = list(agg)
        S = [agg[x][0] for x in qs]
        N = [agg[x][1] for x in qs]
        L = [lb[x] for x in qs]
        C = [clu[x] for x in qs]
        levels = sorted(set(L))
        obs = rng_stat(S, N, L, levels)
        idx = defaultdict(list)
        for i, c in enumerate(C):
            idx[c].append(i)
        groups = [v for v in idx.values() if len(v) > 1]
        for tag, restricted in (("item, free", False),
                                ("item, within-cluster (exact)", True)):
            rnd = random.Random(SEED + 13)
            perm = list(L)
            null = []
            for _ in range(B_PERM):
                if restricted:
                    for ix in groups:
                        lv = [L[i] for i in ix]
                        rnd.shuffle(lv)
                        for i, x in zip(ix, lv):
                            perm[i] = x
                else:
                    rnd.shuffle(perm)
                null.append(rng_stat(S, N, perm, levels))
            f = q(null, 0.95)
            print("  %-13s %-32s %6d %9.4f %9.4f %7s"
                  % ("", tag, len(S), obs, f,
                     ("%.2f" % (obs / f)) if f else "n/a"))

    # =========================================================== S6
    sep("S6  THE FLOOR IS NOT AN MDE -- IT IS THE ~50%-POWER POINT")
    print("  Power computed by shifting the two largest qualifying levels apart")
    print("  by Delta (+D/2, -D/2) on top of the stored permutation draws (which")
    print("  carry the design's real noise), then re-testing against the SAME")
    print("  critical value = the quoted floor. Most favourable placement of a")
    print("  true effect, so MDE80 below is a LOWER bound.\n")
    print("  %-13s %9s %11s %9s %9s %10s"
          % ("stratifier", "floor95", "power@floor", "MDE50", "MDE80", "MDE80/fl"))
    for name, key, unit in strats:
        st = store[name]
        S, N, L, levels, keep = (st["S"], st["N"], st["L"], st["levels"],
                                 st["keep"])
        a, b = sorted(keep, key=lambda l: -st["nn"][l])[:2]
        rnd = random.Random(SEED + 5)
        perm = list(L)
        comp = []                      # (m_a or None, m_b or None, othmax, othmin)
        for _ in range(B_PERM):
            rnd.shuffle(perm)
            ss = defaultdict(float)
            nn = defaultdict(int)
            for s, n, l in zip(S, N, perm):
                ss[l] += s
                nn[l] += n
            ma = ss[a] / nn[a] if nn[a] >= MINC else None
            mb = ss[b] / nn[b] if nn[b] >= MINC else None
            oth = [ss[l] / nn[l] for l in levels
                   if nn[l] >= MINC and l != a and l != b]
            comp.append((ma, mb, max(oth) if oth else None,
                         min(oth) if oth else None))
        fl = st["floor"]

        def power(D):
            hit = 0
            for ma, mb, omx, omn in comp:
                vals = []
                if ma is not None:
                    vals.append(ma + D / 2.0)
                if mb is not None:
                    vals.append(mb - D / 2.0)
                if omx is not None:
                    vals.append(omx)
                    vals.append(omn)
                if len(vals) > 1 and (max(vals) - min(vals)) > fl:
                    hit += 1
            return hit / float(len(comp))

        def solve(t):
            lo, hi = 0.0, 2.0
            for _ in range(24):
                mid = (lo + hi) / 2.0
                if power(mid) < t:
                    lo = mid
                else:
                    hi = mid
            return (lo + hi) / 2.0

        print("  %-13s %9.4f %11.3f %9.4f %9.4f %10.2f"
              % (name, fl, power(fl), solve(0.50), solve(0.80),
                 solve(0.80) / fl))

    # =========================================================== S7
    sep("S7  WHAT IS ACTUALLY RULED OUT: CLUSTER-BOOTSTRAP CONTRAST BOUNDS")
    print("  Nonparametric cluster bootstrap: resample the 208 clusters with")
    print("  replacement, B=8000, percentile method. Reported: 97.5th percentile")
    print("  of the max-min spread over qualifying levels = the largest true")
    print("  spread still compatible with the data at 95% confidence.\n")
    BB = 8000
    byc = defaultdict(list)
    for r in rows:
        byc[r["cluster"]].append(r)
    cls = list(byc)
    nC = len(cls)
    print("  %-13s %9s %12s %11s %12s %14s"
          % ("stratifier", "obs range", "boot 97.5%", "floor95",
             "bound/|d_all|", "verdict"))
    for name, key, unit in strats:
        st = store[name]
        keep = list(st["keep"])
        pre = {}
        for c in cls:
            ss = defaultdict(float)
            nn = defaultdict(int)
            for r in byc[c]:
                l = key(r)
                ss[l] += delta(r)
                nn[l] += 1
            pre[c] = [(l, ss[l], nn[l]) for l in ss]
        rnd = random.Random(SEED + 31)
        draws = []
        for _ in range(BB):
            ss = defaultdict(float)
            nn = defaultdict(int)
            for _ in range(nC):
                for l, s, n in pre[cls[rnd.randrange(nC)]]:
                    ss[l] += s
                    nn[l] += n
            ds = [ss[l] / nn[l] for l in keep if nn[l]]
            draws.append((max(ds) - min(ds)) if len(ds) > 1 else 0.0)
        hi = q(draws, 0.975)
        v = "NOT homogeneous" if hi > 0.5 * abs(overall) else "bounded"
        print("  %-13s %9.4f %12.4f %11.4f %12.2f %14s"
              % (name, st["obs"], hi, st["floor"], hi / abs(overall), v))
    print("\n  |d_all| = %.4f (overall A->B effect). The last column is the" % abs(overall))
    print("  still-compatible between-level spread expressed as a multiple of")
    print("  the main effect. An invariance claim needs this to be SMALL.")


if __name__ == "__main__":
    main()

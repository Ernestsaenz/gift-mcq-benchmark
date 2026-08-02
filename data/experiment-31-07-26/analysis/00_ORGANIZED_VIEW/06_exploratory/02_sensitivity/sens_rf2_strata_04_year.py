"""REFUTATION script 04.

  Y1  The year trend: cluster-bootstrap CI on the slope, leave-one-year-out and
      leave-one-region-out robustness, and honest multiplicity over an expanded
      family of 6 omnibus + 2 ordered tests.
  Y2  Exclusion-set sensitivity of all six heterogeneity p-values.  Both
      exclusions in this experiment are contestable, so a "robustness" claim
      that holds on exactly one exclusion set is not a robustness claim.
  Y3  Chase the one claimed number I could not reproduce (negated_stem
      perm-Q p = 0.89576) across every reconstructable subset.
"""
import bisect
import json
import random
from collections import defaultdict

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")
META = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/dataset_meta.json")
B = 20000
SEED = 771


def d(r):
    return r["B_correct"] - r["A_correct"]


with open(DATA) as fh:
    ALL = json.load(fh)
with open(META) as fh:
    M = json.load(fh)
ADDED8 = {"b213", "b293", "b361", "b396", "b407", "b433", "b445", "b451"}
V1BAD = ({q for q in M["exclusions"]["out_of_domain_law"] if q not in ADDED8}
         | set(M["exclusions"]["adjudicated_key_defect"]))

SUBSETS = {
    "v2_analysis      (shipped: 22 defect + 91 letter-a dropped)":
        lambda r: r["analysis_include"],
    "v1_analysis      (claim's: 14 defect + 91 letter-a dropped)":
        lambda r: r["question_id"] not in V1BAD and not r["excl_nota_position_a"],
    "reinstate_letter_a (22 defect dropped only)":
        lambda r: not r["excl_item_defect"],
    "reinstate_defects  (91 letter-a dropped only)":
        lambda r: not r["excl_nota_position_a"],
    "unfiltered        (all 1691 cells)":
        lambda r: True,
}


def tertile(rows):
    per = {r["question_id"]: r["qlen"] for r in rows}
    v = sorted(per.values())
    n = len(v)
    c1, c2 = v[int(round(n / 3.0)) - 1], v[int(round(2 * n / 3.0)) - 1]
    return lambda r: "T1" if r["qlen"] <= c1 else ("T2" if r["qlen"] <= c2
                                                   else "T3")


def strats(rows):
    t = tertile(rows)
    return [("region", lambda r: r["region"]),
            ("year", lambda r: str(r["year"])),
            ("exam_part", lambda r: r["exam_part"]),
            ("has_context", lambda r: str(r["has_context"])),
            ("negated_stem", lambda r: str(r["negated_stem"])),
            ("qlen_tertile", t)]


def Qstat(S, N, L, levels):
    ss, nn = defaultdict(float), defaultdict(int)
    ts = tn = 0.0
    for s, n, l in zip(S, N, L):
        ss[l] += s
        nn[l] += n
        ts += s
        tn += n
    Q = -ts * ts / tn
    for l in levels:
        if nn[l]:
            Q += ss[l] * ss[l] / nn[l]
    return Q


def blocks(rows, kf):
    agg = defaultdict(lambda: [0.0, 0])
    lab = {}
    for r in rows:
        k = (r["cluster"], kf(r))
        agg[k][0] += d(r)
        agg[k][1] += 1
        lab[k] = kf(r)
    ks = list(agg)
    return ([agg[k][0] for k in ks], [agg[k][1] for k in ks],
            [lab[k] for k in ks])


def permQ(rows, kf, seed, b=B):
    S, N, L = blocks(rows, kf)
    lev = sorted(set(L))
    obs = Qstat(S, N, L, lev)
    rnd = random.Random(seed)
    p = list(L)
    null = []
    for _ in range(b):
        rnd.shuffle(p)
        null.append(Qstat(S, N, p, lev))
    return obs, null, (sum(1 for v in null if v >= obs - 1e-12) + 1) / (b + 1)


def trend_stat(S, N, L, score):
    ss, nn = defaultdict(float), defaultdict(int)
    for s, n, l in zip(S, N, L):
        ss[l] += s
        nn[l] += n
    tot = sum(nn.values())
    sbar = sum(nn[l] * score[l] for l in nn) / tot
    return sum(nn[l] * (score[l] - sbar) * (ss[l] / nn[l]) for l in nn)


def perm_trend(rows, kf, score, seed, b=B):
    S, N, L = blocks(rows, kf)
    obs = trend_stat(S, N, L, score)
    rnd = random.Random(seed)
    p = list(L)
    null = []
    for _ in range(b):
        rnd.shuffle(p)
        null.append(trend_stat(S, N, p, score))
    a = abs(obs)
    return obs, null, (sum(1 for v in null if abs(v) >= a - 1e-12) + 1) / (b + 1)


def wls_slope(rows):
    """Size-weighted OLS slope of d_k on calendar year (delta per decade)."""
    ss, nn = defaultdict(float), defaultdict(int)
    for r in rows:
        ss[r["year"]] += d(r)
        nn[r["year"]] += 1
    ys = sorted(nn)
    tot = sum(nn.values())
    xbar = sum(nn[y] * y for y in ys) / tot
    ybar = sum(ss[y] for y in ys) / tot
    num = sum(nn[y] * (y - xbar) * (ss[y] / nn[y] - ybar) for y in ys)
    den = sum(nn[y] * (y - xbar) ** 2 for y in ys)
    return num / den if den else float("nan")


def boot_slope(rows, Bb, seed):
    byc = defaultdict(list)
    for r in rows:
        byc[r["cluster"]].append(r)
    cl = list(byc)
    n = len(cl)
    rnd = random.Random(seed)
    out = []
    for _ in range(Bb):
        rs = []
        for _ in range(n):
            rs.extend(byc[cl[rnd.randrange(n)]])
        if len({r["year"] for r in rs}) > 1:
            out.append(wls_slope(rs))
    out.sort()
    return out


def holm(pv):
    it = sorted(pv.items(), key=lambda kv: kv[1])
    m = len(it)
    run = 0.0
    o = {}
    for i, (k, p) in enumerate(it):
        run = max(run, min(1.0, (m - i) * p))
        o[k] = run
    return o


def wy(nulls, pobs, two_sided=()):
    names = list(nulls)
    Bm = min(len(nulls[n]) for n in names)
    cols = {}
    for nm in names:
        vals = [abs(v) for v in nulls[nm]] if nm in two_sided else nulls[nm]
        srt = sorted(vals)
        Bn = len(srt)
        cols[nm] = [(Bn - bisect.bisect_left(srt, v - 1e-12) + 1) / (Bn + 1)
                    for v in vals[:Bm]]
    minp = sorted(min(cols[nm][b] for nm in names) for b in range(Bm))
    return {nm: (bisect.bisect_right(minp, pobs[nm] + 1e-12) + 1) / (Bm + 1)
            for nm in names}


def main():
    rows = [r for r in ALL if r["analysis_include"]]
    yrs = sorted({r["year"] for r in rows})

    print("=" * 104)
    print("Y1  THE YEAR TREND (v2 analysis set)")
    print("=" * 104)
    ss, nn = defaultdict(float), defaultdict(int)
    nc = defaultdict(set)
    for r in rows:
        ss[r["year"]] += d(r)
        nn[r["year"]] += 1
        nc[r["year"]].add(r["cluster"])
    for y in yrs:
        print("    %d  n=%4d  clusters=%3d  delta=%+.4f"
              % (y, nn[y], len(nc[y]), ss[y] / nn[y]))
    sl = wls_slope(rows)
    bs = boot_slope(rows, 6000, SEED)
    print("  size-weighted slope of delta on calendar year: %+.5f /yr "
          "(=%+.4f per decade)" % (sl, 10 * sl))
    print("  95%% cluster-bootstrap CI: [%+.5f, %+.5f] /yr  -> excludes 0: %s"
          % (bs[int(0.025 * len(bs))], bs[int(0.975 * len(bs))],
             bs[int(0.025 * len(bs))] > 0 or bs[int(0.975 * len(bs))] < 0))
    frac_pos = sum(1 for v in bs if v > 0) / len(bs)
    print("  bootstrap one-sided evidence: %.4f of draws have slope>0" % frac_pos)

    sc = {str(y): float(y) for y in yrs}
    o, nl, p = perm_trend(rows, lambda r: str(r["year"]), sc, SEED + 1)
    print("  block-permutation ordered test (calendar score): T=%+.3f  "
          "two-sided p=%.5f" % (o, p))

    print("\n  leave-one-YEAR-out (ordered test re-run on the remaining years):")
    for y in yrs:
        sub = [r for r in rows if r["year"] != y]
        s2 = {str(v): float(v) for v in sorted({x["year"] for x in sub})}
        _, _, pp = perm_trend(sub, lambda r: str(r["year"]), s2, SEED + 2, 8000)
        print("    drop %d (n=%4d left): p=%.5f  slope=%+.5f"
              % (y, len(sub), pp, wls_slope(sub)))

    print("\n  leave-one-REGION-out (year and region are collinear, V=0.70):")
    for rg in sorted({r["region"] for r in rows}):
        sub = [r for r in rows if r["region"] != rg]
        yy = sorted({x["year"] for x in sub})
        if len(yy) < 3:
            continue
        s2 = {str(v): float(v) for v in yy}
        _, _, pp = perm_trend(sub, lambda r: str(r["year"]), s2, SEED + 3, 8000)
        print("    drop %-22s (n=%4d left, %d yrs): p=%.5f  slope=%+.5f"
              % (rg, len(sub), len(yy), pp, wls_slope(sub)))

    print("\n  HONEST MULTIPLICITY: family = 6 omnibus Q + 2 ordered "
          "(year, qlen) = 8 tests")
    nulls, pobs, two = {}, {}, set()
    for nm, kf in strats(rows):
        _, nl2, pp = permQ(rows, kf, SEED + 10 + len(nm))
        nulls[nm], pobs[nm] = nl2, pp
    t = tertile(rows)
    for nm, kf, sc2 in (("year_TREND", lambda r: str(r["year"]),
                         {str(y): float(y) for y in yrs}),
                        ("qlen_TREND", t, {"T1": 0.0, "T2": 1.0, "T3": 2.0})):
        _, nl2, pp = perm_trend(rows, kf, sc2, SEED + 20 + len(nm))
        nulls[nm], pobs[nm] = nl2, pp
        two.add(nm)
    h = holm(pobs)
    w = wy(nulls, pobs, two_sided=two)
    print("    %-14s %10s %10s %10s" % ("test", "raw p", "Holm(8)", "WY min-P"))
    for nm in ["region", "year", "year_TREND", "exam_part", "has_context",
               "negated_stem", "qlen_tertile", "qlen_TREND"]:
        print("    %-14s %10.5f %10.4f %10.4f" % (nm, pobs[nm], h[nm], w[nm]))

    # ------------------------------------------------------------------ Y2
    print()
    print("=" * 104)
    print("Y2  EXCLUSION-SET SENSITIVITY of the six heterogeneity p-values")
    print("=" * 104)
    hdr = ["region", "year", "exam_part", "has_context", "negated_stem",
           "qlen_tertile"]
    print("  %-52s %6s %5s %8s %s"
          % ("subset", "cells", "clus", "delta",
             " ".join("%12s" % x[:12] for x in hdr)))
    for nm, f in SUBSETS.items():
        rr = [r for r in ALL if f(r)]
        st = dict(strats(rr))
        ps = {}
        for k in hdr:
            _, _, pp = permQ(rr, st[k], SEED + 40 + len(k), 10000)
            ps[k] = pp
        dd = sum(d(r) for r in rr) / len(rr)
        print("  %-52s %6d %5d %+8.4f %s"
              % (nm, len(rr), len({r["cluster"] for r in rr}), dd,
                 " ".join("%12.5f" % ps[k] for k in hdr)))

    # ------------------------------------------------------------------ Y3
    print()
    print("=" * 104)
    print("Y3  CHASING THE UNREPRODUCIBLE NUMBER: claim says negated_stem "
          "perm-Q p = 0.89576")
    print("=" * 104)
    for nm, f in SUBSETS.items():
        rr = [r for r in ALL if f(r)]
        S, N, L = blocks(rr, lambda r: str(r["negated_stem"]))
        _, _, pp = permQ(rr, lambda r: str(r["negated_stem"]),
                         SEED + 99, 20000)
        dd, nnn = defaultdict(float), defaultdict(int)
        for r in rr:
            dd[r["negated_stem"]] += d(r)
            nnn[r["negated_stem"]] += 1
        print("  %-52s blocks=%3d  p=%.5f  d(True)=%+.4f d(False)=%+.4f"
              % (nm, len(S), pp, dd[True] / nnn[True], dd[False] / nnn[False]))
    print("  claim also states '211/216 blocks for exam_part/negated_stem/"
          "qlen'; reconstructed v1 gives 211/218/211.")


if __name__ == "__main__":
    main()

"""Follow-ups on the strata analysis.

(1) SCALE ROBUSTNESS. The raw delta is mechanically bounded by acc(A): a stratum
    where the models were already weak on A cannot lose much. Re-run the six
    heterogeneity tests on the scale-free RETENTION rate
        rho_k = P(B correct | A correct)  (cells with A_correct==1 only)
    which removes that floor. If a stratification is homogeneous on both scales
    the null is not a scale artifact.

(2) YEAR-TREND FRAGILITY. Only 5 regions span >1 year, so the within-region year
    trend rests on ~5 independent comparisons. Show the per-region year deltas
    and leave-one-region-out p-values.

(3) EXCLUSION x STRATUM INTERACTION. Where do the 91 letter-(a) items and the 14
    adjudicated items sit? If they concentrate in particular years/regions, the
    contested exclusions and the stratification are entangled.

(4) POSITION CONTRAST on the unfiltered set: letter (a) vs (b,c,d), the direct
    test of the construction-defect claim behind exclusion (2).
"""
import random
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/"
                   "tier1_mcq/data/experiment-31-07-26/analysis")
from sens_strata_lib import load, stratifiers, delta, holm, perm_p  # noqa

B_PERM = 20000
SEED = 20260731


def blocks_generic(rows, key, val):
    """val(r) -> (numerator, denominator) contribution."""
    agg = defaultdict(lambda: [0.0, 0.0])
    lab = {}
    for r in rows:
        num, den = val(r)
        if den == 0:
            continue
        k = (r["cluster"], key(r))
        agg[k][0] += num
        agg[k][1] += den
        lab[k] = key(r)
    ks = list(agg)
    return ([agg[k][0] for k in ks], [agg[k][1] for k in ks],
            [lab[k] for k in ks])


def Qstat(S, N, labels, levels):
    ss = defaultdict(float)
    nn = defaultdict(float)
    ts = tn = 0.0
    for s, n, l in zip(S, N, labels):
        ss[l] += s
        nn[l] += n
        ts += s
        tn += n
    Q = -ts * ts / tn
    for l in levels:
        if nn[l]:
            Q += ss[l] * ss[l] / nn[l]
    return Q


def hetero(rows, key, val, seed):
    S, N, L = blocks_generic(rows, key, val)
    levels = sorted(set(L))
    Qo = Qstat(S, N, L, levels)
    rnd = random.Random(seed)
    perm = list(L)
    null = []
    for _ in range(B_PERM):
        rnd.shuffle(perm)
        null.append(Qstat(S, N, perm, levels))
    ss = defaultdict(float); nn = defaultdict(float)
    for s, n, l in zip(S, N, L):
        ss[l] += s; nn[l] += n
    est = {l: ss[l] / nn[l] for l in levels if nn[l]}
    cnt = {l: nn[l] for l in levels}
    return perm_p(Qo, null), Qo, est, cnt


def main():
    print("#" * 100)
    print("(1) SCALE ROBUSTNESS: heterogeneity of RETENTION  rho = P(B ok | A ok)")
    print("#" * 100)
    for subset in ["analysis", "all"]:
        rows = load(subset)
        strats, _ = stratifiers(rows)
        aok = [r for r in rows if r["A_correct"] == 1]
        base = sum(r["B_correct"] for r in aok) / len(aok)
        print("\n-- subset=%s : %d cells with A correct, overall retention "
              "rho=%.4f (so %.4f of previously-correct answers are lost)"
              % (subset, len(aok), base, 1 - base))
        ps_d, ps_r = {}, {}
        for i, (nm, key, unit) in enumerate(strats):
            pd_, Qd, ed, cd = hetero(rows, key,
                                     lambda r: (delta(r), 1), SEED + i)
            pr_, Qr, er, cr = hetero(aok, key,
                                     lambda r: (r["B_correct"], 1), SEED + 50 + i)
            ps_d[nm] = pd_; ps_r[nm] = pr_
            big = [l for l in er if cr[l] >= 30]
            if len(big) > 1:
                lo = min(big, key=lambda l: er[l]); hi = max(big, key=lambda l: er[l])
                span = "rho %s=%.3f .. %s=%.3f" % (str(lo)[:14], er[lo],
                                                   str(hi)[:14], er[hi])
            else:
                span = "-"
            print("   %-14s  delta-scale p=%.5f | retention-scale p=%.5f   %s"
                  % (nm, pd_, pr_, span))
        hd = holm(ps_d); hr = holm(ps_r)
        print("   Holm-adjusted (family of 6): delta-scale min=%.4f, "
              "retention-scale min=%.4f"
              % (min(hd.values()), min(hr.values())))

    print("\n" + "#" * 100)
    print("(2) YEAR-TREND FRAGILITY")
    print("#" * 100)
    for subset in ["analysis", "all"]:
        rows = load(subset)
        print("\n-- subset=%s : per-region x year delta (only regions spanning "
              ">1 year are identified)" % subset)
        g = defaultdict(list)
        for r in rows:
            g[(r["region"], r["year"])].append(r)
        yrs_in_reg = defaultdict(set)
        for (reg, yr) in g:
            yrs_in_reg[reg].add(yr)
        multi = sorted(r for r, v in yrs_in_reg.items() if len(v) > 1)
        for reg in multi:
            parts = []
            for yr in sorted(yrs_in_reg[reg]):
                rs = g[(reg, yr)]
                parts.append("%d: %+.3f (n=%d)"
                             % (yr, sum(delta(r) for r in rs) / len(rs), len(rs)))
            print("     %-22s %s" % (reg, "   ".join(parts)))
        singles = sorted(r for r, v in yrs_in_reg.items() if len(v) == 1)
        print("     NOT identified for year (single exam year): %s"
              % ", ".join(singles))
        # leave-one-region-out conditional trend
        print("     leave-one-region-out within-region year trend "
              "(two-sided permutation p):")
        full = trend_p(rows, exclude=None)
        print("        all 5 regions: cov=%.2f p=%.5f" % full)
        for reg in multi:
            c, p = trend_p(rows, exclude=reg)
            print("        drop %-22s cov=%8.2f p=%.5f" % (reg, c, p))

    print("\n" + "#" * 100)
    print("(3) EXCLUSION x STRATUM INTERACTION")
    print("#" * 100)
    allr = load("all")
    for f, nm in [("excl_nota_position_a", "91 letter-(a) items"),
                  ("excl_item_defect", "14 adjudicated/out-of-domain items")]:
        print("\n-- %s (%s): share of each stratum's cells that are excluded"
              % (f, nm))
        for sname, keyf in [("year", lambda r: str(r["year"])),
                            ("region", lambda r: r["region"]),
                            ("has_context", lambda r: str(r["has_context"]))]:
            tot = Counter(); exc = Counter()
            for r in allr:
                tot[keyf(r)] += 1
                if r[f]:
                    exc[keyf(r)] += 1
            line = "  ".join("%s=%.2f(%d/%d)" % (k, exc[k] / tot[k], exc[k], tot[k])
                             for k in sorted(tot, key=lambda x: -tot[x]))
            print("     %-12s %s" % (sname, line))
        # heterogeneity of the excluded items' own delta by year
        sub = [r for r in allr if r[f]]
        if sub:
            d = sum(delta(r) for r in sub) / len(sub)
            print("     excluded cells themselves: n=%d, delta=%+.4f "
                  "(vs %+.4f in the retained analysis set)"
                  % (len(sub), d, -0.1555))

    print("\n" + "#" * 100)
    print("(4) POSITION CONTRAST on the unfiltered set: letter (a) vs (b,c,d)")
    print("#" * 100)
    p, Q, est, cnt = hetero(allr, lambda r: "a" if r["correct_letter"] == "a"
                            else "bcd", lambda r: (delta(r), 1), SEED + 777)
    print("   delta(a)   = %+.4f  (n=%d cells)" % (est["a"], cnt["a"]))
    print("   delta(bcd) = %+.4f  (n=%d cells)" % (est["bcd"], cnt["bcd"]))
    print("   difference = %+.4f ; cluster-block permutation p = %.5f"
          % (est["a"] - est["bcd"], p))
    aok = [r for r in allr if r["A_correct"] == 1]
    p2, Q2, e2, c2 = hetero(aok, lambda r: "a" if r["correct_letter"] == "a"
                            else "bcd", lambda r: (r["B_correct"], 1), SEED + 778)
    print("   retention rho(a) = %.4f (n=%d) vs rho(bcd) = %.4f (n=%d); p=%.5f"
          % (e2["a"], c2["a"], e2["bcd"], c2["bcd"], p2))


def trend_p(rows, exclude):
    agg = defaultdict(lambda: [0.0, 0])
    meta = {}
    for r in rows:
        if exclude is not None and r["region"] == exclude:
            continue
        agg[r["cluster"]][0] += delta(r)
        agg[r["cluster"]][1] += 1
        meta[r["cluster"]] = (r["region"], float(r["year"]))
    ks = list(agg)
    S = [agg[k][0] for k in ks]; N = [agg[k][1] for k in ks]
    R = [meta[k][0] for k in ks]; Y = [meta[k][1] for k in ks]
    yr = defaultdict(set)
    for r_, y in zip(R, Y):
        yr[r_].add(y)
    keep = [i for i in range(len(S)) if len(yr[R[i]]) > 1]
    S = [S[i] for i in keep]; N = [N[i] for i in keep]
    R = [R[i] for i in keep]; Y = [Y[i] for i in keep]
    if not S:
        return (float("nan"), float("nan"))

    def stat(years):
        bys = defaultdict(lambda: [0.0, 0.0, 0])
        for s, n, r_, y in zip(S, N, R, years):
            bys[r_][0] += n * y; bys[r_][1] += s; bys[r_][2] += n
        mY = {k: v[0] / v[2] for k, v in bys.items()}
        mD = {k: v[1] / v[2] for k, v in bys.items()}
        return sum((y - mY[r_]) * (s - n * mD[r_])
                   for s, n, r_, y in zip(S, N, R, years))

    obs = stat(Y)
    idx = defaultdict(list)
    for i, r_ in enumerate(R):
        idx[r_].append(i)
    rnd = random.Random(SEED + 31)
    perm = list(Y)
    cnt = 0
    for _ in range(B_PERM):
        for ix in idx.values():
            v = [Y[i] for i in ix]
            rnd.shuffle(v)
            for i, x in zip(ix, v):
                perm[i] = x
        if abs(stat(perm)) >= abs(obs) - 1e-9:
            cnt += 1
    return (obs, (cnt + 1) / (B_PERM + 1))


if __name__ == "__main__":
    main()

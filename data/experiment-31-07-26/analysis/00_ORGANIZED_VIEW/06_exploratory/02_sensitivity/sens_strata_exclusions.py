"""Do the strata conclusions survive the two contested exclusions?
Plus two extra stratifiers outside the pre-specified family of six:
  - model            (4 levels; perfectly balanced across items, so unconfounded)
  - correct_letter   (a/b/c/d; on the unfiltered set 'a' IS the construction
                      defect, so this doubles as a validation of exclusion (2))
Plus a monotone YEAR-TREND test (more powerful than the omnibus Q if the year
effect is a gradient), conditioned on region.
"""
import bisect
import random
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/"
                   "tier1_mcq/data/experiment-31-07-26/analysis")
from sens_strata_lib import (load, stratifiers, delta, stratum_table,  # noqa
                             qlen_tertile_map, holm)
from sens_strata_hetero import blocks_for, Q_range, cochran_Q  # noqa
from sens_strata_lib import perm_p  # noqa

B_PERM = 20000
SEED = 20260731

SUBSETS = [
    ("analysis", "primary: both exclusions applied (1299 cells)"),
    ("plus_nota_a", "reinstate the 91 letter-(a) items (drop only the 14)"),
    ("plus_defect", "reinstate the 14 adjudicated items (drop only letter-(a))"),
    ("all", "NO exclusions at all (1691 cells)"),
]


def run_family(rows, label):
    strats, cuts = stratifiers(rows)
    n = len(rows)
    A = sum(r["A_correct"] for r in rows) / n
    Bv = sum(r["B_correct"] for r in rows) / n
    print("\n" + "=" * 100)
    print("SUBSET %s : %d cells, %d items, %d clusters | acc(A)=%.4f acc(B)=%.4f "
          "delta=%+.4f" % (label, n, len(set(r["question_id"] for r in rows)),
                           len(set(r["cluster"] for r in rows)), A, Bv, Bv - A))
    print("  qlen tertile cuts: T1<=%d T2 %d-%d T3>%d" % (cuts[0], cuts[0] + 1,
                                                          cuts[1], cuts[1]))
    print("=" * 100)
    ps = {}
    rows_out = []
    for si, (name, key, unit) in enumerate(strats):
        S, N, L, split = blocks_for(rows, key)
        levels = sorted(set(L))
        Qo, Ro, Rob = Q_range(S, N, L, levels, big=40)
        # deterministic seed: str.__hash__ is salted per process, never use it
        rnd = random.Random(SEED + 1000 * si)
        perm = list(L)
        null = []
        for _ in range(B_PERM):
            rnd.shuffle(perm)
            null.append(Q_range(S, N, perm, levels, big=40)[0])
        p = perm_p(Qo, null)
        cq = cochran_Q(rows, key)
        ps[name] = p
        tab = stratum_table(rows, key)
        big = {l: t for l, t in tab.items() if t["n_cells"] >= 40}
        if big:
            mn = min(big, key=lambda l: big[l]["d"])
            mx = max(big, key=lambda l: big[l]["d"])
            span = "%s %+.3f .. %s %+.3f" % (str(mn)[:16], big[mn]["d"],
                                             str(mx)[:16], big[mx]["d"])
        else:
            span = "-"
        rows_out.append((name, len(levels), Qo, p, cq["p"] if cq else float("nan"),
                         cq["I2"] if cq else float("nan"), span))
    hol = holm(ps)
    print("  %-14s %4s %8s %9s %9s %10s %6s  %s"
          % ("stratifier", "K", "permQ", "p", "Holm", "CochranQ p", "I2",
             "range over levels>=40 cells"))
    for name, K, Q, p, cp, i2, span in rows_out:
        print("  %-14s %4d %8.3f %9.5f %9.4f %10.5f %6.3f  %s"
              % (name, K, Q, p, hol[name], cp, i2, span))
    return ps


def extra_stratifier(rows, name, key, unit_is_item=False):
    S, N, L, split = blocks_for(rows, key)
    levels = sorted(set(L))
    Qo, Ro, Rob = Q_range(S, N, L, levels, big=40)
    rnd = random.Random(SEED + 4242)
    perm = list(L)
    null = []
    for _ in range(B_PERM):
        rnd.shuffle(perm)
        null.append(Q_range(S, N, perm, levels, big=40)[0])
    p = perm_p(Qo, null)
    cq = cochran_Q(rows, key)
    tab = stratum_table(rows, key)
    print("  %s : permQ=%.4f p=%.5f | CochranQ p=%.5f I2=%.3f"
          % (name, Qo, p, cq["p"] if cq else float("nan"),
             cq["I2"] if cq else float("nan")))
    for lev in sorted(tab, key=lambda l: tab[l]["d"]):
        t = tab[lev]
        print("      %-26s n=%5d  acc(A)=%.4f acc(B)=%.4f  delta=%+.4f"
              % (str(lev)[:26], t["n_cells"], t["A"], t["B"], t["d"]))
    return p


def model_permutation(rows):
    """Model is crossed with item, so the correct exchangeability unit is the
    MODEL LABEL WITHIN ITEM: permute which of the 4 model labels each of an
    item's 4 cells carries. This conditions out every item/cluster/exam effect."""
    byit = defaultdict(list)
    for r in rows:
        byit[r["question_id"]].append(r)
    models = sorted(set(r["model"] for r in rows))

    def stat(assign):
        ss = defaultdict(float)
        nn = defaultdict(int)
        for qid, rs in byit.items():
            for r, m in zip(rs, assign[qid]):
                ss[m] += delta(r)
                nn[m] += 1
        ds = [ss[m] / nn[m] for m in models if nn[m]]
        tot_s = sum(ss.values())
        tot_n = sum(nn.values())
        Q = sum(ss[m] ** 2 / nn[m] for m in models if nn[m]) - tot_s ** 2 / tot_n
        return Q, max(ds) - min(ds)

    obs_assign = {q: [r["model"] for r in rs] for q, rs in byit.items()}
    Qo, Ro = stat(obs_assign)
    rnd = random.Random(SEED + 99)
    null = []
    cur = {q: list(v) for q, v in obs_assign.items()}
    for _ in range(B_PERM // 2):
        for q in cur:
            rnd.shuffle(cur[q])
        null.append(stat(cur)[0])
    p = (sum(1 for v in null if v >= Qo - 1e-12) + 1) / (len(null) + 1)
    print("  within-item model permutation (conditions out item/cluster/exam): "
          "Q=%.4f  p=%.5f  range=%.4f  (B=%d)" % (Qo, p, Ro, len(null)))
    return p


def year_trend(rows):
    """Monotone trend of the delta in calendar year, conditioned on region
    (only regions spanning >=2 years contribute). Statistic = within-region
    centred covariance between year and block delta; permutation within region."""
    agg = defaultdict(lambda: [0.0, 0])
    meta = {}
    for r in rows:
        k = (r["cluster"],)
        agg[k][0] += delta(r)
        agg[k][1] += 1
        meta[k] = (r["region"], r["year"])
    ks = list(agg)
    S = [agg[k][0] for k in ks]
    N = [agg[k][1] for k in ks]
    R = [meta[k][0] for k in ks]
    Y = [float(meta[k][1]) for k in ks]
    yr_in_r = defaultdict(set)
    for r_, y in zip(R, Y):
        yr_in_r[r_].add(y)
    keep = [i for i in range(len(S)) if len(yr_in_r[R[i]]) > 1]
    S = [S[i] for i in keep]; N = [N[i] for i in keep]
    R = [R[i] for i in keep]; Y = [Y[i] for i in keep]

    def stat(years):
        # cell-weighted, region-centred covariance of year with delta
        tot = 0.0
        bys = defaultdict(lambda: [0.0, 0.0, 0])  # sum wY, sum wD*, n
        for s, n, r_, y in zip(S, N, R, years):
            bys[r_][0] += n * y
            bys[r_][1] += s
            bys[r_][2] += n
        mY = {r_: v[0] / v[2] for r_, v in bys.items()}
        mD = {r_: v[1] / v[2] for r_, v in bys.items()}
        for s, n, r_, y in zip(S, N, R, years):
            tot += (y - mY[r_]) * (s - n * mD[r_])
        return tot

    obs = stat(Y)
    idx_by_r = defaultdict(list)
    for i, r_ in enumerate(R):
        idx_by_r[r_].append(i)
    rnd = random.Random(SEED + 31)
    perm = list(Y)
    null = []
    for _ in range(B_PERM):
        for ix in idx_by_r.values():
            v = [Y[i] for i in ix]
            rnd.shuffle(v)
            for i, x in zip(ix, v):
                perm[i] = x
        null.append(stat(perm))
    p_two = (sum(1 for v in null if abs(v) >= abs(obs) - 1e-9) + 1) / (B_PERM + 1)
    print("  year LINEAR TREND conditioned on region: %d clusters, %d cells; "
          "cov stat=%.2f  two-sided p=%.5f" % (len(S), sum(N), obs, p_two))
    print("     (positive stat = delta becomes LESS negative in later years)")
    return p_two


def main():
    allp = {}
    for key, lab in SUBSETS:
        rows = load(key)
        allp[key] = run_family(rows, "%s -- %s" % (key, lab))

    print("\n" + "#" * 100)
    print("STABILITY OF THE 6 HETEROGENEITY p-VALUES ACROSS EXCLUSION SETS "
          "(permutation Q)")
    print("#" * 100)
    names = list(allp["analysis"].keys())
    print("  %-14s %12s %12s %12s %12s" % ("stratifier", "analysis",
                                           "plus_nota_a", "plus_defect", "all"))
    for nm in names:
        print("  %-14s %12.5f %12.5f %12.5f %12.5f"
              % (nm, allp["analysis"][nm], allp["plus_nota_a"][nm],
                 allp["plus_defect"][nm], allp["all"][nm]))

    print("\n" + "#" * 100)
    print("EXTRA STRATIFIERS (outside the pre-specified family of 6)")
    print("#" * 100)
    for key in ["analysis", "all"]:
        rows = load(key)
        print("\n-- subset=%s --" % key)
        extra_stratifier(rows, "correct_letter", lambda r: r["correct_letter"])
        print()
        extra_stratifier(rows, "model (block permutation)", lambda r: r["model"])
        model_permutation(rows)

    print("\n" + "#" * 100)
    print("YEAR TREND (the only sub-0.10 signal in the conditional analysis)")
    print("#" * 100)
    for key in ["analysis", "all"]:
        print("-- subset=%s" % key)
        year_trend(load(key))


if __name__ == "__main__":
    main()

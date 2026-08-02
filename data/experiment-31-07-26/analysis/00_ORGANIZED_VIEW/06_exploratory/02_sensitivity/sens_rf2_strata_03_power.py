"""REFUTATION script 03: how much heterogeneity would this design MISS?

A non-rejection only licenses "no heterogeneity" if the test could have seen it.
Three independent lines:

  P1  BIAS-CORRECTED heterogeneity variance tau^2 with a cluster bootstrap CI.
      tau2_naive = sum_k w_k (d_k - dbar)^2   with w_k = n_k/n
      tau2_hat   = tau2_naive - sum_k w_k v_k   (v_k = cluster-robust Var(d_k))
      The UPPER end of the CI is the largest between-level SD the data cannot
      rule out.  Compare it with the observed effect size (-0.155).

  P2  SIMULATED POWER of the block-permutation Q test on the REAL cluster
      structure.  Plant a genuine effect by re-flipping concordant-correct
      cells (A=1,B=1 -> B=0) with probability pi inside a randomly chosen half
      of the levels; this preserves every count and the whole nesting.
      Report power vs the induced delta gap, raw alpha=.05 and Holm(6).

  P3  COLLINEARITY of the six stratifiers (Cramer's V / normalised mutual
      information over clusters).  Six near-duplicated looks are not six
      independent chances to detect heterogeneity.
"""
import json
import math
import random
from collections import defaultdict

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")
SEED = 4242


def d(r):
    return r["B_correct"] - r["A_correct"]


def load():
    with open(DATA) as fh:
        return [r for r in json.load(fh) if r["analysis_include"]]


def tertile(rows):
    per = {r["question_id"]: r["qlen"] for r in rows}
    v = sorted(per.values())
    n = len(v)
    c1, c2 = v[int(round(n / 3.0)) - 1], v[int(round(2 * n / 3.0)) - 1]
    return lambda r: "T1" if r["qlen"] <= c1 else ("T2" if r["qlen"] <= c2
                                                   else "T3")


def strat_list(rows):
    t = tertile(rows)
    return [("region", lambda r: r["region"]),
            ("year", lambda r: str(r["year"])),
            ("exam_part", lambda r: r["exam_part"]),
            ("has_context", lambda r: str(r["has_context"])),
            ("negated_stem", lambda r: str(r["negated_stem"])),
            ("qlen_tertile", t)]


# ------------------------------------------------------------------ P1: tau
def level_stats(rows, keyf):
    g = defaultdict(list)
    for r in rows:
        g[keyf(r)].append(r)
    dk, vk, nk = {}, {}, {}
    for lev, rs in g.items():
        n = len(rs)
        m = sum(d(r) for r in rs) / n
        byc = defaultdict(float)
        for r in rs:
            byc[r["cluster"]] += d(r) - m
        G = len(byc)
        nk[lev] = n
        dk[lev] = m
        vk[lev] = ((G / (G - 1.0)) * sum(x * x for x in byc.values()) / (n * n)
                   if G >= 2 else float("nan"))
    return dk, vk, nk


def tau2(rows, keyf):
    dk, vk, nk = level_stats(rows, keyf)
    tot = sum(nk.values())
    dbar = sum(nk[l] * dk[l] for l in nk) / tot
    naive = sum(nk[l] / tot * (dk[l] - dbar) ** 2 for l in nk)
    noise = sum(nk[l] / tot * vk[l] for l in nk
                if vk[l] == vk[l])          # skip NaN (single-cluster levels)
    return naive, noise, max(0.0, naive - noise), len(nk)


def boot_tau(rows, keyf, B, seed):
    byc = defaultdict(list)
    for r in rows:
        byc[r["cluster"]].append(r)
    cl = list(byc)
    n = len(cl)
    rnd = random.Random(seed)
    out = []
    for _ in range(B):
        rs = []
        for _ in range(n):
            rs.extend(byc[cl[rnd.randrange(n)]])
        try:
            out.append(tau2(rs, keyf)[2])
        except ZeroDivisionError:
            pass
    out.sort()
    return out


# ------------------------------------------------------------- P2: power sim
def Qstat(S, N, labels, levels):
    ss, nn = defaultdict(float), defaultdict(int)
    ts = tn = 0.0
    for s, nv, l in zip(S, N, labels):
        ss[l] += s
        nn[l] += nv
        ts += s
        tn += nv
    Q = -ts * ts / tn
    for l in levels:
        if nn[l]:
            Q += ss[l] * ss[l] / nn[l]
    return Q


def blocks_from(cells, keyf):
    agg = defaultdict(lambda: [0.0, 0])
    lab = {}
    for c in cells:
        k = (c["cluster"], keyf(c))
        agg[k][0] += c["dl"]
        agg[k][1] += 1
        lab[k] = keyf(c)
    ks = list(agg)
    return ([agg[k][0] for k in ks], [agg[k][1] for k in ks],
            [lab[k] for k in ks])


def perm_p_Q(cells, keyf, seed, B):
    S, N, L = blocks_from(cells, keyf)
    levels = sorted(set(L))
    obs = Qstat(S, N, L, levels)
    rnd = random.Random(seed)
    p = list(L)
    ge = 0
    for _ in range(B):
        rnd.shuffle(p)
        if Qstat(S, N, p, levels) >= obs - 1e-12:
            ge += 1
    return (ge + 1) / (B + 1)


def power_sim(rows, keyf, name, pis, n_sim, B_perm, seed):
    """Split the levels into two arms (alternating by descending cell count so
    both arms carry comparable mass), then knock out concordant-correct cells
    in ONE arm with probability pi.  Report achieved delta-gap and power."""
    lv = defaultdict(int)
    for r in rows:
        lv[keyf(r)] += 1
    order = sorted(lv, key=lambda l: -lv[l])
    armA = set(order[0::2])
    base = []
    for r in rows:
        base.append(dict(cluster=r["cluster"], lev=keyf(r), dl=d(r),
                         conc=(r["A_correct"] == 1 and r["B_correct"] == 1),
                         arm=keyf(r) in armA))
    kf = lambda c: c["lev"]
    nA = sum(1 for c in base if c["arm"])
    print("    arms: %d cells in boosted arm, %d in the other (levels split "
          "%d/%d)" % (nA, len(base) - nA, len(armA), len(lv) - len(armA)))
    rnd = random.Random(seed)
    for pi in pis:
        hits = hits_holm = 0
        gaps = []
        for s in range(n_sim):
            cells = []
            for c in base:
                dl = c["dl"]
                if c["arm"] and c["conc"] and rnd.random() < pi:
                    dl = -1
                cells.append(dict(cluster=c["cluster"], lev=c["lev"], dl=dl))
            sa = sn = sb = snb = 0.0
            for c in cells:
                if c["lev"] in armA:
                    sa += c["dl"]
                    sn += 1
                else:
                    sb += c["dl"]
                    snb += 1
            gaps.append(abs(sa / sn - sb / snb))
            p = perm_p_Q(cells, kf, seed + 1000 * s + int(pi * 1e4), B_perm)
            hits += p < 0.05
            hits_holm += p < 0.05 / 6.0
        gaps.sort()
        print("    pi=%.3f  induced |gap| median=%.4f   power(raw .05)=%.2f   "
              "power(Bonf/Holm .05/6)=%.2f"
              % (pi, gaps[len(gaps) // 2], hits / n_sim, hits_holm / n_sim))


# ------------------------------------------------------- P3: collinearity
def cramers_v(rows, k1, k2):
    """Computed over CLUSTERS (the independent unit), using each cluster's
    modal level, so that a 60-cell cluster does not count 60 times."""
    byc = defaultdict(list)
    for r in rows:
        byc[r["cluster"]].append(r)
    pairs = []
    for c, rs in byc.items():
        a = defaultdict(int)
        b = defaultdict(int)
        for r in rs:
            a[k1(r)] += 1
            b[k2(r)] += 1
        pairs.append((max(a, key=a.get), max(b, key=b.get)))
    n = len(pairs)
    tab = defaultdict(int)
    ra = defaultdict(int)
    rb = defaultdict(int)
    for x, y in pairs:
        tab[(x, y)] += 1
        ra[x] += 1
        rb[y] += 1
    chi2 = 0.0
    for x in ra:
        for y in rb:
            e = ra[x] * rb[y] / n
            o = tab.get((x, y), 0)
            chi2 += (o - e) ** 2 / e
    k = min(len(ra), len(rb))
    return math.sqrt(chi2 / (n * (k - 1))) if k > 1 else float("nan")


def main():
    rows = load()
    strats = strat_list(rows)
    n = len(rows)
    dall = sum(d(r) for r in rows) / n

    print("=" * 104)
    print("P1  HOW MUCH BETWEEN-LEVEL HETEROGENEITY IS COMPATIBLE WITH THESE "
          "DATA?  (v2 set, overall delta=%+.4f)" % dall)
    print("=" * 104)
    print("  %-13s %3s %11s %11s %11s %10s %-22s"
          % ("stratifier", "K", "tau2_naive", "samp.noise", "tau2_hat",
             "tau_hat", "95% boot CI for tau"))
    for nm, kf in strats:
        na, no, th, K = tau2(rows, kf)
        bs = boot_tau(rows, kf, 3000, SEED)
        lo = math.sqrt(bs[int(0.025 * len(bs))])
        hi = math.sqrt(bs[min(len(bs) - 1, int(0.975 * len(bs)))])
        print("  %-13s %3d %11.6f %11.6f %11.6f %10.4f  [%.4f, %.4f]"
              % (nm, K, na, no, th, math.sqrt(th), lo, hi))
        print("       -> upper 95%% bound on the between-level SD is %.1f%% of "
              "the overall effect |%.4f|" % (100 * hi / abs(dall), dall))

    print()
    print("=" * 104)
    print("P2  SIMULATED POWER of the block-permutation Q test on the REAL "
          "design")
    print("=" * 104)
    for nm, kf in (("region", strats[0][1]), ("year", strats[1][1])):
        print("  --- %s ---" % nm)
        power_sim(rows, kf, nm, [0.05, 0.10, 0.15, 0.20], 200, 1500,
                  SEED + 7)

    print()
    print("=" * 104)
    print("P3  COLLINEARITY of the six stratifiers (Cramer's V over the 201 "
          "clusters)")
    print("=" * 104)
    names = [s[0] for s in strats]
    print("  %-13s %s" % ("", " ".join("%12s" % x[:12] for x in names)))
    for i, (n1, k1) in enumerate(strats):
        cells = []
        for j, (n2, k2) in enumerate(strats):
            cells.append("%12.3f" % (1.0 if i == j else cramers_v(rows, k1, k2)))
        print("  %-13s %s" % (n1, " ".join(cells)))

    # concentration: how many effectively independent clusters carry each level?
    print()
    print("  Cluster-mass concentration (Kish effective n over cluster sizes):")
    byc = defaultdict(int)
    for r in rows:
        byc[r["cluster"]] += 1
    sz = list(byc.values())
    kish = sum(sz) ** 2 / sum(s * s for s in sz)
    print("    %d clusters, %d cells; Kish effective #clusters = %.1f "
          "(largest cluster = %d cells = %.1f%% of the data)"
          % (len(sz), sum(sz), kish, max(sz), 100 * max(sz) / sum(sz)))


if __name__ == "__main__":
    main()

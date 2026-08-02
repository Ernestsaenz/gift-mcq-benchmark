"""REFUTATION script 02: independent permutation heterogeneity tests.

Re-implements the Q test from scratch and adds tests the original omitted:
  T1  block-permutation Q            (their test, my code, v1 and v2 sets)
  T2  WITHIN-CLUSTER permutation Q   (correct null for item-level stratifiers:
                                      negated_stem, qlen_tertile -- restricted
                                      exchangeability, strictly more powerful)
  T3  ORDERED trend test for the two ordinal stratifiers (year, qlen_tertile):
      cluster-weighted linear contrast, block permutation
  T4  exam_part after a PRE-SPECIFIABLE coarsening into 5 families
      (singleton levels destroy the omnibus df budget)
  T5  positive control: same machinery applied to `model`, a covariate known
      to be heterogeneous, to show whether the machinery has any power at all.
Multiplicity: Holm + Westfall-Young min-P over the family of 6.
"""
import bisect
import json
import random
from collections import defaultdict

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")
META = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/dataset_meta.json")
B_PERM = 20000
SEED = 90210


def d(r):
    return r["B_correct"] - r["A_correct"]


def load(which):
    with open(DATA) as fh:
        rows = json.load(fh)
    if which == "v2":
        return [r for r in rows if r["analysis_include"]]
    if which == "v1":
        with open(META) as fh:
            m = json.load(fh)
        added8 = {"b213", "b293", "b361", "b396", "b407", "b433", "b445",
                  "b451"}
        bad = ({q for q in m["exclusions"]["out_of_domain_law"]
                if q not in added8}
               | set(m["exclusions"]["adjudicated_key_defect"]))
        return [r for r in rows if r["question_id"] not in bad
                and not r["excl_nota_position_a"]]
    raise ValueError(which)


def tertile(rows):
    per = {r["question_id"]: r["qlen"] for r in rows}
    v = sorted(per.values())
    n = len(v)
    c1 = v[int(round(n / 3.0)) - 1]
    c2 = v[int(round(2 * n / 3.0)) - 1]
    return lambda r: "T1" if r["qlen"] <= c1 else ("T2" if r["qlen"] <= c2
                                                   else "T3")


EXAM_FAMILY = [
    ("main", lambda s: s.startswith("main")),
    ("reserva", lambda s: s.startswith("reserva")),
    ("caso", lambda s: s.startswith("caso")),
    ("cuestionario", lambda s: s.startswith("cuestionario")),
    ("teorico-practica", lambda s: s == "teorico-practica"),
]


def exam_family(r):
    s = r["exam_part"]
    for nm, f in EXAM_FAMILY:
        if f(s):
            return nm
    return "other"


def strat_list(rows):
    t = tertile(rows)
    return [
        ("region", lambda r: r["region"], "cluster"),
        ("year", lambda r: str(r["year"]), "cluster"),
        ("exam_part", lambda r: r["exam_part"], "cluster"),
        ("has_context", lambda r: str(r["has_context"]), "cluster"),
        ("negated_stem", lambda r: str(r["negated_stem"]), "item"),
        ("qlen_tertile", t, "item"),
    ]


# --------------------------------------------------------------- Q machinery
def Qstat(S, N, labels, levels):
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
    for l in levels:
        if nn[l]:
            Q += ss[l] * ss[l] / nn[l]
    return Q


def blocks(rows, keyf):
    """(cluster, level) blocks: maximal covariate-homogeneous cluster subsets."""
    agg = defaultdict(lambda: [0.0, 0])
    lab = {}
    for r in rows:
        k = (r["cluster"], keyf(r))
        agg[k][0] += d(r)
        agg[k][1] += 1
        lab[k] = keyf(r)
    ks = list(agg)
    cl = defaultdict(list)
    for c, _ in ks:
        cl[c].append(1)
    return ([agg[k][0] for k in ks], [agg[k][1] for k in ks],
            [lab[k] for k in ks], [k[0] for k in ks],
            sum(1 for c, v in cl.items() if len(v) > 1))


def perm_Q_free(S, N, L, seed, B=B_PERM):
    """Unrestricted label permutation across blocks (the original's null)."""
    levels = sorted(set(L))
    obs = Qstat(S, N, L, levels)
    rnd = random.Random(seed)
    p = list(L)
    null = []
    for _ in range(B):
        rnd.shuffle(p)
        null.append(Qstat(S, N, p, levels))
    return obs, null


def perm_Q_within_item(rows, keyf, seed, B=B_PERM):
    """RESTRICTED null for a stratifier that varies WITHIN clusters: permute
    the item-level label only among items of the SAME cluster.  Preserves each
    cluster's label composition, removes all between-cluster nuisance variance.
    Strictly more powerful than free permutation when the covariate is nested."""
    it = {}
    for r in rows:
        q = r["question_id"]
        if q not in it:
            it[q] = [0.0, 0, keyf(r), r["cluster"]]
        it[q][0] += d(r)
        it[q][1] += 1
    keys = list(it)
    S = [it[k][0] for k in keys]
    N = [it[k][1] for k in keys]
    L = [it[k][2] for k in keys]
    C = [it[k][3] for k in keys]
    levels = sorted(set(L))
    obs = Qstat(S, N, L, levels)
    idx = defaultdict(list)
    for i, c in enumerate(C):
        idx[c].append(i)
    groups = [v for v in idx.values() if len(v) > 1]
    rnd = random.Random(seed)
    p = list(L)
    null = []
    for _ in range(B):
        for g in groups:
            sub = [p[i] for i in g]
            rnd.shuffle(sub)
            for i, v in zip(g, sub):
                p[i] = v
        null.append(Qstat(S, N, p, levels))
    n_free = sum(len(g) for g in groups)
    return obs, null, len(keys), n_free, len(groups)


def perm_trend(S, N, L, score, seed, B=B_PERM):
    """Ordered alternative: T = sum_k n_k * (score_k - sbar) * d_k, i.e. the
    size-weighted covariance between the ordinal score and the cell delta.
    Two-sided p from |T| under the same block-exchangeable null."""
    def stat(labs):
        ss = defaultdict(float)
        nn = defaultdict(int)
        for s, n, l in zip(S, N, labs):
            ss[l] += s
            nn[l] += n
        tot = sum(nn.values())
        sbar = sum(nn[l] * score[l] for l in nn) / tot
        return sum(nn[l] * (score[l] - sbar) * (ss[l] / nn[l])
                   for l in nn if nn[l])
    obs = stat(L)
    rnd = random.Random(seed)
    p = list(L)
    null = []
    for _ in range(B):
        rnd.shuffle(p)
        null.append(stat(p))
    return obs, null


def pval_ge(obs, null):
    return (sum(1 for v in null if v >= obs - 1e-12) + 1) / (len(null) + 1)


def pval_abs(obs, null):
    a = abs(obs)
    return (sum(1 for v in null if abs(v) >= a - 1e-12) + 1) / (len(null) + 1)


def holm(pv):
    it = sorted(pv.items(), key=lambda kv: kv[1])
    m = len(it)
    run = 0.0
    out = {}
    for i, (k, p) in enumerate(it):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = run
    return out


def westfall_young(nulls, pobs):
    names = list(nulls)
    B = min(len(nulls[n]) for n in names)
    cols = {}
    for nm in names:
        srt = sorted(nulls[nm])
        Bn = len(srt)
        cols[nm] = [(Bn - bisect.bisect_left(srt, v - 1e-12) + 1) / (Bn + 1)
                    for v in nulls[nm][:B]]
    minp = sorted(min(cols[nm][b] for nm in names) for b in range(B))
    return {nm: (bisect.bisect_right(minp, pobs[nm] + 1e-12) + 1) / (B + 1)
            for nm in names}


def deltas_by(rows, keyf):
    ss = defaultdict(float)
    nn = defaultdict(int)
    for r in rows:
        ss[keyf(r)] += d(r)
        nn[keyf(r)] += 1
    return {l: ss[l] / nn[l] for l in nn}, dict(nn)


# ------------------------------------------------------------------ main
def main():
    for vint in ("v2", "v1"):
        rows = load(vint)
        strats = strat_list(rows)
        print("#" * 104)
        print("PERMUTATION HETEROGENEITY  vintage=%s  cells=%d items=%d "
              "clusters=%d" % (vint, len(rows),
                               len({r["question_id"] for r in rows}),
                               len({r["cluster"] for r in rows})))
        print("#" * 104)
        nulls = {}
        pobs = {}
        for nm, kf, unit in strats:
            S, N, L, C, split = blocks(rows, kf)
            obs, null = perm_Q_free(S, N, L, SEED + 17 * len(nm))
            nulls[nm] = null
            pobs[nm] = pval_ge(obs, null)
            dd, nn = deltas_by(rows, kf)
            rng = max(dd.values()) - min(dd.values())
            print("  %-13s K=%2d blocks=%3d split=%2d  Q=%8.4f  p=%.5f   "
                  "range(delta)=%.4f" % (nm, len(set(L)), len(S), split, obs,
                                         pobs[nm], rng))
        h = holm(pobs)
        wy = westfall_young(nulls, pobs)
        print("  %-13s %10s %10s %10s" % ("", "raw p", "Holm", "WY min-P"))
        for nm, _, _ in strats:
            print("  %-13s %10.5f %10.4f %10.4f" % (nm, pobs[nm], h[nm], wy[nm]))
        print()

    # ------------------------------------------------ everything else on v2
    rows = load("v2")
    strats = strat_list(rows)
    print("#" * 104)
    print("T2  WITHIN-CLUSTER (restricted) permutation for item-level "
          "stratifiers -- v2 set")
    print("#" * 104)
    for nm, kf, unit in strats:
        if unit != "item":
            continue
        obs, null, nit, nfree, ngrp = perm_Q_within_item(rows, kf, SEED + 5)
        print("  %-13s Q=%8.4f  p=%.5f   [%d items, %d permutable inside %d "
              "multi-item clusters]" % (nm, obs, pval_ge(obs, null), nit,
                                        nfree, ngrp))
    # region/year/exam_part are cluster-constant -> no within-cluster freedom
    for nm, kf, unit in strats:
        if unit == "item":
            continue
        S, N, L, C, split = blocks(rows, kf)
        print("  %-13s cluster-constant: %d clusters split by it -> no "
              "within-cluster permutation possible" % (nm, split))

    print()
    print("#" * 104)
    print("T3  ORDERED / TREND alternatives (v2 set)")
    print("#" * 104)
    yrs = sorted({r["year"] for r in rows})
    S, N, L, C, _ = blocks(rows, lambda r: str(r["year"]))
    sc = {str(y): float(y) for y in yrs}
    obs, null = perm_trend(S, N, L, sc, SEED + 31)
    print("  year, linear-in-calendar-year contrast : T=%+.4f  two-sided "
          "p=%.5f" % (obs, pval_abs(obs, null)))
    sc2 = {str(y): float(i) for i, y in enumerate(yrs)}
    obs2, null2 = perm_trend(S, N, L, sc2, SEED + 32)
    print("  year, linear-in-RANK contrast          : T=%+.4f  two-sided "
          "p=%.5f" % (obs2, pval_abs(obs2, null2)))
    t = tertile(rows)
    S3, N3, L3, C3, _ = blocks(rows, t)
    sc3 = {"T1": 0.0, "T2": 1.0, "T3": 2.0}
    obs3, null3 = perm_trend(S3, N3, L3, sc3, SEED + 33)
    print("  qlen tertile, linear contrast          : T=%+.4f  two-sided "
          "p=%.5f" % (obs3, pval_abs(obs3, null3)))

    print()
    print("#" * 104)
    print("T4  exam_part COARSENED to 5 families (v2 set)")
    print("#" * 104)
    dd, nn = deltas_by(rows, exam_family)
    for l in sorted(dd, key=lambda x: dd[x]):
        print("    %-18s n=%4d  delta=%+.4f" % (l, nn[l], dd[l]))
    S4, N4, L4, C4, sp4 = blocks(rows, exam_family)
    obs4, null4 = perm_Q_free(S4, N4, L4, SEED + 41)
    print("  coarse exam_part Q=%.4f  p=%.5f   (vs K=19 raw p above)"
          % (obs4, pval_ge(obs4, null4)))
    # drop singleton/near-singleton levels from the raw stratifier
    dd19, nn19 = deltas_by(rows, lambda r: r["exam_part"])
    keep = {l for l in nn19 if nn19[l] >= 20}
    sub = [r for r in rows if r["exam_part"] in keep]
    S5, N5, L5, C5, _ = blocks(sub, lambda r: r["exam_part"])
    obs5, null5 = perm_Q_free(S5, N5, L5, SEED + 42)
    print("  exam_part levels with >=20 cells only (K=%d, n=%d): Q=%.4f "
          " p=%.5f" % (len(set(L5)), len(sub), obs5, pval_ge(obs5, null5)))

    print()
    print("#" * 104)
    print("T5  POSITIVE CONTROL -- does this machinery detect anything?")
    print("#" * 104)
    dd, nn = deltas_by(rows, lambda r: r["model"])
    for l in sorted(dd, key=lambda x: dd[x]):
        print("    %-28s n=%4d  delta=%+.4f" % (l, nn[l], dd[l]))
    # model varies WITHIN item: restricted permutation among the 4 cells of an
    # item is the exact analogue of the within-cluster test above.
    itm = defaultdict(list)
    for r in rows:
        itm[r["question_id"]].append(r)
    S6, N6, L6 = [], [], []
    for q, rs in itm.items():
        for r in rs:
            S6.append(d(r))
            N6.append(1)
            L6.append(r["model"])
    levels = sorted(set(L6))
    obs6 = Qstat(S6, N6, L6, levels)
    rnd = random.Random(SEED + 51)
    pos = 0
    idxs = []
    off = 0
    for q, rs in itm.items():
        idxs.append(list(range(off, off + len(rs))))
        off += len(rs)
    p = list(L6)
    null6 = []
    for _ in range(B_PERM):
        for g in idxs:
            s = [p[i] for i in g]
            rnd.shuffle(s)
            for i, v in zip(g, s):
                p[i] = v
        null6.append(Qstat(S6, N6, p, levels))
    print("  model (within-item permutation): Q=%.4f  p=%.5f"
          % (obs6, pval_ge(obs6, null6)))


if __name__ == "__main__":
    main()

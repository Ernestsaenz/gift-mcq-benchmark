"""Confound-broken (conditional) heterogeneity tests + detectability floor.

WHY
---
region, year, exam_part and has_context are near-collinear with EXAM BLOCKS
(region x year x exam_part). A marginal "region effect" is therefore not
identified separately from "that one exam was harder". The conditional tests
below only use variation that exists *inside* a conditioning stratum, so the
exam-block effect is differenced out:

   Q_cond = sum_g [ sum_k S_gk^2/n_gk  -  S_g^2/n_g ]

   g = conditioning stratum (e.g. region), k = level (e.g. year).
Null: level labels are exchangeable among permutation blocks WITHIN g. Only
conditioning strata that contain >=2 distinct levels contribute; everything else
is silently differenced away (and reported).

DETECTABILITY FLOOR
-------------------
For each (unconditional) stratification we report the 95th percentile of the
permutation null of the max-min delta range: the smallest between-level spread
that this design could have called significant at alpha=0.05. A null result
above/below that number means very different things.
"""
import bisect
import random
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/"
                   "tier1_mcq/data/experiment-31-07-26/analysis")
from sens_strata_lib import load, stratifiers, delta, qlen_tertile_map  # noqa

B_PERM = 20000
SEED = 20260731


def blocks(rows, key, cond):
    """Permutation blocks = maximal (cluster x level) homogeneous subsets.
    Each block carries its conditioning stratum g (constant by construction when
    cond is coarser than cluster; verified)."""
    agg = defaultdict(lambda: [0.0, 0])
    meta = {}
    for r in rows:
        k = (r["cluster"], key(r), cond(r))
        agg[k][0] += delta(r)
        agg[k][1] += 1
        meta[k] = (key(r), cond(r))
    ks = list(agg)
    return ([agg[k][0] for k in ks], [agg[k][1] for k in ks],
            [meta[k][0] for k in ks], [meta[k][1] for k in ks])


def qcond(S, N, L, G):
    ss = defaultdict(float)
    nn = defaultdict(int)
    gs = defaultdict(float)
    gn = defaultdict(int)
    for s, n, l, g in zip(S, N, L, G):
        ss[(g, l)] += s
        nn[(g, l)] += n
        gs[g] += s
        gn[g] += n
    Q = 0.0
    for kk, n in nn.items():
        if n:
            Q += ss[kk] * ss[kk] / n
    for g, n in gn.items():
        if n:
            Q -= gs[g] * gs[g] / n
    return Q


def cond_test(rows, name, key, cname, cond, seed):
    S, N, L, G = blocks(rows, key, cond)
    # which conditioning strata are informative (>=2 levels present)
    lev_in_g = defaultdict(set)
    cells_in_g = Counter()
    for s, n, l, g in zip(S, N, L, G):
        lev_in_g[g].add(l)
        cells_in_g[g] += n
    good = {g for g, v in lev_in_g.items() if len(v) > 1}
    keep = [i for i in range(len(S)) if G[i] in good]
    if not keep:
        return None
    S = [S[i] for i in keep]
    N = [N[i] for i in keep]
    L = [L[i] for i in keep]
    G = [G[i] for i in keep]
    Qobs = qcond(S, N, L, G)
    # permute WITHIN g
    idx_by_g = defaultdict(list)
    for i, g in enumerate(G):
        idx_by_g[g].append(i)
    rnd = random.Random(seed)
    perm = list(L)
    null = []
    groups = list(idx_by_g.values())
    for _ in range(B_PERM):
        for ix in groups:
            labs = [L[i] for i in ix]
            rnd.shuffle(labs)
            for i, lb in zip(ix, labs):
                perm[i] = lb
        null.append(qcond(S, N, perm, G))
    p = (sum(1 for v in null if v >= Qobs - 1e-12) + 1) / (B_PERM + 1)
    # informative level deltas within the retained subset
    ss = defaultdict(float)
    nn = defaultdict(int)
    for s, n, l in zip(S, N, L):
        ss[l] += s
        nn[l] += n
    ds = {l: ss[l] / nn[l] for l in nn}
    return dict(Q=Qobs, p=p, n_blocks=len(S),
                n_cells=sum(N), n_strata_used=len(good),
                n_strata_total=len(lev_in_g), levels=ds, ncell_level=dict(nn))


def main():
    subset = sys.argv[1] if len(sys.argv) > 1 else "analysis"
    rows = load(subset)
    lab, cuts = qlen_tertile_map(rows)
    print("#" * 100)
    print("CONDITIONAL (CONFOUND-BROKEN) HETEROGENEITY   subset=%s  cells=%d"
          % (subset, len(rows)))
    print("#" * 100)

    exam = lambda r: "%s|%s" % (r["region"], r["year"])
    block = lambda r: "%s|%s|%s" % (r["region"], r["year"], r["exam_part"])
    tests = [
        ("year", lambda r: str(r["year"]), "region", lambda r: r["region"]),
        ("region", lambda r: r["region"], "year", lambda r: str(r["year"])),
        ("exam_part", lambda r: r["exam_part"], "exam(region,year)", exam),
        ("has_context", lambda r: str(r["has_context"]), "region", lambda r: r["region"]),
        ("has_context", lambda r: str(r["has_context"]), "exam(region,year)", exam),
        ("negated_stem", lambda r: str(r["negated_stem"]), "exam block(r,y,p)", block),
        ("qlen_tertile", lambda r: lab(r["qlen"]), "exam block(r,y,p)", block),
        ("negated_stem", lambda r: str(r["negated_stem"]), "cluster", lambda r: str(r["cluster"])),
        ("qlen_tertile", lambda r: lab(r["qlen"]), "cluster", lambda r: str(r["cluster"])),
    ]
    for i, (nm, key, cnm, cond) in enumerate(tests):
        res = cond_test(rows, nm, key, cnm, cond, SEED + 100 * i)
        print("\n--- %s  |  conditioned on %s ---" % (nm, cnm))
        if res is None:
            print("    NOT IDENTIFIED: no conditioning stratum contains >1 level.")
            continue
        print("    informative conditioning strata: %d of %d ; retained %d cells "
              "in %d permutation blocks"
              % (res["n_strata_used"], res["n_strata_total"], res["n_cells"],
                 res["n_blocks"]))
        for l in sorted(res["levels"], key=lambda x: res["levels"][x]):
            print("       %-26s d=%+.4f  (n=%d cells retained)"
                  % (str(l)[:26], res["levels"][l], res["ncell_level"][l]))
        print("    conditional permutation Q = %.4f   p = %.5f  (B=%d, labels "
              "shuffled only within conditioning stratum)"
              % (res["Q"], res["p"], B_PERM))

    # ------------------------------------------------ detectability floor
    print("\n" + "#" * 100)
    print("DETECTABILITY FLOOR: null 95th pct of the max-min delta range")
    print("(levels with >=40 cells; a design cannot 'find' heterogeneity smaller "
          "than this at alpha=.05)")
    print("#" * 100)
    strats, _ = stratifiers(rows)
    print("  %-14s %10s %10s %12s" % ("stratifier", "obs range", "null p95",
                                      "obs/floor"))
    for name, key, unit in strats:
        agg = defaultdict(lambda: [0.0, 0])
        for r in rows:
            k = (r["cluster"], key(r))
            agg[k][0] += delta(r)
            agg[k][1] += 1
        ks = list(agg)
        S = [agg[k][0] for k in ks]
        N = [agg[k][1] for k in ks]
        L = [k[1] for k in ks]
        levels = sorted(set(L))

        def rng(labels):
            ss = defaultdict(float)
            nn = defaultdict(int)
            for s, n, l in zip(S, N, labels):
                ss[l] += s
                nn[l] += n
            ds = [ss[l] / nn[l] for l in levels if nn[l] >= 40]
            return (max(ds) - min(ds)) if len(ds) > 1 else 0.0

        obs = rng(L)
        rnd = random.Random(SEED + 5)
        perm = list(L)
        null = []
        for _ in range(B_PERM):
            rnd.shuffle(perm)
            null.append(rng(perm))
        null.sort()
        p95 = null[int(0.95 * len(null))]
        print("  %-14s %10.4f %10.4f %12.2f"
              % (name, obs, p95, obs / p95 if p95 else float("nan")))

    # ------------------------------------------------ sign consistency
    print("\n" + "#" * 100)
    print("SIGN CONSISTENCY OF THE A->B DELTA ACROSS LEVELS")
    print("#" * 100)
    for name, key, unit in strats:
        g = defaultdict(list)
        for r in rows:
            g[key(r)].append(r)
        neg = zer = pos = 0
        neg40 = tot40 = 0
        for l, rs in g.items():
            d = sum(delta(r) for r in rs) / len(rs)
            if d < 0:
                neg += 1
            elif d > 0:
                pos += 1
            else:
                zer += 1
            if len(rs) >= 40:
                tot40 += 1
                if d < 0:
                    neg40 += 1
        print("  %-14s all levels: %d neg / %d zero / %d pos ; "
              "levels>=40 cells: %d/%d negative"
              % (name, neg, zer, pos, neg40, tot40))


if __name__ == "__main__":
    main()

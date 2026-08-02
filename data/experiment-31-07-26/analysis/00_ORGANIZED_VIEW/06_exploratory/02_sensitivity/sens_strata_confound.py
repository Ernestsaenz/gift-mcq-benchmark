"""Confounding diagnostics: how far is each stratifier from being a relabelling
of a single exam block?

Exam = (region, year). Block = (region, year, exam_part).
Reported for each stratifier level: the exams it touches, and the share of its
cells that come from its single largest exam ("purity"). Purity ~1.0 means the
level IS one exam and the 'effect of the stratifier' is unidentifiable from an
exam effect.
"""
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/"
                   "tier1_mcq/data/experiment-31-07-26/analysis")
from sens_strata_lib import load, stratifiers  # noqa: E402


def cramers_v(pairs):
    """Cramer's V for a 2-way table given a list of (a,b) observations."""
    t = Counter(pairs)
    ra = Counter(a for a, b in pairs)
    rb = Counter(b for a, b in pairs)
    n = len(pairs)
    chi2 = 0.0
    for a in ra:
        for b in rb:
            e = ra[a] * rb[b] / n
            o = t.get((a, b), 0)
            chi2 += (o - e) ** 2 / e
    k = min(len(ra), len(rb))
    return math_sqrt(chi2 / (n * (k - 1))) if k > 1 else 0.0


def math_sqrt(x):
    return x ** 0.5


def main():
    rows = load("analysis")
    strats, cuts = stratifiers(rows)
    print("=" * 100)
    print("CONFOUNDING DIAGNOSTICS  (analysis set: %d cells, %d items, %d clusters)"
          % (len(rows), len(set(r["question_id"] for r in rows)),
             len(set(r["cluster"] for r in rows))))
    print("qlen tertile cutpoints (over unique items): <=%d | %d-%d | >%d"
          % (cuts[0], cuts[0] + 1, cuts[1], cuts[1]))
    print("=" * 100)

    # cluster-level association between the design factors
    cl = {}
    for r in rows:
        cl[r["cluster"]] = r
    cvals = list(cl.values())
    print("\nCluster-level Cramer's V between design factors (208 clusters):")
    facs = ["region", "year", "exam_part", "has_context"]
    for i in range(len(facs)):
        for j in range(i + 1, len(facs)):
            v = cramers_v([(str(r[facs[i]]), str(r[facs[j]])) for r in cvals])
            print("   %-12s x %-12s  V = %.3f" % (facs[i], facs[j], v))
    for f in ["negated_stem", "qlen"]:
        pass
    # item-level for the within-cluster-varying factors
    it = {}
    for r in rows:
        it[r["question_id"]] = r
    ivals = list(it.values())
    lab, _ = None, None
    from sens_strata_lib import qlen_tertile_map
    lab, _ = qlen_tertile_map(rows)
    print("\nItem-level Cramer's V vs region / exam block (325 items):")
    for f, fn in [("negated_stem", lambda r: str(r["negated_stem"])),
                  ("qlen_tertile", lambda r: lab(r["qlen"]))]:
        for g, gn in [("region", lambda r: r["region"]),
                      ("exam(reg,yr)", lambda r: "%s|%s" % (r["region"], r["year"])),
                      ("block(r,y,p)", lambda r: "%s|%s|%s" % (r["region"], r["year"], r["exam_part"]))]:
            v = cramers_v([(fn(r), gn(r)) for r in ivals])
            print("   %-12s x %-14s V = %.3f" % (f, g, v))

    print("\n" + "=" * 100)
    print("PER-LEVEL EXAM PURITY")
    print("=" * 100)
    for name, key, unit in strats:
        g = defaultdict(list)
        for r in rows:
            g[key(r)].append(r)
        print("\n--- %s (perm unit: %s) ---" % (name, unit))
        print("   %-28s %6s %6s %6s  %5s  %5s  %s"
              % ("level", "cells", "items", "clust", "exams", "purity", "top exam"))
        for lev in sorted(g, key=lambda l: -len(g[l])):
            rs = g[lev]
            ex = Counter("%s %s" % (r["region"], r["year"]) for r in rs)
            top, topn = ex.most_common(1)[0]
            print("   %-28s %6d %6d %6d  %5d  %5.2f  %s"
                  % (lev[:28], len(rs), len(set(r["question_id"] for r in rs)),
                     len(set(r["cluster"] for r in rs)), len(ex),
                     topn / len(rs), top))

    print("\n" + "=" * 100)
    print("CLUSTER SIZE CONCENTRATION (effective independent units)")
    print("=" * 100)
    cs = Counter()
    for r in rows:
        cs[r["cluster"]] += 1
    sizes = sorted(cs.values(), reverse=True)
    tot = sum(sizes)
    print("   208 clusters, %d cells. Largest 12 clusters hold %d cells (%.1f%%)."
          % (tot, sum(sizes[:12]), 100 * sum(sizes[:12]) / tot))
    print("   size distribution:", dict(Counter(sizes)))
    # Kish effective n on cluster sizes
    eff = tot ** 2 / sum(s * s for s in sizes)
    print("   Kish effective number of clusters (n^2 / sum n_k^2) = %.1f "
          "of 208" % eff)


if __name__ == "__main__":
    main()

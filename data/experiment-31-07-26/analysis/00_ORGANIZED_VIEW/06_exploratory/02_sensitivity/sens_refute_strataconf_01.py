"""INDEPENDENT recomputation of the 'strata-robustness' confounding claim.

Everything is rebuilt from paired_clean.json alone (no sens_strata_lib import),
so nothing is inherited from the script under audit.

Exam   = (region, year)          Block = (region, year, exam_part)
Purity = share of a level's CELLS coming from its single largest exam.
Cramer's V = sqrt(chi2 / (n * (k-1))),  k = min(#rows, #cols).
Kish n_eff = (sum n_k)^2 / sum n_k^2.
"""
import json
from collections import Counter, defaultdict

P = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
     "experiment-31-07-26/analysis/paired_clean.json")


def load(which="analysis"):
    rows = json.load(open(P))
    if which == "analysis":
        return [r for r in rows if r["analysis_include"]]
    if which == "all":
        return rows
    if which == "no_defect_only":          # keep nota-a, drop only defects
        return [r for r in rows if not r["excl_item_defect"]]
    if which == "no_nota_only":            # keep defects, drop only nota-a
        return [r for r in rows if not r["excl_nota_position_a"]]
    raise ValueError(which)


def cramers_v(pairs):
    t = Counter(pairs)
    ra = Counter(a for a, _ in pairs)
    rb = Counter(b for _, b in pairs)
    n = len(pairs)
    chi2 = 0.0
    for a, na in ra.items():
        for b, nb in rb.items():
            e = na * nb / n
            chi2 += (t.get((a, b), 0) - e) ** 2 / e
    k = min(len(ra), len(rb))
    return (chi2 / (n * (k - 1))) ** 0.5 if k > 1 else 0.0


def theil_u(pairs):
    """U(y|x): fraction of H(y) explained by x. 1.0 == x determines y."""
    import math
    n = len(pairs)
    py = Counter(b for _, b in pairs)
    hy = -sum(c / n * math.log(c / n) for c in py.values())
    if hy == 0:
        return 1.0
    px = Counter(a for a, _ in pairs)
    hyx = 0.0
    for x, nx in px.items():
        sub = Counter(b for a, b in pairs if a == x)
        h = -sum(c / nx * math.log(c / nx) for c in sub.values())
        hyx += nx / n * h
    return (hy - hyx) / hy


def qlen_tertiles(rows):
    """Tertile cutpoints over UNIQUE ITEMS (each item counted once)."""
    lens = sorted({r["question_id"]: r["qlen"] for r in rows}.values())
    n = len(lens)
    c1 = lens[n // 3]
    c2 = lens[2 * n // 3]
    # cut so that T1 <= c1, T2 in (c1, c2], T3 > c2 -- mirror of the usual
    def lab(q):
        return "T1" if q <= c1 else ("T2" if q <= c2 else "T3")
    return lab, c1, c2


def section(t):
    print("\n" + "=" * 92)
    print(t)
    print("=" * 92)


def main():
    rows = load("analysis")
    items = {r["question_id"]: r for r in rows}
    clus = {r["cluster"]: r for r in rows}
    ncell, nitem, nclu = len(rows), len(items), len(clus)
    print("analysis set: %d cells / %d items / %d clusters" % (ncell, nitem, nclu))

    # ---- 0. are the 'design factors' actually constant within cluster? ----
    section("0. WITHIN-CLUSTER CONSTANCY OF EACH FACTOR (the claim's premise)")
    bycl = defaultdict(list)
    for r in rows:
        bycl[r["cluster"]].append(r)
    for f in ["region", "year", "exam_part", "has_context", "negated_stem",
              "correct_letter"]:
        bad = [c for c, rs in bycl.items() if len({str(r[f]) for r in rs}) > 1]
        print("   %-14s constant in %d/%d clusters   (varies in %d)"
              % (f, nclu - len(bad), nclu, len(bad)))
    qv = [c for c, rs in bycl.items() if len({r["qlen"] for r in rs}) > 1]
    print("   %-14s constant in %d/%d clusters" % ("qlen", nclu - len(qv), nclu))

    # ---- 1. exams and regions ----
    section("1. EXAM / REGION / YEAR STRUCTURE")
    exams = sorted({(r["region"], r["year"]) for r in rows})
    regions = sorted({r["region"] for r in rows})
    years = sorted({r["year"] for r in rows})
    print("   exams (region,year) = %d ; regions = %d ; years = %d"
          % (len(exams), len(regions), len(years)))
    reg_years = defaultdict(set)
    for r in rows:
        reg_years[r["region"]].add(r["year"])
    single = sorted(g for g, ys in reg_years.items() if len(ys) == 1)
    print("   regions spanning exactly ONE year: %d of %d" % (len(single), len(regions)))
    for g in single:
        print("        - %-24s %s" % (g, sorted(reg_years[g])))
    print("   regions spanning >1 year:")
    for g in regions:
        if len(reg_years[g]) > 1:
            print("        - %-24s %s" % (g, sorted(reg_years[g])))

    def purity(rs):
        ex = Counter((r["region"], r["year"]) for r in rs)
        top, tn = ex.most_common(1)[0]
        return tn / len(rs), top, len(ex)

    print("\n   PURITY by region level (cells | items | clusters | #exams | purity):")
    grp = defaultdict(list)
    for r in rows:
        grp[r["region"]].append(r)
    for lev in sorted(grp, key=lambda l: -len(grp[l])):
        rs = grp[lev]
        p, top, nex = purity(rs)
        print("      %-26s %5d %5d %5d %4d  %.2f  <- %s %s"
              % (lev[:26], len(rs), len({r['question_id'] for r in rs}),
                 len({r['cluster'] for r in rs}), nex, p, top[0][:18], top[1]))

    print("\n   PURITY by year level:")
    grp = defaultdict(list)
    for r in rows:
        grp[r["year"]].append(r)
    for lev in sorted(grp, key=lambda l: -len(grp[l])):
        rs = grp[lev]
        p, top, nex = purity(rs)
        print("      %-26s %5d %5d %5d %4d  %.2f  <- %s %s"
              % (lev, len(rs), len({r['question_id'] for r in rs}),
                 len({r['cluster'] for r in rs}), nex, p, top[0][:18], top[1]))

    # ---- 2. exam_part ----
    section("2. exam_part LEVELS")
    grp = defaultdict(list)
    for r in rows:
        grp[r["exam_part"]].append(r)
    one_clu = 0
    print("   %-22s %5s %5s %5s %5s %6s  %s"
          % ("level", "cells", "items", "clus", "exams", "purity", "has_context"))
    for lev in sorted(grp, key=lambda l: -len(grp[l])):
        rs = grp[lev]
        p, top, nex = purity(rs)
        nc = len({r["cluster"] for r in rs})
        one_clu += (nc == 1)
        hc = sorted({str(r["has_context"]) for r in rs})
        print("   %-22s %5d %5d %5d %5d  %.2f   %s"
              % (lev[:22], len(rs), len({r['question_id'] for r in rs}), nc, nex, p, hc))
    print("\n   exam_part levels = %d ; levels living in exactly ONE cluster = %d"
          % (len(grp), one_clu))

    # exam_part -> has_context determinism, at every unit
    section("3. DOES exam_part DETERMINE has_context?")
    for unit, rs in [("cell", rows), ("item", list(items.values())),
                     ("cluster", list(clus.values()))]:
        pr = [(r["exam_part"], str(r["has_context"])) for r in rs]
        v = cramers_v(pr)
        u = theil_u(pr)
        viol = sum(1 for lev, g in
                   [(l, [b for a, b in pr if a == l]) for l in {a for a, _ in pr}]
                   if len(set(g)) > 1)
        print("   unit=%-8s n=%4d  V=%.3f  U(has_context|exam_part)=%.3f  "
              "levels with mixed has_context = %d" % (unit, len(pr), v, u, viol))

    # ---- 4. has_context = True stratum ----
    section("4. has_context STRATA")
    for val in [True, False]:
        rs = [r for r in rows if r["has_context"] is val]
        p, top, nex = purity(rs)
        print("   has_context=%-5s cells=%4d items=%4d clusters=%3d exams=%2d "
              "purity=%.2f  top=%s %s"
              % (val, len(rs), len({r['question_id'] for r in rs}),
                 len({r['cluster'] for r in rs}), nex, p, top[0], top[1]))
        ex = Counter("%s %s" % (r["region"], r["year"]) for r in rs)
        print("        exam breakdown:", ex.most_common())

    # ---- 5. qlen tertiles ----
    section("5. qlen TERTILES (cutpoints over unique items)")
    lab, c1, c2 = qlen_tertiles(rows)
    print("   cutpoints: T1 <= %d ; T2 %d-%d ; T3 > %d" % (c1, c1 + 1, c2, c2))
    grp = defaultdict(list)
    for r in rows:
        grp[lab(r["qlen"])].append(r)
    for lev in ["T1", "T2", "T3"]:
        rs = grp[lev]
        p, top, nex = purity(rs)
        print("   %s cells=%4d items=%4d clusters=%3d exams=%2d purity=%.2f  top=%s %s"
              % (lev, len(rs), len({r['question_id'] for r in rs}),
                 len({r['cluster'] for r in rs}), nex, p, top[0], top[1]))
        ex = Counter("%s %s" % (r["region"], r["year"]) for r in rs)
        print("        exam breakdown:", ex.most_common()[:8])

    # ---- 6. Cramer's V matrices ----
    section("6. CRAMER'S V")
    cvals = list(clus.values())
    facs = ["region", "year", "exam_part", "has_context"]
    print("   CLUSTER level (n=%d):" % len(cvals))
    for i in range(len(facs)):
        for j in range(i + 1, len(facs)):
            v = cramers_v([(str(r[facs[i]]), str(r[facs[j]])) for r in cvals])
            print("      %-12s x %-12s V=%.3f" % (facs[i], facs[j], v))
    ivals = list(items.values())
    print("   ITEM level (n=%d):" % len(ivals))
    gets = [("region", lambda r: r["region"]),
            ("exam(r,y)", lambda r: "%s|%s" % (r["region"], r["year"])),
            ("block(r,y,p)", lambda r: "%s|%s|%s" % (r["region"], r["year"], r["exam_part"])),
            ("cluster", lambda r: str(r["cluster"]))]
    for f, fn in [("negated_stem", lambda r: str(r["negated_stem"])),
                  ("qlen_tertile", lambda r: lab(r["qlen"])),
                  ("has_context", lambda r: str(r["has_context"])),
                  ("correct_letter", lambda r: r["correct_letter"])]:
        for g, gn in gets:
            print("      %-14s x %-14s V=%.3f"
                  % (f, g, cramers_v([(fn(r), gn(r)) for r in ivals])))

    # ---- 7. cluster size concentration ----
    section("7. CLUSTER SIZE CONCENTRATION")
    cs = Counter(r["cluster"] for r in rows)
    sizes = sorted(cs.values(), reverse=True)
    tot = sum(sizes)
    print("   %d clusters, %d cells. top12 = %d cells (%.1f%%)"
          % (len(sizes), tot, sum(sizes[:12]), 100 * sum(sizes[:12]) / tot))
    print("   Kish n_eff = %.1f of %d" % (tot ** 2 / sum(s * s for s in sizes), len(sizes)))
    # same on ITEMS per cluster (design unit is the item, not the cell)
    ci = Counter()
    for q, r in items.items():
        ci[r["cluster"]] += 1
    isz = sorted(ci.values(), reverse=True)
    it = sum(isz)
    print("   ITEM-level: %d items, top12 = %d (%.1f%%), Kish n_eff = %.1f of %d"
          % (it, sum(isz[:12]), 100 * sum(isz[:12]) / it,
             it ** 2 / sum(s * s for s in isz), len(isz)))
    print("   size distribution (cells/cluster):", dict(sorted(Counter(sizes).items())))


if __name__ == "__main__":
    main()

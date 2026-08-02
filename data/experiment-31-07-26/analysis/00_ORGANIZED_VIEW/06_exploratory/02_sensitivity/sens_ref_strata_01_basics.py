"""INDEPENDENT refutation pass #1 for the 'strata-robustness' claim.

Nothing is imported from sens_strata_lib / sens_strata_hetero.  Everything here
is re-derived from paired_clean.json with the stdlib only.

Pass 1 = structural audit + overall numbers + per-level tables + sign audit.
"""
import json
from collections import defaultdict, Counter

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")

ROWS = json.load(open(DATA))


def subset(name):
    if name == "analysis":
        return [r for r in ROWS if r["analysis_include"]]
    if name == "all":
        return list(ROWS)
    if name == "plus_nota_a":     # put the 91 letter-(a) items back
        return [r for r in ROWS if not r["excl_item_defect"]]
    if name == "plus_defect":     # put the 14 adjudicated items back
        return [r for r in ROWS if not r["excl_nota_position_a"]]
    raise ValueError(name)


def d(r):
    return r["B_correct"] - r["A_correct"]


def qlen_tertile_fn(rows):
    per = {}
    for r in rows:
        per[r["question_id"]] = r["qlen"]
    v = sorted(per.values())
    n = len(v)
    c1 = v[int(round(n / 3.0)) - 1]
    c2 = v[int(round(2 * n / 3.0)) - 1]

    def lab(q):
        if q <= c1:
            return "T1"
        if q <= c2:
            return "T2"
        return "T3"
    return lab, (c1, c2)


def strat_defs(rows):
    lab, cuts = qlen_tertile_fn(rows)
    return [("region", lambda r: r["region"]),
            ("year", lambda r: str(r["year"])),
            ("exam_part", lambda r: r["exam_part"]),
            ("has_context", lambda r: str(r["has_context"])),
            ("negated_stem", lambda r: str(r["negated_stem"])),
            ("qlen_tertile", lambda r: lab(r["qlen"]))], cuts


def main():
    print("=" * 96)
    print("STRUCTURAL AUDIT")
    print("=" * 96)
    print("records total          : %d" % len(ROWS))
    for nm in ("analysis", "all", "plus_nota_a", "plus_defect"):
        rs = subset(nm)
        print("  subset %-12s cells=%4d items=%4d clusters=%3d"
              % (nm, len(rs), len(set(r["question_id"] for r in rs)),
                 len(set(r["cluster"] for r in rs))))

    A = subset("analysis")
    # cell completeness
    per_item = Counter(r["question_id"] for r in A)
    incomplete = {q: c for q, c in per_item.items() if c != 4}
    print("\nitems with != 4 model-cells in the analysis set: %d  %s"
          % (len(incomplete), sorted(incomplete.items())[:20]))
    per_item_all = Counter(r["question_id"] for r in ROWS)
    inc_all = {q: c for q, c in per_item_all.items() if c != 4}
    print("items with != 4 model-cells in the FULL file    : %d  %s"
          % (len(inc_all), sorted(inc_all.items())[:20]))
    print("models present: %s" % sorted(set(r["model"] for r in ROWS)))
    mc = Counter(r["model"] for r in A)
    print("cells per model (analysis): %s" % dict(sorted(mc.items())))

    # exclusion bookkeeping
    ex_def = set(r["question_id"] for r in ROWS if r["excl_item_defect"])
    ex_a = set(r["question_id"] for r in ROWS if r["excl_nota_position_a"])
    print("\nexcl_item_defect items      : %d  %s" % (len(ex_def), sorted(ex_def)))
    print("excl_nota_position_a items  : %d (overlap with defect: %d)"
          % (len(ex_a), len(ex_a & ex_def)))
    bad = [r for r in ROWS
           if r["analysis_include"] != (not r["excl_item_defect"]
                                        and not r["excl_nota_position_a"])]
    print("rows where analysis_include != NOT(defect or nota_a): %d" % len(bad))
    # is excl_nota_position_a exactly correct_letter=='a'?
    mism = [r["question_id"] for r in ROWS
            if r["excl_nota_position_a"] != (r["correct_letter"] == "a")]
    print("rows where excl_nota_position_a != (correct_letter=='a'): %d"
          % len(mism))

    # ---- overall
    print("\n" + "=" * 96)
    print("OVERALL (analysis set)")
    print("=" * 96)
    n = len(A)
    a = sum(r["A_correct"] for r in A)
    b = sum(r["B_correct"] for r in A)
    n10 = sum(1 for r in A if r["A_correct"] == 1 and r["B_correct"] == 0)
    n01 = sum(1 for r in A if r["A_correct"] == 0 and r["B_correct"] == 1)
    print("cells=%d  acc(A)=%.4f acc(B)=%.4f delta=%+.4f  n10=%d n01=%d  "
          "(n10-n01)/n=%+.4f" % (n, a / n, b / n, (b - a) / n, n10, n01,
                                 -(n10 - n01) / n))

    strats, cuts = strat_defs(A)
    print("\nqlen tertile cutpoints (unique items): c1=%d c2=%d" % cuts)

    # ---- cluster-homogeneity of each stratifier
    print("\n" + "=" * 96)
    print("BLOCK STRUCTURE: how many clusters are split by each stratifier")
    print("=" * 96)
    for nm, key in strats:
        byc = defaultdict(set)
        for r in A:
            byc[r["cluster"]].add(key(r))
        split = sum(1 for v in byc.values() if len(v) > 1)
        nblocks = sum(len(v) for v in byc.values())
        print("  %-13s levels=%2d  clusters_split=%3d  blocks=%3d"
              % (nm, len(set(key(r) for r in A)), split, nblocks))

    # ---- per-level tables + SIGN AUDIT
    print("\n" + "=" * 96)
    print("PER-LEVEL DELTAS AND SIGN AUDIT (analysis set)")
    print("=" * 96)
    sign_summary = {}
    for nm, key in strats:
        g = defaultdict(list)
        for r in A:
            g[key(r)].append(r)
        neg = pos = zero = 0
        print("\n-- %s" % nm)
        print("   %-30s %6s %5s %5s %8s %8s %9s %5s %5s"
              % ("level", "cells", "items", "clus", "accA", "accB", "delta",
                 "n10", "n01"))
        for lev in sorted(g, key=lambda l: sum(d(r) for r in g[l]) / len(g[l])):
            rs = g[lev]
            nn = len(rs)
            aa = sum(r["A_correct"] for r in rs) / nn
            bb = sum(r["B_correct"] for r in rs) / nn
            dd = bb - aa
            t10 = sum(1 for r in rs if r["A_correct"] == 1 and r["B_correct"] == 0)
            t01 = sum(1 for r in rs if r["A_correct"] == 0 and r["B_correct"] == 1)
            if dd < -1e-12:
                neg += 1
            elif dd > 1e-12:
                pos += 1
            else:
                zero += 1
            print("   %-30s %6d %5d %5d %8.4f %8.4f %+9.4f %5d %5d"
                  % (str(lev)[:30], nn, len(set(r["question_id"] for r in rs)),
                     len(set(r["cluster"] for r in rs)), aa, bb, dd, t10, t01))
        sign_summary[nm] = (neg, zero, pos, len(g))
        print("   SIGNS: %d negative, %d exactly zero, %d POSITIVE  (of %d levels)"
              % (neg, zero, pos, len(g)))

    print("\n" + "=" * 96)
    print("SIGN SUMMARY")
    print("=" * 96)
    for nm, (neg, zero, pos, K) in sign_summary.items():
        flag = "" if (zero == 0 and pos == 0) else "   <-- NOT all-negative"
        print("  %-13s %2d/%2d negative, %d zero, %d positive%s"
              % (nm, neg, K, zero, pos, flag))

    # ---- model stratifier (NOT in the family of six) for context
    print("\n-- model (not one of the six 'requested' stratifiers)")
    g = defaultdict(list)
    for r in A:
        g[r["model"]].append(r)
    for lev in sorted(g, key=lambda l: sum(d(r) for r in g[l]) / len(g[l])):
        rs = g[lev]
        nn = len(rs)
        aa = sum(r["A_correct"] for r in rs) / nn
        bb = sum(r["B_correct"] for r in rs) / nn
        print("   %-30s %6d %8.4f %8.4f %+9.4f" % (lev, nn, aa, bb, bb - aa))


if __name__ == "__main__":
    main()

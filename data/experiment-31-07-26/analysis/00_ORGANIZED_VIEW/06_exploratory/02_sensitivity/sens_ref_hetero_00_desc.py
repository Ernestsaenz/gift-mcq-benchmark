"""REFUTATION pass 0: independent descriptive reconstruction of the strata claim.

Nothing imported from sens_strata_lib.py -- everything re-derived from the raw
JSON so that a bug there cannot propagate into here.
"""
import json
from collections import defaultdict, Counter

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")


def load(subset):
    rows = json.load(open(DATA))
    if subset == "analysis":
        return [r for r in rows if r["analysis_include"]]
    if subset == "all":
        return rows
    if subset == "plus_nota_a":      # reinstate the 91 letter-(a) items
        return [r for r in rows if not r["excl_item_defect"]]
    if subset == "plus_defect":      # reinstate the adjudicated/out-of-domain items
        return [r for r in rows if not r["excl_nota_position_a"]]
    raise ValueError(subset)


def qlen_tertile(rows, mode="item"):
    """Tertile labels. mode='item' -> cutpoints over unique items (as claimed);
    mode='cell' -> over cells."""
    if mode == "item":
        per = {}
        for r in rows:
            per[r["question_id"]] = r["qlen"]
        vals = sorted(per.values())
    else:
        vals = sorted(r["qlen"] for r in rows)
    n = len(vals)
    c1 = vals[int(round(n / 3.0)) - 1]
    c2 = vals[int(round(2 * n / 3.0)) - 1]

    def lab(q):
        if q <= c1:
            return "T1"
        if q <= c2:
            return "T2"
        return "T3"
    return lab, (c1, c2)


def stratifiers(rows):
    lab, cuts = qlen_tertile(rows)
    return [
        ("region", lambda r: r["region"]),
        ("year", lambda r: str(r["year"])),
        ("exam_part", lambda r: r["exam_part"]),
        ("has_context", lambda r: str(r["has_context"])),
        ("negated_stem", lambda r: str(r["negated_stem"])),
        ("qlen_tertile", lambda r: lab(r["qlen"])),
    ], cuts


def d(r):
    return r["B_correct"] - r["A_correct"]


def main():
    raw = json.load(open(DATA))
    print("=" * 96)
    print("RAW FILE: %d rows, %d items, %d clusters"
          % (len(raw), len(set(r["question_id"] for r in raw)),
             len(set(r["cluster"] for r in raw))))
    print("  excl_item_defect      : %d items / %d rows"
          % (len(set(r["question_id"] for r in raw if r["excl_item_defect"])),
             sum(1 for r in raw if r["excl_item_defect"])))
    print("  excl_nota_position_a  : %d items / %d rows"
          % (len(set(r["question_id"] for r in raw if r["excl_nota_position_a"])),
             sum(1 for r in raw if r["excl_nota_position_a"])))
    print("  analysis_include      : %d rows" % sum(1 for r in raw if r["analysis_include"]))
    # is analysis_include exactly the complement of the two flags?
    bad = [r for r in raw
           if r["analysis_include"] != (not r["excl_item_defect"]
                                        and not r["excl_nota_position_a"])]
    print("  rows where analysis_include != NOT(defect or pos_a): %d" % len(bad))
    print("  per-model row counts (all): %s" % dict(Counter(r["model"] for r in raw)))

    for subset in ("analysis", "plus_nota_a", "plus_defect", "all"):
        rows = load(subset)
        n = len(rows)
        A = sum(r["A_correct"] for r in rows) / n
        Bv = sum(r["B_correct"] for r in rows) / n
        n10 = sum(1 for r in rows if r["A_correct"] and not r["B_correct"])
        n01 = sum(1 for r in rows if not r["A_correct"] and r["B_correct"])
        print("\nSUBSET %-12s cells=%4d items=%3d clusters=%3d "
              "accA=%.4f accB=%.4f delta=%+.4f  n10=%d n01=%d"
              % (subset, n, len(set(r["question_id"] for r in rows)),
                 len(set(r["cluster"] for r in rows)), A, Bv, Bv - A, n10, n01))

    rows = load("analysis")
    strats, cuts = stratifiers(rows)
    print("\nqlen tertile cutpoints (unique items, analysis subset): c1=%d c2=%d"
          % cuts)

    print("\n" + "=" * 96)
    print("SIGN CONSISTENCY CHECK  (analysis subset, current v2 file)")
    print("=" * 96)
    for name, key in strats:
        g = defaultdict(list)
        for r in rows:
            g[key(r)].append(r)
        neg = pos = zero = 0
        detail = []
        for lev, rs in sorted(g.items()):
            dk = sum(d(r) for r in rs) / len(rs)
            if dk < 0:
                neg += 1
            elif dk > 0:
                pos += 1
            else:
                zero += 1
            detail.append((lev, len(rs), len(set(r["question_id"] for r in rs)),
                           len(set(r["cluster"] for r in rs)), dk))
        print("\n%-13s K=%d   negative=%d  zero=%d  POSITIVE=%d"
              % (name, len(g), neg, zero, pos))
        for lev, nc, ni, ncl, dk in sorted(detail, key=lambda t: t[4]):
            flag = ""
            if dk >= 0:
                flag = "   <== NOT DOWN"
            print("    %-28s cells=%4d items=%3d clusters=%3d  delta=%+.4f%s"
                  % (str(lev)[:28], nc, ni, ncl, dk, flag))

    # within-cluster variation of each stratifier (needed to judge the block scheme)
    print("\n" + "=" * 96)
    print("WITHIN-CLUSTER VARIATION OF EACH STRATIFIER (analysis subset)")
    print("=" * 96)
    for name, key in strats:
        bycl = defaultdict(set)
        for r in rows:
            bycl[r["cluster"]].add(key(r))
        mixed = sum(1 for v in bycl.values() if len(v) > 1)
        blocks = sum(len(v) for v in bycl.values())
        print("  %-13s clusters=%d  mixed clusters=%d  blocks=%d"
              % (name, len(bycl), mixed, blocks))


if __name__ == "__main__":
    main()

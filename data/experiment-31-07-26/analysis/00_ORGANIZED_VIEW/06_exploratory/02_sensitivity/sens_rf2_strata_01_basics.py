"""REFUTATION pass on "strata-robustness".  Independent re-implementation.

Nothing is imported from sens_strata_lib / sens_strata_hetero.  Every estimator,
bootstrap and permutation below is written from scratch so that agreement (or
disagreement) with the claim is informative.

Cell = (question_id, model).  delta = B_correct - A_correct in {-1,0,+1}.
d_k   = mean(delta | level k) = acc(B|k) - acc(A|k).

Script 01: counts, exclusion-set reconstruction, overall effect, per-level
tables, and the literal sign-consistency audit.
"""
import json
import random
from collections import defaultdict

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")
META = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/dataset_meta.json")

SEED = 90210


def load_all():
    with open(DATA) as fh:
        return json.load(fh)


def subset(rows, which):
    if which == "analysis":            # v2 shipped set: 22 defect + letter-(a)
        return [r for r in rows if r["analysis_include"]]
    if which == "all":
        return list(rows)
    if which == "keep_nota_a":         # drop defects only
        return [r for r in rows if not r["excl_item_defect"]]
    if which == "keep_defect":         # drop letter-(a) only
        return [r for r in rows if not r["excl_nota_position_a"]]
    if which == "v1":                  # emulate the SUPERSEDED 14-item list
        with open(META) as fh:
            m = json.load(fh)
        v1 = set(m["exclusions"]["out_of_domain_law"][:0])   # placeholder
        return None
    raise ValueError(which)


def d(r):
    return r["B_correct"] - r["A_correct"]


def qlen_tertile_fn(rows):
    """Cutpoints over UNIQUE ITEMS.  Independent implementation: use the
    order statistics at ceil(n/3) and ceil(2n/3) positions."""
    per_item = {}
    for r in rows:
        per_item[r["question_id"]] = r["qlen"]
    v = sorted(per_item.values())
    n = len(v)
    c1 = v[int(round(n / 3.0)) - 1]
    c2 = v[int(round(2 * n / 3.0)) - 1]

    def f(r):
        q = r["qlen"]
        if q <= c1:
            return "T1"
        if q <= c2:
            return "T2"
        return "T3"
    return f, (c1, c2)


def make_strats(rows):
    tert, cuts = qlen_tertile_fn(rows)
    return [
        ("region", lambda r: r["region"]),
        ("year", lambda r: str(r["year"])),
        ("exam_part", lambda r: r["exam_part"]),
        ("has_context", lambda r: str(r["has_context"])),
        ("negated_stem", lambda r: str(r["negated_stem"])),
        ("qlen_tertile", tert),
    ], cuts


# ------------------------------------------------------------------ bootstrap
def cluster_boot_ci(rows, keyf, B, seed, alpha=0.05):
    """Percentile CI for d_k, resampling CLUSTERS with replacement.
    Only per-row precomputed deltas are aggregated, so the duplicate-cluster
    re-grouping hazard flagged in dataset_meta.bootstrap_caveat does not bite."""
    byc = defaultdict(list)
    for r in rows:
        byc[r["cluster"]].append((keyf(r), d(r)))
    cl = list(byc)
    n = len(cl)
    levels = sorted({keyf(r) for r in rows})
    draws = {l: [] for l in levels}
    draws["__ALL__"] = []
    rnd = random.Random(seed)
    for _ in range(B):
        s = defaultdict(float)
        c = defaultdict(int)
        ts = 0.0
        tc = 0
        for _ in range(n):
            for lv, dl in byc[cl[rnd.randrange(n)]]:
                s[lv] += dl
                c[lv] += 1
                ts += dl
                tc += 1
        for l in levels:
            draws[l].append(s[l] / c[l] if c[l] else None)
        draws["__ALL__"].append(ts / tc)
    out = {}
    for l, vs in draws.items():
        vs = sorted(x for x in vs if x is not None)
        if len(vs) < 200:
            out[l] = (None, None, len(vs))
            continue
        out[l] = (vs[int(alpha / 2 * len(vs))],
                  vs[min(len(vs) - 1, int((1 - alpha / 2) * len(vs)))],
                  len(vs))
    return out


def table(rows, keyf):
    g = defaultdict(list)
    for r in rows:
        g[keyf(r)].append(r)
    out = {}
    for lev, rs in g.items():
        n = len(rs)
        a = sum(r["A_correct"] for r in rs)
        b = sum(r["B_correct"] for r in rs)
        n10 = sum(1 for r in rs if r["A_correct"] and not r["B_correct"])
        n01 = sum(1 for r in rs if not r["A_correct"] and r["B_correct"])
        out[lev] = dict(n=n, items=len({r["question_id"] for r in rs}),
                        clus=len({r["cluster"] for r in rs}),
                        A=a / n, B=b / n, dd=(b - a) / n, n10=n10, n01=n01,
                        nA=a)
    return out


def main():
    allrows = load_all()
    with open(META) as fh:
        meta = json.load(fh)

    print("=" * 104)
    print("PROVENANCE CHECK")
    print("=" * 104)
    print("export_version      :", meta["export_version"])
    print("meta counts (v2)    : cells=%d items=%d clusters=%d"
          % (meta["counts"]["ab_cells_analysis"],
             meta["counts"]["ab_items_analysis"],
             meta["counts"]["ab_clusters_analysis"]))
    print("meta superseded v1  : cells=%d items=%d clusters=%d"
          % (meta["superseded_v1_counts"]["ab_cells"],
             meta["superseded_v1_counts"]["ab_items"],
             meta["superseded_v1_counts"]["ab_clusters"]))
    print("defect item list now: %d law + %d adjudicated = %d items"
          % (len(meta["exclusions"]["out_of_domain_law"]),
             len(meta["exclusions"]["adjudicated_key_defect"]),
             len(meta["exclusions"]["out_of_domain_law"])
             + len(meta["exclusions"]["adjudicated_key_defect"])))

    rows = subset(allrows, "analysis")
    print("\nfile as read        : total=%d  analysis_include=%d  items=%d "
          "clusters=%d" % (len(allrows), len(rows),
                           len({r["question_id"] for r in rows}),
                           len({r["cluster"] for r in rows})))
    dfl = {r["question_id"] for r in allrows if r["excl_item_defect"]}
    nta = {r["question_id"] for r in allrows if r["excl_nota_position_a"]}
    print("flagged excl_item_defect items      : %d" % len(dfl))
    print("flagged excl_nota_position_a items  : %d" % len(nta))
    print("overlap (both flags)                : %d" % len(dfl & nta))

    # Rebuild the v1 analysis set: 11 law + 3 adjudicated, per the v1 note.
    law19 = meta["exclusions"]["out_of_domain_law"]
    added8 = {"b213", "b293", "b361", "b396", "b407", "b433", "b445", "b451"}
    law11 = [q for q in law19 if q not in added8]
    v1_defect = set(law11) | set(meta["exclusions"]["adjudicated_key_defect"])
    v1rows = [r for r in allrows
              if r["question_id"] not in v1_defect
              and not r["excl_nota_position_a"]]
    print("\nRECONSTRUCTED v1 set: cells=%d items=%d clusters=%d  "
          "(target 1299/325/208)"
          % (len(v1rows), len({r["question_id"] for r in v1rows}),
             len({r["cluster"] for r in v1rows})))
    print("  the 8 items promoted to defect in v2 and their cell counts:")
    for q in sorted(added8):
        rs = [r for r in allrows if r["question_id"] == q]
        if not rs:
            print("    %-6s ABSENT from paired_clean.json" % q)
            continue
        print("    %-6s cells=%d  letter=%s  nota_a=%s  region=%s  part=%s  "
              "A=%d/%d B=%d/%d"
              % (q, len(rs), rs[0]["correct_letter"],
                 rs[0]["excl_nota_position_a"], rs[0]["region"],
                 rs[0]["exam_part"],
                 sum(r["A_correct"] for r in rs), len(rs),
                 sum(r["B_correct"] for r in rs), len(rs)))

    # -------------------------------------------------- overall, both vintages
    for nm, rr in (("v2 analysis (shipped)", rows),
                   ("v1 analysis (claim's)", v1rows)):
        n = len(rr)
        A = sum(r["A_correct"] for r in rr) / n
        Bv = sum(r["B_correct"] for r in rr) / n
        ci = cluster_boot_ci(rr, lambda r: "ALL", 10000, SEED)["__ALL__"]
        n10 = sum(1 for r in rr if r["A_correct"] and not r["B_correct"])
        n01 = sum(1 for r in rr if not r["A_correct"] and r["B_correct"])
        print("\n%-22s n=%4d  acc(A)=%.4f acc(B)=%.4f delta=%+.4f  "
              "95%% CI [%+.4f,%+.4f]  n10=%d n01=%d"
              % (nm, n, A, Bv, Bv - A, ci[0], ci[1], n10, n01))

    # -------------------------------------------------- per-level tables (v2)
    strats, cuts = make_strats(rows)
    print("\nqlen tertile cutpoints over unique items: c1=%d c2=%d" % cuts)
    signs = {}
    for name, keyf in strats:
        t = table(rows, keyf)
        boot = cluster_boot_ci(rows, keyf, 4000, SEED + 3)
        print("\n" + "-" * 104)
        print("STRATIFIER %s  (%d levels)" % (name, len(t)))
        print("  %-26s %5s %5s %5s %7s %7s %9s %-19s %4s %4s"
              % ("level", "cells", "item", "clst", "accA", "accB", "delta",
                 "95% clus-boot CI", "n10", "n01"))
        neg = zer = pos = 0
        for lev in sorted(t, key=lambda l: t[l]["dd"]):
            x = t[lev]
            lo, hi, _ = boot[lev]
            ci = ("[%+.3f,%+.3f]" % (lo, hi)) if lo is not None else "[  n/a  ]"
            print("  %-26s %5d %5d %5d %7.4f %7.4f %+9.4f %-19s %4d %4d"
                  % (str(lev)[:26], x["n"], x["items"], x["clus"], x["A"],
                     x["B"], x["dd"], ci, x["n10"], x["n01"]))
            if x["dd"] < 0:
                neg += 1
            elif x["dd"] == 0:
                zer += 1
            else:
                pos += 1
        signs[name] = (neg, zer, pos, len(t))
        print("  SIGNS: negative=%d  zero=%d  POSITIVE=%d  (of %d levels)"
              % (neg, zer, pos, len(t)))

    print("\n" + "=" * 104)
    print("SIGN-CONSISTENCY AUDIT (v2 analysis set)")
    print("=" * 104)
    for k, (neg, zer, pos, K) in signs.items():
        flag = "" if (zer == 0 and pos == 0) else "   <-- NOT all-down"
        print("  %-14s %2d/%2d negative, %d zero, %d positive%s"
              % (k, neg, K, zer, pos, flag))


if __name__ == "__main__":
    main()

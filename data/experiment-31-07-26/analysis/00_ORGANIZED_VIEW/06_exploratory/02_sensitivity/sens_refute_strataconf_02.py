"""Part 2: (a) chase the one number that did not reproduce (13 vs 11 exam_part
levels in a single cluster) across every reconstructable exclusion set;
(b) test the SUBSTANTIVE claim -- 'not separable from individual exam blocks' --
by looking for WITHIN-EXAM variation in each stratifier and, where it exists,
comparing the within-exam contrast to the pooled between-exam contrast.
"""
import json
import random
from collections import Counter, defaultdict

from sens_refute_strataconf_01 import load, qlen_tertiles

SETS = ["analysis", "all", "no_defect_only", "no_nota_only"]


def exam(r):
    return "%s %s" % (r["region"], r["year"])


def part_a():
    print("=" * 92)
    print("A. 'thirteen of twenty exam_part levels live in exactly one cluster'")
    print("=" * 92)
    for s in SETS:
        rows = load(s)
        grp = defaultdict(list)
        for r in rows:
            grp[r["exam_part"]].append(r)
        one = [l for l, rs in grp.items() if len({r["cluster"] for r in rs}) == 1]
        oneex = [l for l, rs in grp.items() if len({exam(r) for r in rs}) == 1]
        print("   set=%-16s levels=%2d  single-CLUSTER=%2d  single-EXAM=%2d  "
              "(%d cells, %d clusters)"
              % (s, len(grp), len(one), len(oneex), len(rows),
                 len({r['cluster'] for r in rows})))
        if s == "analysis":
            print("        single-cluster levels:", sorted(one))
            cells = sum(len(grp[l]) for l in one)
            print("        they hold %d/%d cells = %.1f%%"
                  % (cells, len(rows), 100 * cells / len(rows)))


def part_b():
    rows = load("analysis")
    lab, c1, c2 = qlen_tertiles(rows)
    print("\n" + "=" * 92)
    print("B. WITHIN-EXAM VARIATION IN EACH STRATIFIER (is it really inseparable?)")
    print("=" * 92)
    facs = [("has_context", lambda r: str(r["has_context"])),
            ("exam_part", lambda r: r["exam_part"]),
            ("qlen_tertile", lambda r: lab(r["qlen"])),
            ("negated_stem", lambda r: str(r["negated_stem"])),
            ("correct_letter", lambda r: r["correct_letter"])]
    byex = defaultdict(list)
    for r in rows:
        byex[exam(r)].append(r)
    for name, fn in facs:
        multi = {e: rs for e, rs in byex.items() if len({fn(r) for r in rs}) > 1}
        ncell = sum(len(rs) for rs in multi.values())
        print("\n   %-14s exams with >=2 levels present: %2d/17   cells in them: "
              "%4d/%d (%.0f%%)"
              % (name, len(multi), ncell, len(rows), 100 * ncell / len(rows)))
        for e in sorted(multi, key=lambda e: -len(multi[e]))[:6]:
            print("        %-26s %s" % (e, dict(Counter(fn(r) for r in multi[e]))))


def acc(rs, k):
    return sum(r[k] for r in rs) / len(rs) if rs else float("nan")


def delta(rs):
    """paired A->B drop in accuracy (positive = B worse)."""
    return acc(rs, "A_correct") - acc(rs, "B_correct")


def cluster_boot(groups, stat, nboot=4000, seed=7):
    """Cluster bootstrap CI on a statistic computed from a dict level->rows.
    groups: dict cluster -> rows. stat(list_of_rows) -> float or None."""
    rnd = random.Random(seed)
    keys = list(groups)
    out = []
    for _ in range(nboot):
        samp = []
        for _ in range(len(keys)):
            samp.extend(groups[keys[rnd.randrange(len(keys))]])
        v = stat(samp)
        if v is not None and v == v:
            out.append(v)
    out.sort()
    if not out:
        return (float("nan"), float("nan"))
    return out[int(0.025 * len(out))], out[int(0.975 * len(out)) - 1]


def part_c():
    rows = load("analysis")
    lab, _, _ = qlen_tertiles(rows)
    print("\n" + "=" * 92)
    print("C. POOLED vs WITHIN-EXAM CONTRAST  (delta = accA - accB, positive = B worse)")
    print("   CI = nonparametric cluster bootstrap, 4000 resamples of whole clusters")
    print("=" * 92)

    def report(name, fn, la, lb):
        sel = [r for r in rows if fn(r) in (la, lb)]
        # pooled
        A = [r for r in sel if fn(r) == la]
        B = [r for r in sel if fn(r) == lb]
        pooled = delta(A) - delta(B)
        gr = defaultdict(list)
        for r in sel:
            gr[r["cluster"]].append(r)

        def st(s):
            a = [r for r in s if fn(r) == la]
            b = [r for r in s if fn(r) == lb]
            if not a or not b:
                return None
            return delta(a) - delta(b)
        lo, hi = cluster_boot(gr, st)
        print("\n   %s: [%s] n=%d  vs  [%s] n=%d" % (name, la, len(A), lb, len(B)))
        print("      delta(%s)=%+.4f  delta(%s)=%+.4f" % (la, delta(A), lb, delta(B)))
        print("      POOLED contrast      = %+.4f   95%% CI [%+.4f, %+.4f]"
              % (pooled, lo, hi))
        # within-exam: only exams holding both levels, weight by cells
        byex = defaultdict(list)
        for r in sel:
            byex[exam(r)].append(r)
        keep = {e: rs for e, rs in byex.items()
                if {fn(r) for r in rs} >= {la, lb}}
        if not keep:
            print("      WITHIN-EXAM          = NOT IDENTIFIED (no exam holds both levels)")
            return
        num = den = 0.0
        for e, rs in keep.items():
            a = [r for r in rs if fn(r) == la]
            b = [r for r in rs if fn(r) == lb]
            w = min(len(a), len(b))
            num += w * (delta(a) - delta(b))
            den += w
        wexam = num / den
        selk = [r for r in sel if exam(r) in keep]
        gr2 = defaultdict(list)
        for r in selk:
            gr2[r["cluster"]].append(r)

        def st2(s):
            bx = defaultdict(list)
            for r in s:
                bx[exam(r)].append(r)
            n2 = d2 = 0.0
            for e, rs in bx.items():
                a = [r for r in rs if fn(r) == la]
                b = [r for r in rs if fn(r) == lb]
                if not a or not b:
                    continue
                w = min(len(a), len(b))
                n2 += w * (delta(a) - delta(b))
                d2 += w
            return n2 / d2 if d2 else None
        lo2, hi2 = cluster_boot(gr2, st2)
        print("      WITHIN-EXAM contrast = %+.4f   95%% CI [%+.4f, %+.4f]   "
              "(%d exams, %d cells)"
              % (wexam, lo2, hi2, len(keep), len(selk)))
        for e in sorted(keep, key=lambda e: -len(keep[e])):
            rs = keep[e]
            a = [r for r in rs if fn(r) == la]
            b = [r for r in rs if fn(r) == lb]
            print("           %-26s d(%s)=%+.3f (n=%d)  d(%s)=%+.3f (n=%d)  diff=%+.3f"
                  % (e, la, delta(a), len(a), lb, delta(b), len(b),
                     delta(a) - delta(b)))

    report("has_context", lambda r: str(r["has_context"]), "True", "False")
    report("qlen tertile T3 vs T1", lambda r: lab(r["qlen"]), "T3", "T1")
    report("qlen tertile T3 vs T2", lambda r: lab(r["qlen"]), "T3", "T2")
    report("negated_stem", lambda r: str(r["negated_stem"]), "True", "False")


def part_d():
    """How much does the has_context / long-qlen stratum change if the dominant
    exam (Illes Balears 2022) is removed?"""
    rows = load("analysis")
    lab, _, _ = qlen_tertiles(rows)
    print("\n" + "=" * 92)
    print("D. LEAVE-THE-DOMINANT-EXAM-OUT for the two 'impure' strata")
    print("=" * 92)
    for name, fn, lv in [("has_context=True", lambda r: str(r["has_context"]), "True"),
                         ("qlen T3", lambda r: lab(r["qlen"]), "T3")]:
        rs = [r for r in rows if fn(r) == lv]
        full = delta(rs)
        drop = [r for r in rs if exam(r) != "Illes Balears 2022"]
        print("   %-18s all %4d cells: delta=%+.4f | without IB2022 %3d cells "
              "(%d exams): delta=%+.4f"
              % (name, len(rs), full, len(drop),
                 len({exam(r) for r in drop}), delta(drop)))
        for e in sorted({exam(r) for r in rs}):
            sub = [r for r in rs if exam(r) == e]
            print("        %-26s n=%4d delta=%+.4f" % (e, len(sub), delta(sub)))


if __name__ == "__main__":
    part_a()
    part_b()
    part_c()
    part_d()

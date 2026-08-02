"""INDEPENDENT refutation pass #2: heterogeneity tests, rebuilt from scratch.

Implements, with a DIFFERENT seed and a from-scratch code path:

  T1  Block-exchangeable permutation of the size-weighted between-level SS
      Q = sum_k S_k^2/n_k - S^2/n            [replicates the claimed primary test]
  T2  Studentised between-level statistic  F* = Q_between / Q_within-ish, using
      the same block permutation (guards against the n_k-instability of T1 when
      level size is confounded with block size, which it badly is here).
  T3  CONDITIONAL-SCALE heterogeneity: restrict to cells with A_correct==1 and
      test heterogeneity of the flip probability P(B wrong | A right).  This is
      the scale that is free of the acc(A) ceiling; raw delta is mechanically
      attenuated wherever acc(A) is low.
  T4  Ordered-stratifier TREND tests (year, qlen tertile) -- the omnibus Q throws
      away the ordering and is badly under-powered against a monotone pattern.
  T5  Westfall-Young min-P done PROPERLY: one shared permutation index per
      replicate across all six stratifiers (joint, dependence-aware), contrasted
      with the independent-streams version actually used.
  T6  Two-level contrast p-values for every level vs the rest (leave-one-level-
      out), block permutation, to see whether ANY single level is an outlier
      even when the omnibus is silent.

p = (#{stat_perm >= stat_obs} + 1) / (B + 1) everywhere.
"""
import bisect
import json
import math
import random
import sys
from collections import defaultdict, Counter

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")
ROWS = json.load(open(DATA))
B_PERM = 20000
SEED = 815491           # deliberately different from the 20260731 used upstream


def subset(name):
    if name == "analysis":
        return [r for r in ROWS if r["analysis_include"]]
    if name == "all":
        return list(ROWS)
    if name == "plus_nota_a":
        return [r for r in ROWS if not r["excl_item_defect"]]
    if name == "plus_defect":
        return [r for r in ROWS if not r["excl_nota_position_a"]]
    raise ValueError(name)


def qlen_tertile_fn(rows):
    per = {}
    for r in rows:
        per[r["question_id"]] = r["qlen"]
    v = sorted(per.values())
    n = len(v)
    c1 = v[int(round(n / 3.0)) - 1]
    c2 = v[int(round(2 * n / 3.0)) - 1]

    def lab(q):
        return "T1" if q <= c1 else ("T2" if q <= c2 else "T3")
    return lab


def strat_defs(rows):
    lab = qlen_tertile_fn(rows)
    return [("region", lambda r: r["region"]),
            ("year", lambda r: str(r["year"])),
            ("exam_part", lambda r: r["exam_part"]),
            ("has_context", lambda r: str(r["has_context"])),
            ("negated_stem", lambda r: str(r["negated_stem"])),
            ("qlen_tertile", lambda r: lab(r["qlen"]))]


def perm_p(obs, null):
    return (sum(1 for v in null if v >= obs - 1e-12) + 1) / (len(null) + 1)


# --------------------------------------------------------------------- blocks
def make_blocks(rows, key, yfun):
    """Maximal (cluster, level)-homogeneous blocks.  Returns per-block
    (sum y, n, sum y^2, label)."""
    S = defaultdict(float)
    N = defaultdict(int)
    SS = defaultdict(float)
    L = {}
    for r in rows:
        y = yfun(r)
        if y is None:
            continue
        k = (r["cluster"], key(r))
        S[k] += y
        N[k] += 1
        SS[k] += y * y
        L[k] = key(r)
    ks = list(S)
    return ([S[k] for k in ks], [N[k] for k in ks], [SS[k] for k in ks],
            [L[k] for k in ks])


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


def Fstat(S, N, SS, labels, levels, tot_SS):
    """Studentised: between-SS / (within-SS / (n-K)).  tot_SS = sum y^2 over all
    cells (permutation-invariant), so within-SS = tot_SS - S^2/n - Q."""
    ss = defaultdict(float)
    nn = defaultdict(int)
    ts = 0.0
    tn = 0
    for s, n, l in zip(S, N, labels):
        ss[l] += s
        nn[l] += n
        ts += s
        tn += n
    between = -ts * ts / tn
    K = 0
    for l in levels:
        if nn[l]:
            between += ss[l] * ss[l] / nn[l]
            K += 1
    within = tot_SS - ts * ts / tn - between
    if within <= 0 or K < 2 or tn - K <= 0:
        return 0.0
    return (between / (K - 1)) / (within / (tn - K))


def run_family(rows, tag, yfun, ylabel, B=B_PERM, seed=SEED, verbose=True):
    """Returns {name: dict(Q, pQ, F, pF, nullQ)}."""
    strats = strat_defs(rows)
    tot_SS = sum(yfun(r) ** 2 for r in rows if yfun(r) is not None)
    out = {}
    for si, (nm, key) in enumerate(strats):
        S, N, SS, L = make_blocks(rows, key, yfun)
        levels = sorted(set(L))
        Qo = Qstat(S, N, L, levels)
        Fo = Fstat(S, N, SS, L, levels, tot_SS)
        rnd = random.Random(seed + 7919 * si)
        perm = list(L)
        Qn, Fn = [], []
        for _ in range(B):
            rnd.shuffle(perm)
            Qn.append(Qstat(S, N, perm, levels))
            Fn.append(Fstat(S, N, SS, perm, levels, tot_SS))
        out[nm] = dict(Q=Qo, pQ=perm_p(Qo, Qn), F=Fo, pF=perm_p(Fo, Fn),
                       nullQ=Qn, K=len(levels), nblocks=len(S))
    if verbose:
        print("\n%s  (outcome = %s; %d cells, %d blocks-basis)"
              % (tag, ylabel, sum(1 for r in rows if yfun(r) is not None),
                 out[strats[0][0]]["nblocks"]))
        print("  %-14s %3s %10s %10s %10s %10s"
              % ("stratifier", "K", "Q", "perm-Q p", "F*", "perm-F* p"))
        for nm, _ in strats:
            r = out[nm]
            print("  %-14s %3d %10.4f %10.5f %10.4f %10.5f"
                  % (nm, r["K"], r["Q"], r["pQ"], r["F"], r["pF"]))
    return out


def holm(p):
    it = sorted(p.items(), key=lambda kv: kv[1])
    m = len(it)
    adj = {}
    run = 0.0
    for i, (k, v) in enumerate(it):
        run = max(run, min(1.0, (m - i) * v))
        adj[k] = run
    return adj


# ------------------------------------------------------------------ joint WY
def joint_wy(rows, yfun, B=B_PERM, seed=SEED + 31):
    """Westfall-Young min-P with a SHARED permutation across the six
    stratifiers.  Because region/year/exam_part/has_context are all
    cluster-constant, one cluster permutation index drives all of them; for the
    3 stratifiers with split clusters we permute the same cluster index and let
    the split blocks follow their cluster.  This is the dependence-aware
    version; the upstream script used independent streams instead."""
    strats = strat_defs(rows)
    clusters = sorted(set(r["cluster"] for r in rows))
    cidx = {c: i for i, c in enumerate(clusters)}
    # per (cluster, level) block sums, but indexed by cluster so a single
    # cluster permutation moves every stratifier's labels coherently
    per_c = defaultdict(list)     # cluster -> list of (label_vector, S, n)
    for r in rows:
        per_c[r["cluster"]].append(r)
    lab_of = []      # lab_of[i][s] = list of (label, S, n) blocks for cluster i
    for c in clusters:
        rs = per_c[c]
        row = []
        for nm, key in strats:
            agg = defaultdict(lambda: [0.0, 0])
            for r in rs:
                agg[key(r)][0] += yfun(r)
                agg[key(r)][1] += 1
            row.append([(lv, v[0], v[1]) for lv, v in agg.items()])
        lab_of.append(row)

    levels = []
    for si, (nm, key) in enumerate(strats):
        levels.append(sorted(set(key(r) for r in rows)))

    def stats_for(order):
        """order[i] = which cluster's LABELS are pasted onto cluster i's data.
        We instead paste cluster i's data onto cluster order[i]'s labels: build
        per-stratifier (S,n,label) triples."""
        res = []
        for si in range(len(strats)):
            ss = defaultdict(float)
            nn = defaultdict(int)
            ts = 0.0
            tn = 0
            for i in range(len(clusters)):
                donor = lab_of[order[i]][si]      # label structure
                mine = lab_of[i][si]              # data
                # paste: distribute my blocks onto donor labels proportionally
                # by simply relabelling my j-th block with donor's j-th label
                # (cycling if the donor has fewer blocks)
                for j, (lv, s, n) in enumerate(mine):
                    dl = donor[j % len(donor)][0]
                    ss[dl] += s
                    nn[dl] += n
                    ts += s
                    tn += n
            Q = -ts * ts / tn
            for l in levels[si]:
                if nn[l]:
                    Q += ss[l] * ss[l] / nn[l]
            res.append(Q)
        return res

    ident = list(range(len(clusters)))
    obs = stats_for(ident)
    rnd = random.Random(seed)
    order = list(ident)
    cols = [[] for _ in strats]
    for _ in range(B):
        rnd.shuffle(order)
        st = stats_for(order)
        for si in range(len(strats)):
            cols[si].append(st[si])
    # column-wise p of every replicate, then min across columns
    colp = []
    for si in range(len(strats)):
        srt = sorted(cols[si])
        Bn = len(srt)
        colp.append([(Bn - bisect.bisect_left(srt, v - 1e-12) + 1) / (Bn + 1)
                     for v in cols[si]])
    minp = sorted(min(colp[si][b] for si in range(len(strats)))
                  for b in range(B))
    pobs = {}
    for si, (nm, key) in enumerate(strats):
        srt = sorted(cols[si])
        Bn = len(srt)
        pobs[nm] = (Bn - bisect.bisect_left(srt, obs[si] - 1e-12) + 1) / (Bn + 1)
    wy = {}
    for nm in pobs:
        wy[nm] = (bisect.bisect_right(minp, pobs[nm] + 1e-12) + 1) / (B + 1)
    return pobs, wy


def main():
    A = subset("analysis")
    print("#" * 96)
    print("PASS 2 -- independent heterogeneity tests (seed=%d, B=%d)"
          % (SEED, B_PERM))
    print("#" * 96)

    # ---------------- T1/T2 on the raw delta scale
    raw = run_family(A, "T1/T2  RAW DELTA SCALE", lambda r: r["B_correct"] - r["A_correct"],
                     "delta = B_correct - A_correct")
    hp = holm({k: v["pQ"] for k, v in raw.items()})
    print("  Holm-adjusted perm-Q p: %s"
          % {k: round(v, 4) for k, v in sorted(hp.items())})

    # ---------------- T3 conditional scale
    cond = run_family(A, "T3  CONDITIONAL SCALE  P(B wrong | A right)",
                      lambda r: (1 - r["B_correct"]) if r["A_correct"] == 1 else None,
                      "1{B wrong} among A-correct cells")
    hpc = holm({k: v["pQ"] for k, v in cond.items()})
    print("  Holm-adjusted perm-Q p: %s"
          % {k: round(v, 4) for k, v in sorted(hpc.items())})

    # ---------------- T3b conditional recovery scale
    rec = run_family(A, "T3b RECOVERY SCALE  P(B right | A wrong)",
                     lambda r: r["B_correct"] if r["A_correct"] == 0 else None,
                     "1{B right} among A-wrong cells")

    # ---------------- T4 trend tests
    print("\nT4  ORDERED-STRATIFIER TREND TESTS (block permutation, B=%d)" % B_PERM)
    for nm, score in (("year", lambda r: float(r["year"])),
                      ("qlen_tertile", None),
                      ("qlen_raw", lambda r: float(r["qlen"]))):
        if nm == "qlen_tertile":
            lab = qlen_tertile_fn(A)
            score = lambda r: {"T1": 1.0, "T2": 2.0, "T3": 3.0}[lab(r["qlen"])]
        # blocks are whole clusters when score is cluster-constant, else
        # (cluster, score) blocks
        S = defaultdict(float)
        N = defaultdict(int)
        X = {}
        for r in A:
            k = (r["cluster"], score(r))
            S[k] += r["B_correct"] - r["A_correct"]
            N[k] += 1
            X[k] = score(r)
        ks = list(S)
        Sv = [S[k] for k in ks]
        Nv = [N[k] for k in ks]
        Xv = [X[k] for k in ks]
        # centred score, statistic = |sum_b (x_b - xbar_w) * S_b| with weights
        tn = sum(Nv)
        xbar = sum(x * n for x, n in zip(Xv, Nv)) / tn
        obs = abs(sum((x - xbar) * s for x, s in zip(Xv, Sv)))
        rnd = random.Random(SEED + 991)
        perm = list(Xv)
        null = []
        for _ in range(B_PERM):
            rnd.shuffle(perm)
            xb = sum(x * n for x, n in zip(perm, Nv)) / tn
            null.append(abs(sum((x - xb) * s for x, s in zip(perm, Sv))))
        print("  %-14s blocks=%3d  |T|=%.3f  two-sided perm p=%.5f"
              % (nm, len(ks), obs, perm_p(obs, null)))

    # ---------------- T5 joint WY
    print("\nT5  WESTFALL-YOUNG min-P, JOINT permutation vs INDEPENDENT streams")
    pobs, wyj = joint_wy(A, lambda r: r["B_correct"] - r["A_correct"])
    print("  %-14s %10s %12s %12s"
          % ("stratifier", "perm-Q p", "WY joint", "Holm"))
    for nm in [s[0] for s in strat_defs(A)]:
        print("  %-14s %10.5f %12.4f %12.4f"
              % (nm, pobs[nm], wyj[nm], hp[nm]))

    # ---------------- T6 per-level outlier scan
    print("\nT6  PER-LEVEL leave-one-level-out contrast (level vs rest),")
    print("    block permutation of the binary indicator, B=%d, raw p (no mult. adj.)"
          % (B_PERM // 4))
    strats = strat_defs(A)
    scan = []
    for si, (nm, key) in enumerate(strats):
        levels = sorted(set(key(r) for r in A))
        for lev in levels:
            bkey = (lambda r, k=key, lv=lev: "IN" if k(r) == lv else "OUT")
            S, N, SS, L = make_blocks(A, bkey, lambda r: r["B_correct"] - r["A_correct"])
            Qo = Qstat(S, N, L, ["IN", "OUT"])
            rnd = random.Random(SEED + 13 * si + 101 * hash(str(lev)) % 9973)
            perm = list(L)
            null = []
            for _ in range(B_PERM // 4):
                rnd.shuffle(perm)
                null.append(Qstat(S, N, perm, ["IN", "OUT"]))
            p = perm_p(Qo, null)
            rs = [r for r in A if key(r) == lev]
            dd = sum(r["B_correct"] - r["A_correct"] for r in rs) / len(rs)
            scan.append((p, nm, str(lev), len(rs), dd))
    scan.sort()
    print("  %-14s %-28s %6s %9s %10s" % ("stratifier", "level", "cells", "delta", "raw p"))
    for p, nm, lev, n, dd in scan[:14]:
        print("  %-14s %-28s %6d %+9.4f %10.5f" % (nm, lev[:28], n, dd, p))
    nlev = len(scan)
    print("  total level-contrasts tested: %d ; number with raw p<0.05: %d ; "
          "Bonferroni threshold 0.05/%d = %.5f ; smallest p = %.5f"
          % (nlev, sum(1 for s in scan if s[0] < 0.05), nlev, 0.05 / nlev, scan[0][0]))


if __name__ == "__main__":
    main()

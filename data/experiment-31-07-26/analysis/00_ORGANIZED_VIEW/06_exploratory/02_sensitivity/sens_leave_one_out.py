#!/usr/bin/env python3
"""
sens_leave_one_out.py -- influence / leave-one-out analysis for the paired A-vs-B design.

Estimand: pooled delta = mean over analysis cells of (B_correct - A_correct),
          i.e. accuracy(B) - accuracy(A) in percentage points.

Everything is stdlib only. Methods are named inline and echoed in the output.
"""
import json, math, random, collections, sys

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
RECS = json.load(open(PATH))

def subset(name):
    if name == "analysis":
        return [r for r in RECS if r["analysis_include"]]
    if name == "unfiltered":
        return list(RECS)
    if name == "no_defect_only":          # drop only the 14 defective items
        return [r for r in RECS if not r["excl_item_defect"]]
    if name == "no_nota_a_only":          # drop only the 91 letter-(a) items
        return [r for r in RECS if not r["excl_nota_position_a"]]
    raise ValueError(name)

def delta(cells):
    n = len(cells)
    if n == 0: return float("nan"), 0, 0
    s = sum(c["B_correct"] - c["A_correct"] for c in cells)
    return 100.0 * s / n, s, n

# ---------------------------------------------------------------- bootstrap
def cluster_bootstrap_ci(cells, B=20000, seed=20260731, alpha=0.05):
    """Nonparametric cluster bootstrap: resample CLUSTERS with replacement
    (clusters = clinical-context groups, the unit of dependence), carrying all
    of a cluster's cells. Percentile interval."""
    by = collections.defaultdict(list)
    for c in cells: by[c["cluster"]].append(c)
    groups = list(by.values())
    # precompute (sum_delta, n) per cluster so the loop is cheap
    g = [(sum(x["B_correct"] - x["A_correct"] for x in grp), len(grp)) for grp in groups]
    K = len(g)
    rnd = random.Random(seed)
    out = []
    for _ in range(B):
        s = 0; n = 0
        for _ in range(K):
            ds, dn = g[rnd.randrange(K)]
            s += ds; n += dn
        out.append(100.0 * s / n)
    out.sort()
    lo = out[int(math.floor(alpha / 2 * B))]
    hi = out[min(B - 1, int(math.ceil((1 - alpha / 2) * B)) - 1)]
    return lo, hi, out

# ---------------------------------------------------------------- permutation
def cluster_permutation_p(cells, B=20000, seed=20260731):
    """Two-sided cluster-level sign-flip permutation test of H0: E[B-A]=0.
    Under H0 (exchangeability of the A/B label within a paired cell) the sign of
    every within-cell difference may be flipped; flips are applied at CLUSTER
    level so the dependence structure is preserved. p = (1+#{|t*|>=|t_obs|})/(1+B)."""
    by = collections.defaultdict(list)
    for c in cells: by[c["cluster"]].append(c)
    g = [[x["B_correct"] - x["A_correct"] for x in grp] for grp in by.values()]
    gs = [sum(v) for v in g]
    n = sum(len(v) for v in g)
    obs = 100.0 * sum(gs) / n
    rnd = random.Random(seed)
    K = len(g); ge = 0
    for _ in range(B):
        s = 0
        for i in range(K):
            s += gs[i] if rnd.random() < 0.5 else -gs[i]
        if abs(100.0 * s / n) >= abs(obs) - 1e-12: ge += 1
    return obs, (1 + ge) / (1 + B)

# ---------------------------------------------------------------- LOO engine
def loo(cells, keyfn):
    """Delete-one-group jackknife on the pooled delta. Returns list of
    (key, delta_without_group, shift_pp, n_cells_dropped, sum_delta_dropped)."""
    tot_d, tot_s, tot_n = delta(cells)
    by = collections.defaultdict(lambda: [0, 0])
    for c in cells:
        k = keyfn(c)
        by[k][0] += c["B_correct"] - c["A_correct"]
        by[k][1] += 1
    rows = []
    for k, (s, n) in by.items():
        if tot_n - n == 0: continue
        d_wo = 100.0 * (tot_s - s) / (tot_n - n)
        rows.append((k, d_wo, d_wo - tot_d, n, s))
    rows.sort(key=lambda r: -abs(r[2]))
    return tot_d, tot_n, rows

def fmt(x, p=3):
    return f"{x:+.{p}f}"

# ================================================================= main
def main():
    SET = sys.argv[1] if len(sys.argv) > 1 else "analysis"
    cells = subset(SET)
    d0, s0, n0 = delta(cells)
    items = sorted(set(c["question_id"] for c in cells))
    clusters = sorted(set(c["cluster"] for c in cells))
    models = sorted(set(c["model"] for c in cells))

    print(f"=== SUBSET: {SET} ===")
    print(f"cells={n0}  items={len(items)}  clusters={len(clusters)}  models={len(models)}")
    accA = 100.0 * sum(c["A_correct"] for c in cells) / n0
    accB = 100.0 * sum(c["B_correct"] for c in cells) / n0
    print(f"acc A = {accA:.3f}%   acc B = {accB:.3f}%")
    print(f"POOLED DELTA (B-A) = {d0:+.4f} pp   (net discordant cells = {s0})")
    disc = collections.Counter()
    for c in cells:
        disc[c["B_correct"] - c["A_correct"]] += 1
    print(f"cell-level: B>A (0->1): {disc[1]}   B<A (1->0): {disc[-1]}   tied: {disc[0]}")

    lo, hi, boot = cluster_bootstrap_ci(cells)
    print(f"cluster bootstrap 95% CI (20000 reps, percentile): [{lo:+.3f}, {hi:+.3f}] pp")
    obs, p = cluster_permutation_p(cells)
    print(f"cluster sign-flip permutation p (20000 reps, two-sided) = {p:.5f}")
    halfwidth = (hi - lo) / 2
    print(f"CI half-width = {halfwidth:.3f} pp  -> reference scale for judging LOO shifts")

    # ---------------- (i) leave-one-CLUSTER-out
    print("\n--- (i) LEAVE-ONE-CLUSTER-OUT ---")
    d_full, n_full, rows = loo(cells, lambda c: c["cluster"])
    ds = [r[1] for r in rows]
    print(f"recomputations: {len(rows)}")
    print(f"pooled delta range across LOCO: [{min(ds):+.4f}, {max(ds):+.4f}] pp  (full={d_full:+.4f})")
    print(f"max |shift| = {max(abs(r[2]) for r in rows):.4f} pp")
    print(f"clusters whose removal moves pooled delta by >1.0 pp: "
          f"{sum(1 for r in rows if abs(r[2]) > 1.0)}")
    print(f"clusters whose removal moves pooled delta by >0.5 pp: "
          f"{sum(1 for r in rows if abs(r[2]) > 0.5)}")
    print(f"clusters whose removal flips the SIGN of the pooled delta: "
          f"{sum(1 for r in rows if (r[1] > 0) != (d_full > 0))}")
    print("top 12 most influential clusters:")
    csize = collections.Counter(c["cluster"] for c in cells)
    citems = collections.defaultdict(set)
    for c in cells: citems[c["cluster"]].add(c["question_id"])
    print(f"{'cluster':>8} {'cells':>6} {'items':>6} {'sumD':>6} {'delta_wo':>10} {'shift_pp':>10}")
    for k, dwo, sh, n, s in rows[:12]:
        print(f"{k:>8} {n:>6} {len(citems[k]):>6} {s:>+6} {dwo:>+10.4f} {sh:>+10.4f}")

    # ---------------- (ii) leave-one-MODEL-out
    print("\n--- (ii) LEAVE-ONE-MODEL-OUT ---")
    d_full, n_full, mrows = loo(cells, lambda c: c["model"])
    print(f"{'model':>26} {'cells':>6} {'accA':>7} {'accB':>7} {'own_delta':>10} "
          f"{'delta_wo':>10} {'shift_pp':>10}")
    per = collections.defaultdict(lambda: [0, 0, 0])
    for c in cells:
        p_ = per[c["model"]]; p_[0] += c["A_correct"]; p_[1] += c["B_correct"]; p_[2] += 1
    mrows_sorted = sorted(mrows, key=lambda r: r[0])
    for k, dwo, sh, n, s in mrows_sorted:
        a, b, nn = per[k]
        print(f"{k:>26} {n:>6} {100.0*a/nn:>6.2f}% {100.0*b/nn:>6.2f}% "
              f"{100.0*s/nn:>+10.3f} {dwo:>+10.4f} {sh:>+10.4f}")
    md = [(k, 100.0 * per[k][2] and 100.0 * s / n) for k, dwo, sh, n, s in mrows]
    print(f"per-model delta range: [{min(100.0*s/n for _,_,_,n,s in mrows):+.3f}, "
          f"{max(100.0*s/n for _,_,_,n,s in mrows):+.3f}] pp")
    print(f"models with delta of the SAME sign as pooled: "
          f"{sum(1 for _,_,_,n,s in mrows if (s>0)==(s0>0) and s!=0)}/{len(mrows)}")
    print(f"LOMO pooled-delta range: [{min(r[1] for r in mrows):+.4f}, {max(r[1] for r in mrows):+.4f}]")
    print(f"max |shift| = {max(abs(r[2]) for r in mrows):.4f} pp; "
          f"any sign flip: {any((r[1]>0)!=(d_full>0) for r in mrows)}")

    # ---------------- (iii) leave-one-ITEM-out
    print("\n--- (iii) LEAVE-ONE-ITEM-OUT (top 10 influential items) ---")
    d_full, n_full, irows = loo(cells, lambda c: c["question_id"])
    ids = [r[1] for r in irows]
    print(f"recomputations: {len(irows)}")
    print(f"pooled delta range across LOIO: [{min(ids):+.4f}, {max(ids):+.4f}] pp")
    print(f"max |shift| = {max(abs(r[2]) for r in irows):.4f} pp; "
          f"items with |shift|>1pp: {sum(1 for r in irows if abs(r[2])>1.0)}; "
          f"items with |shift|>0.25pp: {sum(1 for r in irows if abs(r[2])>0.25)}")
    meta = {}
    for c in cells: meta[c["question_id"]] = c
    print(f"{'item':>7} {'cells':>5} {'sumD':>5} {'shift_pp':>9} {'letter':>6} {'cluster':>7} "
          f"{'negstem':>7} {'ctx':>4} {'qlen':>5} {'year':>5} {'part':>10} region")
    for k, dwo, sh, n, s in irows[:10]:
        m = meta[k]
        print(f"{k:>7} {n:>5} {s:>+5} {sh:>+9.4f} {m['correct_letter']:>6} {m['cluster']:>7} "
              f"{str(m['negated_stem']):>7} {str(m['has_context']):>4} {m['qlen']:>5} "
              f"{m['year']:>5} {m['exam_part']:>10} {m['region']}")

    top10 = [r[0] for r in irows[:10]]
    print("\ncommon-feature audit of the top-10 items vs. the rest:")
    rest = [i for i in items if i not in set(top10)]
    def prof(idlist, label):
        L = collections.Counter(meta[i]["correct_letter"] for i in idlist)
        neg = sum(1 for i in idlist if meta[i]["negated_stem"])
        ctx = sum(1 for i in idlist if meta[i]["has_context"])
        ql = sorted(meta[i]["qlen"] for i in idlist)
        med = ql[len(ql)//2]
        yr = collections.Counter(meta[i]["year"] for i in idlist)
        reg = collections.Counter(meta[i]["region"] for i in idlist)
        n = len(idlist)
        print(f"  {label:>8} n={n:<4} letters={dict(sorted(L.items()))} "
              f"neg_stem={neg}({100.0*neg/n:.0f}%) has_ctx={ctx}({100.0*ctx/n:.0f}%) "
              f"median_qlen={med} years={dict(sorted(yr.items()))}")
        print(f"           regions={dict(reg.most_common(4))}")
    prof(top10, "top10")
    prof(rest, "rest")

    # direction of the top-10
    pos = sum(1 for k,_,sh,_,s in irows[:10] if s > 0)
    negn = sum(1 for k,_,sh,_,s in irows[:10] if s < 0)
    print(f"  direction: {pos} of the top-10 push the pooled delta UP (B better), {negn} push it DOWN")

    # how much of the total effect do the top-10 items carry?
    top_s = sum(r[4] for r in irows[:10])
    print(f"  top-10 items contribute net {top_s:+d} of the total net {s0:+d} discordant cells "
          f"({100.0*top_s/s0:.1f}% of the raw signal) from {sum(r[3] for r in irows[:10])}/{n0} cells")

    # concentration curve: how many items needed to reach 50% of |signal|
    contrib = sorted(((r[0], r[4]) for r in irows), key=lambda t: -abs(t[1]))
    run = 0; need = None
    tot_abs = sum(abs(c) for _, c in contrib)
    for j, (k, c) in enumerate(contrib, 1):
        run += abs(c)
        if need is None and run >= 0.5 * tot_abs:
            need = j
    print(f"  concentration: {need}/{len(items)} items carry 50% of the total ABSOLUTE "
          f"item-level signal (sum|net| = {tot_abs})")
    nz = sum(1 for _, c in contrib if c != 0)
    print(f"  items with any A/B discordance at all: {nz}/{len(items)} "
          f"({100.0*nz/len(items):.1f}%)")

    # drop the whole top-10 at once
    keep = [c for c in cells if c["question_id"] not in set(top10)]
    dk, _, nk = delta(keep)
    print(f"  dropping ALL top-10 items at once: delta = {dk:+.4f} pp on {nk} cells "
          f"(shift {dk-d0:+.4f} pp)")
    # drop the 10 most positive and 10 most negative
    pos10 = [r[0] for r in sorted(irows, key=lambda r: -r[4])[:10]]
    neg10 = [r[0] for r in sorted(irows, key=lambda r:  r[4])[:10]]
    for nm, lst in (("10 most PRO-B items", pos10), ("10 most PRO-A items", neg10)):
        kp = [c for c in cells if c["question_id"] not in set(lst)]
        dd, _, nn2 = delta(kp)
        print(f"  dropping {nm}: delta = {dd:+.4f} pp (shift {dd-d0:+.4f} pp)")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
sens_refute_loo_cluster3.py -- INDEPENDENT recomputation of the delete-one-cluster
jackknife, written from scratch (does not import sens_leave_one_out.py).

Estimand: pooled delta = 100 * mean over cells of (B_correct - A_correct), in pp.
Jackknife: for each cluster k, delta_wo(k) = 100*(S - S_k)/(N - n_k);
           shift(k) = delta_wo(k) - delta_full.
No p-values are needed for this task; every number below is a deterministic
recomputation from paired_clean.json (no resampling).
"""
import json, collections

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
R = json.load(open(PATH))

def report(cells, label):
    N = len(cells)
    S = sum(c["B_correct"] - c["A_correct"] for c in cells)
    d0 = 100.0 * S / N
    print(f"\n================ SUBSET: {label} ================")
    print(f"cells N={N}  net S={S:+d}  pooled delta={d0:+.4f} pp")
    print(f"items={len(set(c['question_id'] for c in cells))}  "
          f"clusters={len(set(c['cluster'] for c in cells))}")

    agg = collections.defaultdict(lambda: [0, 0, set()])   # cluster -> [S_k, n_k, items]
    for c in cells:
        a = agg[c["cluster"]]
        a[0] += c["B_correct"] - c["A_correct"]
        a[1] += 1
        a[2].add(c["question_id"])

    rows = []
    for k, (s, n, its) in agg.items():
        if N - n == 0:
            continue
        dwo = 100.0 * (S - s) / (N - n)
        rows.append({"cluster": k, "n": n, "items": len(its), "S": s,
                     "delta_wo": dwo, "shift": dwo - d0,
                     "delta_own": 100.0 * s / n})
    rows.sort(key=lambda r: -abs(r["shift"]))

    print(f"\n-- clusters ranked by |shift| (top 15) --")
    print(f"{'rank':>4} {'cluster':>8} {'cells':>6} {'items':>6} {'net':>5} "
          f"{'own_delta':>10} {'delta_wo':>10} {'shift_pp':>10}")
    for i, r in enumerate(rows[:15], 1):
        print(f"{i:>4} {r['cluster']:>8} {r['n']:>6} {r['items']:>6} {r['S']:>+5} "
              f"{r['delta_own']:>+10.4f} {r['delta_wo']:>+10.4f} {r['shift']:>+10.4f}")

    # size ranking
    bysize = sorted(rows, key=lambda r: -r["n"])
    print(f"\n-- clusters ranked by SIZE (top 12) --")
    print(f"{'rank':>4} {'cluster':>8} {'cells':>6} {'items':>6} {'net':>5} "
          f"{'own_delta':>10} {'shift_pp':>10} {'shift_rank':>11}")
    shift_rank = {r["cluster"]: i for i, r in enumerate(rows, 1)}
    for i, r in enumerate(bysize[:12], 1):
        print(f"{i:>4} {r['cluster']:>8} {r['n']:>6} {r['items']:>6} {r['S']:>+5} "
              f"{r['delta_own']:>+10.4f} {r['shift']:>+10.4f} {shift_rank[r['cluster']]:>11}")

    # null clusters ranked by size (the claim's mechanism)
    nulls = sorted([r for r in rows if r["S"] == 0], key=lambda r: -r["n"])
    print(f"\n-- NULL clusters (net==0): {len(nulls)} of {len(rows)}; top 10 by size --")
    print(f"{'cluster':>8} {'cells':>6} {'items':>6} {'shift_pp':>10} {'shift_rank':>11}")
    for r in nulls[:10]:
        print(f"{r['cluster']:>8} {r['n']:>6} {r['items']:>6} {r['shift']:>+10.4f} "
              f"{shift_rank[r['cluster']]:>11}")

    return d0, N, S, rows, shift_rank, agg


def cluster_detail(cells, cid, label):
    sub = [c for c in cells if c["cluster"] == cid]
    print(f"\n-- DETAIL cluster {cid} [{label}] --")
    for f in ("region", "year", "exam_part", "has_context"):
        vals = sorted(set(str(c[f]) for c in sub))
        print(f"   {f:<12} = {vals}  (constant: {len(vals)==1})")
    peritem = collections.defaultdict(lambda: [0, 0])
    letters = {}
    for c in sub:
        peritem[c["question_id"]][0] += c["B_correct"] - c["A_correct"]
        peritem[c["question_id"]][1] += 1
        letters[c["question_id"]] = c["correct_letter"]
    def keyf(q):
        return int(q[1:]) if q[1:].isdigit() else 0
    print(f"   items={len(peritem)} cells={len(sub)}  net={sum(v[0] for v in peritem.values()):+d}")
    print(f"   {'item':>7} {'cells':>5} {'net':>5} {'letter':>7}")
    for q in sorted(peritem, key=keyf):
        s, n = peritem[q]
        print(f"   {q:>7} {n:>5} {s:>+5} {letters[q]:>7}")
    # models present
    mm = collections.Counter(c["model"] for c in sub)
    print(f"   models: {dict(mm)}")


cells_analysis = [r for r in R if r["analysis_include"]]
d0, N, S, rows, srank, agg = report(cells_analysis, "analysis (analysis_include==true)")
cluster_detail(cells_analysis, 3, "analysis")
cluster_detail(cells_analysis, 19, "analysis")

# closed-form identity check: shift = n/(N-n) * (delta_full - delta_own)
print("\n-- closed-form identity check (top 5) --")
for r in rows[:5]:
    pred = r["n"] / (N - r["n"]) * (d0 - r["delta_own"])
    print(f"   cluster {r['cluster']:>4}: shift={r['shift']:+.6f}  closed-form={pred:+.6f}  "
          f"ok={abs(pred-r['shift'])<1e-9}")

# what the claim asserts, verbatim
print("\n================ CLAIM CHECK (analysis subset) ================")
claim = {3: (44, 0, -16.0956, -0.5452), 0: (24, -10, None, +0.4916),
         1: (68, -5, None, -0.4528), 72: (4, +4, None, -0.3569),
         19: (80, -16, None, +0.2920)}
lut = {r["cluster"]: r for r in rows}
for cid, (n, net, dwo, sh) in claim.items():
    if cid not in lut:
        print(f"   cluster {cid}: ABSENT from analysis subset")
        continue
    r = lut[cid]
    print(f"   cluster {cid:>3}: claimed n={n} net={net:+d} shift={sh:+.4f} "
          f"|| actual n={r['n']} net={r['S']:+d} shift={r['shift']:+.4f} "
          f"delta_wo={r['delta_wo']:+.4f} rank={srank[cid]}  "
          f"MATCH={n==r['n'] and net==r['S'] and abs(sh-r['shift'])<5e-4}")

print(f"\n   most influential cluster by |shift| = {rows[0]['cluster']} "
       f"(shift {rows[0]['shift']:+.4f} pp, n={rows[0]['n']}, net={rows[0]['S']:+d})")
print(f"   top-5 by |shift|: {[(r['cluster'], round(r['shift'],4)) for r in rows[:5]]}")
print(f"   largest cluster by cells = {max(rows, key=lambda r: r['n'])['cluster']} "
      f"({max(r['n'] for r in rows)} cells)")

# sensitivity of the ranking to the two contested exclusions
for nm, sel in (("unfiltered (all 1691)", lambda r: True),
                ("no_defect_only", lambda r: not r["excl_item_defect"]),
                ("no_nota_a_only", lambda r: not r["excl_nota_position_a"])):
    cs = [r for r in R if sel(r)]
    dd, NN, SS, rr, sr2, _ = report(cs, nm)
    l2 = {r["cluster"]: r for r in rr}
    c3 = l2.get(3)
    print(f"   -> cluster 3: n={c3['n']} net={c3['S']:+d} shift={c3['shift']:+.4f} "
          f"rank={sr2[3]} / {len(rr)} clusters; top cluster = {rr[0]['cluster']} "
          f"(shift {rr[0]['shift']:+.4f})")

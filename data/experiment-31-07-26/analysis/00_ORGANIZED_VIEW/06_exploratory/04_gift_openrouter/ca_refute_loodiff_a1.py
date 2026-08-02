"""Independent recomputation of the 'coverage-bias' LOO-difficulty claim.
Stdlib only. Reads cross_arm_A.json directly (no ca_lib, no ca_cov_grid).
"""
import json, math, random, os, collections

BASE = os.path.dirname(os.path.abspath(__file__))
rows = [r for r in json.load(open(os.path.join(BASE, "cross_arm_A.json")))
        if r.get("analysis_include")]
MODELS = sorted({r["model"] for r in rows})
print("cells", len(rows), "items", len({r["question_id"] for r in rows}),
      "clusters", len({r["cluster"] for r in rows}), "models", len(MODELS))

byitem = collections.defaultdict(dict)
for r in rows:
    byitem[r["question_id"]][r["model"]] = r
QS = sorted(byitem)
print("items with exactly 4 models:",
      sum(1 for q in QS if len(byitem[q]) == 4), "of", len(QS))

for q in QS:
    cells = byitem[q]
    nk = sum(c["or_correct"] for c in cells.values())
    for m, c in cells.items():
        c["naive_k"] = nk
        c["loo_k"] = nk - c["or_correct"]
        c["delta"] = c["gift_correct"] - c["or_correct"]

# ---------------------------------------------------------------- [1] identity
bad = 0
for q in QS:
    cells = byitem[q]
    if len(cells) != 4:
        continue
    lo = sum(c["loo_k"] for c in cells.values()) / 4.0
    nk = cells[MODELS[0]]["naive_k"]
    if abs(lo - 0.75 * nk) > 1e-12:
        bad += 1
print(f"\n[1] identity mean_m loo_k(i,m) == 0.75*naive_k(i): violations = {bad}"
      f" / {len(QS)} items")
print("    sum_m loo_k = sum_m (naive_k - or_m) = 4*naive_k - naive_k = 3*naive_k")
print("    -> TAUTOLOGY whenever an item has all 4 cells. Arithmetic, not a finding.")

# --------------------------------------------- [2] item-level Spearman, both axes
def rank(v):
    idx = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and v[idx[j + 1]] == v[idx[i]]:
            j += 1
        a = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            r[idx[k]] = a
        i = j + 1
    return r


def spear(xs, ys):
    rx, ry = rank(xs), rank(ys)
    mx = sum(rx) / len(rx); my = sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return num / (dx * dy) if dx and dy else float("nan")


il_d, il_naive, il_loo, il_gift = [], [], [], []
for q in QS:
    cs = list(byitem[q].values())
    il_d.append(sum(c["delta"] for c in cs) / len(cs))
    il_naive.append(cs[0]["naive_k"])
    il_loo.append(sum(c["loo_k"] for c in cs) / len(cs))
    il_gift.append(sum(c["gift_correct"] for c in cs) / len(cs))

rho_naive = spear(il_naive, il_d)
rho_loo = spear(il_loo, il_d)
print(f"\n[2] item-level Spearman (n_items={len(QS)})")
print(f"    rho(naive_k,             mean delta) = {rho_naive:+.6f}")
print(f"    rho(mean LOO difficulty, mean delta) = {rho_loo:+.6f}")
print(f"    difference = {abs(rho_naive - rho_loo):.2e}  <-- forced by the identity;")
print("    0.75*naive_k is a strictly increasing transform and Spearman is rank-")
print("    based, so the LOO 'fix' changes NOTHING at the item level.")

chk = max(abs(d - (g - nk / 4.0)) for d, g, nk in zip(il_d, il_gift, il_naive))
print(f"    algebraic check max|mean_delta - (mean_gift - naive_k/4)| = {chk:.2e}")

# ------------------------------- [3] the RIGHT null: keep contamination, kill signal
gift_by_model = {m: [byitem[q][m]["gift_correct"] for q in QS if m in byitem[q]]
                 for m in MODELS}
qs_by_model = {m: [q for q in QS if m in byitem[q]] for m in MODELS}
rng = random.Random(20260731)
P = 20000
null_rho, ge = [], 0
for _ in range(P):
    perm_gift = {}
    for m in MODELS:
        v = gift_by_model[m][:]
        rng.shuffle(v)
        perm_gift[m] = dict(zip(qs_by_model[m], v))
    d2 = []
    for q in QS:
        cs = byitem[q]
        d2.append(sum(perm_gift[m][q] - cs[m]["or_correct"] for m in cs) / len(cs))
    r = spear(il_naive, d2)
    null_rho.append(r)
    if r <= rho_naive + 1e-12:
        ge += 1
null_rho.sort()
mean_null = sum(null_rho) / len(null_rho)
print(f"\n[3] ARTEFACT-ONLY null (permute gift_correct within model across items,")
print(f"    P={P}: preserves the algebraic contamination, destroys real signal)")
print(f"    observed rho(naive_k, mean delta) = {rho_naive:+.4f}")
print(f"    null mean rho = {mean_null:+.4f}   null 2.5/50/97.5 pct = "
      f"{null_rho[int(.025*P)]:+.4f} / {null_rho[P//2]:+.4f} / {null_rho[int(.975*P)]:+.4f}")
print(f"    one-sided p (null rho <= observed) = {(ge+1)/(P+1):.4f}")
print(f"    share of observed rho reproduced by the artefact alone: "
      f"{100*mean_null/rho_naive:.1f}%")

rng2 = random.Random(99)
c2 = 0
for _ in range(P):
    y = il_d[:]
    rng2.shuffle(y)
    if abs(spear(il_naive, y)) >= abs(rho_naive) - 1e-12:
        c2 += 1
print(f"    claim's null (shuffle mean delta across items): p = {(c2+1)/(P+1):.4f}")
print("    -> that null ALSO destroys the algebraic link, so it rejects even when")
print("       the correlation is 100% artefact. It cannot diagnose contamination.")

# ------------------------------------------------ [4] stratified deltas, v2 data
def table(key, ks):
    out = {}
    print(f"\n{'k':>2s} {'cells':>6s} {'items':>6s} {'GIFT%':>7s} {'OR%':>7s} "
          f"{'delta_pp':>9s} {'b':>4s} {'c':>4s}")
    for k in ks:
        sub = [c for q in QS for c in byitem[q].values() if c[key] == k]
        if not sub:
            continue
        n = len(sub)
        g = sum(c["gift_correct"] for c in sub); o = sum(c["or_correct"] for c in sub)
        b = sum(1 for c in sub if c["delta"] == 1)
        cc = sum(1 for c in sub if c["delta"] == -1)
        ni = len({c["question_id"] for c in sub})
        print(f"{k:2d} {n:6d} {ni:6d} {100*g/n:6.1f}% {100*o/n:6.1f}% "
              f"{100*(g-o)/n:+8.2f} {b:4d} {cc:4d}")
        out[k] = dict(n=n, delta=(g - o) / n, b=b, c=cc)
    return out


print("\n[4a] NAIVE difficulty (contaminated) -- v2 canonical file")
tn = table("naive_k", range(5))
print("\n[4b] LEAVE-ONE-OUT difficulty -- v2 canonical file")
tl = table("loo_k", range(4))

print("\n[5] claim's quoted numbers vs v2 recomputation")
for k, q in [(1, 35.0), (2, 17.2), (3, 10.4), (4, -1.67)]:
    print(f"    naive_k={k}: claim {q:+6.2f} pp   v2 {100*tn[k]['delta']:+6.2f} pp")
for k, q in [(1, 8.51), (2, 5.11), (3, 0.89)]:
    print(f"    loo_k  ={k}: claim {q:+6.2f} pp   v2 {100*tl[k]['delta']:+6.2f} pp")
print(f"    loo_k  =0: claim NOT REPORTED       v2 {100*tl[0]['delta']:+6.2f} pp "
      f"(n={tl[0]['n']}) <- omitted stratum")
print(f"    naive_k=0: claim NOT REPORTED       v2 {100*tn[0]['delta']:+6.2f} pp "
      f"(n={tn[0]['n']}) <- forced >= 0, mirror of the k=4 point the claim makes")

# ------------------------- [6] does LOO actually decontaminate the CELL level?
print("\n[6] residual (non-algebraic) contamination in the LOO stratification")
for k in range(4):
    sub = [c for q in QS for c in byitem[q].values() if c["loo_k"] == k]
    orr = sum(c["or_correct"] for c in sub) / len(sub)
    print(f"    loo_k={k}: n={len(sub):5d}  OR accuracy in stratum = {100*orr:5.1f}%"
          f"  -> max attainable delta = {100*(1-orr):+5.1f} pp, "
          f"min = {100*(0-orr):+6.1f} pp")
print("    OR accuracy still rises steeply with loo_k, so the ceiling on delta")
print("    still tightens with k. LOO removes the deterministic term, NOT the")
print("    ceiling; a declining delta-vs-loo_k trend is still partly mechanical.")

json.dump({"n_cells": len(rows), "n_items": len(QS),
           "rho_naive": rho_naive, "rho_loo": rho_loo,
           "null_mean_rho": mean_null, "identity_violations": bad,
           "tab_naive": {str(k): v for k, v in tn.items()},
           "tab_loo": {str(k): v for k, v in tl.items()}},
          open(os.path.join(BASE, "ca_refute_loodiff_a1_out.json"), "w"), indent=1)

#!/usr/bin/env python
"""
Per-model contrasts of the A->B robustness delta.
Stdlib only. No numpy/scipy/pandas.

Design: paired binary outcome, same 325 items under condition A (verbatim) and
condition B (correct option's TEXT replaced by none-of-the-above, LETTER unchanged),
crossed with 4 models, items nested in 208 clinical-context clusters. runs=1.

Primary: cluster bootstrap over the 208 clusters (the top-level independent unit)
for each of the 6 pairwise contrasts of delta_m = A_acc_m - B_acc_m.
Holm-Bonferroni across the 6 tests.
Secondary check: cluster-level sign-flip permutation test on the same contrast.
"""
import json, math, random
from collections import defaultdict

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
B_BOOT = 20000
B_PERM = 20000
SEED = 20260731

rows = [r for r in json.load(open(PATH)) if r.get("analysis_include") is True]

MODELS = sorted({r["model"] for r in rows})
M = len(MODELS)
MIDX = {m: i for i, m in enumerate(MODELS)}
SHORT = {m: m.split("/")[-1] for m in MODELS}

items = {r["question_id"] for r in rows}
clusters = sorted({r["cluster"] for r in rows})

print("=" * 78)
print("0. DATA CONFIRMATION")
print("=" * 78)
print(f"cells={len(rows)}  items={len(items)}  clusters={len(clusters)}  models={M}")

# cells per model, and completeness of the item x model grid
per_model_items = defaultdict(set)
for r in rows:
    per_model_items[r["model"]].add(r["question_id"])
for m in MODELS:
    print(f"  {SHORT[m]:<20} cells={len(per_model_items[m])}")
missing = []
for q in sorted(items):
    for m in MODELS:
        if q not in per_model_items[m]:
            missing.append((q, SHORT[m]))
print(f"  incomplete item x model cells: {len(missing)} -> {missing}")

# item -> cluster map (verify each item belongs to exactly one cluster)
item_cluster = {}
bad = 0
for r in rows:
    q, c = r["question_id"], r["cluster"]
    if q in item_cluster and item_cluster[q] != c:
        bad += 1
    item_cluster[q] = c
print(f"  items with inconsistent cluster assignment: {bad}")

# ---------------------------------------------------------------- observed
print()
print("=" * 78)
print("1. OBSERVED MARGINALS (recomputed from analysis_include==true)")
print("=" * 78)
nA = [0] * M; sA = [0] * M; sB = [0] * M
for r in rows:
    i = MIDX[r["model"]]
    nA[i] += 1
    sA[i] += r["A_correct"]
    sB[i] += r["B_correct"]
obs_A = [sA[i] / nA[i] for i in range(M)]
obs_B = [sB[i] / nA[i] for i in range(M)]
obs_D = [obs_A[i] - obs_B[i] for i in range(M)]
print(f"{'model':<20} {'n':>5} {'A_acc':>8} {'B_acc':>8} {'delta(pp)':>10}  A_k/B_k")
for i, m in enumerate(MODELS):
    print(f"{SHORT[m]:<20} {nA[i]:>5} {obs_A[i]*100:>7.1f}% {obs_B[i]*100:>7.1f}% "
          f"{obs_D[i]*100:>9.1f}   {sA[i]}/{sB[i]}")

# --------------------------------------------- per-cluster sufficient stats
# delta_m = (sum_A_m - sum_B_m) / n_m ; all quantities additive over clusters
cl_n = defaultdict(lambda: [0] * M)
cl_a = defaultdict(lambda: [0] * M)
cl_b = defaultdict(lambda: [0] * M)
for r in rows:
    i = MIDX[r["model"]]; c = r["cluster"]
    cl_n[c][i] += 1
    cl_a[c][i] += r["A_correct"]
    cl_b[c][i] += r["B_correct"]
CL = sorted(cl_n)
K = len(CL)
CN = [cl_n[c] for c in CL]
CA = [cl_a[c] for c in CL]
CB = [cl_b[c] for c in CL]

PAIRS = [(i, j) for i in range(M) for j in range(i + 1, M)]
obs_contrast = {p: obs_D[p[0]] - obs_D[p[1]] for p in PAIRS}

# ------------------------------------------------------------- cluster boot
print()
print("=" * 78)
print("2. CLUSTER BOOTSTRAP  (B=%d, resample the %d clusters with replacement," % (B_BOOT, K))
print("   recompute all 4 deltas inside each replicate so the item x model")
print("   dependence is preserved; seed=%d)" % SEED)
print("=" * 78)
rng = random.Random(SEED)
boot_D = [[] for _ in range(M)]
boot_C = {p: [] for p in PAIRS}
boot_A = [[] for _ in range(M)]
degenerate = 0
for b in range(B_BOOT):
    idx = [rng.randrange(K) for _ in range(K)]
    n = [0] * M; a = [0] * M; bb = [0] * M
    for t in idx:
        cn, ca, cb = CN[t], CA[t], CB[t]
        for i in range(M):
            n[i] += cn[i]; a[i] += ca[i]; bb[i] += cb[i]
    if min(n) == 0:
        degenerate += 1
        continue
    d = [(a[i] - bb[i]) / n[i] for i in range(M)]
    for i in range(M):
        boot_D[i].append(d[i])
        boot_A[i].append(a[i] / n[i])
    for p in PAIRS:
        boot_C[p].append(d[p[0]] - d[p[1]])

def pct(v, q):
    s = sorted(v); n = len(s)
    if n == 1: return s[0]
    h = (n - 1) * q
    lo = int(math.floor(h)); hi = min(lo + 1, n - 1)
    return s[lo] + (h - lo) * (s[hi] - s[lo])

def sd(v):
    n = len(v); mu = sum(v) / n
    return math.sqrt(sum((x - mu) ** 2 for x in v) / (n - 1))

def boot_p(v, obs):
    """Two-sided bootstrap p by inverting the percentile interval:
    p = 2*min(Pr*(theta*<=0), Pr*(theta*>=0)), with the +1 continuity
    correction of Davison & Hinkley (1997, eq. 4.10). Capped at 1."""
    n = len(v)
    le = sum(1 for x in v if x <= 0)
    ge = sum(1 for x in v if x >= 0)
    return min(1.0, 2 * min((le + 1) / (n + 1), (ge + 1) / (n + 1)))

print(f"replicates used={len(boot_C[PAIRS[0]])}  degenerate dropped={degenerate}")
print()
print("Per-model delta, cluster-bootstrap 95% percentile CI:")
for i, m in enumerate(MODELS):
    print(f"  {SHORT[m]:<20} delta={obs_D[i]*100:>6.2f}pp  "
          f"[{pct(boot_D[i],0.025)*100:>6.2f}, {pct(boot_D[i],0.975)*100:>6.2f}]  "
          f"SE={sd(boot_D[i])*100:.2f}pp")

# ------------------------------------------- cluster sign-flip permutation
# For the pair (m,m'), the per-item quantity is
#   g(item) = (A_m - B_m) - (A_m' - B_m')   in {-2,-1,0,1,2}
# Under H0 the two models degrade identically, so the joint distribution of
# g within a cluster is symmetric about 0 -> flip the sign of each cluster's
# total, keeping the denominator fixed. Valid with clusters as the exchange
# unit; it is a randomisation test, not an asymptotic one.
cl_g = {p: [0] * K for p in PAIRS}
cl_gn = {p: [0] * K for p in PAIRS}
byitem = defaultdict(dict)
for r in rows:
    byitem[r["question_id"]][MIDX[r["model"]]] = (r["A_correct"], r["B_correct"])
clpos = {c: t for t, c in enumerate(CL)}
for q, d in byitem.items():
    t = clpos[item_cluster[q]]
    for p in PAIRS:
        i, j = p
        if i in d and j in d:
            gi = d[i][0] - d[i][1]
            gj = d[j][0] - d[j][1]
            cl_g[p][t] += gi - gj
            cl_gn[p][t] += 1

perm_p = {}
rng2 = random.Random(SEED + 1)
for p in PAIRS:
    denom = sum(cl_gn[p])
    stat = sum(cl_g[p]) / denom
    ge = 0
    for _ in range(B_PERM):
        s = 0
        for t in range(K):
            v = cl_g[p][t]
            if v:
                s += v if rng2.getrandbits(1) else -v
        if abs(s / denom) >= abs(stat) - 1e-12:
            ge += 1
    perm_p[p] = (ge + 1) / (B_PERM + 1)

# --------------------------------------------------------------- Holm
res = []
for p in PAIRS:
    v = boot_C[p]
    res.append({
        "pair": p,
        "obs": obs_contrast[p],
        "lo": pct(v, 0.025), "hi": pct(v, 0.975),
        "se": sd(v),
        "p_boot": boot_p(v, obs_contrast[p]),
        "p_perm": perm_p[p],
    })

def holm(entries, key, out):
    order = sorted(range(len(entries)), key=lambda k: entries[k][key])
    n = len(entries); running = 0.0
    for rank, k in enumerate(order):
        adj = min(1.0, (n - rank) * entries[k][key])
        running = max(running, adj)   # enforce monotonicity
        entries[k][out] = running

holm(res, "p_boot", "p_holm_boot")
holm(res, "p_perm", "p_holm_perm")

print()
print("=" * 78)
print("3. SIX PAIRWISE CONTRASTS OF THE DELTA  (delta_i - delta_j, pp)")
print("   Holm-Bonferroni across the 6 tests, alpha=0.05")
print("=" * 78)
hdr = (f"{'contrast':<43} {'diff':>7} {'95% CI (boot)':>18} {'p_boot':>8} "
       f"{'p_Holm':>8} {'p_perm':>8} {'pHolm_pm':>9}  sig")
print(hdr)
print("-" * len(hdr))
for e in sorted(res, key=lambda x: -abs(x["obs"])):
    i, j = e["pair"]
    name = f"{SHORT[MODELS[i]]} - {SHORT[MODELS[j]]}"
    ci = f"[{e['lo']*100:>6.2f},{e['hi']*100:>6.2f}]"
    sig = "***" if e["p_holm_boot"] < 0.001 else "**" if e["p_holm_boot"] < 0.01 \
        else "*" if e["p_holm_boot"] < 0.05 else "ns"
    print(f"{name:<43} {e['obs']*100:>7.2f} {ci:>18} {e['p_boot']:>8.4f} "
          f"{e['p_holm_boot']:>8.4f} {e['p_perm']:>8.4f} {e['p_holm_perm']:>9.4f}  {sig}")
print()
print("NOTE: the bootstrap p-value floor is 2/(B+1) = %.5f; the permutation floor"
      % (2 / (B_BOOT + 1)))
print("      is 1/(B+1) = %.5f. Values at the floor are reported as '< floor'." % (1 / (B_PERM + 1)))

# ------------------------------------- 4. robustness vs baseline ability
print()
print("=" * 78)
print("4. IS ROBUSTNESS (small delta) ASSOCIATED WITH BASELINE ABILITY (high A)?")
print("=" * 78)
x = obs_A[:]   # baseline ability
y = obs_D[:]   # delta (loss)
n = M

def pearson(x, y):
    n = len(x); mx = sum(x) / n; my = sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x); syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy)

def rank(v):
    order = sorted(range(len(v)), key=lambda k: v[k])
    r = [0.0] * len(v); k = 0
    while k < len(order):
        j = k
        while j + 1 < len(order) and v[order[j + 1]] == v[order[k]]:
            j += 1
        avg = (k + j) / 2 + 1
        for t in range(k, j + 1):
            r[order[t]] = avg
        k = j + 1
    return r

r_p = pearson(x, y)
r_s = pearson(rank(x), rank(y))

# exact permutation over all 4! = 24 relabelings of y against x
from itertools import permutations
allp = list(permutations(range(n)))
ge_p = sum(1 for perm in allp if abs(pearson(x, [y[k] for k in perm])) >= abs(r_p) - 1e-12)
ge_s = sum(1 for perm in allp
           if abs(pearson(rank(x), rank([y[k] for k in perm]))) >= abs(r_s) - 1e-12)
print(f"n = {n} models (this is the entire sample size for this question)")
print(f"  Pearson  r(A_acc, delta) = {r_p:+.4f}   exact permutation p = {ge_p}/24 = {ge_p/24:.4f}")
print(f"  Spearman rho             = {r_s:+.4f}   exact permutation p = {ge_s}/24 = {ge_s/24:.4f}")
print(f"  Smallest attainable two-sided exact p with n=4 is 2/24 = {2/24:.4f}")
print("  -> no arrangement of 4 points can reach p<0.05. The test has no power.")

# bootstrap the correlation to show its instability (clusters resampled;
# the 4 model deltas move together, so this is the honest uncertainty)
rb = []
for b in range(len(boot_D[0])):
    xb = [boot_A[i][b] for i in range(M)]
    yb = [boot_D[i][b] for i in range(M)]
    try:
        rb.append(pearson(xb, yb))
    except ZeroDivisionError:
        pass
print(f"  Cluster-bootstrap 95% CI for Pearson r: "
      f"[{pct(rb,0.025):+.3f}, {pct(rb,0.975):+.3f}]  (median {pct(rb,0.5):+.3f})")
sign_flip = sum(1 for v in rb if v > 0) / len(rb)
print(f"  fraction of bootstrap replicates with r > 0: {sign_flip:.3f}")

# ---- ceiling-free reframing: conditional retention among A-correct items
print()
print("  Ceiling problem: delta is bounded above by A_acc, so a low-A model")
print("  mechanically has more room to lose. Two ceiling-free quantities:")
print()
print(f"{'model':<20} {'A_acc':>7} {'P(B ok | A ok)':>15} {'n(A ok)':>8} {'odds-ratio B/A':>15}")
cond = {}
for m in MODELS:
    i = MIDX[m]
    nAok = sum(1 for r in rows if r["model"] == m and r["A_correct"] == 1)
    nBokAok = sum(1 for r in rows if r["model"] == m and r["A_correct"] == 1 and r["B_correct"] == 1)
    cond[m] = nBokAok / nAok
    oa = obs_A[i] / (1 - obs_A[i]); ob = obs_B[i] / (1 - obs_B[i])
    print(f"{SHORT[m]:<20} {obs_A[i]*100:>6.1f}% {cond[m]*100:>14.1f}% {nAok:>8} {ob/oa:>15.3f}")

r_p2 = pearson([obs_A[i] for i in range(M)], [cond[m] for m in MODELS])
ge_p2 = sum(1 for perm in allp
            if abs(pearson([obs_A[i] for i in range(M)],
                           [[cond[m] for m in MODELS][k] for k in perm])) >= abs(r_p2) - 1e-12)
print(f"\n  Pearson r(A_acc, P(B ok|A ok)) = {r_p2:+.4f}  exact perm p = {ge_p2}/24 = {ge_p2/24:.4f}")

# ---- strongest ceiling-free test: common subset where ALL 4 models got A right
common = [q for q in items
          if len(byitem[q]) == M and all(byitem[q][i][0] == 1 for i in range(M))]
print()
print(f"  Common-subset analysis: {len(common)} items that ALL 4 models answered")
print("  correctly under A. On this subset baseline ability is equalised by")
print("  construction (A_acc = 100% for every model), so any remaining spread in")
print("  B accuracy is robustness that is NOT explained by baseline ability.")
print()
sub_B = []
for i, m in enumerate(MODELS):
    k = sum(byitem[q][i][1] for q in common)
    sub_B.append(k / len(common))
    print(f"    {SHORT[m]:<20} B_acc on common subset = {k}/{len(common)} = {k/len(common)*100:>5.1f}%")
print(f"    spread = {(max(sub_B)-min(sub_B))*100:.1f}pp")

# cluster bootstrap CI for the common-subset B accuracies and their contrasts
csub = defaultdict(lambda: [0, [0] * M])
for q in common:
    c = item_cluster[q]
    csub[c][0] += 1
    for i in range(M):
        csub[c][1][i] += byitem[q][i][1]
CS = sorted(csub); KS = len(CS)
CSn = [csub[c][0] for c in CS]; CSk = [csub[c][1] for c in CS]
rng3 = random.Random(SEED + 2)
sb = {p: [] for p in PAIRS}
sbm = [[] for _ in range(M)]
for b in range(B_BOOT):
    idx = [rng3.randrange(KS) for _ in range(KS)]
    tot = 0; kk = [0] * M
    for t in idx:
        tot += CSn[t]
        for i in range(M):
            kk[i] += CSk[t][i]
    if tot == 0: continue
    acc = [kk[i] / tot for i in range(M)]
    for i in range(M): sbm[i].append(acc[i])
    for p in PAIRS: sb[p].append(acc[p[0]] - acc[p[1]])
print(f"    (cluster bootstrap over the {KS} clusters represented in the subset)")
for i, m in enumerate(MODELS):
    print(f"    {SHORT[m]:<20} 95% CI [{pct(sbm[i],0.025)*100:>5.1f},{pct(sbm[i],0.975)*100:>5.1f}]")
sres = []
for p in PAIRS:
    sres.append({"pair": p, "obs": sub_B[p[0]] - sub_B[p[1]],
                 "lo": pct(sb[p], 0.025), "hi": pct(sb[p], 0.975),
                 "p_boot": boot_p(sb[p], sub_B[p[0]] - sub_B[p[1]])})
holm(sres, "p_boot", "p_holm")
print()
print("    Pairwise contrasts on the common subset (Holm across the same 6 tests):")
for e in sorted(sres, key=lambda x: -abs(x["obs"])):
    i, j = e["pair"]
    nm = f"{SHORT[MODELS[i]]} - {SHORT[MODELS[j]]}"
    sig = "*" if e["p_holm"] < 0.05 else "ns"
    print(f"      {nm:<43} {e['obs']*100:>6.2f}pp "
          f"[{e['lo']*100:>6.2f},{e['hi']*100:>6.2f}] p_Holm={e['p_holm']:.4f} {sig}")

# ---- rank agreement, stated plainly
print()
order_A = sorted(range(M), key=lambda i: -obs_A[i])
order_D = sorted(range(M), key=lambda i: obs_D[i])
print("  Rank by baseline A accuracy (best first): " + ", ".join(SHORT[MODELS[i]] for i in order_A))
print("  Rank by robustness, smallest delta first: " + ", ".join(SHORT[MODELS[i]] for i in order_D))
print("  Rank by common-subset B acc (best first): " +
      ", ".join(SHORT[MODELS[i]] for i in sorted(range(M), key=lambda i: -sub_B[i])))

json.dump({
    "models": [SHORT[m] for m in MODELS],
    "A": obs_A, "B": obs_B, "delta": obs_D,
    "contrasts": [{"pair": [SHORT[MODELS[e["pair"][0]]], SHORT[MODELS[e["pair"][1]]]],
                   "obs_pp": e["obs"] * 100, "ci_pp": [e["lo"] * 100, e["hi"] * 100],
                   "p_boot": e["p_boot"], "p_holm_boot": e["p_holm_boot"],
                   "p_perm": e["p_perm"], "p_holm_perm": e["p_holm_perm"]} for e in res],
    "pearson_r": r_p, "spearman": r_s, "perm_p_pearson": ge_p / 24,
    "r_boot_ci": [pct(rb, 0.025), pct(rb, 0.975)],
    "common_subset_n": len(common), "common_subset_B": sub_B,
    "cond_retention": {SHORT[m]: cond[m] for m in MODELS},
}, open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
        "experiment-31-07-26/analysis/prim_model_contrasts_out.json", "w"), indent=1)
print("\nwrote prim_model_contrasts_out.json")

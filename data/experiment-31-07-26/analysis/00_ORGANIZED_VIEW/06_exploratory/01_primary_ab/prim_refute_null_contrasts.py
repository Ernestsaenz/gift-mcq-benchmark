#!/usr/bin/env python
"""
INDEPENDENT recomputation of the three "null" per-model contrasts.
Stdlib only. Different seed, independently written estimator + resampler.

Target claim: gemma/qwen/glm are mutually indistinguishable in how much they
lose (A->B), all CIs comfortably straddle zero.

Scales examined:
  (1) raw pp drop            delta_m = A_m - B_m           <- what the claim uses
  (2) conditional retention  P(B ok | A ok)                <- ceiling-free
  (3) common-subset B acc    B acc on items ALL models got right under A
  (4) log odds ratio         log[ (B/(1-B)) / (A/(1-A)) ]  <- ceiling-free
"""
import json, math, random
from collections import defaultdict

PATH = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
        "experiment-31-07-26/analysis/paired_clean.json")
B_BOOT = 60000
B_PERM = 60000
SEED = 987654321          # deliberately different from prim_model_contrasts.py

raw = json.load(open(PATH))
rows = [r for r in raw if r.get("analysis_include") is True]

MODELS = sorted({r["model"] for r in rows})
M = len(MODELS)
MI = {m: i for i, m in enumerate(MODELS)}
SH = {m: m.split("/")[-1] for m in MODELS}
items = sorted({r["question_id"] for r in rows})
clusters = sorted({r["cluster"] for r in rows})
K = len(clusters)
CPOS = {c: t for t, c in enumerate(clusters)}
item_cluster = {r["question_id"]: r["cluster"] for r in rows}

print("=== 0. DATA ===")
print(f"raw rows={len(raw)}  clean cells={len(rows)}  items={len(items)}  "
      f"clusters={K}  models={M}")
percell = defaultdict(int)
for r in rows:
    percell[r["model"]] += 1
for m in MODELS:
    print(f"   {SH[m]:<20} n={percell[m]}")

# ---- observed marginals -----------------------------------------------------
nA = [0]*M; sA = [0]*M; sB = [0]*M; sBA = [0]*M
for r in rows:
    i = MI[r["model"]]
    nA[i] += 1; sA[i] += r["A_correct"]; sB[i] += r["B_correct"]
    if r["A_correct"] == 1 and r["B_correct"] == 1:
        sBA[i] += 1
obsA = [sA[i]/nA[i] for i in range(M)]
obsB = [sB[i]/nA[i] for i in range(M)]
obsD = [obsA[i]-obsB[i] for i in range(M)]
obsR = [sBA[i]/sA[i] for i in range(M)]           # P(B ok | A ok)

print("\n=== 1. OBSERVED (recomputed) ===")
print(f"{'model':<20}{'n':>6}{'A':>9}{'B':>9}{'drop pp':>10}{'P(B|A)':>10}")
for i, m in enumerate(MODELS):
    print(f"{SH[m]:<20}{nA[i]:>6}{obsA[i]*100:>8.1f}%{obsB[i]*100:>8.1f}%"
          f"{obsD[i]*100:>10.2f}{obsR[i]*100:>9.1f}%")

# ---- per-cluster sufficient statistics --------------------------------------
cn = [[0]*M for _ in range(K)]        # cells
ca = [[0]*M for _ in range(K)]        # A correct
cb = [[0]*M for _ in range(K)]        # B correct
cba = [[0]*M for _ in range(K)]       # A&B correct
for r in rows:
    i = MI[r["model"]]; t = CPOS[r["cluster"]]
    cn[t][i] += 1; ca[t][i] += r["A_correct"]; cb[t][i] += r["B_correct"]
    if r["A_correct"] and r["B_correct"]:
        cba[t][i] += 1

# ---- common subset: items every model answered correctly under A ------------
byitem = defaultdict(dict)
for r in rows:
    byitem[r["question_id"]][MI[r["model"]]] = (r["A_correct"], r["B_correct"])
common = [q for q in items
          if len(byitem[q]) == M and all(byitem[q][i][0] == 1 for i in range(M))]
csn = [0]*K
csk = [[0]*M for _ in range(K)]
for q in common:
    t = CPOS[item_cluster[q]]
    csn[t] += 1
    for i in range(M):
        csk[t][i] += byitem[q][i][1]
obsCS = [sum(csk[t][i] for t in range(K))/len(common) for i in range(M)]

# ---- log odds ratio ---------------------------------------------------------
def lor(a, b):
    return math.log((b/(1-b))/(a/(1-a)))
obsL = [lor(obsA[i], obsB[i]) for i in range(M)]

PAIRS = [(i, j) for i in range(M) for j in range(i+1, M)]

# ---- cluster bootstrap ------------------------------------------------------
rng = random.Random(SEED)
bD = {p: [] for p in PAIRS}
bR = {p: [] for p in PAIRS}
bC = {p: [] for p in PAIRS}
bL = {p: [] for p in PAIRS}
bDm = [[] for _ in range(M)]
used = 0
for _ in range(B_BOOT):
    idx = [rng.randrange(K) for _ in range(K)]
    n = [0]*M; a = [0]*M; b = [0]*M; ab = [0]*M
    tot = 0; kk = [0]*M
    for t in idx:
        rn, ra, rb, rab = cn[t], ca[t], cb[t], cba[t]
        tot += csn[t]
        ck = csk[t]
        for i in range(M):
            n[i] += rn[i]; a[i] += ra[i]; b[i] += rb[i]; ab[i] += rab[i]
            kk[i] += ck[i]
    if min(n) == 0 or min(a) == 0 or tot == 0:
        continue
    used += 1
    d = [(a[i]-b[i])/n[i] for i in range(M)]
    rr = [ab[i]/a[i] for i in range(M)]
    cs = [kk[i]/tot for i in range(M)]
    ok_l = all(0 < a[i] < n[i] and 0 < b[i] < n[i] for i in range(M))
    if ok_l:
        ll = [lor(a[i]/n[i], b[i]/n[i]) for i in range(M)]
    for i in range(M):
        bDm[i].append(d[i])
    for p in PAIRS:
        bD[p].append(d[p[0]]-d[p[1]])
        bR[p].append(rr[p[0]]-rr[p[1]])
        bC[p].append(cs[p[0]]-cs[p[1]])
        if ok_l:
            bL[p].append(ll[p[0]]-ll[p[1]])

def pct(v, q):
    s = sorted(v); n = len(s)
    h = (n-1)*q; lo = int(math.floor(h)); hi = min(lo+1, n-1)
    return s[lo] + (h-lo)*(s[hi]-s[lo])

def sd(v):
    n = len(v); mu = sum(v)/n
    return math.sqrt(sum((x-mu)**2 for x in v)/(n-1))

def p_percentile(v):
    """two-sided percentile-inversion bootstrap p, Davison & Hinkley continuity"""
    n = len(v)
    le = sum(1 for x in v if x <= 0)
    ge = sum(1 for x in v if x >= 0)
    return min(1.0, 2*min((le+1)/(n+1), (ge+1)/(n+1)))

def normcdf(z):
    return 0.5*(1+math.erf(z/math.sqrt(2)))

def p_wald(obs, se):
    if se == 0:
        return 1.0
    return 2*(1-normcdf(abs(obs)/se))

def holm(ps):
    n = len(ps)
    order = sorted(range(n), key=lambda k: ps[k])
    out = [0.0]*n; run = 0.0
    for rank, k in enumerate(order):
        adj = min(1.0, (n-rank)*ps[k])
        run = max(run, adj)
        out[k] = run
    return out

# ---- cluster sign-flip permutation (independent implementation) -------------
# per-item g = (A-B)_i - (A-B)_j ; cluster totals; flip cluster sign
cg = {p: [0]*K for p in PAIRS}
cgn = {p: 0 for p in PAIRS}
for q in items:
    d = byitem[q]; t = CPOS[item_cluster[q]]
    for p in PAIRS:
        i, j = p
        if i in d and j in d:
            cg[p][t] += (d[i][0]-d[i][1]) - (d[j][0]-d[j][1])
            cgn[p] += 1
rng2 = random.Random(SEED+7)
permp = {}
for p in PAIRS:
    stat = abs(sum(cg[p]))
    nz = [v for v in cg[p] if v != 0]
    ge = 0
    for _ in range(B_PERM):
        s = 0
        for v in nz:
            s += v if rng2.getrandbits(1) else -v
        if abs(s) >= stat - 1e-9:
            ge += 1
    permp[p] = (ge+1)/(B_PERM+1)

print(f"\n=== 2. CLUSTER BOOTSTRAP  B={B_BOOT} used={used} seed={SEED} ===")
print("Per-model drop with cluster-bootstrap 95% percentile CI:")
for i, m in enumerate(MODELS):
    print(f"   {SH[m]:<20} {obsD[i]*100:>6.2f}pp  "
          f"[{pct(bDm[i],.025)*100:>6.2f},{pct(bDm[i],.975)*100:>6.2f}]  SE={sd(bDm[i])*100:.2f}")

def table(title, obs_vals, boots, unit="pp", scale=100.0, perm=None):
    print(f"\n--- {title} ---")
    ps = []
    recs = []
    for p in PAIRS:
        v = boots[p]
        o = obs_vals[p[0]] - obs_vals[p[1]]
        recs.append(dict(p=p, o=o, lo=pct(v,.025), hi=pct(v,.975), se=sd(v),
                         pb=p_percentile(v), pw=p_wald(o, sd(v))))
        ps.append(recs[-1]["pb"])
    hp = holm(ps)
    for k, e in enumerate(recs):
        e["holm"] = hp[k]
    print(f"{'contrast':<42}{'diff':>9}{'95% CI':>20}{'SE':>8}{'p_boot':>9}"
          f"{'p_wald':>9}{'Holm':>8}" + ("  p_perm" if perm else ""))
    for e in sorted(recs, key=lambda x: -abs(x["o"])):
        i, j = e["p"]
        nm = f"{SH[MODELS[i]]} - {SH[MODELS[j]]}"
        ci = f"[{e['lo']*scale:>7.2f},{e['hi']*scale:>7.2f}]"
        extra = f"  {perm[e['p']]:.4f}" if perm else ""
        print(f"{nm:<42}{e['o']*scale:>9.2f}{ci:>20}{e['se']*scale:>8.2f}"
              f"{e['pb']:>9.4f}{e['pw']:>9.4f}{e['holm']:>8.4f}{extra}")
    return recs

r1 = table("(1) RAW pp DROP  delta = A - B   [the claim's scale]", obsD, bD, perm=permp)
r2 = table("(2) CONDITIONAL RETENTION  P(B ok | A ok)  [ceiling-free]", obsR, bR)
print(f"     common subset n = {len(common)} items "
      f"(all {M} models correct under A)")
for i, m in enumerate(MODELS):
    print(f"       {SH[m]:<20} common-subset B acc = {obsCS[i]*100:.1f}%")
r3 = table("(3) COMMON-SUBSET B ACCURACY  [baseline equalised by construction]",
           obsCS, bC)
r4 = table("(4) LOG ODDS RATIO of B vs A  [ceiling-free]", obsL, bL, scale=1.0)

# ---- equivalence assessment on the claim's own scale ------------------------
print("\n=== 3. IS 'INDISTINGUISHABLE' SUPPORTED? (TOST-style read of the CI) ===")
print("For each of the three null contrasts on the raw pp scale, the largest")
print("true difference still inside the 95% CI:")
for e in r1:
    i, j = e["p"]
    if "gemini" in SH[MODELS[i]] or "gemini" in SH[MODELS[j]]:
        continue
    nm = f"{SH[MODELS[i]]} - {SH[MODELS[j]]}"
    print(f"   {nm:<42} CI [{e['lo']*100:>6.2f},{e['hi']*100:>6.2f}]  "
          f"max |diff| still compatible = {max(abs(e['lo']),abs(e['hi']))*100:.2f}pp  "
          f"width={ (e['hi']-e['lo'])*100:.2f}pp")
print("\n  Reference: the SIGNIFICANT gemini-qwen contrast is 7.69pp.")
print("  Any null CI whose bound exceeds 7.69pp cannot rule out a difference as")
print("  large as one this study did call significant.")

json.dump({
    "seed": SEED, "B_BOOT": B_BOOT, "used": used,
    "models": [SH[m] for m in MODELS],
    "A": obsA, "B": obsB, "drop": obsD, "retention": obsR,
    "common_n": len(common), "common_B": obsCS, "logOR": obsL,
    "scales": {
        name: [{"pair": [SH[MODELS[e["p"][0]]], SH[MODELS[e["p"][1]]]],
                "diff": e["o"], "lo": e["lo"], "hi": e["hi"], "se": e["se"],
                "p_boot": e["pb"], "p_wald": e["pw"], "p_holm": e["holm"]}
               for e in recs]
        for name, recs in [("drop_pp", r1), ("retention", r2),
                           ("common_subset_B", r3), ("log_or", r4)]
    },
    "perm_p_drop": {f"{SH[MODELS[p[0]]]}-{SH[MODELS[p[1]]]}": permp[p] for p in PAIRS},
}, open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
        "experiment-31-07-26/analysis/prim_refute_null_contrasts.json", "w"), indent=1)
print("\nwrote prim_refute_null_contrasts.json")

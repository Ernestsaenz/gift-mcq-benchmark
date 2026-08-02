#!/usr/bin/env python3
"""
stats_ceiling_contrasts.py

Part 2 of the multiplicity/ceiling work.

  (a) CEILING COMPRESSION quantified directly: the probability scale is locally
      flat near p=1 (slope dp/dtheta = p(1-p)), so an identical latent
      degradation produces a much smaller percentage-point delta for a model
      operating at 97.8% than for one at 79.4%. Compute the compression factor
      and the counterfactual "what would delta be if the latent hit were equal".
  (b) CONDITIONAL RETENTION -- P(B wrong | A right) -- the base-rate-free
      paired robustness measure, plus its bootstrap CI.
  (c) BETWEEN-MODEL CONTRASTS -- the 6 pairwise "model X is more robust than
      model Y" claims, each tested by a cluster-level label-swap permutation on
      the shared items, then Holm/BH corrected. This is where multiplicity
      actually bites.

Standard library only. All p-values computed here.
"""

import json, math, random, itertools, collections, os

HERE = os.path.dirname(os.path.abspath(__file__))
recs = [r for r in json.load(open(os.path.join(HERE, "paired_clean.json")))
        if r["analysis_include"]]
MODELS = sorted({r["model"] for r in recs})
SEED = 20260731
NPERM = 50000
BOOT = 20000
CHANCE = 0.25

out = []
def P(s=""):
    out.append(s); print(s)

def logistic(x):
    return 1.0 / (1.0 + math.exp(-x))

def haldane_lo(succ, n):
    return math.log((succ + 0.5) / (n - succ + 0.5))

by_model = {m: [r for r in recs if r["model"] == m] for m in MODELS}

def stats(rows):
    n = len(rows)
    a = sum(r["A_correct"] for r in rows)
    bc = sum(r["B_correct"] for r in rows)
    b = sum(1 for r in rows if r["A_correct"] == 1 and r["B_correct"] == 0)
    c = sum(1 for r in rows if r["A_correct"] == 0 and r["B_correct"] == 1)
    return dict(n=n, A=a, B=bc, pA=a/n, pB=bc/n, b=b, c=c, delta=(a-bc)/n)

S = {m: stats(by_model[m]) for m in MODELS}

# ------------------------------------------------------------------ (a)
P("=" * 78)
P("(a) CEILING COMPRESSION -- local sensitivity of the percentage-point scale")
P("=" * 78)
P("slope of probability w.r.t. latent ability at the model's own operating")
P("point in condition A:  dp/dtheta = pA*(1-pA).  A flat slope means a large")
P("latent degradation is squeezed into a small pp delta.")
P("")
P(f"{'model':28s} {'pA':>7s} {'errA':>7s} {'pA(1-pA)':>9s} {'compression vs gemma':>22s}")
slope = {m: S[m]["pA"] * (1 - S[m]["pA"]) for m in MODELS}
ref = max(slope, key=lambda m: slope[m])          # steepest slope = least compressed
for m in MODELS:
    P(f"{m:28s} {S[m]['pA']:7.4f} {1-S[m]['pA']:7.4f} {slope[m]:9.5f} "
      f"{slope[ref]/slope[m]:22.2f}x")
P(f"(reference = {ref}, the least ceiling-compressed model)")

P("")
P("error-rate multiplication (ceiling-free, directly interpretable):")
P(f"{'model':28s} {'err_A':>8s} {'err_B':>8s} {'err ratio':>10s}")
errmult = {}
for m in MODELS:
    ea, eb = 1 - S[m]["pA"], 1 - S[m]["pB"]
    errmult[m] = eb / ea if ea > 0 else float("nan")
    P(f"{m:28s} {ea:8.4f} {eb:8.4f} {errmult[m]:10.3f}x")

P("")
P("COUNTERFACTUAL: give every model the SAME latent (log-odds) degradation,")
P("then read off what the raw pp delta would look like.")
lo_shift = {m: haldane_lo(S[m]["A"], S[m]["n"]) - haldane_lo(S[m]["B"], S[m]["n"])
            for m in MODELS}
for donor in MODELS:
    sh = lo_shift[donor]
    P(f"  if all models suffered {donor.split('/')[-1]}'s log-odds shift "
      f"({sh:.4f}):")
    row = []
    for m in MODELS:
        pb = logistic(haldane_lo(S[m]["A"], S[m]["n"]) - sh)
        row.append(f"{m.split('/')[-1]}: delta={S[m]['pA']-pb:.4f}")
    P("      " + " | ".join(row))
P("")
P("=> identical latent damage yields raw deltas that differ by an order of")
P("   magnitude purely because of where each model sits on the curve.")

# ------------------------------------------------------------------ (b)
P("")
P("=" * 78)
P("(b) CONDITIONAL RETENTION -- P(B wrong | A right), base-rate free")
P("=" * 78)
P(f"{'model':28s} {'A-right':>8s} {'lost':>5s} {'loss rate':>10s} {'retention':>10s} "
  f"{'A-wrong':>8s} {'gained':>7s} {'gain rate':>10s}")
lossrate = {}
for m in MODELS:
    s = S[m]
    lr = s["b"] / s["A"]
    gr = s["c"] / (s["n"] - s["A"]) if s["n"] - s["A"] > 0 else float("nan")
    lossrate[m] = lr
    P(f"{m:28s} {s['A']:8d} {s['b']:5d} {lr:10.4f} {1-lr:10.4f} "
      f"{s['n']-s['A']:8d} {s['c']:7d} {gr:10.4f}")

# ------------------------------------------------------------------ rankings
METRICS = {
    "raw_delta":       {m: S[m]["delta"] for m in MODELS},
    "delta/pA":        {m: S[m]["delta"] / S[m]["pA"] for m in MODELS},
    "delta/(pA-.25)":  {m: S[m]["delta"] / (S[m]["pA"] - CHANCE) for m in MODELS},
    "log_odds_shift":  lo_shift,
    "err_multiplier":  errmult,
    "loss_rate":       lossrate,
    "cond_logOR":      {m: math.log((S[m]["b"] + .5) / (S[m]["c"] + .5)) for m in MODELS},
}
P("")
P("=" * 78)
P("RANKING UNDER EVERY CANDIDATE METRIC (1 = worst / least robust)")
P("=" * 78)
P(f"{'metric':20s} " + " ".join(f"{m.split('/')[-1][:14]:>15s}" for m in MODELS))
for k, d in METRICS.items():
    order = sorted(MODELS, key=lambda m: d[m], reverse=True)
    rk = {m: i + 1 for i, m in enumerate(order)}
    P(f"{k:20s} " + " ".join(f"{rk[m]:>15d}" for m in MODELS))
P("")
for k, d in METRICS.items():
    order = sorted(MODELS, key=lambda m: d[m], reverse=True)
    P(f"  {k:20s}: " + " > ".join(f"{m.split('/')[-1]}({d[m]:.3f})" for m in order))

# ------------------------------------------------------------------ (c)
P("")
P("=" * 78)
P("(c) BETWEEN-MODEL CONTRASTS -- 6 pairwise 'X degrades more than Y' claims")
P("cluster-level label-swap permutation on shared items, "
  f"NPERM={NPERM}, seed={SEED}")
P("=" * 78)

# per-item degradation d = A_correct - B_correct, per model
dmap = collections.defaultdict(dict)          # qid -> model -> d
cl_of = {}
for r in recs:
    dmap[r["question_id"]][r["model"]] = r["A_correct"] - r["B_correct"]
    cl_of[r["question_id"]] = r["cluster"]

rng = random.Random(SEED)
contrasts = []
for m1, m2 in itertools.combinations(MODELS, 2):
    qids = [q for q, dd in dmap.items() if m1 in dd and m2 in dd]
    pairs = [(cl_of[q], dmap[q][m1], dmap[q][m2]) for q in qids]
    n = len(pairs)
    obs = sum(p[1] - p[2] for p in pairs) / n
    byc = collections.defaultdict(list)
    for cl, d1, d2 in pairs:
        byc[cl].append((d1, d2))
    keys = list(byc)
    ge = 0
    for _ in range(NPERM):
        tot = 0
        for k in keys:
            if rng.random() < 0.5:
                for d1, d2 in byc[k]: tot += d1 - d2
            else:
                for d1, d2 in byc[k]: tot += d2 - d1
        if abs(tot / n) >= abs(obs) - 1e-12:
            ge += 1
    pval = (ge + 1) / (NPERM + 1)
    contrasts.append(dict(m1=m1, m2=m2, n=n, obs=obs, p=pval))

def holm(pvals, alpha=0.05):
    idx = sorted(range(len(pvals)), key=lambda i: pvals[i]); m = len(pvals)
    res = [None]*m; run = 0.0
    for rank, i in enumerate(idx):
        run = max(run, min(1.0, (m - rank) * pvals[i]))
        res[i] = dict(thr=alpha/(m-rank), adj=run)
    return res

def bh(pvals, alpha=0.05):
    idx = sorted(range(len(pvals)), key=lambda i: pvals[i]); m = len(pvals)
    res = [None]*m; run = 1.0
    for rank in range(m-1, -1, -1):
        i = idx[rank]
        run = min(run, min(1.0, pvals[i]*m/(rank+1)))
        res[i] = dict(thr=alpha*(rank+1)/m, adj=run)
    return res

cp = [c["p"] for c in contrasts]
CH, CB = holm(cp, 0.05), bh(cp, 0.05)
P(f"{'contrast':58s} {'n':>4s} {'d1-d2':>8s} {'p_perm':>9s} {'Holm':>9s} {'BH':>9s} {'surv':>5s}")
for i, c in enumerate(contrasts):
    tag = f"{c['m1'].split('/')[-1]} vs {c['m2'].split('/')[-1]}"
    surv = "YES" if CH[i]["adj"] < 0.05 else "no"
    P(f"{tag:58s} {c['n']:4d} {c['obs']:8.4f} {c['p']:9.5f} "
      f"{CH[i]['adj']:9.5f} {CB[i]['adj']:9.5f} {surv:>5s}")
P(f"  Holm thresholds (m=6): " +
  ", ".join(f"{0.05/(6-r):.5f}" for r in range(6)))
P(f"  BH   thresholds (m=6): " +
  ", ".join(f"{0.05*(r+1)/6:.5f}" for r in range(6)))

# same contrasts on the LOG-ODDS scale, via cluster bootstrap
P("")
P(f"Same 6 contrasts on the LOG-ODDS scale (cluster bootstrap B={BOOT}):")
clusters = sorted({r["cluster"] for r in recs})
bycl = collections.defaultdict(list)
for r in recs:
    bycl[r["cluster"]].append(r)
rng2 = random.Random(SEED + 7)
boot_lo = collections.defaultdict(list)
for _ in range(BOOT):
    rows = [r for _ in range(len(clusters))
            for r in bycl[clusters[rng2.randrange(len(clusters))]]]
    cur = {}
    good = True
    for m in MODELS:
        rs = [r for r in rows if r["model"] == m]
        if not rs: good = False; break
        s = stats(rs)
        cur[m] = haldane_lo(s["A"], s["n"]) - haldane_lo(s["B"], s["n"])
    if not good: continue
    for m1, m2 in itertools.combinations(MODELS, 2):
        boot_lo[(m1, m2)].append(cur[m1] - cur[m2])

def pct(v, q):
    v = sorted(v); k = (len(v)-1)*q
    lo, hi = math.floor(k), math.ceil(k)
    return v[lo] if lo == hi else v[lo]*(hi-k) + v[hi]*(k-lo)

lo_p = []
lo_rows = []
for m1, m2 in itertools.combinations(MODELS, 2):
    v = boot_lo[(m1, m2)]
    obs = lo_shift[m1] - lo_shift[m2]
    frac = sum(1 for x in v if x <= 0) / len(v)
    pboot = 2 * min(frac, 1 - frac)
    pboot = max(pboot, 1.0 / len(v))
    lo_p.append(pboot)
    lo_rows.append((m1, m2, obs, pct(v, .025), pct(v, .975), pboot))
LH, LB = holm(lo_p, 0.05), bh(lo_p, 0.05)
P(f"{'contrast':58s} {'dLO':>8s} {'95% CI':>20s} {'p_boot':>8s} {'Holm':>8s} {'surv':>5s}")
for i, (m1, m2, obs, lo, hi, pb) in enumerate(lo_rows):
    tag = f"{m1.split('/')[-1]} vs {m2.split('/')[-1]}"
    surv = "YES" if LH[i]["adj"] < 0.05 else "no"
    P(f"{tag:58s} {obs:8.4f} [{lo:8.4f},{hi:8.4f}] {pb:8.5f} {LH[i]['adj']:8.5f} {surv:>5s}")

# ------------------------------------------------------------------ retention CI
P("")
P(f"Cluster-bootstrap 95% CI on loss rate P(B wrong | A right), B={BOOT}:")
rng3 = random.Random(SEED + 11)
boot_lr = collections.defaultdict(list)
for _ in range(BOOT):
    rows = [r for _ in range(len(clusters))
            for r in bycl[clusters[rng3.randrange(len(clusters))]]]
    for m in MODELS:
        rs = [r for r in rows if r["model"] == m]
        if not rs: continue
        s = stats(rs)
        if s["A"] > 0:
            boot_lr[m].append(s["b"] / s["A"])
for m in MODELS:
    v = boot_lr[m]
    P(f"  {m:28s} {lossrate[m]:.4f}  95% CI [{pct(v,.025):.4f}, {pct(v,.975):.4f}]")

with open(os.path.join(HERE, "stats_ceiling_contrasts_output.txt"), "w") as fh:
    fh.write("\n".join(out) + "\n")

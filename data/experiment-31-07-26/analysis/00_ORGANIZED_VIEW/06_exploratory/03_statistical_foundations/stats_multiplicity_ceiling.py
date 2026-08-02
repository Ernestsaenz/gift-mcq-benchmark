#!/usr/bin/env python3
"""
stats_multiplicity_ceiling.py

Two threats to the tier-1 MCQ robustness claim:
  (1) MULTIPLICITY -- size of the hypothesis-test family, Holm-Bonferroni and
      Benjamini-Hochberg adjustment of the primary per-model A-vs-B tests.
  (2) CEILING     -- gemini sits at ~97.8% in condition A. Raw delta (pA - pB)
      is not comparable across models with different pA. Recompute the effect
      as a share of the maximum possible decline and as a log-odds change,
      and show how the model RANKING moves.

Standard library only. Every p-value is computed here, exactly, from the data.
No scipy/numpy.
"""

import json, math, random, itertools, collections, os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "paired_clean.json")
META = os.path.join(HERE, "dataset_meta.json")

CHANCE = 0.25            # 4 lettered options remain in both conditions
BOOT = 20000
SEED = 20260731

# ---------------------------------------------------------------- exact stats

def log_comb(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)

def binom_pmf_half(n, k):
    return math.exp(log_comb(n, k) - n * math.log(2.0))

def mcnemar_exact_p(b, c):
    """Two-sided exact McNemar: X ~ Bin(b+c, 1/2), doubled one-tail, capped at 1.
    b = A-correct & B-wrong (losses), c = A-wrong & B-correct (gains)."""
    n = b + c
    if n == 0:
        return 1.0
    lo = sum(binom_pmf_half(n, k) for k in range(0, b + 1))
    hi = sum(binom_pmf_half(n, k) for k in range(b, n + 1))
    return min(1.0, 2.0 * min(lo, hi))

def logit(p):
    return math.log(p / (1.0 - p))

def haldane_logodds(succ, n):
    """log-odds with Haldane-Anscombe 0.5 correction (needed at the ceiling)."""
    return math.log((succ + 0.5) / (n - succ + 0.5))

# ---------------------------------------------------------------- load

recs = [r for r in json.load(open(DATA)) if r["analysis_include"]]
meta = json.load(open(META))
MODELS = sorted({r["model"] for r in recs})

def cell_stats(rows):
    n = len(rows)
    if n == 0:
        return None
    a = sum(r["A_correct"] for r in rows)
    bcorr = sum(r["B_correct"] for r in rows)
    b = sum(1 for r in rows if r["A_correct"] == 1 and r["B_correct"] == 0)   # losses
    c = sum(1 for r in rows if r["A_correct"] == 0 and r["B_correct"] == 1)   # gains
    return dict(n=n, A=a, B=bcorr, pA=a / n, pB=bcorr / n,
                disc_b=b, disc_c=c, delta=(a - bcorr) / n,
                p=mcnemar_exact_p(b, c))

by_model = {m: [r for r in recs if r["model"] == m] for m in MODELS}
prim = {m: cell_stats(by_model[m]) for m in MODELS}

out = []
def P(s=""):
    out.append(s)
    print(s)

P("=" * 78)
P("PRIMARY PER-MODEL A-vs-B (exact McNemar, two-sided, no approximation)")
P("=" * 78)
P(f"{'model':28s} {'n':>4s} {'pA':>7s} {'pB':>7s} {'delta':>7s} {'b':>4s} {'c':>4s} {'p_exact':>10s}")
for m in MODELS:
    s = prim[m]
    P(f"{m:28s} {s['n']:4d} {s['pA']:7.4f} {s['pB']:7.4f} {s['delta']:7.4f} "
      f"{s['disc_b']:4d} {s['disc_c']:4d} {s['p']:10.3e}")

# ---------------------------------------------------------------- multiplicity

P("")
P("=" * 78)
P("(1) MULTIPLICITY -- size of the hypothesis-test family")
P("=" * 78)

FACTORS = {
    "correct_letter": lambda r: r["correct_letter"],
    "negated_stem":   lambda r: r["negated_stem"],
    "has_context":    lambda r: r["has_context"],
    "region":         lambda r: r["region"],
    "year":           lambda r: r["year"],
}

levels = {f: sorted({str(g(r)) for r in recs}) for f, g in FACTORS.items()}
n_levels = {f: len(v) for f, v in levels.items()}
P("factor levels present in the analysis set:")
for f in FACTORS:
    P(f"  {f:16s} {n_levels[f]:2d} levels: {', '.join(levels[f])}")

L = sum(n_levels.values())
n_primary = len(MODELS)
n_sub_permodel = L * len(MODELS)
n_sub_pooled = L
n_moderator_permodel = len(FACTORS) * len(MODELS)
n_moderator_pooled = len(FACTORS)
n_between_model = len(list(itertools.combinations(MODELS, 2)))
TOTAL = (n_primary + n_sub_permodel + n_sub_pooled +
         n_moderator_permodel + n_moderator_pooled + n_between_model)

P("")
P("test inventory for the full analysis programme as described:")
P(f"  primary per-model A-vs-B .................... {n_primary:4d}")
P(f"  subgroup A-vs-B, per model ({L} levels x 4) ... {n_sub_permodel:4d}")
P(f"  subgroup A-vs-B, pooled over models ......... {n_sub_pooled:4d}")
P(f"  moderator/interaction tests, per model ...... {n_moderator_permodel:4d}")
P(f"  moderator/interaction tests, pooled ......... {n_moderator_pooled:4d}")
P(f"  between-model contrasts on delta (4 choose 2) {n_between_model:4d}")
P(f"  {'TOTAL':44s} {TOTAL:4d}")
P(f"  expected false positives at alpha=.05 if all null: {0.05*TOTAL:.1f}")
P(f"  P(>=1 false positive) if all null & independent : "
  f"{1-0.95**TOTAL:.4f}")

# --- Holm-Bonferroni and BH on the 4 PRIMARY p-values
def holm(pvals, alpha=0.05):
    idx = sorted(range(len(pvals)), key=lambda i: pvals[i])
    m = len(pvals)
    res = [None] * m
    running = 0.0
    for rank, i in enumerate(idx):
        thr = alpha / (m - rank)
        adj = min(1.0, (m - rank) * pvals[i])
        running = max(running, adj)          # enforce monotonicity
        res[i] = dict(rank=rank + 1, thr=thr, adj=running)
    return res

def bh(pvals, alpha=0.05):
    idx = sorted(range(len(pvals)), key=lambda i: pvals[i])
    m = len(pvals)
    res = [None] * m
    running = 1.0
    for rank in range(m - 1, -1, -1):
        i = idx[rank]
        adj = min(1.0, pvals[i] * m / (rank + 1))
        running = min(running, adj)          # step-up monotonicity
        res[i] = dict(rank=rank + 1, thr=alpha * (rank + 1) / m, adj=running)
    return res

pv = [prim[m]["p"] for m in MODELS]
H = holm(pv, 0.05)
B = bh(pv, 0.05)

P("")
P("Holm-Bonferroni and Benjamini-Hochberg on the m=4 PRIMARY per-model tests")
P(f"{'model':28s} {'p_raw':>11s} {'rank':>4s} {'Holm thr':>9s} {'Holm adj':>11s} "
  f"{'BH thr':>8s} {'BH adj':>11s} {'survives':>9s}")
for i, m in enumerate(MODELS):
    surv = "YES" if (H[i]["adj"] < 0.05 and B[i]["adj"] < 0.05) else "no"
    P(f"{m:28s} {pv[i]:11.3e} {H[i]['rank']:4d} {H[i]['thr']:9.5f} {H[i]['adj']:11.3e} "
      f"{B[i]['thr']:8.5f} {B[i]['adj']:11.3e} {surv:>9s}")

# --- what if the whole family is corrected together?
P("")
P(f"If the SAME 4 primary tests are corrected inside the full family of "
  f"{TOTAL} tests:")
for i, m in enumerate(MODELS):
    bonf_full = min(1.0, pv[i] * TOTAL)
    P(f"  {m:28s} p*{TOTAL} = {bonf_full:.3e}   "
      f"{'still significant' if bonf_full < 0.05 else 'NOT significant'}")

# --- actually run every subgroup test, to show the empirical multiplicity load
P("")
P("Empirical subgroup sweep (all per-model x level A-vs-B exact McNemar tests):")
sub_results = []
for f, g in FACTORS.items():
    for lev in levels[f]:
        for m in MODELS:
            rows = [r for r in by_model[m] if str(g(r)) == lev]
            s = cell_stats(rows)
            if s is None:
                continue
            sub_results.append((f, lev, m, s))
n_run = len(sub_results)
n_est = sum(1 for _, _, _, s in sub_results if s["disc_b"] + s["disc_c"] > 0)
n_nominal = sum(1 for _, _, _, s in sub_results if s["p"] < 0.05)
n_underpowered = sum(1 for _, _, _, s in sub_results if s["n"] < 30)
P(f"  subgroup tests actually runnable ............ {n_run}")
P(f"  ... with >=1 discordant pair (estimable) .... {n_est}")
P(f"  ... with cell n < 30 (structurally underpowered) {n_underpowered}")
P(f"  ... nominally significant at p<.05 .......... {n_nominal}")
sub_p = [s["p"] for _, _, _, s in sub_results]
subH = holm(sub_p, 0.05)
subB = bh(sub_p, 0.05)
P(f"  ... surviving Holm within the subgroup family {sum(1 for h in subH if h['adj']<0.05)}")
P(f"  ... surviving BH   within the subgroup family {sum(1 for b in subB if b['adj']<0.05)}")

# smallest-p subgroup findings, post-correction
order = sorted(range(n_run), key=lambda i: sub_p[i])[:8]
P("")
P("  strongest subgroup findings (BH-adjusted within the subgroup family):")
P(f"  {'factor':15s} {'level':22s} {'model':28s} {'n':>4s} {'delta':>7s} {'p_raw':>10s} {'BH adj':>10s}")
for i in order:
    f, lev, m, s = sub_results[i]
    P(f"  {f:15s} {lev:22s} {m:28s} {s['n']:4d} {s['delta']:7.4f} "
      f"{sub_p[i]:10.3e} {subB[i]['adj']:10.3e}")

# ---------------------------------------------------------------- ceiling

P("")
P("=" * 78)
P("(2) CEILING -- raw delta is not comparable across models with different pA")
P("=" * 78)

def metrics(s):
    pA, pB, n = s["pA"], s["pB"], s["n"]
    room_zero = pA                      # max possible decline: pA -> 0
    room_chance = pA - CHANCE           # max decline before hitting blind guessing
    lo_A = haldane_logodds(s["A"], n)
    lo_B = haldane_logodds(s["B"], n)
    # conditional (McNemar) odds ratio from discordant pairs
    b, c = s["disc_b"], s["disc_c"]
    cond_or = (b + 0.5) / (c + 0.5)
    return dict(
        raw_delta=s["delta"],
        frac_of_max=(s["delta"] / room_zero) if room_zero > 0 else float("nan"),
        frac_to_chance=(s["delta"] / room_chance) if room_chance > 0 else float("nan"),
        d_logodds=lo_A - lo_B,
        marg_or=math.exp(lo_A - lo_B),
        cond_logor=math.log(cond_or),
        cond_or=cond_or,
        retention=(s["pB"] / s["pA"]) if s["pA"] > 0 else float("nan"),
        room_zero=room_zero, room_chance=room_chance,
    )

M = {m: metrics(prim[m]) for m in MODELS}

P(f"{'model':28s} {'pA':>7s} {'pB':>7s} {'raw d':>7s} {'room':>6s} "
  f"{'d/room':>7s} {'d/(pA-.25)':>10s} {'dLogOdds':>9s} {'margOR':>8s} {'condOR':>7s}")
for m in MODELS:
    s, x = prim[m], M[m]
    P(f"{m:28s} {s['pA']:7.4f} {s['pB']:7.4f} {x['raw_delta']:7.4f} "
      f"{x['room_zero']:6.4f} {x['frac_of_max']:7.4f} {x['frac_to_chance']:10.4f} "
      f"{x['d_logodds']:9.4f} {x['marg_or']:8.3f} {x['cond_or']:7.3f}")

P("")
P("How much of gemini's raw-delta advantage is just having more room to fall?")
P(f"  gemini room to zero  = {M[MODELS[0]]['room_zero']:.4f}")
for m in MODELS:
    P(f"  {m:28s} room_to_zero={M[m]['room_zero']:.4f}  "
      f"room_to_chance={M[m]['room_chance']:.4f}")

# --- rankings under each metric (1 = most fragile / largest drop)
METRIC_KEYS = [
    ("raw_delta",      "raw delta (pA-pB)",              True),
    ("frac_of_max",    "delta / max possible decline",   True),
    ("frac_to_chance", "delta / (pA - chance)",          True),
    ("d_logodds",      "marginal log-odds change",       True),
    ("cond_logor",     "conditional (McNemar) log-OR",   True),
]

def rank_by(key, desc=True):
    o = sorted(MODELS, key=lambda m: M[m][key], reverse=desc)
    return {m: i + 1 for i, m in enumerate(o)}, o

P("")
P("MODEL RANKING (1 = biggest degradation / least robust) under each metric:")
P(f"{'metric':34s} " + " ".join(f"{m.split('/')[-1][:14]:>15s}" for m in MODELS))
ranks = {}
for key, label, desc in METRIC_KEYS:
    rk, order_m = rank_by(key, desc)
    ranks[key] = rk
    P(f"{label:34s} " + " ".join(f"{rk[m]:>15d}" for m in MODELS))
P("")
for key, label, desc in METRIC_KEYS:
    rk, order_m = rank_by(key, desc)
    P(f"  {label:34s}: " + "  >  ".join(f"{m.split('/')[-1]}({M[m][key]:.3f})"
                                        for m in order_m))

# Kendall tau between raw-delta ranking and each other ranking
def kendall_tau(r1, r2):
    conc = disc = 0
    for a, b in itertools.combinations(MODELS, 2):
        s1 = r1[a] - r1[b]
        s2 = r2[a] - r2[b]
        if s1 * s2 > 0: conc += 1
        elif s1 * s2 < 0: disc += 1
    tot = conc + disc
    return (conc - disc) / tot if tot else float("nan")

P("")
P("Kendall tau of each ranking vs the raw-delta ranking:")
for key, label, desc in METRIC_KEYS[1:]:
    P(f"  {label:34s} tau = {kendall_tau(ranks['raw_delta'], ranks[key]):+.3f}")

# ---------------------------------------------------------------- bootstrap

P("")
P("=" * 78)
P("CLUSTER BOOTSTRAP (resample the 208 clusters with replacement, "
  f"B={BOOT}, seed={SEED})")
P("=" * 78)

clusters = sorted({r["cluster"] for r in recs})
by_cluster = collections.defaultdict(list)
for r in recs:
    by_cluster[r["cluster"]].append(r)

rng = random.Random(SEED)
boot_metrics = {m: collections.defaultdict(list) for m in MODELS}
boot_rank_top = {key: collections.Counter() for key, _, _ in METRIC_KEYS}

for _ in range(BOOT):
    draw = [by_cluster[clusters[rng.randrange(len(clusters))]]
            for _ in range(len(clusters))]
    rows = [r for grp in draw for r in grp]
    bm = {}
    ok = True
    for m in MODELS:
        s = cell_stats([r for r in rows if r["model"] == m])
        if s is None or s["pA"] <= 0 or s["pA"] >= 1.0 and False:
            ok = False; break
        bm[m] = metrics(s)
    if not ok:
        continue
    for m in MODELS:
        for key, _, _ in METRIC_KEYS:
            boot_metrics[m][key].append(bm[m][key])
    for key, _, desc in METRIC_KEYS:
        top = max(MODELS, key=lambda m: bm[m][key])
        boot_rank_top[key][top] += 1

def pct(v, q):
    v = sorted(v)
    if not v: return float("nan")
    k = (len(v) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return v[lo] if lo == hi else v[lo] * (hi - k) + v[hi] * (k - lo)

P("percentile 95% CIs (cluster bootstrap):")
for key, label, _ in METRIC_KEYS:
    P(f"  {label}")
    for m in MODELS:
        v = boot_metrics[m][key]
        P(f"    {m:28s} {M[m][key]:8.4f}  95% CI [{pct(v,0.025):8.4f}, {pct(v,0.975):8.4f}]")

P("")
P("P(model has the LARGEST value of the metric) -- ranking stability:")
P(f"{'metric':34s} " + " ".join(f"{m.split('/')[-1][:14]:>15s}" for m in MODELS))
for key, label, _ in METRIC_KEYS:
    tot = sum(boot_rank_top[key].values())
    P(f"{label:34s} " + " ".join(
        f"{boot_rank_top[key][m]/tot:>15.3f}" for m in MODELS))

# ---------------------------------------------------------------- cluster permutation sensitivity
P("")
P("=" * 78)
P("SENSITIVITY: cluster-level randomisation test for each primary comparison")
P("(sign-flip A/B labels for whole clusters; accounts for item nesting)")
P("=" * 78)
rng2 = random.Random(SEED + 1)
NPERM = 20000
for m in MODELS:
    rows = by_model[m]
    cl = collections.defaultdict(list)
    for r in rows:
        cl[r["cluster"]].append(r)
    keys = list(cl)
    obs = sum(r["A_correct"] - r["B_correct"] for r in rows) / len(rows)
    ge = 0
    for _ in range(NPERM):
        tot = 0
        for k in keys:
            sgn = 1 if rng2.random() < 0.5 else -1
            for r in cl[k]:
                tot += sgn * (r["A_correct"] - r["B_correct"])
        if abs(tot / len(rows)) >= abs(obs) - 1e-12:
            ge += 1
    pperm = (ge + 1) / (NPERM + 1)
    P(f"  {m:28s} obs delta={obs:7.4f}  perm p={pperm:.5f}  "
      f"(exact McNemar p={prim[m]['p']:.3e})")

with open(os.path.join(HERE, "stats_multiplicity_ceiling_output.txt"), "w") as fh:
    fh.write("\n".join(out) + "\n")

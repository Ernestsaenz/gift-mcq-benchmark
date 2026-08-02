#!/usr/bin/env python3
"""
sens_refute_gridflip_exact.py -- stress tests that go BEYOND the Monte-Carlo grid.

(E1) EXACT cluster sign-flip permutation p-value by dynamic programming.
     The sign-flip null is T = sum_k eps_k * S_k, eps_k iid uniform{-1,+1},
     S_k = integer sum of d = B-A over the cells of cluster k. All S_k are small
     integers, so the FULL null distribution of T is computable exactly by integer
     convolution -- no sampling, no floor, no Monte-Carlo error. Two-sided
     p = P(|T| >= |T_obs|) computed to machine precision.
     This settles whether "p < 0.00005" / "p = 0.00010" are real numbers or
     resolution artefacts of a 20000-rep sampler.

(E2) CLUSTER-ROBUST (linearised sandwich) Wald CI as an independent alternative to
     the percentile bootstrap. delta = sum_k S_k / sum_k N_k; the influence-function
     variance is  Var = (C/(C-1)) * sum_k (S_k - delta*N_k)^2 / N^2.
     Also reports the BASIC (reflected) bootstrap interval, which corrects the
     percentile interval's bias in the opposite direction.

(E3) LEAVE-ONE-CLUSTER-OUT: the most adverse single cluster deletion, to check no
     estimate is propped up by one clinical-context block.

(E4) ADVERSARIAL RESTORATION of the 3 contested items that dataset_meta lists as
     excluded but that are ABSENT from paired_clean.json entirely (b343, b420,
     b430). They cannot be restored from data, so bound them: assume every one of
     their 4 model cells took the value MOST hostile to the claim (A wrong, B
     right, d = +1) and recompute. If the sign still holds under that bound, the
     missing rows cannot flip anything.

stdlib only.
"""

import json, os, math, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = json.load(open(os.path.join(HERE, "paired_clean.json")))
MODELS = sorted(set(r["model"] for r in ROWS))
R = 20000
SEED = 5150

FILTERS = {
    "S1_none":        lambda r: True,
    "S2_drop_defect": lambda r: not r["excl_item_defect"],
    "S3_drop_posA":   lambda r: not r["excl_nota_position_a"],
    "S4_drop_both":   lambda r: r["analysis_include"],
}
SIDS = list(FILTERS)


def subset(sid, model=None):
    f = FILTERS[sid]
    return [r for r in ROWS if f(r) and (model is None or r["model"] == model)]


def cluster_stats(cells):
    """[(N_k, S_k)] per cluster."""
    g = defaultdict(lambda: [0, 0])
    for r in cells:
        e = g[r["cluster"]]
        e[0] += 1
        e[1] += r["B_correct"] - r["A_correct"]
    return [tuple(v) for v in g.values()]


# ------------------------------------------------------------------ E1 exact perm
def exact_signflip_p(cs):
    """Exact two-sided cluster sign-flip p via integer convolution DP."""
    N = sum(n for n, _ in cs)
    S = [s for _, s in cs]
    Tobs = abs(sum(S))
    nz = [abs(s) for s in S if s != 0]
    if not nz:
        return 1.0, N, 0
    # dist over T = sum eps_k*|s_k| ; symmetric, integer support
    span = sum(nz)
    # probabilities as floats; support offset by span
    dist = [0.0] * (2 * span + 1)
    dist[span] = 1.0
    lo, hi = span, span
    for a in nz:
        nd = [0.0] * (2 * span + 1)
        for i in range(lo, hi + 1):
            p = dist[i]
            if p:
                nd[i - a] += 0.5 * p
                nd[i + a] += 0.5 * p
        dist = nd
        lo -= a; hi += a
    tail = 0.0
    for i in range(lo, hi + 1):
        if abs(i - span) >= Tobs:
            tail += dist[i]
    return min(1.0, tail), N, len(nz)


# ------------------------------------------------------------------ E2 robust Wald
def robust_wald(cs):
    N = sum(n for n, _ in cs)
    C = len(cs)
    d = sum(s for _, s in cs) / N
    v = sum((s - d * n) ** 2 for n, s in cs) * (C / (C - 1)) / (N ** 2)
    se = math.sqrt(v)
    return d, se, d - 1.959963985 * se, d + 1.959963985 * se


# ------------------------------------------------------------------ bootstrap
def pct(v, q):
    i = q * (len(v) - 1)
    a, b = int(math.floor(i)), int(math.ceil(i))
    return v[a] if a == b else v[a] + (v[b] - v[a]) * (i - a)


def boot(cs, reps, rng):
    C = len(cs)
    out = []
    for _ in range(reps):
        n = s = 0
        for _ in range(C):
            gn, gs = cs[rng.randrange(C)]
            n += gn; s += gs
        if n:
            out.append(s / n)
    out.sort()
    return pct(out, 0.025), pct(out, 0.975)


# ------------------------------------------------------------------ E3 LOO cluster
def loo_worst(cs):
    Ntot = sum(n for n, _ in cs); Stot = sum(s for _, s in cs)
    best = None
    for n, s in cs:
        if Ntot - n <= 0:
            continue
        d = (Stot - s) / (Ntot - n)
        if best is None or d > best:
            best = d
    return best


print("=" * 122)
print("E1/E2/E3  EXACT PERMUTATION + ALTERNATIVE CI + LEAVE-ONE-CLUSTER-OUT")
print("=" * 122)
print(f"{'key':<24}{'set':<16}{'delta':>10}{'p_EXACT':>13}{'wald_lo':>10}{'wald_hi':>10}"
      f"{'pct_lo':>10}{'pct_hi':>10}{'basic_hi':>10}{'LOOworst':>10}")
print("-" * 122)
res = {}
for key in ["POOLED"] + MODELS:
    model = None if key == "POOLED" else key
    for sid in SIDS:
        cells = subset(sid, model)
        cs = cluster_stats(cells)
        pex, N, nz = exact_signflip_p(cs)
        d, se, wlo, whi = robust_wald(cs)
        rng = random.Random(SEED + len(key) * 7 + SIDS.index(sid))
        plo, phi = boot(cs, R, rng)
        basic_hi = 2 * d - plo          # reflected/basic bootstrap upper limit
        lw = loo_worst(cs)
        res[(key, sid)] = dict(delta=d, p_exact=pex, se=se, wald=(wlo, whi),
                               pct=(plo, phi), basic_hi=basic_hi, loo_worst=lw, nz=nz)
        print(f"{key.split('/')[-1]:<24}{sid:<16}{d:>10.4f}{pex:>13.3e}{wlo:>10.4f}{whi:>10.4f}"
              f"{plo:>10.4f}{phi:>10.4f}{basic_hi:>10.4f}{lw:>10.4f}")
    print("-" * 122)

print()
print("=" * 122)
print("E4  ADVERSARIAL BOUND ON THE 3 ITEMS dataset_meta LISTS BUT paired_clean DOES NOT CONTAIN")
print("    (b343, b420, b430 -- assume all 12 of their cells are A-wrong/B-right, d=+1, the")
print("     most hostile possible values -- and add them to the S1 'unfiltered' corner)")
print("=" * 122)
for key in ["POOLED"] + MODELS:
    model = None if key == "POOLED" else key
    cells = subset("S1_none", model)
    n = len(cells); s = sum(r["B_correct"] - r["A_correct"] for r in cells)
    add = 12 if model is None else 3
    print(f"  {key.split('/')[-1]:<24} observed {s/n:+.4f}  ->  adversarial bound {(s+add)/(n+add):+.4f}")

print()
print("=" * 122)
print("E5  CLAIM-BY-CLAIM VERDICT")
print("=" * 122)
allneg = all(v["delta"] < 0 for v in res.values())
allpct = all(v["pct"][1] < 0 for v in res.values())
allwald = all(v["wald"][1] < 0 for v in res.values())
allbasic = all(v["basic_hi"] < 0 for v in res.values())
allloo = all(v["loo_worst"] < 0 for v in res.values())
print("all 20 deltas negative                       :", allneg)
print("all 20 percentile-bootstrap CIs exclude 0    :", allpct)
print("all 20 cluster-robust Wald CIs exclude 0     :", allwald)
print("all 20 basic(reflected) bootstrap CIs excl 0 :", allbasic)
print("all 20 survive worst single-cluster deletion :", allloo)
mx = max(res.items(), key=lambda kv: kv[1]["p_exact"])
print("largest EXACT permutation p in grid          :", mx[0], f"{mx[1]['p_exact']:.3e}")
print("claim asserts weakest p = 1.0e-04 (gemini S4); exact value there is",
      f"{res[('google/gemini-3.6-flash','S4_drop_both')]['p_exact']:.3e}")
print("n estimates whose EXACT p is below 5e-05     :",
      sum(1 for v in res.values() if v["p_exact"] < 5e-5), "of 20")
worst_hi = max(res.items(), key=lambda kv: kv[1]["pct"][1])
print("estimate nearest to zero (pct CI upper)      :", worst_hi[0],
      f"hi={worst_hi[1]['pct'][1]:+.4f}  ({abs(worst_hi[1]['pct'][1])*100:.2f} pts clear, NOT 13.1)")

json.dump({f"{k[0]}|{k[1]}": v for k, v in res.items()},
          open(os.path.join(HERE, "sens_refute_gridflip_exact_out.json"), "w"), indent=1)

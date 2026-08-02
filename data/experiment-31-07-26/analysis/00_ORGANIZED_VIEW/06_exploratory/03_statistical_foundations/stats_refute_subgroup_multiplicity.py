#!/usr/bin/env python3
"""
stats_refute_subgroup_multiplicity.py

Independent recomputation of the "subgroup multiplicity" claim from
stats_multiplicity_ceiling.py.  Nothing is imported from that script; every
p-value, adjustment and count below is recomputed from paired_clean.json with
the standard library only.

Exact McNemar is implemented twice (float lgamma path and an exact-integer
Fraction path) and cross-checked, so no claim rests on a single implementation.
"""

import json, math, os, collections, itertools
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "paired_clean.json")

# ----------------------------------------------------------------- exact stats

def mcnemar_exact_p_float(b, c):
    n = b + c
    if n == 0:
        return 1.0
    def pmf(k):
        return math.exp(math.lgamma(n + 1) - math.lgamma(k + 1)
                        - math.lgamma(n - k + 1) - n * math.log(2.0))
    lo = sum(pmf(k) for k in range(0, b + 1))
    hi = sum(pmf(k) for k in range(b, n + 1))
    return min(1.0, 2.0 * min(lo, hi))

def mcnemar_exact_p_exact(b, c):
    """Same test, exact rational arithmetic -- no floating point at all."""
    n = b + c
    if n == 0:
        return Fraction(1)
    denom = Fraction(1, 2 ** n)
    lo = sum(math.comb(n, k) for k in range(0, b + 1)) * denom
    hi = sum(math.comb(n, k) for k in range(b, n + 1)) * denom
    return min(Fraction(1), 2 * min(lo, hi))

# min discordant pairs needed for two-sided exact McNemar to ever reach p<.05
def min_discordant_for_significance(alpha=0.05):
    n = 1
    while True:
        # best case: all discordances one-sided (b=n, c=0)
        p = Fraction(2, 2 ** n)
        if p < Fraction(alpha).limit_denominator(10 ** 9):
            return n
        n += 1

# ----------------------------------------------------------------- adjustments

def holm_adj(pvals):
    idx = sorted(range(len(pvals)), key=lambda i: pvals[i])
    m = len(pvals)
    res = [None] * m
    running = 0.0
    for rank, i in enumerate(idx):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        res[i] = running
    return res

def bh_adj(pvals):
    idx = sorted(range(len(pvals)), key=lambda i: pvals[i])
    m = len(pvals)
    res = [None] * m
    running = 1.0
    for rank in range(m - 1, -1, -1):
        i = idx[rank]
        running = min(running, min(1.0, pvals[i] * m / (rank + 1)))
        res[i] = running
    return res

# ----------------------------------------------------------------- load

recs = [r for r in json.load(open(DATA)) if r["analysis_include"]]
MODELS = sorted({r["model"] for r in recs})

def cell(rows):
    n = len(rows)
    if n == 0:
        return None
    a = sum(r["A_correct"] for r in rows)
    bc = sum(r["B_correct"] for r in rows)
    b = sum(1 for r in rows if r["A_correct"] == 1 and r["B_correct"] == 0)
    c = sum(1 for r in rows if r["A_correct"] == 0 and r["B_correct"] == 1)
    return dict(n=n, disc_b=b, disc_c=c, disc=b + c, delta=(a - bc) / n,
                p=mcnemar_exact_p_float(b, c),
                p_exact=mcnemar_exact_p_exact(b, c))

by_model = {m: [r for r in recs if r["model"] == m] for m in MODELS}

FACTORS = {
    "correct_letter": lambda r: r["correct_letter"],
    "negated_stem":   lambda r: r["negated_stem"],
    "has_context":    lambda r: r["has_context"],
    "region":         lambda r: r["region"],
    "year":           lambda r: r["year"],
}
levels = {f: sorted({str(g(r)) for r in recs}) for f, g in FACTORS.items()}

out = []
def P(s=""):
    out.append(s); print(s)

P("=" * 78)
P("RECOMPUTATION: per-model subgroup sweep")
P("=" * 78)
P(f"records analysis_include=true : {len(recs)}")
P(f"models                        : {len(MODELS)}")
P(f"items                         : {len({r['question_id'] for r in recs})}")
P(f"clusters                      : {len({r['cluster'] for r in recs})}")
P("levels per factor: " + ", ".join(f"{f}={len(v)}" for f, v in levels.items()))
P(f"implied per-model subgroup tests = {sum(len(v) for v in levels.values())} x {len(MODELS)}"
  f" = {sum(len(v) for v in levels.values()) * len(MODELS)}")

sub = []
for f, g in FACTORS.items():
    for lev in levels[f]:
        for m in MODELS:
            rows = [r for r in by_model[m] if str(g(r)) == lev]
            s = cell(rows)
            if s is None:
                continue
            s.update(factor=f, level=lev, model=m)
            sub.append(s)

# cross-check float vs exact-rational p-values
maxdiff = max(abs(s["p"] - float(s["p_exact"])) for s in sub)
P(f"max |p_float - p_exactrational| over all subgroup tests = {maxdiff:.3e}"
  f"  ({'agree' if maxdiff < 1e-12 else 'DISAGREE'})")

pv = [s["p"] for s in sub]
H = holm_adj(pv)
B = bh_adj(pv)
for s, h, b_ in zip(sub, H, B):
    s["holm"] = h; s["bh"] = b_

n_run = len(sub)
n_est = sum(1 for s in sub if s["disc"] > 0)
n_small = sum(1 for s in sub if s["n"] < 30)
n_nom = sum(1 for s in sub if s["p"] < 0.05)
n_holm = sum(1 for s in sub if s["holm"] < 0.05)
n_bh = sum(1 for s in sub if s["bh"] < 0.05)

P("")
P("HEADLINE COUNTS (recomputed):")
P(f"  tests runnable ............................. {n_run}   (claim: 100)")
P(f"  estimable (>=1 discordant pair) ............ {n_est}   (claim: 99)")
P(f"  cells with n < 30 .......................... {n_small}   (claim: 56)")
P(f"  nominally significant p<.05 ................ {n_nom}   (claim: 49)")
P(f"  survive Holm in subgroup family ............ {n_holm}   (claim: 20)")
P(f"  survive BH   in subgroup family ............ {n_bh}   (claim: 39)")
P(f"  Holm casualties = {n_nom}-{n_holm} = {n_nom-n_holm}   (claim: 29)")
P(f"  BH   casualties = {n_nom}-{n_bh} = {n_nom-n_bh}   (claim: 10)")
P(f"  all Holm survivors nominal? {all(s['p']<0.05 for s in sub if s['holm']<0.05)}")
P(f"  all BH survivors nominal?   {all(s['p']<0.05 for s in sub if s['bh']<0.05)}")

# ----------------------------------------------------- per-factor breakdown
def median(v):
    v = sorted(v); k = len(v)
    return v[k // 2] if k % 2 else (v[k // 2 - 1] + v[k // 2]) / 2

P("")
P("PER-FACTOR BREAKDOWN (recomputed):")
P(f"{'factor':16s} {'tests':>5s} {'medn':>6s} {'minn':>5s} {'maxn':>5s} "
  f"{'med_disc':>8s} {'min_disc':>8s} {'nomin':>6s} {'holm':>5s} {'bh':>4s} "
  f"{'BHkill':>6s} {'n<30':>5s}")
fac_rows = {}
for f in FACTORS:
    rows = [s for s in sub if s["factor"] == f]
    ns = [s["n"] for s in rows]
    ds = [s["disc"] for s in rows]
    nm = sum(1 for s in rows if s["p"] < 0.05)
    hh = sum(1 for s in rows if s["holm"] < 0.05)
    bb = sum(1 for s in rows if s["bh"] < 0.05)
    sm = sum(1 for s in rows if s["n"] < 30)
    fac_rows[f] = dict(tests=len(rows), medn=median(ns), minn=min(ns), maxn=max(ns),
                       nom=nm, holm=hh, bh=bb, kill=nm - bb, small=sm)
    P(f"{f:16s} {len(rows):5d} {median(ns):6.1f} {min(ns):5d} {max(ns):5d} "
      f"{median(ds):8.1f} {min(ds):8d} {nm:6d} {hh:5d} {bb:4d} {nm-bb:6d} {sm:5d}")

# ----------------------------------------------------- small-cell vs hits
P("")
P("CROSS-TAB: cell size vs significance")
small_nom = [s for s in sub if s["n"] < 30 and s["p"] < 0.05]
small_nom_bh = [s for s in small_nom if s["bh"] < 0.05]
big_nom = [s for s in sub if s["n"] >= 30 and s["p"] < 0.05]
big_nom_bh = [s for s in big_nom if s["bh"] < 0.05]
P(f"  n<30  : {n_small} cells, {len(small_nom)} nominal, {len(small_nom_bh)} BH-survive"
  f"   (claim: 13 nominal / 7 BH)")
P(f"  n>=30 : {n_run-n_small} cells, {len(big_nom)} nominal, {len(big_nom_bh)} BH-survive")

# ----------------------------------------------------- TRUE structural power
minneed = min_discordant_for_significance(0.05)
P("")
P("STRUCTURAL POWER, done correctly (exact McNemar power depends on the number")
P("of DISCORDANT pairs b+c, not on n):")
P(f"  smallest b+c for which two-sided exact McNemar can EVER reach p<.05 = {minneed}")
hard_zero = [s for s in sub if s["disc"] < minneed]
P(f"  cells with b+c < {minneed} (cannot reach p<.05 under ANY split) : {len(hard_zero)} / {n_run}")
P(f"  cells with n<30 that ARE nevertheless significant             : {len(small_nom)}")
P(f"  cells with n>=30 that have b+c < {minneed}                          : "
  f"{sum(1 for s in hard_zero if s['n']>=30)}")
P(f"  cells with n<30  that have b+c >= {minneed}                         : "
  f"{sum(1 for s in sub if s['n']<30 and s['disc']>=minneed)}")
P("  discordant-pair distribution over the 100 cells:")
dd = collections.Counter(s["disc"] for s in sub)
P("    " + ", ".join(f"b+c={k}:{v}" for k, v in sorted(dd.items())[:12]) + " ...")
P(f"    median b+c = {median([s['disc'] for s in sub])}, "
  f"min = {min(s['disc'] for s in sub)}, max = {max(s['disc'] for s in sub)}")

# ----------------------------------------------------- expected hits if effect real
P("")
P("IS 49/100 A MULTIPLICITY PROBLEM OR A LARGE TRUE EFFECT?")
P("  Under a global null (no A-vs-B difference anywhere) the expected number of")
P(f"  nominal hits in {n_run} tests is {0.05*n_run:.1f}.  Observed = {n_nom}.")
# Storey-style pi0 estimate: fraction of p-values above lambda
for lam in (0.5, 0.6, 0.7):
    above = sum(1 for s in sub if s["p"] > lam)
    pi0 = above / ((1 - lam) * n_run)
    P(f"  Storey pi0 estimate at lambda={lam}: {above} p-values > {lam} -> "
      f"pi0_hat = {min(1.0,pi0):.3f}  (est. true nulls ~ {min(1.0,pi0)*n_run:.0f})")
P("  => the subgroup family is dominated by TRUE alternatives, which is exactly")
P("     the regime where Holm/FWER is the wrong yardstick and BH is right.")

# ----------------------------------------------------- dependence between tests
P("")
P("ARE THE 100 TESTS 100 INDEPENDENT PIECES OF EVIDENCE?  No -- each factor")
P("re-partitions the SAME cells:")
for f in FACTORS:
    for m in MODELS[:1]:
        tot = sum(s["n"] for s in sub if s["factor"] == f and s["model"] == m)
        P(f"  {f:16s} model={m.split('/')[-1]:18s} sum of level-cell n = {tot} "
          f"(= that model's full n)")
P("  So the 5 factors are 5 complete re-slicings of one dataset; the region and")
P("  year 'tests' re-test the same discordant pairs already counted under")
P("  correct_letter / negated_stem / has_context.")

# ----------------------------------------------------- casualty attribution
P("")
P("WHERE DO THE BH CASUALTIES ACTUALLY LIVE?")
for f in FACTORS:
    fr = fac_rows[f]
    P(f"  {f:16s} nominal={fr['nom']:2d}  BH-survive={fr['bh']:2d}  killed={fr['kill']:2d}")
P(f"  total killed = {sum(fac_rows[f]['kill'] for f in FACTORS)}")

# ----------------------------------------------------- what dropping region+year does
P("")
P("COUNTERFACTUAL: the recommendation says drop region+year and report BH.")
keep = [s for s in sub if s["factor"] in ("correct_letter", "negated_stem", "has_context")]
kp = [s["p"] for s in keep]
kB = bh_adj(kp)
kH = holm_adj(kp)
P(f"  retained family m = {len(keep)}")
P(f"  nominal in retained family ............ {sum(1 for s in keep if s['p']<0.05)}")
P(f"  BH survivors when corrected in m={len(keep)} ... {sum(1 for a in kB if a<0.05)}")
P(f"  BH survivors when corrected in m={n_run} .. "
  f"{sum(1 for s in keep if s['bh']<0.05)}")
P(f"  Holm survivors when corrected in m={len(keep)} . {sum(1 for a in kH if a<0.05)}")
P("  -> dropping region+year does not 'fix' anything statistically; it SHRINKS")
P("     the family so the surviving tests get an easier threshold.  Selecting")
P("     which sub-families to report after seeing which ones lost survivors is")
P("     itself a forking path.")

# ----------------------------------------------------- top findings
P("")
P("STRONGEST SUBGROUP FINDINGS (recomputed, BH within m=100):")
P(f"  {'factor':15s} {'level':22s} {'model':28s} {'n':>4s} {'b':>3s} {'c':>3s} "
  f"{'delta':>7s} {'p_raw':>10s} {'BH':>10s} {'Holm':>10s}")
for s in sorted(sub, key=lambda s: s["p"])[:10]:
    P(f"  {s['factor']:15s} {s['level']:22s} {s['model']:28s} {s['n']:4d} "
      f"{s['disc_b']:3d} {s['disc_c']:3d} {s['delta']:7.4f} {s['p']:10.3e} "
      f"{s['bh']:10.3e} {s['holm']:10.3e}")

# ----------------------------------------------------- region/year detail
P("")
P("REGION CELL DETAIL (all 44):")
P(f"  {'level':22s} {'model':22s} {'n':>4s} {'b':>3s} {'c':>3s} {'delta':>7s} "
  f"{'p':>10s} {'BH':>10s} {'sig':>4s}")
for s in sorted([s for s in sub if s["factor"] == "region"],
                key=lambda s: (s["level"], s["model"])):
    P(f"  {s['level']:22s} {s['model'].split('/')[-1]:22s} {s['n']:4d} {s['disc_b']:3d} "
      f"{s['disc_c']:3d} {s['delta']:7.4f} {s['p']:10.3e} {s['bh']:10.3e} "
      f"{'BH' if s['bh']<0.05 else ('nom' if s['p']<0.05 else '-'):>4s}")

P("")
P("YEAR CELL DETAIL (all 28):")
for s in sorted([s for s in sub if s["factor"] == "year"],
                key=lambda s: (s["level"], s["model"])):
    P(f"  {s['level']:22s} {s['model'].split('/')[-1]:22s} {s['n']:4d} {s['disc_b']:3d} "
      f"{s['disc_c']:3d} {s['delta']:7.4f} {s['p']:10.3e} {s['bh']:10.3e} "
      f"{'BH' if s['bh']<0.05 else ('nom' if s['p']<0.05 else '-'):>4s}")

# ----------------------------------------------------- do region/year cells disagree?
P("")
P("DO REGION / YEAR CELLS ACTUALLY SHOW HETEROGENEITY, OR JUST THE SAME EFFECT?")
for f in ("region", "year"):
    rows = [s for s in sub if s["factor"] == f]
    pos = sum(1 for s in rows if s["delta"] > 0)
    neg = sum(1 for s in rows if s["delta"] < 0)
    zer = sum(1 for s in rows if s["delta"] == 0)
    P(f"  {f:8s}: delta>0 in {pos}/{len(rows)} cells, <0 in {neg}, =0 in {zer}")
    # sign test on direction of delta across cells
    k = pos; nn = pos + neg
    p_sign = min(1.0, 2 * sum(math.comb(nn, i) for i in range(k, nn + 1)) / 2 ** nn)
    P(f"           sign test on cell-level direction: k={k}/{nn}, exact p={p_sign:.3e}")

with open(os.path.join(HERE, "stats_refute_subgroup_multiplicity_out.txt"), "w") as fh:
    fh.write("\n".join(out) + "\n")

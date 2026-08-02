"""REFUTATION pass on the 'Monte-Carlo floor' robustness claim.

Independent recomputation of every ANALYTIC specification in the specification
curve, from paired_clean.json, using implementations written from scratch and
deliberately different from sens_speccurve_lib.py:

  * exact McNemar   -> exact rational arithmetic (fractions.Fraction), then a
                       log-safe conversion.  No floating binomial sum.
  * logistic on a binary regressor -> the MLE is the closed-form log odds ratio
                       of the 2x2 arm x correct table.  No Newton-Raphson.
  * Student-t tail  -> regularized incomplete beta via the Gauss hypergeometric
                       series  I_x(a,b) = x^a (1-x)^b / (a B(a,b)) * 2F1(a+b,1;a+1;x),
                       not the Lentz continued fraction used by the pipeline.
  * chi2 (even df)  -> same closed form (it is exact; no independent variant needed),
                       recomputed in log space to avoid underflow.

It also does what the claim does NOT do: it RESOLVES the floored resampling
p-values analytically instead of deleting those specs, and it disaggregates the
'separate' specs whose Fisher combination the pipeline itself flags as invalid.

Method notes for every p-value are printed inline.
"""
import json, os, math
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "paired_clean.json")
rows = json.load(open(DATA))
MODELS = sorted(set(r["model"] for r in rows))
NM = len(MODELS)

# ---------------------------------------------------------------- data variants
_b320 = [r for r in rows if r["question_id"] == "b320"][0]
STRICT_EXTRA = dict(
    question_id="b320", model="z-ai/glm-5.2", cluster=_b320["cluster"],
    correct_letter=_b320["correct_letter"], A_correct=0, B_correct=1,
    excl_item_defect=False, excl_nota_position_a=False, analysis_include=True)

EXCLUSIONS = {
    "primary":     lambda r: (not r["excl_item_defect"]) and (not r["excl_nota_position_a"]),
    "defect_only": lambda r: not r["excl_item_defect"],
    "notaA_only":  lambda r: not r["excl_nota_position_a"],
    "none":        lambda r: True,
}


def get_rows(exclusion, outcome):
    base = rows + ([STRICT_EXTRA] if outcome == "strict" else [])
    keep = EXCLUSIONS[exclusion]
    return [r for r in base if keep(r)]


# ---------------------------------------------------------------- numerics
def log10_from_fraction(fr):
    """log10 of a positive Fraction, exact-ish for astronomically small values."""
    if fr == 0:
        return float("-inf")
    n, d = fr.numerator, fr.denominator
    # use bit lengths to keep everything in range
    bn, bd = n.bit_length(), d.bit_length()
    mn = n >> max(0, bn - 200)
    md = d >> max(0, bd - 200)
    return (math.log10(mn) + max(0, bn - 200) * math.log10(2.0)
            - math.log10(md) - max(0, bd - 200) * math.log10(2.0))


def mcnemar_exact_frac(b, c):
    """Exact two-sided McNemar, EXACT rational arithmetic.  X ~ Bin(b+c, 1/2)."""
    n = b + c
    if n == 0:
        return Fraction(1)
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1))
    p = Fraction(2 * tail, 1 << n)
    return min(Fraction(1), p)


def _lbeta(a, b):
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def betai_hyp(a, b, x, maxit=100000, eps=1e-16):
    """I_x(a,b) via the 2F1 series.  Independent of the pipeline's Lentz CF.

    I_x(a,b) = x^a (1-x)^b / (a B(a,b)) * sum_{n>=0} [ (a+b)_n / (a+1)_n ] x^n
    Returns (value, log10_value) so tiny tails survive underflow.
    """
    if x <= 0.0:
        return 0.0, float("-inf")
    if x >= 1.0:
        return 1.0, 0.0
    if x > (a + 1.0) / (a + b + 2.0):
        v, _ = betai_hyp(b, a, 1.0 - x)
        v = 1.0 - v
        return v, (math.log10(v) if v > 0 else float("-inf"))
    s, term = 1.0, 1.0
    for n in range(1, maxit):
        term *= (a + b + n - 1.0) / (a + 1.0 + n - 1.0) * x
        s += term
        if abs(term) < eps * abs(s):
            break
    lg = (a * math.log(x) + b * math.log1p(-x) - math.log(a) - _lbeta(a, b)
          + math.log(s))
    return math.exp(lg) if lg > -700 else 0.0, lg / math.log(10.0)


def t_two_sided(t, df):
    """P(|T_df| > |t|).  Returns (p, log10 p)."""
    if df <= 0:
        return float("nan"), float("nan")
    t = abs(t)
    if not math.isfinite(t):
        return 0.0, float("-inf")
    return betai_hyp(df / 2.0, 0.5, df / (df + t * t))


def chi2_sf_even_log10(x, df):
    """log10 P(chi2_df > x) for even df, computed in log space."""
    k = df // 2
    h = x / 2.0
    # sum_{i=0}^{k-1} h^i / i!  -> log-sum-exp
    logs = [i * math.log(h) - math.lgamma(i + 1.0) for i in range(k)]
    M = max(logs)
    lsum = M + math.log(sum(math.exp(l - M) for l in logs))
    return (-h + lsum) / math.log(10.0)


def fisher_log10(ps_log10):
    """Fisher combination taking per-test log10 p's; returns log10 combined p."""
    stat = -2.0 * math.log(10.0) * sum(ps_log10)
    return chi2_sf_even_log10(stat, 2 * len(ps_log10))


# ---------------------------------------------------------------- estimators
def two_by_two(recs):
    nA = len(recs); sA = sum(r["A_correct"] for r in recs)
    nB = len(recs); sB = sum(r["B_correct"] for r in recs)
    return sA, nA, sB, nB


def logit_closed_form(recs):
    """MLE of arm coefficient in logit(correct) ~ 1 + arm.

    With a single binary regressor the MLE is EXACTLY the sample log odds ratio.
    Returns (beta1, fitted pA, fitted pB).
    """
    sA, nA, sB, nB = two_by_two(recs)
    pA = sA / nA; pB = sB / nB
    return math.log((pB / (1 - pB)) / (pA / (1 - pA))), pA, pB


def logit_cluster_robust(recs):
    """Cluster-robust sandwich SE for the closed-form logit, clusters = context groups."""
    b1, pA, pB = logit_closed_form(recs)
    # Bread: X'WX with x=(1,arm); W=p(1-p) constant within arm
    wA = pA * (1 - pA); wB = pB * (1 - pB)
    n = len(recs)
    s00 = n * wA + n * wB
    s01 = n * wB
    s11 = n * wB
    det = s00 * s11 - s01 * s01
    i01 = -s01 / det; i11 = s00 / det
    # scores per cluster: u = sum_i x_i (y_i - p_i)
    sc = {}
    for r in recs:
        g = r["cluster"]
        u = sc.setdefault(g, [0.0, 0.0])
        u[0] += (r["A_correct"] - pA)          # arm A: x=(1,0)
        u[0] += (r["B_correct"] - pB)          # arm B: x=(1,1)
        u[1] += (r["B_correct"] - pB)
    G = len(sc)
    corr = G / (G - 1.0)
    m00 = corr * sum(u[0] * u[0] for u in sc.values())
    m01 = corr * sum(u[0] * u[1] for u in sc.values())
    m11 = corr * sum(u[1] * u[1] for u in sc.values())
    # v11 of  I M I
    a10 = i01 * m00 + i11 * m01
    a11 = i01 * m01 + i11 * m11
    v11 = a10 * i01 + a11 * i11
    se = math.sqrt(v11)
    p, lp = t_two_sided(b1 / se, G - 1)
    return b1, se, p, lp, G


def ols_cluster_robust(d, gid):
    """Intercept-only OLS mean-vs-0 with cluster-robust SE, t(G-1)."""
    n = len(d)
    mean = sum(d) / n
    agg = {}
    for x, g in zip(d, gid):
        agg[g] = agg.get(g, 0.0) + (x - mean)
    G = len(agg)
    meat = sum(u * u for u in agg.values())
    var = (G / (G - 1.0)) * meat / (n * n)
    se = math.sqrt(var)
    p, lp = t_two_sided(mean / se, G - 1)
    return mean, se, p, lp, G


def unit_series(recs):
    """Return the per-unit paired-difference series used by the curve (pp units)."""
    byit, bycl = {}, {}
    for r in recs:
        byit.setdefault(r["question_id"], []).append(r)
        bycl.setdefault(r["cluster"], []).append(r)
    it_d, it_cl = [], []
    for q, qr in byit.items():
        it_d.append(100.0 * (sum(x["B_correct"] for x in qr) - sum(x["A_correct"] for x in qr)) / len(qr))
        it_cl.append(qr[0]["cluster"])
    cl_d, cl_g = [], []
    for g in sorted(bycl):
        rs = bycl[g]
        cl_d.append(100.0 * (sum(x["B_correct"] for x in rs) - sum(x["A_correct"] for x in rs)) / len(rs))
        cl_g.append(g)
    md = []
    for m in MODELS:
        mr = [r for r in recs if r["model"] == m]
        md.append(100.0 * (sum(x["B_correct"] for x in mr) - sum(x["A_correct"] for x in mr)) / len(mr))
    return it_d, it_cl, cl_d, cl_g, md


# ---------------------------------------------------------------- main loop
print("=" * 100)
print("PART 1 -- independent recomputation of all 64 ANALYTIC specifications")
print("=" * 100)

analytic = []
for exclusion in ("primary", "defect_only", "notaA_only", "none"):
    for outcome in ("lenient", "strict"):
        recs = get_rows(exclusion, outcome)
        it_d, it_cl, cl_d, cl_g, md = unit_series(recs)

        def rec(unit, inf, pool, est, p, lp, extra=""):
            analytic.append(dict(exclusion=exclusion, outcome=outcome, unit=unit,
                                 inference=inf, pooling=pool, delta_pp=est,
                                 p=p, log10p=lp, note=extra))

        # --- cell / mcnemar_exact / pooled  (EXACT rational)
        b = sum(1 for r in recs if r["A_correct"] == 1 and r["B_correct"] == 0)
        c = sum(1 for r in recs if r["A_correct"] == 0 and r["B_correct"] == 1)
        fr = mcnemar_exact_frac(b, c)
        sA, nA, sB, nB = two_by_two(recs)
        est_cell = 100.0 * (sB - sA) / nA
        rec("cell", "mcnemar_exact", "pooled", est_cell, float(fr), log10_from_fraction(fr),
            f"b={b} c={c} n_disc={b+c}")

        # --- cell / logit_robustSE / pooled
        b1, se, p, lp, G = logit_cluster_robust(recs)
        rec("cell", "logit_robustSE", "pooled", est_cell, p, lp, f"logOR={b1:.4f} se={se:.4f} G={G}")

        # --- item / cluster / model  ols_robustSE / pooled
        m_, s_, p_, lp_, G_ = ols_cluster_robust(it_d, it_cl)
        rec("item", "ols_robustSE", "pooled", m_, p_, lp_, f"n={len(it_d)} G={G_}")
        m_, s_, p_, lp_, G_ = ols_cluster_robust(cl_d, cl_g)
        rec("cluster", "ols_robustSE", "pooled", m_, p_, lp_, f"n={len(cl_d)} G={G_}")
        m_, s_, p_, lp_, G_ = ols_cluster_robust(md, list(range(NM)))
        rec("model", "ols_robustSE", "pooled", m_, p_, lp_, f"n=4 G=4 t(3)")

        # --- separate (Fisher across 4 models)
        mcn_lp, log_lp, olc_lp, pm_delta = [], [], [], []
        for j, m in enumerate(MODELS):
            mr = [r for r in recs if r["model"] == m]
            bb = sum(1 for r in mr if r["A_correct"] == 1 and r["B_correct"] == 0)
            cc = sum(1 for r in mr if r["A_correct"] == 0 and r["B_correct"] == 1)
            mcn_lp.append(log10_from_fraction(mcnemar_exact_frac(bb, cc)))
            log_lp.append(logit_cluster_robust(mr)[3])
            bycl = {}
            for r in mr:
                bycl.setdefault(r["cluster"], []).append(r)
            dd, gg = [], []
            for g in sorted(bycl):
                rs = bycl[g]
                dd.append(100.0 * (sum(x["B_correct"] for x in rs) - sum(x["A_correct"] for x in rs)) / len(rs))
                gg.append(g)
            olc_lp.append(ols_cluster_robust(dd, gg)[3])
            pm_delta.append(100.0 * (sum(x["B_correct"] for x in mr) - sum(x["A_correct"] for x in mr)) / len(mr))
        est_sep = sum(pm_delta) / NM
        for nm, lps in (("mcnemar_exact", mcn_lp), ("logit_robustSE", log_lp)):
            L = fisher_log10(lps)
            rec("cell", nm, "separate", est_sep, 10.0 ** L if L > -300 else 0.0, L,
                "per-model log10p=" + ",".join(f"{v:.2f}" for v in lps))
        L = fisher_log10(olc_lp)
        rec("cluster", "ols_robustSE", "separate", est_sep, 10.0 ** L if L > -300 else 0.0, L,
            "per-model log10p=" + ",".join(f"{v:.2f}" for v in olc_lp))

print(f"recomputed {len(analytic)} analytic specs")

# ---- compare against the published curve
pub = json.load(open(os.path.join(HERE, "sens_speccurve_results.json")))["results"]
AN = ("mcnemar_exact", "logit_robustSE", "ols_robustSE")
pubmap = {(x["exclusion"], x["outcome"], x["unit"], x["inference"], x["pooling"]): x
          for x in pub if x["inference"] in AN}
print(f"published analytic specs: {len(pubmap)}")
worst = 0.0
for a in analytic:
    k = (a["exclusion"], a["outcome"], a["unit"], a["inference"], a["pooling"])
    q = pubmap[k]["p"]
    lq = math.log10(q) if q > 0 else -400.0
    worst = max(worst, abs(a["log10p"] - lq))
    if abs(a["log10p"] - lq) > 0.02:
        print(f"  MISMATCH {k}: mine log10p={a['log10p']:.4f} published log10p={lq:.4f}")
print(f"max |log10 p| discrepancy vs published: {worst:.2e}")

json.dump(analytic, open(os.path.join(HERE, "sens_refute_mcfloor_01_out.json"), "w"), indent=1)


def summarise(tag, specs):
    ps = sorted(x["p"] for x in specs)
    lps = sorted(x["log10p"] for x in specs)
    n = len(ps)
    med = (lps[n // 2 - 1] + lps[n // 2]) / 2 if n % 2 == 0 else lps[n // 2]
    print(f"\n{tag}: n={n}")
    print(f"  median p = 1e{med:.2f}   max p = {ps[-1]:.4g}   min p = 1e{lps[0]:.1f}")
    print(f"  frac p<0.05 = {sum(1 for p in ps if p < 0.05)/n:.3f}"
          f"   frac p<0.001 = {sum(1 for p in ps if p < 0.001)/n:.3f}")


print("\n" + "=" * 100)
print("PART 2 -- the claim's headline numbers, recomputed")
print("=" * 100)
summarise("ANALYTIC-ONLY SUBSET (claim's subset)", analytic)

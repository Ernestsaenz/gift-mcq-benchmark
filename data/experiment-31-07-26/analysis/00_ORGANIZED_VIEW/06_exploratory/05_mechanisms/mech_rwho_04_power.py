"""R4. What do the 'flat' verdicts actually license?

A null Wald test is not evidence of a null effect.  For each feature the claim calls
flat, report the largest effect the data still tolerate (the far end of the 95% CI)
and the minimum OR the design could have detected at 80% power, given the realised
cluster-robust SE:   MDOR = exp(1.96*SE + 0.84*SE) = exp(2.80*SE).
Also: an equivalence (TOST-style) test against a pre-set 'negligible' band of
OR in [1/1.5, 1.5] -- if the CI does not fit inside the band, 'flat' is not established.
"""
import math
from mech_rwho_00_data import cells, MODELS
from mech_rwho_lib import run, norm_cdf

Ac = [r for r in cells if r["A_correct"] == 1]


def zf(f):
    v = [f(r) for r in Ac]
    m = sum(v) / len(v)
    s = math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))
    return lambda r: (f(r) - m) / s


TERMS = [
    ("model=gemma-4-26b", lambda r: float(r["model"] == MODELS[1])),
    ("model=qwen3.6-35b", lambda r: float(r["model"] == MODELS[2])),
    ("model=glm-5.2", lambda r: float(r["model"] == MODELS[3])),
    ("NOTA slot=c (vs b)", lambda r: float(r["correct_letter"] == "c")),
    ("NOTA slot=d (vs b)", lambda r: float(r["correct_letter"] == "d")),
    ("negated_stem", lambda r: float(r["negated_stem"])),
    ("has_context", lambda r: float(r["has_context"])),
    ("qlen (z)", zf(lambda r: r["qlen"])),
    ("peer A-acc (LOO, 0-1)", lambda r: r["loo_A_acc"]),
    ("log correct-opt len (z)", zf(lambda r: math.log(r["correct_chars"]))),
    ("correct opt was longest", lambda r: float(r["is_longest"])),
]

b, V, names, ll, G = run(Ac, lambda r: r["lost"], TERMS, quiet=True)
BAND = math.log(1.5)
print("=" * 104)
print("R4. PRECISION OF THE 'FLAT' VERDICTS  (claimed spec, cluster-robust CR1, G=%d)" % G)
print(f"  {'term':<28}{'OR':>7}{'SE':>7}{'95% CI (OR)':>20}"
      f"{'|OR| still tolerated':>21}{'80%-power MDOR':>16}{'equiv?':>8}")
FLAT = ["NOTA slot=c (vs b)", "NOTA slot=d (vs b)", "negated_stem", "has_context",
        "qlen (z)", "log correct-opt len (z)", "correct opt was longest"]
for nm in FLAT + ["peer A-acc (LOO, 0-1)", "model=gemma-4-26b"]:
    j = names.index(nm)
    se = math.sqrt(V[j][j])
    lo, hi = b[j] - 1.96 * se, b[j] + 1.96 * se
    worst = max(abs(lo), abs(hi))
    mdor = math.exp(2.80 * se)
    equiv = "YES" if (lo > -BAND and hi < BAND) else "no"
    print(f"  {nm:<28}{math.exp(b[j]):>7.2f}{se:>7.3f}"
          f"{'[%.2f, %.2f]' % (math.exp(lo), math.exp(hi)):>20}"
          f"{math.exp(worst):>21.2f}{mdor:>16.2f}{equiv:>8}")
print("  'equiv?' = both CI limits inside OR (1/1.5, 1.5); TOST at alpha=.05 with a")
print("  1.5-fold negligibility band.  MDOR = exp(2.80*SE), the smallest OR this design")
print("  would reject the null for 80% of the time at the realised SE.")

print()
print("=" * 104)
print("R5. IS THERE ANY ITEM-LEVEL SIGNAL LEFT TO FIND?")
print("  Item-level heterogeneity test: fit P(lost) ~ model dummies only, then compare the")
print("  observed between-item variance of the loss count with its binomial expectation.")
Xm = [[1.0, float(r["model"] == MODELS[1]), float(r["model"] == MODELS[2]),
       float(r["model"] == MODELS[3])] for r in Ac]
from mech_rwho_lib import fit_logit, chi2_sf
bm, _, pm, _ = fit_logit(Xm, [float(r["lost"]) for r in Ac])
byq = {}
for i, r in enumerate(Ac):
    byq.setdefault(r["question_id"], []).append((r["lost"], pm[i]))
stat = 0.0
for q, v in byq.items():
    o = sum(x for x, _ in v)
    e = sum(p for _, p in v)
    var = sum(p * (1 - p) for _, p in v)
    if var > 0:
        stat += (o - e) ** 2 / var
df = len(byq)
print(f"  dispersion chi2 = {stat:.1f} on {df} items (Pearson-type overdispersion statistic),")
print(f"  ratio = {stat/df:.3f},  p = {chi2_sf(stat, df):.4g}")
print("  (>1 with small p = real item-to-item variation in loss beyond model identity;")
print("   ~1 = the loss process is nearly exchangeable across items.)")

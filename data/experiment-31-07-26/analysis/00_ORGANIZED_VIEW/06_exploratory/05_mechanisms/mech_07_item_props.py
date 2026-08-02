"""(iii, supplement) Item properties that are NOT derived from model accuracy:
question length, presence of a clinical vignette, negated stem, and the
character length of the correct option that was deleted in B.

Retention P(B correct | A correct) is the outcome throughout: it is free of the
ceiling artifact that contaminates difficulty scores built from A accuracy.

Method: logistic regression MLE (own Newton-Raphson) with model dummies,
Wald p from the inverse observed information, plus a cluster bootstrap
(208 clusters, 2000 reps, percentile) 95% CI on each coefficient.
"""
import json, math
from mech_merge import load_merged
from mech_lib_effort import (MODELS, SHORT, mean, sd, median, logistic_fit,
                             cluster_bootstrap, boot_p_two_sided, quantile)
from mech_lib_effort import cp_ci as binom_exact_ci

rows = load_merged()
db = json.load(open("mech_db_cells.json"))
tx = {tuple(t["key"]): t for t in db["texts"]}
for r in rows:
    ta = tx.get(("balanced_a_310726", r["question_id"]))
    r["ans_chars"] = len(ta["correct_option_text"]) if ta else float("nan")

mods = MODELS[1:]
sub = [r for r in rows if r["A_correct"] == 1]

# standardise continuous predictors on the retained subset
for f in ("qlen", "ans_chars"):
    v = [r[f] for r in sub]
    mu, s = mean(v), sd(v)
    for r in rows:
        r["z_" + f] = (r[f] - mu) / s

print("=" * 104)
print("(iii-supplement) ITEM PROPERTIES vs RETENTION  P(B correct | A correct)")
print(f"n = {len(sub)} retained cells of {len(rows)}")
print("=" * 104)


def design(rs):
    X, y = [], []
    for r in rs:
        X.append([r["z_qlen"], r["z_ans_chars"],
                  1.0 if r["has_context"] else 0.0,
                  1.0 if r["negated_stem"] else 0.0]
                 + [1.0 if r["model"] == mm else 0.0 for mm in mods])
        y.append(float(r["B_correct"]))
    return X, y


X, y = design(sub)
b, se = logistic_fit(X, y)
names = ["intercept", "z_qlen", "z_deleted_answer_chars", "has_context",
         "negated_stem"] + [SHORT[mm] for mm in mods]


def coef(i):
    def g(rs):
        rs = [r for r in rs if r["A_correct"] == 1]
        XX, yy = design(rs)
        if len(set(yy)) < 2:
            return None
        bb, _ = logistic_fit(XX, yy)
        return None if bb is None else bb[i]
    return g


for i, nm in enumerate(names):
    z = b[i] / se[i]
    _, lo, hi, reps = cluster_bootstrap(rows, coef(i), B=1500, seed=70 + i)
    print(f"   {nm:<24} b={b[i]:>+8.4f} OR={math.exp(b[i]):>6.3f} "
          f"p_wald={math.erfc(abs(z)/math.sqrt(2)):>9.4g} "
          f"cluster-boot 95% CI [{lo:>+7.4f},{hi:>+7.4f}] "
          f"p_boot={boot_p_two_sided(reps,0.0):.4g}")

print()
print("-" * 104)
print("Marginal view: retention by tercile of the deleted correct-option length")
print("-" * 104)
v = sorted(r["ans_chars"] for r in sub)
t1, t2 = v[len(v) // 3], v[2 * len(v) // 3]
print(f"   terciles of deleted-answer length: <= {t1:.0f}, "
      f"{t1:.0f}-{t2:.0f}, > {t2:.0f} chars")
print(f"{'band':>28} {'n':>6} {'retention':>10} {'95% CI (Clopper-Pearson)':>28}")
for lab, sel in ((f"short (<= {t1:.0f} chars)", lambda x: x <= t1),
                 (f"mid ({t1:.0f}-{t2:.0f})", lambda x: t1 < x <= t2),
                 (f"long (> {t2:.0f} chars)", lambda x: x > t2)):
    rs = [r for r in sub if sel(r["ans_chars"])]
    k = sum(r["B_correct"] for r in rs)
    ci = binom_exact_ci(k, len(rs))
    print(f"{lab:>28} {len(rs):>6} {k/len(rs):>10.3f} "
          f"[{ci[0]:.3f},{ci[1]:.3f}]{'':>10}")

print()
print("-" * 104)
print("Retention by question length (qlen) tercile")
print("-" * 104)
v = sorted(r["qlen"] for r in sub)
q1, q2 = v[len(v) // 3], v[2 * len(v) // 3]
for lab, sel in ((f"short (<= {q1} chars)", lambda x: x <= q1),
                 (f"mid ({q1}-{q2})", lambda x: q1 < x <= q2),
                 (f"long (> {q2} chars)", lambda x: x > q2)):
    rs = [r for r in sub if sel(r["qlen"])]
    k = sum(r["B_correct"] for r in rs)
    ci = binom_exact_ci(k, len(rs))
    print(f"{lab:>28} {len(rs):>6} {k/len(rs):>10.3f} "
          f"[{ci[0]:.3f},{ci[1]:.3f}]")

print()
print("-" * 104)
print("Sanity: is qlen actually a difficulty proxy?  correlation with A accuracy")
print("-" * 104)
from mech_lib_effort import spearman, pearson
for m in MODELS:
    rs = [r for r in rows if r["model"] == m]
    print(f"   {SHORT[m]:<18} spearman(qlen, A_correct) = "
          f"{spearman([r['qlen'] for r in rs], [r['A_correct'] for r in rs]):+.3f}   "
          f"spearman(qlen, A_reason) = "
          f"{spearman([r['qlen'] for r in rs], [r['A_reason'] for r in rs]):+.3f}")

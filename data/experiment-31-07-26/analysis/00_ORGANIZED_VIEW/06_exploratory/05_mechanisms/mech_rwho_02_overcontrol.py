"""R2. Is 'all item features are flat' an artefact of the specification?

Two structural worries about the claimed model:
  (i)  peer A-accuracy (LOO) is an item-level near-sufficient statistic for item
       difficulty.  Every item feature acts on loss partly THROUGH difficulty, so
       conditioning on it estimates direct effects only and blocks the indirect path.
  (ii) the design is internally collinear: has_context <-> qlen, and
       log correct-option length <-> 'correct option was longest'.
Both push item-feature coefficients toward zero.
"""
import math
from mech_rwho_00_data import cells, MODELS
from mech_rwho_lib import run, wald, fit_logit, build, norm_cdf

Ac = [r for r in cells if r["A_correct"] == 1]


def zf(rows, f):
    v = [f(r) for r in rows]
    m = sum(v) / len(v)
    s = math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))
    return lambda r: (f(r) - m) / s


MOD = [("model=gemma-4-26b", lambda r: float(r["model"] == MODELS[1])),
       ("model=qwen3.6-35b", lambda r: float(r["model"] == MODELS[2])),
       ("model=glm-5.2", lambda r: float(r["model"] == MODELS[3]))]

ITEM = [("NOTA slot=c (vs b)", lambda r: float(r["correct_letter"] == "c")),
        ("NOTA slot=d (vs b)", lambda r: float(r["correct_letter"] == "d")),
        ("negated_stem", lambda r: float(r["negated_stem"])),
        ("has_context", lambda r: float(r["has_context"])),
        ("qlen (z)", zf(Ac, lambda r: r["qlen"])),
        ("log correct-opt len (z)", zf(Ac, lambda r: math.log(r["correct_chars"]))),
        ("correct opt was longest", lambda r: float(r["is_longest"]))]
PEER = ("peer A-acc (LOO, 0-1)", lambda r: r["loo_A_acc"])

print("=" * 96)
print("A. HOW MUCH ITEM INFORMATION DOES peer A-accuracy ALREADY CARRY?")
print("   Regress the LOO peer A-accuracy of an item on the same item features")
print("   (OLS on the 325 items, one row per item; R^2 by ANOVA decomposition).")
items = {}
for r in cells:
    items.setdefault(r["question_id"], r)
rows_i = list(items.values())
XI, ni = build(rows_i, ITEM)
yi = [r["loo_A_acc"] for r in rows_i]


def ols(X, y):
    n, k = len(X), len(X[0])
    XtX = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    Xty = [sum(X[i][a] * y[i] for i in range(n)) for a in range(k)]
    from mech_rwho_lib import chol, chol_solve
    return chol_solve(chol(XtX), Xty)


bi = ols(XI, yi)
fit = [sum(XI[i][j] * bi[j] for j in range(len(bi))) for i in range(len(XI))]
my = sum(yi) / len(yi)
sst = sum((v - my) ** 2 for v in yi)
sse = sum((yi[i] - fit[i]) ** 2 for i in range(len(yi)))
print(f"   R^2 of item features on peer A-accuracy = {1 - sse / sst:.3f}  "
      f"(n={len(rows_i)} items, {len(ITEM)} features)")
print("   -> the covariate the claim calls 'item difficulty' is partly a")
print("      re-expression of the very features it is used to adjust away.")

print()
print("=" * 96)
print("B. THE SAME ITEM FEATURES, TOTAL EFFECT (peer A-accuracy DROPPED)")
b2, V2, n2, _, _ = run(Ac, lambda r: r["lost"], MOD + ITEM,
                       label="   P(LOST | A correct) ~ model + item features")
ix = lambda n: n2.index(n)
st, df, p = wald(b2, V2, [ix(t[0]) for t in ITEM])
print(f"\n   joint Wald, ALL 7 item features (7 df): chi2={st:.2f} p={p:.4g}")

print()
print("=" * 96)
print("C. DE-COLLINEARISED: drop 'correct opt was longest' (collinear with length)")
print("   and drop qlen (collinear with has_context); keep peer A-accuracy.")
T3 = MOD + [("NOTA slot=c (vs b)", lambda r: float(r["correct_letter"] == "c")),
            ("NOTA slot=d (vs b)", lambda r: float(r["correct_letter"] == "d")),
            ("negated_stem", lambda r: float(r["negated_stem"])),
            ("has_context", lambda r: float(r["has_context"])),
            ("log correct-opt len (z)", zf(Ac, lambda r: math.log(r["correct_chars"]))),
            PEER]
run(Ac, lambda r: r["lost"], T3, label="   parsimonious, difficulty-adjusted")

print()
print("=" * 96)
print("D. CORRECT-OPTION LENGTH ALONE (model dummies only), several encodings")
enc = [("log chars (z)", lambda r: math.log(r["correct_chars"])),
       ("chars (z)", lambda r: float(r["correct_chars"])),
       ("words (z)", lambda r: float(r["correct_words"])),
       ("words - mean distractor words (z)", lambda r: r["len_diff_w"]),
       ("chars / mean distractor chars (z)", lambda r: r["len_ratio"])]
for lab, f in enc:
    bb, VV, nn, _, _ = run(Ac, lambda r: r["lost"], MOD + [(lab, zf(Ac, f))],
                           quiet=True)
    j = nn.index(lab)
    se = math.sqrt(VV[j][j])
    z = bb[j] / se
    print(f"   {lab:<38} OR={math.exp(bb[j]):.3f} "
          f"[{math.exp(bb[j]-1.96*se):.3f}, {math.exp(bb[j]+1.96*se):.3f}] "
          f"z={z:5.2f} p={2*(1-norm_cdf(abs(z))):.4f}")
print("   (each row: P(lost|A correct) ~ 3 model dummies + that one length term,")
print("    cluster-robust CR1 on 205 stem-clusters, Wald z, two-sided normal p)")

print()
print("=" * 96)
print("E. LENGTH-RANK OF THE CORRECT OPTION (0=longest .. 3=shortest), 3 df")
T5 = MOD + [(f"len_rank={k}", (lambda k: lambda r: float(r["len_rank"] == k))(k))
            for k in (1, 2, 3)]
b5, V5, n5, _, _ = run(Ac, lambda r: r["lost"], T5,
                       label="   P(LOST) ~ model + length rank (ref = rank 0, longest)")
st, df, p = wald(b5, V5, [n5.index(f"len_rank={k}") for k in (1, 2, 3)])
print(f"   joint Wald, length rank (3 df): chi2={st:.2f} p={p:.4g}")

"""Logistic models of P(lost | A correct) and P(gained | A wrong), cluster-robust SEs."""
import math, collections
from mech_who_00_build import cells
from mech_who_lib import logit_fit, cluster_robust, report, wald_joint, lrt

MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
REF = MODELS[0]

def z(vals):
    m = sum(vals) / len(vals)
    s = math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))
    return m, s

def design(rows, terms):
    X, names = [], []
    for r in rows:
        X.append([1.0] + [t[1](r) for t in terms])
    names = ["(intercept)"] + [t[0] for t in terms]
    return X, names

def build_terms(rows):
    mq, sq = z([r["qlen"] for r in rows])
    mc, sc = z([math.log(r["correct_len"]) for r in rows])
    return [
        ("model=gemma-4-26b", lambda r: float(r["model"] == MODELS[1])),
        ("model=qwen3.6-35b", lambda r: float(r["model"] == MODELS[2])),
        ("model=glm-5.2", lambda r: float(r["model"] == MODELS[3])),
        ("NOTA slot = c (vs b)", lambda r: float(r["correct_letter"] == "c")),
        ("NOTA slot = d (vs b)", lambda r: float(r["correct_letter"] == "d")),
        ("negated_stem", lambda r: float(r["negated_stem"])),
        ("has_context", lambda r: float(r["has_context"])),
        ("qlen (z)", lambda r: (r["qlen"] - mq) / sq),
        ("peer A-accuracy (LOO, 0-1)", lambda r: r["loo_A_acc"]),
        ("log correct-option len (z)", lambda r: (math.log(r["correct_len"]) - mc) / sc),
        ("correct opt was longest", lambda r: float(r["is_longest"])),
    ]

def run(rows, outcome, label):
    terms = build_terms(rows)
    X, names = design(rows, terms)
    y = [float(r[outcome]) for r in rows]
    cl = [r["cluster"] for r in rows]
    beta, bread, p, ll = logit_fit(X, y, ridge=0.0)
    V, G = cluster_robust(X, y, p, bread, cl)
    print("=" * 92)
    print(f"{label}   n={len(rows)}  events={int(sum(y))} ({sum(y)/len(rows):.3f})  "
          f"clusters={len(set(cl))}")
    report(names, beta, V, G, label="")
    # joint tests
    for grp, idx in (("model (3 df)", [1, 2, 3]), ("NOTA slot letter (2 df)", [4, 5])):
        st, df, pv = wald_joint(beta, V, idx)
        print(f"    joint Wald, {grp}: chi2={st:.2f}, df={df}, p={pv:.4g}")
    # LRT for each single term (naive, ignores clustering -> report as sensitivity only)
    print("    naive LRT (non-clustered, sensitivity only):")
    for j in range(1, len(names)):
        keep = [i for i in range(len(names)) if i != j]
        Xr = [[row[i] for i in keep] for row in X]
        _, _, _, llr = logit_fit(Xr, y)
        st, df, pv = lrt(ll, llr, 1)
        print(f"      drop {names[j]:<30} LR chi2={st:6.2f}  p={pv:.4g}")
    return beta, V, names

Acorr = [r for r in cells if r["A_correct"] == 1]
Awrong = [r for r in cells if r["A_correct"] == 0]
run(Acorr, "lost", "MODEL 1:  P(LOST | A correct)     outcome = A right, B wrong")
print()
run(Awrong, "gained", "MODEL 2:  P(GAINED | A wrong)    outcome = A wrong, B right")

# ---- sensitivity: model 2 with fewer terms (45 events) ----
print()
print("=" * 92)
print("MODEL 2b (parsimonious, 45 events): model + NOTA slot + peer A-accuracy only")
rows = Awrong
terms = [t for t in build_terms(rows)
         if t[0] in ("model=gemma-4-26b", "model=qwen3.6-35b", "model=glm-5.2",
                     "NOTA slot = c (vs b)", "NOTA slot = d (vs b)",
                     "peer A-accuracy (LOO, 0-1)")]
X, names = design(rows, terms)
y = [float(r["gained"]) for r in rows]
cl = [r["cluster"] for r in rows]
beta, bread, p, ll = logit_fit(X, y)
V, G = cluster_robust(X, y, p, bread, cl)
report(names, beta, V, G, "")
for grp, idx in (("model (3 df)", [1, 2, 3]), ("NOTA slot letter (2 df)", [4, 5])):
    st, df, pv = wald_joint(beta, V, idx)
    print(f"    joint Wald, {grp}: chi2={st:.2f}, df={df}, p={pv:.4g}")

# ---- NOTA slot effect on B accuracy overall (all cells), a cleaner framing ----
print()
print("=" * 92)
print("MODEL 3: P(B correct) on NOTA slot, controlling model + A_correct  (all 1299 cells)")
rows = cells
terms = [("model=gemma-4-26b", lambda r: float(r["model"] == MODELS[1])),
         ("model=qwen3.6-35b", lambda r: float(r["model"] == MODELS[2])),
         ("model=glm-5.2", lambda r: float(r["model"] == MODELS[3])),
         ("NOTA slot = c (vs b)", lambda r: float(r["correct_letter"] == "c")),
         ("NOTA slot = d (vs b)", lambda r: float(r["correct_letter"] == "d")),
         ("A_correct", lambda r: float(r["A_correct"]))]
X, names = design(rows, terms)
y = [float(r["B_correct"]) for r in rows]
cl = [r["cluster"] for r in rows]
beta, bread, p, ll = logit_fit(X, y)
V, G = cluster_robust(X, y, p, bread, cl)
report(names, beta, V, G, "")
st, df, pv = wald_joint(beta, V, [4, 5])
print(f"    joint Wald, NOTA slot letter: chi2={st:.2f}, df={df}, p={pv:.4g}")
print()
print("  same specification but outcome = A_correct (placebo: slot letter should not matter in A)")
X, names = design(rows, terms[:5])
y = [float(r["A_correct"]) for r in rows]
beta, bread, p, ll = logit_fit(X, y)
V, G = cluster_robust(X, y, p, bread, cl)
report(names, beta, V, G, "")
st, df, pv = wald_joint(beta, V, [4, 5])
print(f"    joint Wald, correct-letter: chi2={st:.2f}, df={df}, p={pv:.4g}")

"""Step 1: replicate the who-recovers P(lost | A correct) model on the CURRENT data."""
import math, sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mech_ref_02_build import cells, MODELS
from mech_ref_lib import logit, sandwich, report, wald_joint, norm_p, jackknife_cluster

Ac = [r for r in cells if r["A_correct"] == 1]


def zf(rows, f):
    v = [f(r) for r in rows]
    m = sum(v) / len(v)
    s = math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))
    return lambda r: (f(r) - m) / s


def fit(rows, yf, terms, label, use_t=True, jack=False):
    X = [[1.0] + [t[1](r) for t in terms] for r in rows]
    names = ["(intercept)"] + [t[0] for t in terms]
    y = [float(yf(r)) for r in rows]
    cl = [r["cluster"] for r in rows]
    f = logit(X, y)
    V, G = sandwich(f, cl, "CR1")
    print("=" * 100)
    print(f"{label}\n  n={len(rows)}  events={int(sum(y))} ({sum(y)/len(rows):.3f})  clusters={G}")
    rows_out = report(names, f["beta"], V, G, use_t=use_t)
    if jack:
        Vj, Gj, bj = jackknife_cluster(X, y, cl)
        print("  leave-one-cluster-out jackknife SEs: " +
              ", ".join(f"{names[j]}={math.sqrt(Vj[j][j]):.3f}" for j in range(1, len(names))))
    return f["beta"], V, names, rows_out


TERMS = [
    ("model=gemma-4-26b", lambda r: float(r["model"] == MODELS[1])),
    ("model=qwen3.6-35b", lambda r: float(r["model"] == MODELS[2])),
    ("model=glm-5.2", lambda r: float(r["model"] == MODELS[3])),
    ("NOTA slot = c (vs b)", lambda r: float(r["correct_letter"] == "c")),
    ("NOTA slot = d (vs b)", lambda r: float(r["correct_letter"] == "d")),
    ("negated_stem", lambda r: float(r["negated_stem"])),
    ("has_context", lambda r: float(r["has_context"])),
    ("qlen (z)", zf(Ac, lambda r: r["qlen"])),
    ("peer A-accuracy (LOO, 0-1)", lambda r: r["loo_A_acc"]),
    ("log correct-option len (z)", zf(Ac, lambda r: math.log(r["correct_len"]))),
    ("correct opt was longest", lambda r: float(r["is_longest"])),
]

print("peer A-accuracy (LOO) distribution in the A-correct stratum:")
print("  ", collections.Counter(round(r["loo_A_acc"], 3) for r in Ac))
print("peer A-accuracy by model within the A-correct stratum (mean):")
for m in MODELS:
    rr = [r for r in Ac if r["model"] == m]
    print(f"   {m:<28} n={len(rr):<5} mean loo_A_acc={sum(x['loo_A_acc'] for x in rr)/len(rr):.3f}"
          f"  loss rate={sum(x['lost'] for x in rr)/len(rr):.3f}")
print()

b, V, names, out = fit(Ac, lambda r: r["lost"], TERMS,
                       "M1. EXACT who-recovers SPEC, current paired_clean.json  (t(G-1) reference)",
                       use_t=True)
print()
b2, V2, n2, out2 = fit(Ac, lambda r: r["lost"], TERMS,
                       "M1n. same, but Wald z / normal reference (as the claim reports it)",
                       use_t=False)
for grp, idx in (("model (3 df)", [1, 2, 3]), ("NOTA slot letter (2 df)", [4, 5])):
    st, df, pv = wald_joint(b, V, idx)
    print(f"   joint Wald {grp}: chi2={st:.2f}, df={df}, p={pv:.4g}")

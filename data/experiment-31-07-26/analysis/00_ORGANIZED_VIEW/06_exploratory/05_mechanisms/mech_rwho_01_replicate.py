"""R1. Replicate the claimed P(lost | A correct) logit with an independent implementation."""
import math
from mech_rwho_00_data import cells, MODELS
from mech_rwho_lib import run, wald

Ac = [r for r in cells if r["A_correct"] == 1]


def zf(rows, f):
    v = [f(r) for r in rows]
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
    ("qlen (z)", zf(Ac, lambda r: r["qlen"])),
    ("peer A-acc (LOO, 0-1)", lambda r: r["loo_A_acc"]),
    ("log correct-opt len (z)", zf(Ac, lambda r: math.log(r["correct_chars"]))),
    ("correct opt was longest", lambda r: float(r["is_longest"])),
]

b, V, names, ll, G = run(Ac, lambda r: r["lost"], TERMS,
                         label="R1  P(LOST | A correct)  full claimed specification")
ix = lambda n: names.index(n)
st, df, p = wald(b, V, [ix("model=gemma-4-26b"), ix("model=qwen3.6-35b"), ix("model=glm-5.2")])
print(f"\n  joint Wald model (3 df): chi2={st:.2f} p={p:.4g}")
st, df, p = wald(b, V, [ix("NOTA slot=c (vs b)"), ix("NOTA slot=d (vs b)")])
print(f"  joint Wald NOTA slot letter (2 df): chi2={st:.2f} p={p:.4g}")

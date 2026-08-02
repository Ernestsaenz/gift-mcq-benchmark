"""Part 3: independent validation of the item-fixed-effects machinery.

Within a single model, a logistic regression of correctness on condition with
item fixed effects is exactly the conditional (matched-pair) logit, whose MLE
is log(n01/n10) from the McNemar discordant counts. We recompute the item-FE
fit per model with our own IRLS and check it reproduces that closed form, and
we report exact-binomial McNemar p-values.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prim_linalg import irls_logit, model_based_vcov, cluster_robust_vcov

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
SHORT = {m: m.split("/")[1] for m in MODELS}

raw = json.load(open(os.path.join(HERE, "paired_clean.json")))
cells = [r for r in raw if r.get("analysis_include") is True]


def binom_two_sided_exact(b, c):
    """Exact McNemar: P(X>=max | X~Bin(b+c, 0.5)) * 2, capped at 1."""
    n = b + c
    if n == 0:
        return 1.0
    k = max(b, c)
    tot = 0.0
    for i in range(k, n + 1):
        tot += math.comb(n, i)
    p = 2.0 * tot / (2.0 ** n)
    return min(1.0, p)


print("=" * 78)
print("VALIDATION: per-model item-FE logit  ==  McNemar conditional logit")
print("=" * 78)
print("  n10 = A correct & B wrong (loss);  n01 = A wrong & B correct (gain)")
print("  conditional MLE of the within-item condition log-OR = log(n01/n10)")
print()
print("  %-20s %6s %6s %6s %6s | %10s %10s %10s"
      % ("model", "n11", "n10", "n01", "n00", "log(n01/n10)", "IRLS b",
         "SE_cond"))
for m in MODELS:
    sub = [r for r in cells if r["model"] == m]
    n11 = sum(1 for r in sub if r["A_correct"] == 1 and r["B_correct"] == 1)
    n10 = sum(1 for r in sub if r["A_correct"] == 1 and r["B_correct"] == 0)
    n01 = sum(1 for r in sub if r["A_correct"] == 0 and r["B_correct"] == 1)
    n00 = sum(1 for r in sub if r["A_correct"] == 0 and r["B_correct"] == 0)
    closed = math.log(n01 / n10) if n01 > 0 and n10 > 0 else float("nan")
    se_closed = math.sqrt(1.0 / n01 + 1.0 / n10) if n01 > 0 and n10 > 0 else float("nan")

    # item-FE IRLS restricted to this model, discordant items only
    disc = [r for r in sub if r["A_correct"] != r["B_correct"]]
    ids = sorted(set(r["question_id"] for r in disc))
    ix = {q: i + 1 for i, q in enumerate(ids)}
    X, y = [], []
    for r in disc:
        for cond, key in ((0, "A_correct"), (1, "B_correct")):
            row = [(ix[r["question_id"]], 1.0)]
            if cond == 1:
                row.append((0, 1.0))
            X.append(row)
            y.append(int(r[key]))
    f = irls_logit(X, y, len(ids) + 1, maxit=400, tol=1e-12)
    V = model_based_vcov(f)
    print("  %-20s %6d %6d %6d %6d | %10.5f %10.5f %10.5f"
          % (SHORT[m], n11, n10, n01, n00, closed, f["beta"][0],
             math.sqrt(V[0][0])))
    print("      closed-form SE=%.5f  |  exact McNemar two-sided p=%.4g"
          % (se_closed, binom_two_sided_exact(n10, n01)))
    print("      OR=%.4f  95%% CI [%.4f, %.4f] (closed form, Wald)"
          % (math.exp(closed), math.exp(closed - 1.96 * se_closed),
             math.exp(closed + 1.96 * se_closed)))

# pooled discordant counts across all 4 models
tot10 = sum(1 for r in cells if r["A_correct"] == 1 and r["B_correct"] == 0)
tot01 = sum(1 for r in cells if r["A_correct"] == 0 and r["B_correct"] == 1)
print("\n  POOLED across the 4 models (NOT independent, for description only):")
print("    n10=%d  n01=%d  log(n01/n10)=%+.5f  OR=%.4f"
      % (tot10, tot01, math.log(tot01 / tot10), tot01 / tot10))

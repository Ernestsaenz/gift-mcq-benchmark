"""Independent refutation recount of the cross-arm A claim. Stdlib only.
No import of ca_lib -- every statistic reimplemented from scratch.
"""
import json, math, os, random
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
rows_all = json.load(open(os.path.join(BASE, "cross_arm_A.json")))
rows = [r for r in rows_all if r.get("analysis_include") is True]

MODELS = ["google/gemma-4-26b-a4b-it", "z-ai/glm-5.2",
          "qwen/qwen3.6-35b-a3b", "google/gemini-3.6-flash"]
SHORT = {"google/gemini-3.6-flash": "gemini-3.6-flash",
         "google/gemma-4-26b-a4b-it": "gemma-4-26b-a4b-it",
         "qwen/qwen3.6-35b-a3b": "qwen3.6-35b-a3b",
         "z-ai/glm-5.2": "glm-5.2"}

print("=== SHAPE ===")
print("rows total          :", len(rows_all))
print("analysis_include    :", len(rows))
print("distinct items      :", len(set(r["question_id"] for r in rows)))
print("distinct clusters   :", len(set(r["cluster"] for r in rows)))
print("distinct models     :", len(set(r["model"] for r in rows)))
# is it a perfectly balanced 311 x 4 grid?
per_item = defaultdict(set)
for r in rows:
    per_item[r["question_id"]].add(r["model"])
bad = {q: sorted(v) for q, v in per_item.items() if len(v) != 4}
print("items without all 4 models:", bad)
# check no None correctness sneaks in
print("gift_correct values :", sorted(set(r["gift_correct"] for r in rows)))
print("or_correct values   :", sorted(set(r["or_correct"] for r in rows)))
excl = [r for r in rows_all if not r.get("analysis_include")]
print("excluded rows       :", len(excl),
      "reasons excl_item_defect:", sum(1 for r in excl if r.get("excl_item_defect")))
print("excluded item ids   :", sorted(set(r["question_id"] for r in excl)))


# ------------------------------------------------------------------ tests
def lchoose(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def binom_pmf(k, n):
    return math.exp(lchoose(n, k) - n * math.log(2.0))


def sign_exact(b, c):
    """Two-sided exact binomial (sign) test, p=0.5, on b+c discordant pairs.
    Method: sum of all outcome probabilities <= P(observed)."""
    n = b + c
    if n == 0:
        return 1.0
    obs = binom_pmf(b, n)
    return min(1.0, sum(binom_pmf(k, n) for k in range(n + 1)
                        if binom_pmf(k, n) <= obs * (1 + 1e-9)))


def chi2_sf_1df(x):
    return 1.0 if x <= 0 else math.erfc(math.sqrt(x / 2.0))


def mcnemar_chi2(b, c, cc):
    if b + c == 0:
        return 0.0, 1.0
    num = max(0.0, abs(b - c) - (1.0 if cc else 0.0))
    x2 = num * num / (b + c)
    return x2, chi2_sf_1df(x2)


print("\n=== PER-MODEL RECOUNT (analysis_include) ===")
hdr = (f"{'model':20s} {'n':>4s} {'gk':>4s} {'ok':>4s} {'GIFT%':>7s} {'OR%':>7s} "
       f"{'d_pp':>7s} {'b':>3s} {'c':>3s} {'x2_unc':>7s} {'x2_cc':>6s} {'p_exact':>8s}")
print(hdr)
tot = {"b": 0, "c": 0}
for m in MODELS + ["POOLED"]:
    sub = rows if m == "POOLED" else [r for r in rows if r["model"] == m]
    n = len(sub)
    gk = sum(r["gift_correct"] for r in sub)
    ok = sum(r["or_correct"] for r in sub)
    b = sum(1 for r in sub if r["gift_correct"] and not r["or_correct"])
    c = sum(1 for r in sub if r["or_correct"] and not r["gift_correct"])
    if m != "POOLED":
        tot["b"] += b
        tot["c"] += c
    xu, pu = mcnemar_chi2(b, c, False)
    xc, pc = mcnemar_chi2(b, c, True)
    print(f"{SHORT.get(m, m):20s} {n:4d} {gk:4d} {ok:4d} {100*gk/n:6.2f}% {100*ok/n:6.2f}% "
          f"{100*(gk-ok)/n:+7.3f} {b:3d} {c:3d} {xu:7.3f} {xc:6.3f} {sign_exact(b, c):8.4f}")
    if m == "POOLED":
        print(f"    pooled chi2 uncorrected p = {pu:.6f}   cc p = {pc:.6f}")
print("sum of per-model b,c:", tot)

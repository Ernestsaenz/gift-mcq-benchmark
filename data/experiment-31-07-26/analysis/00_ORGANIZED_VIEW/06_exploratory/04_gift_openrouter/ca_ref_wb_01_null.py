"""REFUTATION of the who-benefits claim:

  "The flips are strongly directional, not noise. A symmetric-noise null
   (GIFT = the same model re-drawn with an outcome-independent flip rate)
   predicts breakage counts 11x recovery counts ... observed ratio 0.52 --
   21x more corrective than the null."

Independent recomputation + interrogation of the null itself.
Stdlib only. Every p-value names its method.
"""
import json, math, random
from collections import defaultdict

BASE = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/"
MODELS = ["google/gemma-4-26b-a4b-it", "z-ai/glm-5.2",
          "qwen/qwen3.6-35b-a3b", "google/gemini-3.6-flash"]
SHORT = {"google/gemma-4-26b-a4b-it": "gemma-4-26b", "z-ai/glm-5.2": "glm-5.2",
         "qwen/qwen3.6-35b-a3b": "qwen3.6-35b", "google/gemini-3.6-flash": "gemini-3.6"}

rows = [r for r in json.load(open(BASE + "cross_arm_A.json")) if r["analysis_include"]]
print("cells=%d items=%d clusters=%d models=%d" % (
    len(rows), len({r["question_id"] for r in rows}),
    len({r["cluster"] for r in rows}), len({r["model"] for r in rows})))


def table(cells):
    """a=both ok, b=GIFT ok & OR wrong (RECOVERY), c=GIFT wrong & OR ok
    (BREAKAGE), d=both wrong."""
    a = b = c = d = 0
    for r in cells:
        g, o = r["gift_correct"], r["or_correct"]
        if g and o:
            a += 1
        elif g and not o:
            b += 1
        elif (not g) and o:
            c += 1
        else:
            d += 1
    return a, b, c, d


def binom_two_sided(k, n, p=0.5):
    """Exact two-sided binomial test by the 'sum of outcomes no more likely
    than observed' rule."""
    if n == 0:
        return 1.0
    def lp(i):
        return (math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                + i * math.log(p) + (n - i) * math.log(1 - p))
    obs = lp(k)
    tot = 0.0
    for i in range(n + 1):
        if lp(i) <= obs + 1e-12:
            tot += math.exp(lp(i))
    return min(1.0, tot)


out = {}

# ------------------------------------------------------------------ 1. confirm
print("\n[1] CONFIRM the observed 2x2 tables")
print("%-13s %5s %6s %6s %7s | %5s %4s %4s %4s" %
      ("model", "n", "GIFT", "OR", "delta", "a", "b(rec)", "c(brk)", "d"))
tab = {}
for m in MODELS + ["POOLED"]:
    cells = rows if m == "POOLED" else [r for r in rows if r["model"] == m]
    a, b, c, d = table(cells)
    tab[m] = (a, b, c, d)
    n = a + b + c + d
    print("%-13s %5d %5.1f%% %5.1f%% %+6.1fpp | %5d %6d %6d %4d" %
          (SHORT.get(m, m), n, 100 * (a + b) / n, 100 * (a + c) / n,
           100 * (b - c) / n, a, b, c, d))
out["tables"] = {m: dict(zip("abcd", tab[m])) for m in tab}

# ---------------------------------------------- 2. reproduce the claim exactly
print("\n[2] REPRODUCE the claim's arithmetic")
print("%-13s %8s %8s %10s %10s %8s" %
      ("model", "obs c/b", "exp c/b", "ratio", "1/ratio", "claim"))
for m in MODELS + ["POOLED"]:
    a, b, c, d = tab[m]
    exp = (a + c) / (b + d) if (b + d) else float("nan")
    obs = (c / b) if b else float("inf")
    ratio = obs / exp if b else float("inf")
    print("%-13s %8s %8.2f %10s %10s" %
          (SHORT.get(m, m), "%.3f" % obs if b else "inf", exp,
           "%.4f" % ratio if b else "inf",
           "%.1fx" % (1 / ratio) if b and ratio > 0 else "n/a"))
    out.setdefault("claim_arith", {})[m] = dict(obs_c_over_b=obs if b else None,
                                                exp_c_over_b=exp,
                                                ratio=ratio if b else None)

# ------------------------------- 3. what the null actually implies about accuracy
print("\n[3] WHAT THE NULL ACTUALLY ASSERTS")
a, b, c, d = tab["POOLED"]
n = a + b + c + d
p_or = (a + c) / n
print("  Under 'flip each cell with prob f, independent of correctness':")
print("    E[GIFT acc] = p_OR - f*(2*p_OR - 1) = %.4f - f*%.4f" % (p_or, 2 * p_or - 1))
for f in (0.02, 0.05, 0.0563, 0.10, 0.20):
    print("      f=%.4f -> E[GIFT acc]=%.4f  (OR=%.4f, delta=%+.2fpp)" %
          (f, p_or - f * (2 * p_or - 1), p_or, -100 * f * (2 * p_or - 1)))
print("  => the 'symmetric-noise null' is NOT a no-difference null. For every")
print("     f>0 it asserts GIFT is STRICTLY WORSE than OR. It is a degradation")
print("     null. A system exactly as good as OR already refutes it.")

# What "ratio to null" does a perfectly neutral system score?
neutral = 1.0 / ((a + c) / (b + d))
print("\n  A hypothetical arm with IDENTICAL accuracy (b=c, zero net effect)")
print("  scores obs c/b = 1.000, ratio-to-null = %.4f, i.e. '%.1fx more" %
      (neutral, 1 / neutral))
print("  corrective than the null' -- with no corrective behaviour at all.")
print("  Observed 21x / neutral %.1fx = %.2fx: the entire headline is base rate" %
      (1 / neutral, (1 / (tab['POOLED'][2] / tab['POOLED'][1])) / (1 / neutral)))
print("  except for a factor of b/c = %d/%d = %.2f." % (b, c, b / c))
out["null_is_degradation"] = dict(p_or=p_or, neutral_ratio_to_null=neutral,
                                  neutral_headline_x=1 / neutral,
                                  observed_headline_x=1 / (c / b) / ((b + d) / (a + c)),
                                  residual_b_over_c=b / c)

# ----------------------------- 4. the correct symmetric-noise null: independent redraw
print("\n[4] THE CORRECT NOISE NULL (independent re-draw from the same per-item")
print("    answer distribution). If OR and GIFT each draw correct w.p. p_i,")
print("    E[b] = sum p_i(1-p_i) = E[c] EXACTLY, so E[c/b] = 1, not 11.08.")
print("    Any exchangeable noise model gives E[b]=E[c]. The claim's 11.08 is")
print("    produced only by a flip model that is deterministic in direction,")
print("    which is a claim of degradation, not of noise.")
print("    Observed c/b = %.3f  -> deviation from the correct null = %.2fx, not 21x."
      % (c / b, b / c))

# ---------------------------------------------- 5. McNemar under the correct null
print("\n[5] McNEMAR (exact binomial on discordants, the correct directional test)")
for m in MODELS + ["POOLED"]:
    a_, b_, c_, d_ = tab[m]
    nd = b_ + c_
    pe = binom_two_sided(c_, nd)
    chi = ((abs(b_ - c_) - 1) ** 2) / nd if nd else float("nan")
    chi_nc = ((b_ - c_) ** 2) / nd if nd else float("nan")
    print("  %-13s b=%2d c=%2d  exact p=%.4f  chi2_cc=%.2f  chi2=%.2f" %
          (SHORT.get(m, m), b_, c_, pe, chi, chi_nc))
    out.setdefault("mcnemar", {})[m] = dict(b=b_, c=c_, exact_p=pe,
                                            chi2_cc=chi, chi2=chi_nc)

# ------------------------------------------- 6. cluster-robust permutation on b vs c
print("\n[6] CLUSTER-ROBUST arm-label permutation on (b-c)/n, clusters as units")
by_cluster = defaultdict(list)
for r in rows:
    by_cluster[r["cluster"]].append(r)
clusters = sorted(by_cluster)


def delta_of(cells):
    a_, b_, c_, d_ = table(cells)
    return (b_ - c_) / (a_ + b_ + c_ + d_)


def perm_p(cells_by_cluster, keys, B=20000, seed=11):
    rng = random.Random(seed)
    allc = [r for k in keys for r in cells_by_cluster[k]]
    obs = delta_of(allc)
    hits = 0
    for _ in range(B):
        swapped = []
        for k in keys:
            fl = rng.random() < 0.5
            for r in cells_by_cluster[k]:
                if fl:
                    swapped.append({"gift_correct": r["or_correct"],
                                    "or_correct": r["gift_correct"]})
                else:
                    swapped.append(r)
        if abs(delta_of(swapped)) >= abs(obs) - 1e-12:
            hits += 1
    return obs, (hits + 1) / (B + 1)


for m in MODELS + ["POOLED"]:
    if m == "POOLED":
        bc = by_cluster
        keys = clusters
    else:
        bc = defaultdict(list)
        for r in rows:
            if r["model"] == m:
                bc[r["cluster"]].append(r)
        keys = sorted(bc)
    obs, p = perm_p(bc, keys, B=20000, seed=11)
    print("  %-13s delta=%+.4f (%+.2fpp)  cluster-perm p=%.4f  (%d clusters)" %
          (SHORT.get(m, m), obs, 100 * obs, p, len(keys)))
    out.setdefault("cluster_perm", {})[m] = dict(delta=obs, p=p, clusters=len(keys))

# ---------------------------------------------- 7. per-model heterogeneity honesty
print("\n[7] PER-MODEL DIRECTION (what pooling hides)")
for m in MODELS:
    a_, b_, c_, d_ = tab[m]
    d_ir = "CORRECTIVE" if b_ > c_ else ("DESTRUCTIVE" if c_ > b_ else "NEUTRAL")
    print("  %-13s b=%2d c=%2d  b/c=%s  -> %s" %
          (SHORT.get(m, m), b_, c_,
           "%.2f" % (b_ / c_) if c_ else "inf", d_ir))
print("  2 of 4 models are NOT corrective. gemini is 0 recoveries / 3 breakages,")
print("  i.e. observed c/b = infinity, which EXCEEDS the null's 11.08 -- the")
print("  claim drops it as 'undefined' rather than as the one arm where the")
print("  null direction is not merely met but exceeded.")

json.dump(out, open(BASE + "ca_ref_wb_01_null.json", "w"), indent=1)
print("\nwritten ca_ref_wb_01_null.json")

"""ca_wb_02: does the GIFT advantage concentrate on items the base model
struggles with?

Two stratifications of item difficulty, both built from the OpenRouter arm:

  ALL4  k = number of the 4 models correct on OpenRouter (0..4).
        Contaminated for a per-model delta, because k contains the model's own
        OpenRouter outcome -> conditioning on it selects on the dependent
        variable.

  LOO   k = number of the OTHER 3 models correct on OpenRouter (0..3).
        Exogenous to model m's own OpenRouter outcome, so the per-model
        GIFT-minus-OR delta inside a stratum is not selected on.

Then the decomposition that actually explains the per-model deltas:

  delta = headroom * recovery - (1 - headroom) * breakage
  headroom = P(OpenRouter wrong)
"""
import json, random, math
from ca_wb_lib import (load, table, MODELS, SHORT, wilson, cluster_boot, ci,
                       boot_p, fisher_exact_2x2, chi2_sf_1df, pct)

rows = load()

# ---------------------------------------------------------- difficulty labels
by_item = {}
for r in rows:
    by_item.setdefault(r["question_id"], {})[r["model"]] = r
k_all = {q: sum(v["or_correct"] for v in d.values()) for q, d in by_item.items()}
assert all(len(d) == 4 for d in by_item.values())

for r in rows:
    r["k_all"] = k_all[r["question_id"]]
    r["k_loo"] = k_all[r["question_id"]] - r["or_correct"]

print("ITEM DIFFICULTY (OpenRouter, 4 models, 311 analysed items)")
dist = {k: sum(1 for q in k_all if k_all[q] == k) for k in range(5)}
for k in range(5):
    print("  k=%d (%d/4 models right on OR): %3d items (%5.1f%%)"
          % (k, k, dist[k], 100 * dist[k] / len(k_all)))
print("  mean k = %.3f  => item-level OR accuracy %.1f%%"
      % (sum(k_all.values()) / len(k_all), 100 * sum(k_all.values()) / (4 * len(k_all))))

# ------------------------------------------------------- per-stratum, pooled
def block(cells):
    a, b, c, d = table(cells)
    n = a + b + c + d
    if n == 0:
        return None
    return dict(n=n, a=a, b=b, c=c, d=d,
                gift=(a + b) / n, orr=(a + c) / n, delta=(b - c) / n,
                rec=(b / (b + d) if b + d else float("nan")), rec_n=b + d,
                brk=(c / (a + c) if a + c else float("nan")), brk_n=a + c)


out = {"k_all_dist": dist}

for lab, key, rng in (("ALL4 (k = #models right on OR, own outcome INCLUDED)", "k_all", range(5)),
                      ("LOO  (k = #OTHER 3 models right on OR)", "k_loo", range(4))):
    print()
    print("=" * 104)
    print(lab)
    print("%-14s %3s %5s %6s %6s %8s %7s %18s %18s" % (
        "model", "k", "n", "GIFT", "OR", "delta", "b/c", "recovery b/(b+d)",
        "breakage c/(a+c)"))
    print("-" * 104)
    res = {}
    for m in MODELS + ["POOLED"]:
        cells = rows if m == "POOLED" else [r for r in rows if r["model"] == m]
        for k in rng:
            s = [r for r in cells if r[key] == k]
            bl = block(s)
            if not bl:
                print("%-14s %3d %5d  --" % (SHORT.get(m, m), k, 0))
                continue
            print("%-14s %3d %5d %6s %6s %+8s %3d/%-3d %6s (%3d)        %6s (%3d)" % (
                SHORT.get(m, m), k, bl["n"], pct(bl["gift"]), pct(bl["orr"]),
                pct(bl["delta"]), bl["b"], bl["c"],
                pct(bl["rec"]), bl["rec_n"], pct(bl["brk"]), bl["brk_n"]))
            res["%s|%d" % (m, k)] = bl
        print("-" * 104)
    out[key] = res

# ---------------------------------------------------- recovery-rate homogeneity
print()
print("=" * 104)
print("IS THE PER-ERROR RECOVERY RATE ITSELF HIGHER FOR WEAKER MODELS?")
print("(this is the claim 'retrieval supplies missing knowledge, more so when the")
print(" model lacks it'; the alternative is that weak models simply have more errors)")
print("%-14s %8s %10s %22s %22s" % ("model", "OR acc", "headroom",
                                    "recovery (b/(b+d))", "breakage (c/(a+c))"))
print("-" * 104)
tab = []
for m in MODELS:
    cells = [r for r in rows if r["model"] == m]
    a, b, c, d = table(cells)
    n = a + b + c + d
    rec, rl, rh = wilson(b, b + d)
    brk, bl2, bh = wilson(c, a + c)
    print("%-14s %8s %10s %6s [%5s,%5s] (n=%2d) %6s [%4s,%4s] (n=%3d)" % (
        SHORT[m], pct((a + c) / n), pct((b + d) / n),
        pct(rec), pct(rl), pct(rh), b + d, pct(brk), pct(bl2), pct(bh), a + c))
    tab.append((m, (a + c) / n, b, d, c, a))
out["per_model"] = {m: dict(or_acc=o, b=b, d=d, c=c, a=a) for m, o, b, d, c, a in tab}

# chi-square homogeneity of recovery across the 4 models (small cells -> also
# report the 3 non-ceiling models and an exact permutation p)
def chi2_homog(counts):
    """counts = [(succ, tot), ...]; Pearson chi-square for equal proportions."""
    S = sum(s for s, t in counts)
    T = sum(t for s, t in counts)
    if T == 0 or S == 0 or S == T:
        return 0.0, len(counts) - 1
    p = S / T
    x2 = 0.0
    for s, t in counts:
        if t == 0:
            continue
        e1, e0 = t * p, t * (1 - p)
        x2 += (s - e1) ** 2 / e1 + ((t - s) - e0) ** 2 / e0
    return x2, len(counts) - 1


def chi2_sf(x, df):
    """Upper tail of chi-square. df<=4 handled by series (stdlib only)."""
    if x <= 0:
        return 1.0
    if df == 1:
        return chi2_sf_1df(x)
    if df == 2:
        return math.exp(-x / 2)
    if df == 3:
        return chi2_sf_1df(x) + math.sqrt(2 * x / math.pi) * math.exp(-x / 2)
    if df == 4:
        return math.exp(-x / 2) * (1 + x / 2)
    raise ValueError


rec_counts = [(out["per_model"][m]["b"],
               out["per_model"][m]["b"] + out["per_model"][m]["d"]) for m in MODELS]
brk_counts = [(out["per_model"][m]["c"],
               out["per_model"][m]["a"] + out["per_model"][m]["c"]) for m in MODELS]
x2r, dfr = chi2_homog(rec_counts)
x2b, dfb = chi2_homog(brk_counts)
print()
print("Pearson chi-square homogeneity of RECOVERY across 4 models: chi2=%.3f df=%d p=%.4f"
      % (x2r, dfr, chi2_sf(x2r, dfr)))
print("  (counts %s ; gemini contributes 0/5 -- a 5-cell stratum)" % (rec_counts,))
r3 = [(out["per_model"][m]["b"], out["per_model"][m]["b"] + out["per_model"][m]["d"])
      for m in MODELS if m != "google/gemini-3.6-flash"]
x2r3, dfr3 = chi2_homog(r3)
print("Excluding the ceiling model gemini: chi2=%.3f df=%d p=%.4f  counts %s"
      % (x2r3, dfr3, chi2_sf(x2r3, dfr3), r3))
print("Pearson chi-square homogeneity of BREAKAGE across 4 models: chi2=%.3f df=%d p=%.4f"
      % (x2b, dfb, chi2_sf(x2b, dfb)))
out["homog"] = dict(rec_chi2=x2r, rec_p=chi2_sf(x2r, dfr),
                    rec3_chi2=x2r3, rec3_p=chi2_sf(x2r3, dfr3),
                    brk_chi2=x2b, brk_p=chi2_sf(x2b, dfb))

# ------------------------------------------------------------- decomposition
print()
print("DECOMPOSITION  delta = headroom*recovery - (1-headroom)*breakage")
print("%-14s %9s %9s %9s %12s %12s %10s" % (
    "model", "headroom", "recovery", "breakage", "gain=h*r", "loss=(1-h)*b", "delta"))
print("-" * 104)
for m in MODELS:
    p = out["per_model"][m]
    a, b, c, d = p["a"], p["b"], p["c"], p["d"]
    n = a + b + c + d
    h = (b + d) / n
    rec = b / (b + d) if b + d else 0.0
    brk = c / (a + c) if a + c else 0.0
    print("%-14s %9s %9s %9s %12s %12s %+10s" % (
        SHORT[m], pct(h), pct(rec), pct(brk), pct(h * rec),
        pct((1 - h) * brk), pct(h * rec - (1 - h) * brk)))

# counterfactual: hold recovery and breakage at the pooled value, vary headroom
a, b, c, d = table(rows)
REC = b / (b + d)
BRK = c / (a + c)
print()
print("COUNTERFACTUAL: pooled recovery=%s and breakage=%s applied to each model's"
      % (pct(REC), pct(BRK)))
print("own headroom -- i.e. what the delta would be if retrieval acted identically")
print("on every model and only the error budget differed:")
print("%-14s %9s %12s %12s %10s" % ("model", "headroom", "pred delta", "obs delta", "resid"))
print("-" * 104)
for m in MODELS:
    p = out["per_model"][m]
    a2, b2, c2, d2 = p["a"], p["b"], p["c"], p["d"]
    n = a2 + b2 + c2 + d2
    h = (b2 + d2) / n
    pred = h * REC - (1 - h) * BRK
    obs = (b2 - c2) / n
    print("%-14s %9s %+12s %+12s %+10s" % (SHORT[m], pct(h), pct(pred), pct(obs),
                                           pct(obs - pred)))
    out["per_model"][m]["pred_delta_common"] = pred
    out["per_model"][m]["obs_delta"] = obs

json.dump(out, open("ca_wb_02_strata.json", "w"), indent=1)
print("\nwritten ca_wb_02_strata.json")

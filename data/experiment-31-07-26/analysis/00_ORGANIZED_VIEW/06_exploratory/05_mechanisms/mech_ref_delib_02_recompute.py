"""REFUTATION step 2: independent recomputation of the deliberation claim.

Statistic under test: median of the paired ratio (B_reason+1)/(A_reason+1),
cluster bootstrap over clusters (B=4000, percentile CI), exact two-sided sign
test on B_reason - A_reason.

Also reports estimators the claim did NOT report, because a median-of-ratios is
only one of several defensible summaries and they disagree in magnitude:
  * Hodges-Lehmann shift  (median of pairwise Walsh averages of the difference)
  * median paired difference
  * exp(median of log-ratio)  == median ratio (identical by monotonicity; kept
    as an arithmetic check that the +1 guard is not doing the work)
  * median ratio WITHOUT the +1 guard, restricted to cells with A_reason>0
"""
import json
import math
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CELLS = HERE / "mech_ref_delib_cells.json"

MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
SHORT = {"google/gemini-3.6-flash": "gemini-3.6-flash",
         "google/gemma-4-26b-a4b-it": "gemma-4-26b",
         "qwen/qwen3.6-35b-a3b": "qwen3.6-35b",
         "z-ai/glm-5.2": "glm-5.2"}


def median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return float("nan")
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def quantile(xs, q):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return float("nan")
    if n == 1:
        return s[0]
    h = (n - 1) * q
    lo = int(math.floor(h))
    hi = min(lo + 1, n - 1)
    return s[lo] + (h - lo) * (s[hi] - s[lo])


def cluster_bootstrap(rows, stat, B=4000, seed=77):
    rng = random.Random(seed)
    by = defaultdict(list)
    for r in rows:
        by[r["cluster"]].append(r)
    keys = list(by)
    K = len(keys)
    reps = []
    for _ in range(B):
        s = []
        for _ in range(K):
            s.extend(by[keys[rng.randrange(K)]])
        v = stat(s)
        if v == v:
            reps.append(v)
    reps.sort()
    return stat(rows), quantile(reps, .025), quantile(reps, .975), reps


def boot_p(reps, null):
    B = len(reps)
    lo = (sum(1 for v in reps if v <= null) + 1) / (B + 1)
    hi = (sum(1 for v in reps if v >= null) + 1) / (B + 1)
    return min(1.0, 2 * min(lo, hi))


def sign_test(vals):
    """Exact two-sided sign test, binomial(n, 0.5), computed in log space."""
    pos = sum(1 for v in vals if v > 0)
    neg = sum(1 for v in vals if v < 0)
    n = pos + neg
    if n == 0:
        return pos, neg, 1.0
    lo = min(pos, neg)
    tail = sum(math.exp(math.lgamma(n + 1) - math.lgamma(k + 1)
                        - math.lgamma(n - k + 1) - n * math.log(2.0))
               for k in range(lo + 1))
    return pos, neg, min(1.0, 2 * tail)


def hodges_lehmann(vals):
    """HL one-sample estimator: median of all Walsh averages (x_i+x_j)/2, i<=j."""
    s = sorted(vals)
    n = len(s)
    w = [(s[i] + s[j]) / 2.0 for i in range(n) for j in range(i, n)]
    return median(w)


def med_ratio(rs, guard=1):
    return median([(r["B_reason_tok"] + guard) / (r["A_reason_tok"] + guard) for r in rs])


def main():
    rows = [r for r in json.load(open(CELLS)) if r["analysis_include"]]
    print("=" * 100)
    print("REFUTATION 2 -- independent recomputation of the reasoning-token claim")
    print(f"cells={len(rows)}  items={len({r['question_id'] for r in rows})} "
          f" clusters={len({r['cluster'] for r in rows})}")
    print("NOTE: the CLAIM cites 324/325 signed pairs per model, i.e. 325 items / 208 clusters.")
    print("      paired_clean.json as it stands today has 318 items / 201 clusters per model.")
    print("=" * 100)
    print(f"{'model':<17} {'n':>4} {'medA':>6} {'medB':>6} {'medRatio':>9} "
          f"{'95% CI cluster-boot':>22} {'p_boot':>8} {'B>A':>5} {'B<A':>5} "
          f"{'tie':>4} {'p_sign(exact)':>14}")
    out = {}
    for m in MODELS:
        rs = [r for r in rows if r["model"] == m]
        ra = [r["A_reason_tok"] for r in rs]
        rb = [r["B_reason_tok"] for r in rs]
        if max(ra + rb) == 0:
            print(f"{SHORT[m]:<17} {len(rs):>4}      0      0   -- zero reasoning tokens in "
                  f"every cell; no deliberation series exists")
            continue
        pt, lo, hi, reps = cluster_bootstrap(rs, med_ratio, B=4000, seed=77)
        d = [b - a for a, b in zip(ra, rb)]
        pos, neg, ps = sign_test(d)
        print(f"{SHORT[m]:<17} {len(rs):>4} {median(ra):>6.0f} {median(rb):>6.0f} "
              f"{pt:>9.3f} [{lo:>7.3f},{hi:>7.3f}]{'':>4} {boot_p(reps, 1.0):>8.4g} "
              f"{pos:>5} {neg:>5} {len(rs)-pos-neg:>4} {ps:>14.3g}")
        out[m] = dict(n=len(rs), med_ratio=pt, ci=[lo, hi], pos=pos, neg=neg, p_sign=ps)

    print()
    print("-" * 100)
    print("Estimator sensitivity (the claim reports ONLY 'median of the paired ratio')")
    print("-" * 100)
    print(f"{'model':<17} {'medRatio(+1)':>13} {'medRatio(A>0 only)':>19} "
          f"{'med diff':>9} {'HL shift':>9} {'mean diff':>10} {'ratio of medians':>17}")
    for m in MODELS:
        rs = [r for r in rows if r["model"] == m]
        ra = [r["A_reason_tok"] for r in rs]
        rb = [r["B_reason_tok"] for r in rs]
        if max(ra + rb) == 0:
            continue
        nz = [r for r in rs if r["A_reason_tok"] > 0]
        r_nz = median([r["B_reason_tok"] / r["A_reason_tok"] for r in nz]) if nz else float("nan")
        d = [b - a for a, b in zip(ra, rb)]
        print(f"{SHORT[m]:<17} {med_ratio(rs):>13.3f} {r_nz:>19.3f} "
              f"{median(d):>9.0f} {hodges_lehmann(d):>9.1f} {sum(d)/len(d):>10.1f} "
              f"{median(rb)/median(ra):>17.3f}")

    print()
    print("-" * 100)
    print("Is the '103% / 103% / 137% of the raw-token change' decomposition arithmetic valid?")
    print("  medians are NOT additive: median(dRaw) != median(dThink) + median(dRest).")
    print("-" * 100)
    print(f"{'model':<17} {'med dRaw':>9} {'med dThink':>11} {'med dRest':>10} "
          f"{'dThink+dRest':>13} {'gap vs dRaw':>12} {'claimed share':>14} "
          f"{'MEAN-based share':>17}")
    for m in MODELS:
        rs = [r for r in rows if r["model"] == m]
        if max(r["A_reason_tok"] for r in rs) == 0 and max(r["B_reason_tok"] for r in rs) == 0:
            continue
        d_raw = median([r["B_ctok"] - r["A_ctok"] for r in rs])
        d_th = median([r["B_reason_tok"] - r["A_reason_tok"] for r in rs])
        d_re = median([(r["B_ctok"] - r["B_reason_tok"]) - (r["A_ctok"] - r["A_reason_tok"])
                       for r in rs])
        mraw = sum(r["B_ctok"] - r["A_ctok"] for r in rs) / len(rs)
        mth = sum(r["B_reason_tok"] - r["A_reason_tok"] for r in rs) / len(rs)
        print(f"{SHORT[m]:<17} {d_raw:>9.0f} {d_th:>11.0f} {d_re:>10.0f} "
              f"{d_th + d_re:>13.0f} {d_th + d_re - d_raw:>12.0f} "
              f"{(d_th / d_raw * 100 if d_raw else float('nan')):>13.0f}% "
              f"{(mth / mraw * 100 if mraw else float('nan')):>16.0f}%")

    print()
    print("-" * 100)
    print("Internal consistency of the provider-reported reasoning_tokens field")
    print("-" * 100)
    print(f"{'model':<17} {'cond':<5} {'%cells reason>completion':>25} "
          f"{'%cells reason==0':>17} {'med reasoning_chars/tok':>24}")
    for m in MODELS:
        for c in "AB":
            rs = [r for r in rows if r["model"] == m]
            bad = 100 * sum(1 for r in rs if r[f"{c}_reason_tok"] > r[f"{c}_ctok"]) / len(rs)
            z = 100 * sum(1 for r in rs if r[f"{c}_reason_tok"] == 0) / len(rs)
            cpt = [r[f"{c}_reasoning_chars"] / r[f"{c}_reason_tok"]
                   for r in rs if r[f"{c}_reason_tok"] > 0]
            print(f"{SHORT[m]:<17} {c:<5} {bad:>25.1f} {z:>17.1f} "
                  f"{(median(cpt) if cpt else float('nan')):>24.2f}")

    (HERE / "mech_ref_delib_02_out.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

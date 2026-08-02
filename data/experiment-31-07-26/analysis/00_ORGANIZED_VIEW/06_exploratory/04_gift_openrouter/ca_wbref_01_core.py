"""ca_wbref_01: independent recomputation + adversarial audit of the
who-benefits claim

    "GIFT rescues 44.7% of the base model's OpenRouter errors and breaks 2.1%
     of its correct answers. The gap is 42.6pp and is the single largest effect
     in this analysis."

All statistics implemented here from the standard library. Method named at
every call site. Nothing imported from ca_wb_lib (independence).
"""
import json, math, os, random
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["google/gemma-4-26b-a4b-it", "z-ai/glm-5.2",
          "qwen/qwen3.6-35b-a3b", "google/gemini-3.6-flash"]
SHORT = {"google/gemma-4-26b-a4b-it": "gemma", "z-ai/glm-5.2": "glm",
         "qwen/qwen3.6-35b-a3b": "qwen", "google/gemini-3.6-flash": "gemini"}
B = 20000

rows = [r for r in json.load(open(os.path.join(BASE, "cross_arm_A.json")))
        if r.get("analysis_include")]


# ------------------------------------------------------------------ stats kit
def wilson(k, n, z=1.959963985):
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    den = 1 + z * z / n
    ctr = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, ctr - h), min(1.0, ctr + h)


def tab(cells):
    """2x2 (a,b,c,d) = (G ok & OR ok, G ok & OR bad, G bad & OR ok, both bad)."""
    a = b = c = d = 0
    for r in cells:
        g, o = r["gift_correct"], r["or_correct"]
        if g and o:
            a += 1
        elif g:
            b += 1
        elif o:
            c += 1
        else:
            d += 1
    return a, b, c, d


def recovery(t):
    a, b, c, d = t
    return b / (b + d) if b + d else None


def breakage(t):
    a, b, c, d = t
    return c / (a + c) if a + c else None


def gap(t):
    r, k = recovery(t), breakage(t)
    return None if r is None or k is None else r - k


def cluster_boot(cells, fn, B=B, seed=20260731):
    """Nonparametric cluster bootstrap: resample the question clusters with
    replacement, K draws where K = number of observed clusters."""
    rng = random.Random(seed)
    g = defaultdict(list)
    for r in cells:
        g[r["cluster"]].append(r)
    keys = list(g)
    K = len(keys)
    out = []
    for _ in range(B):
        s = []
        for _ in range(K):
            s.extend(g[keys[rng.randrange(K)]])
        v = fn(tab(s))
        if v is not None:
            out.append(v)
    out.sort()
    return out


def pctl(v, q):
    if not v:
        return float("nan")
    i = q * (len(v) - 1)
    lo, hi = math.floor(i), math.ceil(i)
    return v[lo] if lo == hi else v[lo] + (v[hi] - v[lo]) * (i - lo)


def ci(v, alpha=0.05):
    return pctl(v, alpha / 2), pctl(v, 1 - alpha / 2)


def boot_p(reps, null):
    """Two-sided bootstrap p by inversion against an explicit null value."""
    if not reps:
        return float("nan")
    n = len(reps)
    lo = sum(1 for v in reps if v <= null) / n
    hi = sum(1 for v in reps if v >= null) / n
    return min(1.0, 2 * min(lo, hi))


def armflip_null(cells, fn, B=B, seed=515):
    """Cluster-level randomization under H0: the GIFT/OR arm label is
    exchangeable. Whole clusters are swapped together, preserving item
    difficulty and within-cluster dependence. Returns (observed, null reps)."""
    rng = random.Random(seed)
    g = defaultdict(list)
    for r in cells:
        g[r["cluster"]].append(r)
    keys = list(g)
    obs = fn(tab(cells))
    reps = []
    for _ in range(B):
        perm = []
        for k in keys:
            if rng.random() < 0.5:
                for r in g[k]:
                    perm.append({**r, "gift_correct": r["or_correct"],
                                 "or_correct": r["gift_correct"]})
            else:
                perm.extend(g[k])
        v = fn(tab(perm))
        if v is not None:
            reps.append(v)
    reps.sort()
    return obs, reps


def perm_p(obs, reps):
    """Two-sided randomization p: share of null reps at least as extreme as
    the observation, measured as |rep - null centre| >= |obs - null centre|,
    with the null centre taken as the null-distribution median."""
    ctr = pctl(reps, 0.5)
    ge = sum(1 for v in reps if abs(v - ctr) >= abs(obs - ctr) - 1e-12)
    return ctr, (ge + 1) / (len(reps) + 1)


def P(x, nd=1):
    return "nan" if x is None or x != x else ("%." + str(nd) + "f") % (100 * x)


out = {}
print("cells=%d items=%d clusters=%d models=%d" % (
    len(rows), len({r["question_id"] for r in rows}),
    len({r["cluster"] for r in rows}), len({r["model"] for r in rows})))

# ============================================================ 1. reproduction
print("\n" + "=" * 96)
print("1. REPRODUCTION of the claim's numbers")
print("=" * 96)
print("%-8s %5s %5s %5s %5s %5s | %7s %7s | %-22s %-22s %8s" % (
    "model", "n", "a", "b", "c", "d", "GIFT", "OR",
    "RECOVERY b/(b+d)", "BREAKAGE c/(a+c)", "gap pp"))
for m in MODELS + ["POOLED"]:
    cells = rows if m == "POOLED" else [r for r in rows if r["model"] == m]
    a, b, c, d = t = tab(cells)
    n = a + b + c + d
    rec, rlo, rhi = wilson(b, b + d)
    brk, blo, bhi = wilson(c, a + c)
    print("%-8s %5d %5d %5d %5d %5d | %6s%% %6s%% | %5s%% [%4s,%4s] %2d/%-4d %4s%% [%3s,%3s] %2d/%-5d %+7s" % (
        SHORT.get(m, m), n, a, b, c, d, P((a + b) / n), P((a + c) / n),
        P(rec), P(rlo), P(rhi), b, b + d,
        P(brk), P(blo), P(bhi), c, a + c, P(rec - brk)))
    out[SHORT.get(m, m)] = dict(n=n, a=a, b=b, c=c, d=d,
                                gift=(a + b) / n, orr=(a + c) / n,
                                recovery=rec, rec_wilson=[rlo, rhi],
                                breakage=brk, brk_wilson=[blo, bhi],
                                gap=rec - brk, rec_den=b + d, brk_den=a + c)

pooled = [r for r in rows]
A, Bc, C, D = tab(pooled)
N = A + Bc + C + D
gb = cluster_boot(pooled, gap)
rb = cluster_boot(pooled, recovery)
kb = cluster_boot(pooled, breakage)
print("\ncluster bootstrap (B=%d, percentile) POOLED:" % B)
print("  recovery %s%%  CI [%s, %s]" % (P(recovery((A, Bc, C, D))), *[P(x) for x in ci(rb)]))
print("  breakage %s%%  CI [%s, %s]" % (P(breakage((A, Bc, C, D))), *[P(x) for x in ci(kb)]))
print("  gap      %spp CI [%s, %s]   two-sided boot p vs null=0 : %.5f" % (
    P(gap((A, Bc, C, D))), *[P(x) for x in ci(gb)], boot_p(gb, 0.0)))
out["POOLED"]["gap_boot_ci"] = list(ci(gb))
out["POOLED"]["rec_boot_ci"] = list(ci(rb))
out["POOLED"]["brk_boot_ci"] = list(ci(kb))
out["POOLED"]["gap_boot_p_vs_0"] = boot_p(gb, 0.0)

# how many clusters actually carry the recovery denominator
orwrong = [r for r in rows if not r["or_correct"]]
print("\n  OR-wrong stratum: %d cells across %d items, %d clusters"
      % (len(orwrong), len({r['question_id'] for r in orwrong}),
         len({r['cluster'] for r in orwrong})))
out["POOLED"]["orwrong_clusters"] = len({r["cluster"] for r in orwrong})
out["POOLED"]["orwrong_items"] = len({r["question_id"] for r in orwrong})

# ================================================ 2. is the gap an effect at all
print("\n" + "=" * 96)
print("2. IS THE 42.6pp GAP AN EFFECT SIZE?  Three independent checks.")
print("=" * 96)

print("\n2a. ALGEBRA: freeze the OR marginal, impose exact McNemar symmetry b=c")
print("    (i.e. GIFT and OR provably equally accurate, zero directional effect)")
for m in MODELS + ["POOLED"]:
    cells = rows if m == "POOLED" else [r for r in rows if r["model"] == m]
    a, b, c, d = tab(cells)
    f = (b + c) / 2.0                       # symmetric discordance
    null_gap = f / (b + d) - f / (a + c)    # same strata sizes
    print("    %-8s observed gap %+6spp   |   gap under b=c=%.1f : %+6spp"
          "   -> %s%% of the observed gap survives with NO effect"
          % (SHORT.get(m, m), P(gap((a, b, c, d))), f, P(null_gap),
             P(null_gap / gap((a, b, c, d))) if gap((a, b, c, d)) else "n/a"))
    out[SHORT.get(m, m)]["gap_under_symmetry"] = null_gap

print("\n2b. ARM REVERSAL: same statistic, arms swapped. If it measured a GIFT")
print("    benefit it should reverse sign / collapse. It does not.")


def rec_rev(t):
    a, b, c, d = t
    return c / (c + d) if c + d else None


def brk_rev(t):
    a, b, c, d = t
    return b / (a + b) if a + b else None


for m in MODELS + ["POOLED"]:
    cells = rows if m == "POOLED" else [r for r in rows if r["model"] == m]
    a, b, c, d = tab(cells)
    rr, kk = rec_rev((a, b, c, d)), brk_rev((a, b, c, d))
    print("    %-8s  OR rescues %5s%% of GIFT's errors (%d/%d), breaks %4s%% of "
          "GIFT's correct (%d/%d), gap %+6spp"
          % (SHORT.get(m, m), P(rr), c, c + d, P(kk), b, a + b,
             P(rr - kk) if rr is not None and kk is not None else None))
    out[SHORT.get(m, m)]["reversed_gap"] = (rr - kk) if rr is not None and kk is not None else None

print("\n2c. RANDOMIZATION: cluster-level arm-flip null (H0: arm label")
print("    exchangeable within cluster; B=%d). The claim's p<0.0001 tests the" % B)
print("    gap against 0. Where does the no-effect null actually sit?")
obs_gap, null_reps = armflip_null(rows, gap)
ctr, p_perm = perm_p(obs_gap, null_reps)
print("    observed gap        = %+6spp" % P(obs_gap))
print("    null median         = %+6spp   null 95%% range [%s, %s]"
      % (P(ctr), *[P(x) for x in ci(null_reps)]))
print("    share of no-effect null reps with gap > 0 : %.4f"
      % (sum(1 for v in null_reps if v > 0) / len(null_reps)))
print("    two-sided randomization p (vs the TRUE null, not vs 0) : %.4f" % p_perm)
print("    two-sided bootstrap p vs null=0 (what the claim reports): %.5f"
      % boot_p(gb, 0.0))
out["POOLED"]["armflip_null_median"] = ctr
out["POOLED"]["armflip_null_ci"] = list(ci(null_reps))
out["POOLED"]["armflip_p"] = p_perm
out["POOLED"]["armflip_frac_null_gap_pos"] = sum(1 for v in null_reps if v > 0) / len(null_reps)

print("\n2d. NET EFFECT the gap is standing in for:  (b-c)/N")
print("    = (%d-%d)/%d = %+.2fpp  == the pooled GIFT-OR accuracy delta (%+.2fpp)"
      % (Bc, C, N, 100 * (Bc - C) / N, 100 * ((A + Bc) / N - (A + C) / N)))

# ================================================= 3. placebo: no retrieval at all
print("\n" + "=" * 96)
print("3. PLACEBO: the same statistic applied to two arms that differ by NO")
print("   retrieval -- two OpenRouter models on the same items.")
print("=" * 96)
bym = defaultdict(dict)
for r in rows:
    bym[r["question_id"]][r["model"]] = r
qclu = {r["question_id"]: r["cluster"] for r in rows}
print("   %-8s vs %-8s | acc1   acc2   delta | 'rescue'  'break'   gap" % ("arm1", "arm2"))
plac = []
for i, m1 in enumerate(MODELS):
    for m2 in MODELS:
        if m1 == m2:
            continue
        cells = []
        for q, dd in bym.items():
            if m1 in dd and m2 in dd:
                cells.append({"gift_correct": dd[m1]["or_correct"],
                              "or_correct": dd[m2]["or_correct"],
                              "cluster": qclu[q]})
        a, b, c, d = tab(cells)
        n = a + b + c + d
        g_ = gap((a, b, c, d))
        print("   %-8s vs %-8s | %5s%% %5s%% %+5spp | %5s%%  %5s%%  %+6spp"
              % (SHORT[m1], SHORT[m2], P((a + b) / n), P((a + c) / n),
                 P((b - c) / n), P(recovery((a, b, c, d))),
                 P(breakage((a, b, c, d))), P(g_)))
        plac.append(dict(arm1=SHORT[m1], arm2=SHORT[m2], n=n,
                         acc1=(a + b) / n, acc2=(a + c) / n,
                         delta=(b - c) / n, gap=g_,
                         recovery=recovery((a, b, c, d)),
                         breakage=breakage((a, b, c, d))))
out["placebo_or_vs_or"] = plac
worse = [p for p in plac if p["delta"] < 0]
print("\n   pairs where arm1 is STRICTLY WORSE than arm2 yet still shows a large")
print("   positive gap: %d of %d. Max gap among them: %spp (%s vs %s, delta %spp)"
      % (len(worse), len(plac), P(max(p["gap"] for p in worse)),
         max(worse, key=lambda p: p["gap"])["arm1"],
         max(worse, key=lambda p: p["gap"])["arm2"],
         P(max(worse, key=lambda p: p["gap"])["delta"])))

json.dump(out, open(os.path.join(BASE, "ca_wbref_01_core.json"), "w"), indent=1)
print("\nwritten ca_wbref_01_core.json")

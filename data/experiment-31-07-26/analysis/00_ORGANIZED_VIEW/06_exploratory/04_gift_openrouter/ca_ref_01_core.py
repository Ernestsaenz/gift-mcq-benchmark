#!/usr/bin/env python
"""Independent refutation recount of the cross-arm A claim. Stdlib only.

Every test implemented here from scratch; nothing imported from stats_lib.py or ca_wb_lib.py.
"""
import json, math, random, collections, itertools

AN = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/"
J = json.load(open(AN + "cross_arm_A.json"))
PULL = json.load(open(AN + "ca_ref_00_pull.json"))

# ---------- my own stats primitives ----------
def chi2_sf_df1(x):
    """P(chi2_1 > x) = erfc(sqrt(x/2))."""
    if x <= 0: return 1.0
    return math.erfc(math.sqrt(x / 2.0))

def lchoose(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)

def binom_pmf_half(n, k):
    return math.exp(lchoose(n, k) - n * math.log(2.0))

def binom_exact_two_sided_half(k, n):
    """Two-sided exact binomial p at p=0.5, method of small p-values."""
    if n == 0: return 1.0
    pk = binom_pmf_half(n, k)
    tot = 0.0
    for i in range(n + 1):
        pi = binom_pmf_half(n, i)
        if pi <= pk * (1 + 1e-12):
            tot += pi
    return min(1.0, tot)

def binom_two_sided_doubled(k, n):
    """The other common convention: 2 * min tail."""
    if n == 0: return 1.0
    lo = sum(binom_pmf_half(n, i) for i in range(0, min(k, n - k) + 1))
    return min(1.0, 2.0 * lo)

# ---------- load cells ----------
cells = [c for c in J if c["analysis_include"]]
print("JSON rows total       :", len(J))
print("analysis_include=true :", len(cells))
print("items                 :", len(set(c["question_id"] for c in cells)))
print("clusters              :", len(set(c["cluster"] for c in cells)))
print("models                :", len(set(c["model"] for c in cells)))
print("excluded rows         :", len(J) - len(cells),
      "items", len(set(c["question_id"] for c in J)) - len(set(c["question_id"] for c in cells)))

# sanity: is every cell's cluster consistent per question, and does every item have 4 models?
q2c = {}
q2m = collections.defaultdict(set)
bad = 0
for c in cells:
    q = c["question_id"]
    if q in q2c and q2c[q] != c["cluster"]: bad += 1
    q2c[q] = c["cluster"]
    q2m[q].add(c["model"])
print("cluster inconsistencies within item:", bad)
print("items with !=4 models:", sum(1 for q, m in q2m.items() if len(m) != 4))

# ---------- per-model + pooled ----------
def mcnemar_block(rows):
    n = len(rows)
    g = sum(r["gift_correct"] for r in rows)
    o = sum(r["or_correct"] for r in rows)
    b = sum(1 for r in rows if r["gift_correct"] == 1 and r["or_correct"] == 0)
    c = sum(1 for r in rows if r["gift_correct"] == 0 and r["or_correct"] == 1)
    return dict(n=n, gift=g, orr=o, gift_pct=100.0 * g / n, or_pct=100.0 * o / n,
                dpp=100.0 * (g - o) / n, b=b, c=c)

print("\n--- per model ---")
bymodel = collections.defaultdict(list)
for c in cells: bymodel[c["model"]].append(c)
for m in sorted(bymodel):
    s = mcnemar_block(bymodel[m])
    nn = s["b"] + s["c"]
    x_u = ((s["b"] - s["c"]) ** 2) / nn if nn else float("nan")
    x_c = ((abs(s["b"] - s["c"]) - 1) ** 2) / nn if nn else float("nan")
    print("%-26s n=%4d GIFT %6.2f%% (%d) OR %6.2f%% (%d) d=%+5.2fpp b=%2d c=%2d  chi2u=%.3f chi2c=%.3f exact=%.4f"
          % (m, s["n"], s["gift_pct"], s["gift"], s["or_pct"], s["orr"], s["dpp"], s["b"], s["c"],
             x_u, x_c, binom_exact_two_sided_half(s["b"], nn) if nn else float("nan")))

P = mcnemar_block(cells)
nn = P["b"] + P["c"]
chi2_u = ((P["b"] - P["c"]) ** 2) / nn
chi2_c = ((abs(P["b"] - P["c"]) - 1) ** 2) / nn
print("\n--- POOLED ---")
print("n=%d GIFT %.4f%% (%d) OR %.4f%% (%d) diff %+.4fpp  b=%d c=%d n_disc=%d"
      % (P["n"], P["gift_pct"], P["gift"], P["or_pct"], P["orr"], P["dpp"], P["b"], P["c"], nn))
print("McNemar uncorrected chi2 = %.6f  p = %.6f  (chi2_1 tail, erfc form)" % (chi2_u, chi2_sf_df1(chi2_u)))
print("McNemar cont-corrected  chi2 = %.6f  p = %.6f" % (chi2_c, chi2_sf_df1(chi2_c)))
print("exact conditional binomial (small-p method) p = %.6f" % binom_exact_two_sided_half(P["b"], nn))
print("exact conditional binomial (2x min tail)    p = %.6f" % binom_two_sided_doubled(P["b"], nn))

# ---------- cluster-level arm-flip randomization ----------
byclus = collections.defaultdict(int)
for c in cells:
    byclus[c["cluster"]] += (c["gift_correct"] - c["or_correct"])
d = list(byclus.values())
T = sum(d)
nz = [x for x in d if x != 0]
print("\n--- cluster arm-flip sign-flip randomization ---")
print("clusters=%d  nonzero-delta clusters=%d  T=b-c=%d" % (len(d), len(nz), T))

# exact enumeration if feasible
if len(nz) <= 24:
    ge = 0; tot = 0
    for signs in itertools.product((1, -1), repeat=len(nz)):
        tot += 1
        if abs(sum(s * v for s, v in zip(signs, nz))) >= abs(T) - 1e-9: ge += 1
    print("EXACT enumeration over %d sign patterns: p = %.6f" % (tot, ge / tot))
else:
    print("exact enumeration infeasible (%d nonzero clusters)" % len(nz))

for B, seed in ((20000, 12345), (200000, 987654321)):
    rng = random.Random(seed)
    ge = 0
    for _ in range(B):
        t = 0
        for v in nz:
            t += v if rng.random() < 0.5 else -v
        if abs(t) >= abs(T) - 1e-9: ge += 1
    print("MonteCarlo B=%-7d seed=%-10d p = %.6f  (+1/+1 corrected %.6f)"
          % (B, seed, ge / B, (ge + 1) / (B + 1)))

# item-level sign flip (finer unit, ignores near-duplicate clustering)
byitem = collections.defaultdict(int)
for c in cells: byitem[c["question_id"]] += (c["gift_correct"] - c["or_correct"])
di = [v for v in byitem.values() if v != 0]
rng = random.Random(4242); ge = 0; B = 200000
for _ in range(B):
    t = sum(v if rng.random() < 0.5 else -v for v in di)
    if abs(t) >= abs(T) - 1e-9: ge += 1
print("item-level sign-flip (nonzero items=%d) B=%d p = %.6f" % (len(di), B, ge / B))

json.dump({"pooled": P, "chi2_u": chi2_u, "chi2_c": chi2_c,
           "p_u": chi2_sf_df1(chi2_u), "p_c": chi2_sf_df1(chi2_c),
           "p_exact": binom_exact_two_sided_half(P["b"], nn)},
          open(AN + "ca_ref_01_core.json", "w"), indent=1)

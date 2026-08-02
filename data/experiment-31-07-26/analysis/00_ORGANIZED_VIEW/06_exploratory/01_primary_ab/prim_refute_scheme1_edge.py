#!/usr/bin/env python
"""Supplementary edge-case checks on the SCHEME-1 claim."""
import json
from fractions import Fraction
from math import comb
from collections import defaultdict

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")
rows = [r for r in json.load(open(DATA)) if r.get("analysis_include") is True]
models = sorted(set(r["model"] for r in rows))

CLAIMED = {"google/gemini-3.6-flash": "3.4655e-06",
           "qwen/qwen3.6-35b-a3b": "5.2573e-09",
           "google/gemma-4-26b-a4b-it": "6.1478e-11",
           "z-ai/glm-5.2": "1.0099e-12",
           "POOLED": "6.2745e-35"}


def dp_counts(K):
    counts = [0] * (2 * K + 1)
    counts[K] = 1
    for _ in range(K):
        nxt = [0] * (2 * K + 1)
        for i, v in enumerate(counts):
            if v:
                nxt[i - 1] += v
                nxt[i + 1] += v
        counts = nxt
    return counts


print("=" * 78)
print("A. EXACT p AS A RATIONAL, AND ROUNDING OF THE CLAIMED 5-SIG-FIG VALUES")
print("=" * 78)
for key in models + ["POOLED"]:
    sub = rows if key == "POOLED" else [r for r in rows if r["model"] == key]
    D = [r["A_correct"] - r["B_correct"] for r in sub]
    b = sum(1 for d in D if d == 1)
    c = sum(1 for d in D if d == -1)
    K, T = b + c, b - c
    cnt = dp_counts(K)
    ge = sum(v for i, v in enumerate(cnt) if abs(i - K) >= abs(T))     # >=  (standard)
    gt = sum(v for i, v in enumerate(cnt) if abs(i - K) > abs(T))      # >   (strict)
    eq = sum(v for i, v in enumerate(cnt) if abs(i - K) == abs(T))
    tot = 1 << K
    p_ge = Fraction(ge, tot)
    p_gt = Fraction(gt, tot)
    p_mid = Fraction(gt, tot) + Fraction(eq, 2 * tot)
    p_mcn = min(Fraction(2 * sum(comb(K, k) for k in range(min(b, c) + 1)), tot),
                Fraction(1))
    print(f"\n{key}   b={b} c={c} K={K} T_obs={T}")
    print(f"  numerator (|T|>=|T_obs|) = {ge}")
    print(f"  denominator 2^K          = {tot}")
    print(f"  p  (>=, standard, CLAIMED DEFN) = {float(p_ge):.10e}")
    print(f"  p  (>,  strict)                 = {float(p_gt):.10e}")
    print(f"  p  (mid-p)                      = {float(p_mid):.10e}")
    print(f"  exact binomial McNemar          = {float(p_mcn):.10e}")
    print(f"  p_ge == p_McNemar as exact Fractions: {p_ge == p_mcn}")
    print(f"  claimed {CLAIMED[key]}  -> matches 5-sig-fig rounding of p_ge: "
          f"{float(CLAIMED[key]) == float(f'{float(p_ge):.4e}')}")

print()
print("=" * 78)
print("B. WHERE THE PERM/McNEMAR EQUIVALENCE BREAKS (b == c tie case)")
print("=" * 78)
print("Uncapped 2*P(X<=min(b,c)) exceeds 1 when b==c; the permutation p is")
print("then exactly 1.  With the standard cap at 1 they agree everywhere.")
for K in (2, 4, 6, 10):
    b = c = K // 2
    cnt = dp_counts(K)
    tot = 1 << K
    p_perm = Fraction(sum(v for i, v in enumerate(cnt) if abs(i - K) >= 0), tot)
    p_raw = Fraction(2 * sum(comb(K, k) for k in range(b + 1)), tot)
    print(f"  K={K:3d} b=c={b:2d}  p_perm={float(p_perm):.6f}  "
          f"2P(X<=min) uncapped={float(p_raw):.6f}  capped={float(min(p_raw,Fraction(1))):.6f}")

print()
print("=" * 78)
print("C. LEAVE-ONE-MODEL-OUT AND CLUSTER-ROBUST SANITY ON THE POOLED NUMBER")
print("=" * 78)
by_item = defaultdict(int)
by_clu = defaultdict(int)
for r in rows:
    d = r["A_correct"] - r["B_correct"]
    by_item[r["question_id"]] += d
    by_clu[r["cluster"]] += d
T = sum(by_item.values())
vc = sum(1 for r in rows if r["A_correct"] != r["B_correct"])
vi = sum(v * v for v in by_item.values())
vk = sum(v * v for v in by_clu.values())


def norm_sf(z):
    # two-sided normal tail via Chebyshev-free continued fraction on erfc
    # use the Mills-ratio asymptotic-free approach: high-accuracy erfc by series/CF
    import math
    x = abs(z) / math.sqrt(2.0)
    if x < 2.0:
        # series for erf
        s, term, n = x, x, 0
        while True:
            n += 1
            term *= -x * x / n
            add = term / (2 * n + 1)
            s += add
            if abs(add) < 1e-18 * abs(s) or n > 300:
                break
        erf = 2.0 / math.sqrt(math.pi) * s
        erfc = 1.0 - erf
    else:
        # Lentz continued fraction for erfc
        tiny = 1e-300
        f, C, Dd = tiny, tiny, 0.0
        for i in range(1, 300):
            a = (i - 1) / 2.0 if i > 1 else 1.0
            bb = x if i % 2 == 1 else 1.0
            Dd = bb + a * Dd
            if Dd == 0:
                Dd = tiny
            C = bb + a / C
            if C == 0:
                C = tiny
            Dd = 1.0 / Dd
            delta = C * Dd
            f *= delta
            if abs(delta - 1.0) < 1e-17:
                break
        erfc = math.exp(-x * x) / math.sqrt(math.pi) * f
    return erfc  # two-sided p for |Z| >= z


for nm, v in (("cell (SCHEME 1)", vc), ("item-level", vi), ("cluster-level", vk)):
    z = T / v ** 0.5
    print(f"  pooled, {nm:16s}: Var={v:5d}  z={z:7.3f}  "
          f"two-sided normal p ~ {norm_sf(z):.3e}")

print()
print("  -> Even under the most conservative (cluster-level) flip constraint the")
print("     pooled effect stays far past any conventional threshold, so the")
print("     claim's QUALITATIVE reading survives; only the literal pooled")
print("     exponent (e-35) is specific to the cell-level scheme.")

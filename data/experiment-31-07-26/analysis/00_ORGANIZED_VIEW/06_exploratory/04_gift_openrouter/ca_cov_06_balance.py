"""ca_cov_06: how well does difficulty stratification actually BALANCE the
covered and uncovered cells? If OpenRouter accuracy still differs inside a
stratum, the stratum is not fine enough and the transfer still leans on an
untested assumption. Also: finer strata, region adjustment, and a log-odds
variant that keeps the 99 observed uncovered cells observed.
"""
import json, os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ca_lib as L

BASE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
SHORT = {"google/gemini-3.6-flash": "gemini", "google/gemma-4-26b-a4b-it": "gemma",
         "qwen/qwen3.6-35b-a3b": "qwen", "z-ai/glm-5.2": "glm"}

G = json.load(open(os.path.join(BASE, "ca_cov_grid.json")))
orc = {tuple(k.split("|")): v for k, v in G["or_correct"].items()}
gic = {tuple(k.split("|")): v for k, v in G["gift_correct"].items()}
covered = set(G["covered"]); defect = set(G["defect"])
items = json.load(open(os.path.join(BASE, "ca_cov_or_full.json")))["items"]
cross = {(r["model"], r["question_id"]): r for r in L.load(include_only=True)}


def loo_k(q, m):
    vs = [orc[(mm, q)] for mm in MODELS if mm != m and (mm, q) in orc]
    return sum(vs) if len(vs) == 3 else None


POP = []
for q in items:
    if q in defect:
        continue
    for m in MODELS:
        if (m, q) not in orc:
            continue
        POP.append({"q": q, "m": m, "or": orc[(m, q)], "gift": gic.get((m, q)),
                    "k": loo_k(q, m), "paired": q in covered,
                    "region": items[q]["region"], "order": items[q]["order"],
                    "cluster": cross[(m, q)]["cluster"] if (m, q) in cross else None})
PAIR = [r for r in POP if r["paired"]]
NONP = [r for r in POP if not r["paired"]]          # 595 cells, 149 items
MISS = [r for r in POP if r["gift"] is None]
EXTRA = [r for r in POP if not r["paired"] and r["gift"] is not None]
N = len(POP)
print(f"population {N} cells | paired {len(PAIR)} | non-paired {len(NONP)} "
      f"(observed {len(EXTRA)}, missing {len(MISS)})")

print("\n=== BALANCE CHECK: OR accuracy inside each LOO-difficulty stratum ===")
print(f"{'k':>2s} {'n_pair':>7s} {'OR_pair':>8s} {'n_nonp':>7s} {'OR_nonp':>8s} "
      f"{'gap_pp':>7s} {'fisher_p':>9s}")
for k in range(4):
    a = [r for r in PAIR if r["k"] == k]
    b_ = [r for r in NONP if r["k"] == k]
    if not a or not b_:
        continue
    ka = sum(r["or"] for r in a); kb = sum(r["or"] for r in b_)
    p = L.fisher_exact_2x2(ka, len(a) - ka, kb, len(b_) - kb)
    print(f"{k:2d} {len(a):7d} {100*ka/len(a):7.2f}% {len(b_):7d} "
          f"{100*kb/len(b_):7.2f}% {100*(kb/len(b_)-ka/len(a)):+6.2f} {p:9.4f}")
ka = sum(r["or"] for r in PAIR); kb = sum(r["or"] for r in NONP)
print(f"{'ALL':>2s} {len(PAIR):7d} {100*ka/len(PAIR):7.2f}% {len(NONP):7d} "
      f"{100*kb/len(NONP):7.2f}% {100*(kb/len(NONP)-ka/len(PAIR)):+6.2f} "
      f"{L.fisher_exact_2x2(ka, len(PAIR)-ka, kb, len(NONP)-kb):9.4f}")
print("-> stratifying on LOO difficulty removes most, but NOT all, of the")
print("   covered/uncovered accuracy gap: residual imbalance stays inside k<=2.")

print("\n=== how much of the 8.0pp raw OR gap does k-stratification explain? ===")
raw = kb / len(NONP) - ka / len(PAIR)
# standardise the non-paired cells to the paired k-distribution
wp = {k: sum(1 for r in PAIR if r["k"] == k) / len(PAIR) for k in range(4)}
std = 0.0
for k in range(4):
    b_ = [r for r in NONP if r["k"] == k]
    if b_:
        std += wp[k] * (sum(r["or"] for r in b_) / len(b_))
print(f"raw OR gap (non-paired - paired)             : {100*raw:+.2f} pp")
print(f"k-standardised non-paired OR accuracy        : {100*std:.2f}%")
print(f"residual gap after k-standardisation         : "
      f"{100*(std - ka/len(PAIR)):+.2f} pp "
      f"({100*(1 - (std - ka/len(PAIR))/raw):.0f}% of the gap explained by difficulty)")

print("\n=== REGION: does it add anything beyond difficulty? ===")
regs = sorted(set(r["region"] for r in POP))
wr = {rg: sum(1 for r in PAIR if r["region"] == rg) / len(PAIR) for rg in regs}
stdr = tw = 0.0
for rg in regs:
    b_ = [r for r in NONP if r["region"] == rg]
    if b_:
        stdr += wr[rg] * (sum(r["or"] for r in b_) / len(b_)); tw += wr[rg]
print(f"region-standardised non-paired OR accuracy   : {100*stdr/tw:.2f}%  "
      f"(residual gap {100*(stdr/tw - ka/len(PAIR)):+.2f} pp)")
# joint region x k
sj = tw2 = 0.0
wj = {}
for r in PAIR:
    wj[(r["region"], r["k"])] = wj.get((r["region"], r["k"]), 0) + 1 / len(PAIR)
for key, w in wj.items():
    b_ = [r for r in NONP if (r["region"], r["k"]) == key]
    if b_:
        sj += w * (sum(r["or"] for r in b_) / len(b_)); tw2 += w
print(f"region x k standardised (coverage {100*tw2:.0f}% of paired weight): "
      f"{100*sj/tw2:.2f}%  (residual gap {100*(sj/tw2 - ka/len(PAIR)):+.2f} pp)")

# ---------------------------------------------------------- E7: finer strata
def est(mode, use_extra_observed):
    agg = {}
    for r in PAIR:
        s = key(r, mode)
        a = agg.setdefault(s, [0, 0]); a[0] += r["gift"] - r["or"]; a[1] += 1
    crude = sum(r["gift"] - r["or"] for r in PAIR) / len(PAIR)
    tgt = MISS if use_extra_observed else (MISS + EXTRA)
    tot = 0.0
    for r in tgt:
        s = key(r, mode)
        tot += agg[s][0] / agg[s][1] if (s in agg and agg[s][1] >= 5) else crude
    base = sum(r["gift"] - r["or"] for r in PAIR)
    if use_extra_observed:
        base += sum(r["gift"] - r["or"] for r in EXTRA)
    return (base + tot) / N


def key(r, mode):
    if mode == "k":
        return r["k"]
    if mode == "m_k":
        return (r["m"], r["k"])
    if mode == "m_he":
        return (r["m"], "E" if r["k"] == 3 else "H")
    if mode == "m_he_reg":
        return (r["m"], "E" if r["k"] == 3 else "H", r["region"])
    if mode == "he_reg":
        return ("E" if r["k"] == 3 else "H", r["region"])
    if mode == "none":
        return 0
    raise ValueError


print("\n=== E7 estimator grid (full-dataset delta, pp) ===")
print(f"{'strata':12s} {'transfer-only':>14s} {'+99 observed':>14s}")
grid = {}
for mode in ["none", "k", "m_he", "m_k", "he_reg", "m_he_reg"]:
    a = est(mode, False); b_ = est(mode, True)
    grid[mode] = [a, b_]
    print(f"{mode:12s} {100*a:+13.2f} {100*b_:+13.2f}")

vals = [v for pair in grid.values() for v in pair]
print(f"\nrange across all specifications: [{100*min(vals):+.2f}, {100*max(vals):+.2f}] pp")

json.dump({"grid": grid, "raw_or_gap": raw,
           "k_standardised": std, "region_standardised": stdr / tw,
           "joint_standardised": sj / tw2,
           "or_pair": ka / len(PAIR), "or_nonpair": kb / len(NONP)},
          open(os.path.join(BASE, "ca_cov_06_out.json"), "w"), indent=1)

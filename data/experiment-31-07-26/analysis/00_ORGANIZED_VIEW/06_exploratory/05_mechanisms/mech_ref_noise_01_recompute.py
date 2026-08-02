"""Independent recomputation of the 'noise bound' claim.

Everything from paired_clean.json directly (not from mech_who_00_build), stdlib only.
Methods named inline.
"""
import json, math, collections, random

random.seed(11)
P = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
rows = [r for r in json.load(open(P)) if r["analysis_include"]]
N = len(rows)
n11 = sum(1 for r in rows if r["A_correct"] and r["B_correct"])
n10 = sum(1 for r in rows if r["A_correct"] and not r["B_correct"])   # lost
n01 = sum(1 for r in rows if not r["A_correct"] and r["B_correct"])   # gained
n00 = N - n11 - n10 - n01
D = n10 + n01
print(f"N={N}  items={len({r['question_id'] for r in rows})} clusters={len({r['cluster'] for r in rows})} models={len({r['model'] for r in rows})}")
print(f"2x2: n11={n11}  lost={n10}  gained={n01}  n00={n00}  discordant={D}")
print(f"A acc={(n11+n10)/N:.4f}  B acc={(n11+n01)/N:.4f}  net drop={(n10-n01)/N:.4f} = {(n10-n01)/N*100:.2f} pts")

def binom_cdf(k, n, p):
    return sum(math.comb(n, i) * p**i * (1-p)**(n-i) for i in range(0, k+1))

print()
print("--- Claim's headline arithmetic ---")
print(f"  gains/losses            = {n01}/{n10} = {n01/n10:.4f}  (claim 18.2%)")
print(f"  2*gains/discordant      = {2*n01}/{D} = {2*n01/D:.4f}  (claim 30.8%)")
print(f"  net systematic cells    = {n10-n01}  ({(n10-n01)/N*100:.2f} acc pts)  (claim 202 / 15.6)")
print(f"  2S/N ceiling            = {2*n01/N:.4f}  (claim 0.069)")
print(f"  S=247 -> 2S/N           = {2*n10/N:.4f}  (claim 0.38)")
one = binom_cdf(n01, D, 0.5)
print(f"  P(gained<={n01} | Bin({D},0.5)) = {one:.3e}  [exact binomial one-sided]  (claim 3.1e-35)")
mc = min(1.0, 2*binom_cdf(min(n10, n01), D, 0.5))
print(f"  exact McNemar two-sided = {mc:.3e}")

print()
print("--- Per-model symmetry ceilings ---")
for m in sorted({r["model"] for r in rows}):
    rs = [r for r in rows if r["model"] == m]
    l = sum(1 for r in rs if r["A_correct"] and not r["B_correct"])
    g = sum(1 for r in rs if not r["A_correct"] and r["B_correct"])
    p = min(1.0, 2*binom_cdf(min(l, g), l+g, 0.5))
    print(f"  {m:<28} n={len(rs):>4} lost={l:>3} gain={g:>3} ceiling(g/l)={g/l:>6.1%} "
          f"2g/D={2*g/(l+g):>6.1%} exactMcNemar={p:.2e}")

# ---------------------------------------------------------------- sampling error
print()
print("--- The 'ceilings' are point estimates, not bounds: sampling error ---")
def cp_upper(k, n, a=0.05):
    """Clopper-Pearson upper limit, bisection on binom_cdf(k;n,p) = a."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo+hi)/2
        if binom_cdf(k, n, mid) > a: lo = mid
        else: hi = mid
    return (lo+hi)/2
def cp_lower(k, n, a=0.05):
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo+hi)/2
        if 1-binom_cdf(k-1, n, mid) > a: hi = mid
        else: lo = mid
    return (lo+hi)/2
# gains ~ Binomial(D, pi) conditional on D discordant  -> 95% upper for E[gains]
hi_pi = cp_upper(n01, D)
print(f"  gains: {n01}/{D} discordant. Clopper-Pearson 95% upper on pi = {hi_pi:.4f} "
      f"-> E[gains] <= {hi_pi*D:.1f}")
print(f"  => noise-attributable-loss ceiling, upper 95%: {hi_pi*D/n10:.1%}  (claim states 18.2% flat)")
# cluster bootstrap for both quantities
byc = collections.defaultdict(list)
for r in rows: byc[r["cluster"]].append(r)
keys = list(byc)
bg, bnet = [], []
for _ in range(6000):
    s = [byc[random.choice(keys)] for _ in keys]
    flat = [r for gg in s for r in gg]
    l = sum(1 for r in flat if r["A_correct"] and not r["B_correct"])
    g = sum(1 for r in flat if not r["A_correct"] and r["B_correct"])
    if l: bg.append(g/l)
    bnet.append((l-g)/len(flat)*len(flat))  # raw net count scaled to same n
bg.sort(); bnet.sort()
print(f"  cluster bootstrap (6000 reps, resample 208 clusters):")
print(f"    gains/losses ratio  95% CI [{bg[150]:.3f}, {bg[5850]:.3f}]   (point {n01/n10:.3f})")
print(f"    net systematic cells 95% CI [{bnet[150]:.0f}, {bnet[5850]:.0f}]  (point {n10-n01})")

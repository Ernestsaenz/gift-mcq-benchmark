"""Is the df=3 t-test really "the most conservative defensible reading"?

The claim says: the only specs missing p<0.001 treat the 4 models as the only
random effect (n=4, df=3), "the most conservative defensible reading", and even
those land at p~0.009.

The df=3 t-test is the most conservative reading *inside this grid*.  It is NOT
the most conservative defensible reading of "4 models are the only random
effect".  This script enumerates the standard alternatives for that same n=4
random effect and shows where they land.

Everything stdlib; primitives from sens_refute_curvep_lib.py.
"""
import json, os, sys, math, itertools, random, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sens_refute_curvep_lib as L

rows = json.load(open(os.path.join(HERE, "paired_clean.json")))
MODELS = sorted(set(r["model"] for r in rows))
NM = len(MODELS)
_b320 = [r for r in rows if r["question_id"] == "b320"][0]
STRICT_EXTRA = dict(question_id="b320", model="z-ai/glm-5.2", cluster=_b320["cluster"],
                    correct_letter=_b320["correct_letter"], A_correct=0, B_correct=1,
                    excl_item_defect=False, excl_nota_position_a=False)
EXCL = {
    "primary":     lambda r: (not r["excl_item_defect"]) and (not r["excl_nota_position_a"]),
    "defect_only": lambda r: not r["excl_item_defect"],
    "notaA_only":  lambda r: not r["excl_nota_position_a"],
    "none":        lambda r: True,
}


def subset(ex, oc):
    base = rows + ([STRICT_EXTRA] if oc == "strict" else [])
    return [r for r in base if EXCL[ex](r)]


def per_model_delta(recs):
    out = []
    for m in MODELS:
        mr = [r for r in recs if r["model"] == m]
        out.append(100.0 * sum(x["B_correct"] - x["A_correct"] for x in mr) / len(mr))
    return out


# ---------------------------------------------------------------- n=4 tests
def t_onesample(d):
    n = len(d)
    m = sum(d) / n
    v = sum((x - m) ** 2 for x in d) / (n - 1)
    se = math.sqrt(v / n)
    return m, se, L.t_two_sided(m / se, n - 1)


def exact_signflip(d):
    """Exact two-sided sign-flip permutation over the n units. 2^n assignments."""
    n = len(d)
    obs = abs(sum(d) / n)
    ge = 0
    for signs in itertools.product((1, -1), repeat=n):
        s = sum(si * di for si, di in zip(signs, d)) / n
        if abs(s) >= obs - 1e-12:
            ge += 1
    return ge / (2 ** n), 2 ** n


def exact_sign_test(d):
    """Two-sided exact sign test: Bin(n, 1/2) on the count of negatives."""
    npos = sum(1 for x in d if x > 0)
    nneg = sum(1 for x in d if x < 0)
    return L.binom_two_sided_exact(npos, nneg)


def exact_signed_rank(d):
    """Exact two-sided Wilcoxon signed-rank over all 2^n sign patterns."""
    n = len(d)
    a = sorted(range(n), key=lambda i: abs(d[i]))
    rank = [0] * n
    for pos, i in enumerate(a):
        rank[i] = pos + 1
    Wobs = sum(rank[i] for i in range(n) if d[i] > 0)
    tot = n * (n + 1) / 2.0
    dev = abs(Wobs - tot / 2.0)
    ge = 0
    for signs in itertools.product((0, 1), repeat=n):
        W = sum(rank[i] for i in range(n) if signs[i])
        if abs(W - tot / 2.0) >= dev - 1e-12:
            ge += 1
    return ge / (2 ** n)


def model_bootstrap(d, B=200000, seed=4242):
    rng = random.Random(seed)
    n = len(d)
    lo = hi = 0
    for _ in range(B):
        s = sum(d[rng.randrange(n)] for _ in range(n)) / n
        if s < 0:
            lo += 1
        elif s > 0:
            hi += 1
        else:
            lo += 0.5; hi += 0.5
    return max(2.0 * min(lo, hi) / B, 1.0 / (B + 1.0)), (2.0 * min(lo, hi) / B) < 1.0 / (B + 1.0)


def loo_models(d):
    """Leave-one-model-out one-sample t (n=3, df=2)."""
    out = []
    for j in range(len(d)):
        dd = [d[i] for i in range(len(d)) if i != j]
        m, se, p = t_onesample(dd)
        out.append((MODELS[j], m, p))
    return out


# --------------------------------------------------- two-way clustered SE
def twoway_cluster_p(recs):
    """Intercept-only OLS on the cell-level paired difference, SE two-way
    clustered on {model} and {clinical cluster} (Cameron-Gelbach-Miller):
        V = V_model + V_cluster - V_intersection,
    each component CR1-corrected, reference t(min(G1,G2)-1).
    This is the standard estimator when BOTH random effects are crossed, which
    is exactly the structure here (4 models x 208-281 clusters).
    """
    d = [100.0 * (r["B_correct"] - r["A_correct"]) for r in recs]
    n = len(d)
    mean = sum(d) / n
    e = [x - mean for x in d]

    def comp(keys):
        agg = {}
        for i in range(n):
            agg[keys[i]] = agg.get(keys[i], 0.0) + e[i]
        G = len(agg)
        meat = sum(u * u for u in agg.values())
        corr = G / (G - 1.0) if G > 1 else 1.0
        return corr * meat / (n * n), G

    v1, G1 = comp([r["model"] for r in recs])
    v2, G2 = comp([r["cluster"] for r in recs])
    v3, G3 = comp([(r["model"], r["cluster"]) for r in recs])
    v = v1 + v2 - v3
    if v <= 0:
        return mean, float("nan"), float("nan"), G1, G2
    se = math.sqrt(v)
    dfx = min(G1, G2) - 1
    return mean, se, L.t_two_sided(mean / se, dfx), G1, G2


print("=" * 96)
print("THE n=4 MODEL-LEVEL RANDOM EFFECT: EVERY STANDARD READING, NOT JUST THE t-TEST")
print("=" * 96)
print("\nMinimum ATTAINABLE two-sided p for an exact rank/sign test on n=4 units:")
print(f"   sign-flip permutation : 2/2^4 = {2/16:.4f}")
print(f"   sign test             : 2*(1/2^4) = {2/16:.4f}")
print(f"   Wilcoxon signed-rank  : 2/2^4 = {2/16:.4f}")
print("   -> NO assumption-free test of a 4-model random effect can reach p<0.05,")
print("      no matter how large the effect.  The df=3 t-test clears 0.05 only")
print("      because it imports a normality assumption over 4 points.\n")

hdr = (f"{'exclusion':<12} {'outcome':<8} {'deltas (per model, pp)':<40} "
       f"{'t(3) p':>9} {'signflip':>9} {'signtest':>9} {'sgnrank':>9} {'boot4':>9} {'2way p':>9}")
print(hdr)
print("-" * len(hdr))
summary = {}
for ex in ("primary", "defect_only", "notaA_only", "none"):
    for oc in ("lenient", "strict"):
        recs = subset(ex, oc)
        d = per_model_delta(recs)
        m, se, pt = t_onesample(d)
        psf, nperm = exact_signflip(d)
        pst = exact_sign_test(d)
        psr = exact_signed_rank(d)
        pb, _ = model_bootstrap(d)
        mm, se2, p2w, G1, G2 = twoway_cluster_p(recs)
        summary[(ex, oc)] = dict(d=d, t=pt, sf=psf, sg=pst, sr=psr, boot=pb, tw=p2w,
                                 se=se, se2=se2)
        ds = "[" + ", ".join(f"{x:+6.2f}" for x in d) + "]"
        print(f"{ex:<12} {oc:<8} {ds:<40} {pt:>9.5f} {psf:>9.4f} {pst:>9.4f} "
              f"{psr:>9.4f} {pb:>9.4f} {p2w:>9.5f}")

print("\n  model order:", [m.split('/')[-1] for m in MODELS])

print("\n" + "=" * 96)
print("LEAVE-ONE-MODEL-OUT AT THE MODEL LEVEL  (n=3, df=2) -- how much rides on 4 draws?")
print("=" * 96)
worst = []
for ex in ("primary", "defect_only", "notaA_only", "none"):
    for oc in ("lenient", "strict"):
        d = summary[(ex, oc)]["d"]
        out = loo_models(d)
        s = "   ".join(f"-{mn.split('/')[-1][:12]:<12} p={p:.4f}" for mn, mm2, p in out)
        mx = max(p for _, _, p in out)
        worst.append((mx, ex, oc, max(out, key=lambda z: z[2])[0]))
        flag = "  <-- FAILS p<0.05" if mx >= 0.05 else ""
        print(f"  {ex:<12} {oc:<8} max p={mx:.4f}{flag}")
        print(f"      {s}")
worst.sort(reverse=True)
print(f"\n  worst leave-one-model-out p over the 8 datasets: {worst[0][0]:.4f} "
      f"({worst[0][1]}/{worst[0][2]}, dropping {worst[0][3].split('/')[-1]})")
print(f"  n datasets whose LOO-model p exceeds 0.05: "
      f"{sum(1 for w in worst if w[0] >= 0.05)}/8")

print("\n" + "=" * 96)
print("WHAT |t| WOULD THE df=3 SPEC NEED?")
print("=" * 96)
for target in (0.05, 0.01, 0.001):
    lo, hi = 0.0, 200.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if L.t_two_sided(mid, 3) > target:
            lo = mid
        else:
            hi = mid
    print(f"   p<{target:<6} requires |t| > {hi:8.4f}   (i.e. mean/sd over the 4 models > {hi/2:.4f})")
obs_t = [abs(summary[k]['d'] and (sum(summary[k]['d'])/4)/summary[k]['se']) for k in summary]
print(f"   observed |t| range across the 8 datasets: {min(obs_t):.4f} .. {max(obs_t):.4f}")
print("   -> p<0.001 at df=3 is UNREACHABLE for this design at any plausible effect size;")
print("      the '8 specs miss p<0.001' is a df=3 ceiling, not a weak-evidence signal,")
print("      and symmetrically the 152/160 'successes' are a df ceiling in the other direction.")

json.dump({f"{k[0]}|{k[1]}": v for k, v in summary.items()},
          open(os.path.join(HERE, "sens_refute_curvep_02_out.json"), "w"), indent=1)

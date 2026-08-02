"""Is the pooled discordant OR a meaningful common effect, or an artefact of
pooling four heterogeneous models?

Two of four models point the other way. Test homogeneity of pi across models
(exact-ish, by enumerating/simulating the conditional distribution), and check
leave-one-model-out and leave-one-cluster-out stability of the headline p.
"""
import json
import math
from fractions import Fraction
from collections import defaultdict

P = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/"
D = [r for r in json.load(open(P + "cross_arm_A.json")) if r["analysis_include"]]
for r in D:
    r["d"] = r["gift_correct"] - r["or_correct"]
disc = [r for r in D if r["d"] != 0]

models = sorted(set(r["model"] for r in D))
bc = {}
for m in models:
    sub = [r for r in disc if r["model"] == m]
    bc[m] = (sum(1 for r in sub if r["d"] == 1), sum(1 for r in sub if r["d"] == -1))
print("per-model (b,c):", bc)


def exact_mcnemar_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    den = 1 << n
    lo = Fraction(sum(math.comb(n, i) for i in range(0, b + 1)), den)
    hi = Fraction(sum(math.comb(n, i) for i in range(b, n + 1)), den)
    return float(min(Fraction(1), 2 * min(lo, hi)))


print("\nper-model exact McNemar p:")
for m in models:
    b, c = bc[m]
    pi = b / (b + c) if b + c else float("nan")
    print("  %-28s b=%2d c=%2d n=%2d  pi=%.3f  p=%.4f" % (m, b, c, b + c, pi, exact_mcnemar_p(b, c)))

# ---------------- homogeneity of pi across models, conditional on per-model n
B = sum(v[0] for v in bc.values())
N = sum(v[0] + v[1] for v in bc.values())
pi0 = B / N


def lr_stat(bs, ns):
    """Likelihood-ratio chi2 for H0: common pi, binomials with fixed n."""
    b_tot, n_tot = sum(bs), sum(ns)
    p0 = b_tot / n_tot
    g = 0.0
    for b, n in zip(bs, ns):
        c = n - b
        if b:
            g += 2 * b * math.log(b / (n * p0))
        if c:
            g += 2 * c * math.log(c / (n * (1 - p0)))
    return g


ns = [bc[m][0] + bc[m][1] for m in models]
bs = [bc[m][0] for m in models]
G = lr_stat(bs, ns)
chi2_sf3 = lambda x: math.exp(-x / 2) * (1 + math.sqrt(x / (2 * math.pi)) * 0  # placeholder
                                         )
# proper 3-df survival: P(X>x) = erfc(sqrt(x/2)) + sqrt(2x/pi)*exp(-x/2)
def sf3(x):
    return math.erfc(math.sqrt(x / 2.0)) + math.sqrt(2.0 * x / math.pi) * math.exp(-x / 2.0)


print("\nhomogeneity of pi across the 4 models")
print("  LR G2 = %.4f  df=3  asymptotic p = %.4f" % (G, sf3(G)))

# exact conditional permutation: shuffle the 70 discordant signs across models
# holding each model's n_disc fixed. Full enumeration is C(70,46)-ish, so do a
# complete-randomisation Monte Carlo with a deterministic LCG (1e6 draws).
class LCG:
    def __init__(self, seed):
        self.s = (seed ^ 0x9E3779B97F4A7C15) & ((1 << 64) - 1)

    def rr(self, n):
        self.s = (self.s * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        return (self.s >> 16) % n


signs = [r["d"] for r in disc]
rng = LCG(20260731)
REPS = 1000000
ge = 0
for _ in range(REPS):
    pool = signs[:]
    # partial Fisher-Yates, then slice by model block sizes
    k = 0
    out = []
    L = len(pool)
    for i in range(L - 1, 0, -1):
        j = rng.rr(i + 1)
        pool[i], pool[j] = pool[j], pool[i]
    idx = 0
    bs_p = []
    for n in ns:
        blk = pool[idx:idx + n]
        idx += n
        bs_p.append(sum(1 for x in blk if x == 1))
    if lr_stat(bs_p, ns) >= G - 1e-12:
        ge += 1
p_perm = (ge + 1) / (REPS + 1)
print("  exact-conditional permutation (1e6 relabelings, LCG seed 20260731) p = %.5f" % p_perm)

# ---------------- leave-one-model-out
print("\nleave-one-model-out pooled exact McNemar:")
for m in models:
    b = sum(v[0] for k, v in bc.items() if k != m)
    c = sum(v[1] for k, v in bc.items() if k != m)
    orr = b / c if c else float("inf")
    print("  drop %-28s b=%2d c=%2d  OR=%.3f  p=%.5f" % (m, b, c, orr, exact_mcnemar_p(b, c)))

# ---------------- leave-one-cluster-out (jackknife on the headline p)
by_clu = defaultdict(list)
for r in disc:
    by_clu[r["cluster"]].append(r["d"])
worst = []
for cl in sorted(by_clu):
    b = sum(1 for r in disc if r["cluster"] != cl and r["d"] == 1)
    c = sum(1 for r in disc if r["cluster"] != cl and r["d"] == -1)
    worst.append((exact_mcnemar_p(b, c), cl, b, c))
worst.sort()
print("\nleave-one-cluster-out: max p = %.5f (drop cluster %s -> b=%d c=%d)" %
      (worst[-1][0], worst[-1][1], worst[-1][2], worst[-1][3]))
print("  n clusters whose removal pushes p above 0.05: %d of %d" %
      (sum(1 for w in worst if w[0] > 0.05), len(worst)))

# ---------------- leave-one-ITEM-out
items = sorted(set(r["question_id"] for r in disc))
wi = []
for q in items:
    b = sum(1 for r in disc if r["question_id"] != q and r["d"] == 1)
    c = sum(1 for r in disc if r["question_id"] != q and r["d"] == -1)
    wi.append((exact_mcnemar_p(b, c), q, b, c))
wi.sort()
print("leave-one-item-out:    max p = %.5f (drop %s -> b=%d c=%d)" %
      (wi[-1][0], wi[-1][1], wi[-1][2], wi[-1][3]))

json.dump({"bc": {k: list(v) for k, v in bc.items()},
           "G2": G, "G2_p_asym": sf3(G), "G2_p_perm": p_perm,
           "loo_model": {m: exact_mcnemar_p(sum(v[0] for k, v in bc.items() if k != m),
                                            sum(v[1] for k, v in bc.items() if k != m))
                         for m in models},
           "loo_cluster_max_p": worst[-1][0], "loo_item_max_p": wi[-1][0]},
          open(P + "ca_ref_02_out.json", "w"), indent=1)

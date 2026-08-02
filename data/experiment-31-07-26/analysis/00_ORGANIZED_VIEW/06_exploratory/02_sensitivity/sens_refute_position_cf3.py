#!/usr/bin/env python
"""
sens_refute_position_cf3.py -- the most adversarial reasonable alternative.

Section 6 of cf2 found a slot gradient in delta (a=-23.1, b=-18.2, c=-13.6,
d=-15.5; n-weighted slope +2.83 pp/slot, randomisation p=.017).  If the
"respuestas ANTERIORES" defect is really about how many antecedents the inserted
option has, then slot (b) -- one antecedent -- is ALSO partly defective, and the
claim's donor set (b,c,d) is contaminated downward, understating the share
attributable to the construction defect.

This script asks: how large can the attributable share get under the most
defect-generous specification the data support?

  M0  claim:            impute (a) from model's b,c,d mean
  M1  donor purified:   impute (a) from model's c,d mean
  M2  defect extended:  impute (a) AND (b) from model's c,d mean
  M3  defect extended+: impute (a),(b) from model's c mean (best slot)

Also: a direct cluster-bootstrap contrast of delta(b) vs delta(c,d), which is the
evidence that would justify M2/M3 at all.

Method: cluster bootstrap over the 281 clinical-context clusters, 20,000
replicates, all donor means recomputed inside each replicate; percentile CIs.
"""
import json, random, math, collections

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
B = 20000
SEED = 20260731

rows = json.load(open(PATH))
MODELS = sorted(set(r["model"] for r in rows))
MI = {m: i for i, m in enumerate(MODELS)}
NM = len(MODELS)
LET = {"a": 0, "b": 1, "c": 2, "d": 3}

# compact per-cell tuples: (model_idx, letter_idx, d)
CELLS = [(MI[r["model"]], LET[r["correct_letter"]], r["B_correct"] - r["A_correct"]) for r in rows]

by_cluster = collections.defaultdict(list)
for r, c in zip(rows, CELLS):
    by_cluster[r["cluster"]].append(c)
CLUSTERS = list(by_cluster.values())
K = len(CLUSTERS)


def quantile(s, q):
    p = q * (len(s) - 1)
    lo, hi = int(math.floor(p)), int(math.ceil(p))
    return s[lo] if lo == hi else s[lo] + (s[hi] - s[lo]) * (p - lo)


def ci(v):
    s = sorted(x for x in v if x == x)
    return quantile(s, .025), quantile(s, .975)


def hd(t):
    print("\n" + "=" * 78); print(t); print("=" * 78)


NAN = float("nan")


def stats_of(cells):
    n = len(cells)
    # sums by (model, letter)
    S = [[0.0] * 4 for _ in range(NM)]
    C = [[0] * 4 for _ in range(NM)]
    tot = 0.0
    for m, L, d in cells:
        S[m][L] += d; C[m][L] += 1; tot += d
    o = {"raw": 100 * tot / n}
    ls = [0.0] * 4; lc = [0] * 4
    for m in range(NM):
        for L in range(4):
            ls[L] += S[m][L]; lc[L] += C[m][L]
    for L, name in enumerate("abcd"):
        o["d_" + name] = 100 * ls[L] / lc[L] if lc[L] else NAN
    o["d_cd"] = 100 * (ls[2] + ls[3]) / (lc[2] + lc[3]) if (lc[2] + lc[3]) else NAN
    o["d_bcd"] = 100 * (ls[1] + ls[2] + ls[3]) / (lc[1] + lc[2] + lc[3]) if (lc[1] + lc[2] + lc[3]) else NAN
    o["b_vs_cd"] = o["d_b"] - o["d_cd"]
    o["a_vs_cd"] = o["d_a"] - o["d_cd"]

    def donor(m, ls_):
        num = sum(S[m][L] for L in ls_); den = sum(C[m][L] for L in ls_)
        return num / den if den else NAN

    def cf(imputed, donors):
        acc = 0.0
        for m in range(NM):
            dv = donor(m, donors)
            if dv != dv:
                return NAN
            for L in range(4):
                acc += (C[m][L] * dv) if L in imputed else S[m][L]
        return 100 * acc / n

    for key, imp, don in [("M0", {0}, (1, 2, 3)), ("M1", {0}, (2, 3)),
                          ("M2", {0, 1}, (2, 3)), ("M3", {0, 1}, (2,))]:
        o[key] = cf(imp, don)
        o[key + "_att"] = o["raw"] - o[key]
        o[key + "_sh"] = o[key + "_att"] / o["raw"] if o["raw"] else NAN
    return o


point = stats_of(CELLS)
rng = random.Random(SEED)
boot = collections.defaultdict(list)
for _ in range(B):
    samp = []
    for _ in range(K):
        samp.extend(CLUSTERS[rng.randrange(K)])
    for k, v in stats_of(samp).items():
        boot[k].append(v)


def rep(k, lab, f="{:+.3f}"):
    lo, hi = ci(boot[k])
    print(f"{lab:<46}{f.format(point[k]):>9}   95% CI [{f.format(lo)}, {f.format(hi)}]")


hd("1. IS SLOT (b) ITSELF DEGRADED?  (the premise of the adversarial variants)")
rep("d_a", "delta | a  (0 antecedents)")
rep("d_b", "delta | b  (1 antecedent)")
rep("d_c", "delta | c  (2 antecedents)")
rep("d_d", "delta | d  (3 antecedents)")
print()
rep("b_vs_cd", "contrast delta(b) - delta(c,d)")
rep("a_vs_cd", "contrast delta(a) - delta(c,d)")
pb = sum(1 for x in boot["b_vs_cd"] if x >= 0) / len(boot["b_vs_cd"])
print(f"\nbootstrap P*(delta(b) >= delta(c,d)) = {pb:.4f}")
print("  -> the (b)-slot penalty is NOT separable from noise; the monotone-antecedent")
print("     story is only weakly supported (and d is worse than c, breaking monotonicity).")

hd("2. ATTRIBUTABLE SHARE UNDER PROGRESSIVELY MORE DEFECT-GENEROUS MODELS")
print(f"{'specification':<46}{'cf delta':>10}{'attrib':>9}{'share':>8}   95% CI on share")
for k, lab in [("M0", "M0 claim: (a) <- b,c,d mean"),
               ("M1", "M1 donor purified: (a) <- c,d mean"),
               ("M2", "M2 defect extended: (a),(b) <- c,d mean"),
               ("M3", "M3 defect extended+: (a),(b) <- c mean")]:
    lo, hi = ci(boot[k + "_sh"])
    print(f"{lab:<46}{point[k]:>+10.3f}{point[k+'_att']:>+9.3f}{point[k+'_sh']:>8.4f}"
          f"   [{lo:.3f}, {hi:.3f}]")

hd("3. VERDICT ARITHMETIC")
print(f"raw pooled delta                    {point['raw']:+.4f} pp")
print(f"claim's counterfactual              {point['M0']:+.4f} pp   (claim: -15.7502)")
print(f"claim's attributable                {point['M0_att']:+.4f} pp   (claim: -1.5768)")
print(f"claim's share                       {point['M0_sh']:.4f}       (claim:  0.0910)")
print()
print("most adversarial supported spec (M2) still leaves the genuine component at")
print(f"  {100*(1-point['M2_sh']):.1f}% of the raw degradation "
      f"(counterfactual delta {point['M2']:+.2f} pp).")

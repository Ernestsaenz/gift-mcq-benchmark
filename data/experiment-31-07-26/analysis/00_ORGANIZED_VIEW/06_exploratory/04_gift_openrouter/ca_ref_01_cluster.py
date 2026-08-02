"""Does the independence assumption behind the exact McNemar hold?

The exact conditional binomial treats the 70 discordant CELLS as 70 independent
Bernoulli(1/2) draws. But a cell is (item x model): 311 items nested in 183
clusters, each crossed with 4 models. If discordance clumps within item/cluster
the effective n < 70 and the exact p is anti-conservative.

Tests implemented from scratch:
  (1) descriptive clumping: how many distinct items/clusters carry the 70
  (2) exact sign-flip permutation at ITEM level  (flip all cells of an item)
  (3) exact sign-flip permutation at CLUSTER level
  (4) design-effect / cluster-robust z on S = b - c
"""
import json
import math
from fractions import Fraction
from collections import defaultdict

P = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/"
D = [r for r in json.load(open(P + "cross_arm_A.json")) if r["analysis_include"]]

# d = +1 GIFT-only-correct, -1 OR-only-correct, 0 concordant
for r in D:
    r["d"] = r["gift_correct"] - r["or_correct"]

disc = [r for r in D if r["d"] != 0]
S_obs = sum(r["d"] for r in disc)
print("n_disc = %d   S = b - c = %d" % (len(disc), S_obs))

by_item = defaultdict(list)
by_clu = defaultdict(list)
for r in disc:
    by_item[r["question_id"]].append(r["d"])
    by_clu[r["cluster"]].append(r["d"])
print("distinct items carrying a discordance : %d" % len(by_item))
print("distinct clusters carrying one        : %d" % len(by_clu))

hist_i = defaultdict(int)
for k, v in by_item.items():
    hist_i[len(v)] += 1
print("items by #discordant cells:", dict(sorted(hist_i.items())))
hist_c = defaultdict(int)
for k, v in by_clu.items():
    hist_c[len(v)] += 1
print("clusters by #discordant cells:", dict(sorted(hist_c.items())))

# how often do multiple discordances in the same item agree in sign?
same, mixed = 0, 0
for k, v in by_item.items():
    if len(v) > 1:
        if len(set(v)) == 1:
            same += 1
        else:
            mixed += 1
print("multi-discordant items: %d all-same-sign, %d mixed" % (same, mixed))
same, mixed = 0, 0
for k, v in by_clu.items():
    if len(v) > 1:
        if len(set(v)) == 1:
            same += 1
        else:
            mixed += 1
print("multi-discordant clusters: %d all-same-sign, %d mixed" % (same, mixed))


# ---------------------------------------------------- exact sign-flip perm
def exact_signflip(group_sums):
    """Exact two-sided permutation p for S = sum_k eps_k * s_k, eps ~ +-1.

    Under H0 the two arms are exchangeable *within a whole group*, so a group's
    entire discordance vector flips together. Enumerated exactly by DP over the
    attainable sums (all s_k are integers).
    """
    nz = [s for s in group_sums if s != 0]
    zero_groups = len(group_sums) - len(nz)
    dist = {0: Fraction(1)}
    for s in nz:
        nd = defaultdict(Fraction)
        for tot, w in dist.items():
            nd[tot + s] += w * Fraction(1, 2)
            nd[tot - s] += w * Fraction(1, 2)
        dist = dict(nd)
    obs = sum(group_sums)
    p_two = sum(w for t, w in dist.items() if abs(t) >= abs(obs))
    p_ge = sum(w for t, w in dist.items() if t >= obs)
    return {"n_groups_flippable": len(nz), "n_groups_zero_sum": zero_groups,
            "p_two_sided": float(p_two), "p_one_sided_ge": float(p_ge),
            "frac": "%d/%d" % (p_two.numerator, p_two.denominator)}


print("\n=== exact sign-flip permutation, ITEM as unit ===")
item_sums = [sum(v) for v in by_item.values()]
res_i = exact_signflip(item_sums)
print(res_i)

print("\n=== exact sign-flip permutation, CLUSTER as unit ===")
clu_sums = [sum(v) for v in by_clu.values()]
res_c = exact_signflip(clu_sums)
print(res_c)

print("\n=== exact sign-flip permutation, CELL as unit (= exact McNemar) ===")
cell_sums = [r["d"] for r in disc]
res_cell = exact_signflip(cell_sums)
print(res_cell)


# ------------------------------------------- cluster-robust z / design effect
def robust_z(groups):
    """S = sum_k s_k. Var_H0(S) = sum_k s_k^2 if groups flip independently
    (mean 0 under sign symmetry). Compare with the cell-level Var = n_disc."""
    var = sum(s * s for s in groups)
    S = sum(groups)
    z = S / math.sqrt(var) if var > 0 else float("nan")
    return {"S": S, "var": var, "z": z,
            "p_normal": math.erfc(abs(z) / math.sqrt(2.0))}


rz_cell = robust_z(cell_sums)
rz_item = robust_z(item_sums)
rz_clu = robust_z(clu_sums)
print("\ncell-level   ", rz_cell)
print("item-level   ", rz_item)
print("cluster-level", rz_clu)
print("design effect (item/cell var)    = %.4f" % (rz_item["var"] / rz_cell["var"]))
print("design effect (cluster/cell var) = %.4f" % (rz_clu["var"] / rz_cell["var"]))
print("effective n_disc (cluster)       = %.1f" % (len(disc) * rz_cell["var"] / rz_clu["var"]))

json.dump({"S": S_obs, "n_disc": len(disc),
           "n_items_with_disc": len(by_item), "n_clusters_with_disc": len(by_clu),
           "perm_item": res_i, "perm_cluster": res_c, "perm_cell": res_cell,
           "robust_cell": rz_cell, "robust_item": rz_item, "robust_cluster": rz_clu},
          open(P + "ca_ref_01_out.json", "w"), indent=1)

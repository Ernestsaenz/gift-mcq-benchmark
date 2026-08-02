"""Step 7A: the pivotal question for test selection.

McNemar conditions on each cell. Under the SHARP null (the swap changes nothing
for any item), the sign of every discordant pair is an independent fair coin
*even when items are clustered*, because every shared item/cluster effect hits
A and B identically. So McNemar is EXACT under the sharp null despite clustering.

The scientific null is weaker: 'the AVERAGE swap effect over the item population
is zero', allowing the effect to vary item to item. Under that null the signs are
no longer independent and McNemar is anticonservative.

So the whole test-selection decision reduces to one empirical question:
   is there real cluster/item-level HETEROGENEITY in the swap effect?
Tested here by holding the discordance pattern fixed and drawing every discordant
sign i.i.d. with the pooled probability q = b/(b+c), then comparing the observed
cluster-level dispersion of the paired difference with its homogeneous-effect null.
"""
import sys, math, random
from collections import defaultdict
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from stats_lib import *

random.seed(31072026)
rows = load()
for r in rows:
    r["d"] = r["B_correct"] - r["A_correct"]
n = len(rows)
dbar = sum(r["d"] for r in rows) / n
disc = [r for r in rows if r["d"] != 0]
b = sum(1 for r in disc if r["d"] == -1)
c = sum(1 for r in disc if r["d"] == 1)
q = b / (b + c)
print("discordant cells = %d (b=%d A-only, c=%d B-only), q = P(d=-1|discordant) = %.4f"
      % (len(disc), b, c, q))
print("delta_hat = %+.6f" % dbar)

def dispersion(dvals, groups_idx):
    """sum_c u_c^2 with u_c = sum_{i in c}(d_i - dbar). This is n^2 * Var_CR0(dbar)."""
    nn = len(dvals)
    db = sum(dvals) / nn
    tot = 0.0
    for idx in groups_idx:
        s = sum(dvals[i] - db for i in idx)
        tot += s * s
    return tot, db

# index structures
idx_cluster = defaultdict(list)
idx_item = defaultdict(list)
for i, r in enumerate(rows):
    idx_cluster[r["cluster"]].append(i)
    idx_item[r["question_id"]].append(i)
G_CLU = list(idx_cluster.values())
G_ITEM = list(idx_item.values())

dvals = [r["d"] for r in rows]
obs_clu, _ = dispersion(dvals, G_CLU)
obs_item, _ = dispersion(dvals, G_ITEM)
obs_cell, _ = dispersion(dvals, [[i] for i in range(n)])
print("\nobserved sum u_c^2 : cluster %.2f | item %.2f | cell(iid) %.2f"
      % (obs_clu, obs_item, obs_cell))
print("implied SE(delta) : cluster %.5f | item %.5f | cell %.5f"
      % (math.sqrt(obs_clu) / n, math.sqrt(obs_item) / n, math.sqrt(obs_cell) / n))

# ---- homogeneous-effect null: discordance pattern FIXED, signs i.i.d. Bernoulli(q)
NS = 20000
disc_idx = [i for i, r in enumerate(rows) if r["d"] != 0]
base = [0] * n
ge_clu = ge_item = 0
sim_clu = []; sim_item = []
for _ in range(NS):
    dv = base[:]
    for i in disc_idx:
        dv[i] = -1 if random.random() < q else 1
    sc, _ = dispersion(dv, G_CLU)
    si, _ = dispersion(dv, G_ITEM)
    sim_clu.append(sc); sim_item.append(si)
    if sc >= obs_clu: ge_clu += 1
    if si >= obs_item: ge_item += 1
sim_clu.sort(); sim_item.sort()
print("\n--- homogeneous-effect null (%d sims), signs i.i.d. given the discordance pattern ---" % NS)
print("cluster dispersion: observed %.2f ; null mean %.2f ; null 95th pct %.2f ; p = %.5f"
      % (obs_clu, mean(sim_clu), quantile(sim_clu, 0.95), (ge_clu + 1) / (NS + 1)))
print("item    dispersion: observed %.2f ; null mean %.2f ; null 95th pct %.2f ; p = %.5f"
      % (obs_item, mean(sim_item), quantile(sim_item, 0.95), (ge_item + 1) / (NS + 1)))
print("variance inflation actually observed: cluster %.3f ; item %.3f (1.0 = no heterogeneity)"
      % (obs_clu / mean(sim_clu), obs_item / mean(sim_item)))

# ---- where does the heterogeneity live: is it the DISCORDANCE pattern clustering,
#      or the SIGN clustering?  Compare with a null that also re-randomises which
#      cells are discordant, keeping the per-cluster count.
print("\n--- decomposition: how clustered is DISCORDANCE itself? ---")
by_item_disc = defaultdict(int)
for r in rows:
    by_item_disc[r["question_id"]] += (1 if r["d"] != 0 else 0)
from collections import Counter
print("items by number of discordant cells (out of ~4):", dict(sorted(Counter(by_item_disc.values()).items())))
exp_if_indep = len(disc) / n
print("marginal P(cell discordant) = %.4f" % exp_if_indep)
# ICC of the discordance indicator across models within item
def icc_oneway(groups):
    gs = [g for g in groups if g]
    k = len(gs); N = sum(len(g) for g in gs)
    grand = sum(sum(g) for g in gs) / N
    ssb = sum(len(g) * (mean(g) - grand) ** 2 for g in gs)
    ssw = sum(sum((x - mean(g)) ** 2 for x in g) for g in gs)
    msb, msw = ssb / (k - 1), ssw / (N - k)
    n0 = (N - sum(len(g) ** 2 for g in gs) / N) / (k - 1)
    return (msb - msw) / (msb + (n0 - 1) * msw)
gi = defaultdict(list)
for r in rows:
    gi[r["question_id"]].append(1 if r["d"] != 0 else 0)
print("ICC of the DISCORDANCE indicator within item (across models) = %.4f" % icc_oneway(list(gi.values())))
# sign clustering among discordant cells only
gs = defaultdict(list)
for r in disc:
    gs[r["question_id"]].append(1 if r["d"] == -1 else 0)
multi_sign = [v for v in gs.values() if len(v) > 1]
print("items with >=2 discordant cells: %d" % len(multi_sign))
print("ICC of the SIGN among discordant cells within item = %.4f" % icc_oneway(multi_sign))
agree = sum(1 for v in multi_sign for i in range(len(v)) for j in range(i + 1, len(v)) if v[i] == v[j])
tot = sum(len(v) * (len(v) - 1) // 2 for v in multi_sign)
print("within-item discordant sign agreement: %d/%d = %.4f (chance given q: %.4f)"
      % (agree, tot, agree / tot, q * q + (1 - q) ** 2))

print("\n=== CONCLUSION OF 7A ===")
print("If the cluster p-value above is small, the swap effect is genuinely")
print("heterogeneous across items/clusters, the iid-cell SE understates Var(delta_hat),")
print("and McNemar's CI (though not its sharp-null p-value) is invalid.")

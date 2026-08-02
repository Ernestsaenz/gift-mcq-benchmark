#!/usr/bin/env python3
"""
sens_loo_detail.py -- follow-ups to sens_leave_one_out.py:
  * distribution of item-level net contributions (is the "top 10" a real tail or a tie?)
  * adversarial deletion / fragility index (how many units must be removed to kill the effect)
  * per-model share of the total signal
  * cluster-size vs influence
Stdlib only.
"""
import json, collections, math, random

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
RECS = json.load(open(PATH))
cells = [r for r in RECS if r["analysis_include"]]
N = len(cells)
S = sum(c["B_correct"] - c["A_correct"] for c in cells)
D0 = 100.0 * S / N
print(f"analysis set: N={N} cells, net={S}, pooled delta={D0:+.4f} pp")

# ---- item net distribution
item_net = collections.defaultdict(int); item_n = collections.Counter()
for c in cells:
    item_net[c["question_id"]] += c["B_correct"] - c["A_correct"]
    item_n[c["question_id"]] += 1
dist = collections.Counter(item_net.values())
print("\nitem-level net (B-A summed over that item's 3-4 model cells):")
for k in sorted(dist, reverse=True):
    print(f"  net={k:+d}: {dist[k]:>4} items")
print(f"  items strictly pro-A (net<0): {sum(v for k,v in dist.items() if k<0)}")
print(f"  items strictly pro-B (net>0): {sum(v for k,v in dist.items() if k>0)}")
print(f"  items tied      (net=0): {dist[0]}")

# is the "top 10" a genuine tail?
mx = max(abs(k) for k in item_net.values())
n_at_mx = sum(1 for v in item_net.values() if abs(v) == mx)
n_at_mx_minus1 = sum(1 for v in item_net.values() if abs(v) == mx - 1)
print(f"\nmaximum attainable |net| for a 4-cell item = 4; observed max |net| = {mx}")
print(f"items at |net|={mx}: {n_at_mx}   items at |net|={mx-1}: {n_at_mx_minus1}")
print(f"-> the 'top 10 influential items' is a slice of a {n_at_mx}-way tie at |net|=4 "
      f"(+{n_at_mx_minus1} at |net|=3); the ranking beyond |net| is arbitrary.")
print(f"upper bound on ANY single item's influence: "
      f"|delta_wo - delta| <= {abs(100.0*(S-(-4))/(N-4) - D0):.4f} pp "
      f"(a 4-cell item that is maximally against the pooled sign)")

# ---- per-model share
print("\nper-model share of the total net signal:")
mnet = collections.Counter(); mn = collections.Counter()
for c in cells:
    mnet[c["model"]] += c["B_correct"] - c["A_correct"]; mn[c["model"]] += 1
for m in sorted(mnet):
    print(f"  {m:>26}  net={mnet[m]:>+5}  ({100.0*mnet[m]/S:5.1f}% of total net)  "
          f"own delta={100.0*mnet[m]/mn[m]:+7.3f} pp")

# ---- fragility index: adversarial deletion
def frag(unit_key, label, target=0.0):
    net = collections.defaultdict(int); cnt = collections.Counter()
    for c in cells:
        k = unit_key(c); net[k] += c["B_correct"] - c["A_correct"]; cnt[k] += 1
    # delete units that are most "pro-A" first (most negative net) to push delta toward 0
    order = sorted(net, key=lambda k: net[k])
    s, n = S, N; steps = 0
    for k in order:
        if 100.0 * s / n >= target: break
        s -= net[k]; n -= cnt[k]; steps += 1
    tot = len(net)
    print(f"  {label}: must adversarially delete {steps}/{tot} ({100.0*steps/tot:.1f}%) "
          f"most-anti-B units to bring the pooled delta to >= {target:+.1f} pp "
          f"(remaining n={n} cells, delta={100.0*s/n:+.3f})")
    return steps, tot

print("\nfragility index (adversarial, worst-case deletion order):")
frag(lambda c: c["question_id"], "items ", 0.0)
frag(lambda c: c["cluster"],     "cluster", 0.0)
frag(lambda c: c["question_id"], "items ", -5.0)
frag(lambda c: c["cluster"],     "cluster", -5.0)

# ---- cluster size vs influence
print("\ncluster structure:")
csz = collections.Counter(c["cluster"] for c in cells)
szdist = collections.Counter(csz.values())
print(f"  cluster sizes (cells): {dict(sorted(szdist.items()))}")
singletons = sum(1 for k, v in csz.items() if v <= 4)
print(f"  clusters of <=4 cells (i.e. single item): {singletons}/{len(csz)}")
cnet = collections.defaultdict(int)
for c in cells: cnet[c["cluster"]] += c["B_correct"] - c["A_correct"]
neg = sum(1 for v in cnet.values() if v < 0); pos = sum(1 for v in cnet.values() if v > 0)
zer = sum(1 for v in cnet.values() if v == 0)
print(f"  clusters with net<0 (pro-A): {neg}   net>0 (pro-B): {pos}   net=0: {zer}")

# ---- fraction of clusters/items reproducing the sign, and a cluster-level sign test
k_neg, k_pos = neg, pos
# exact two-sided binomial on the non-tied clusters
def binom_p(k, n, p=0.5):
    tot = 0.0
    from math import comb
    pk = comb(n, k) * p**n
    for i in range(n + 1):
        pi = comb(n, i) * p**n
        if pi <= pk * (1 + 1e-9): tot += pi
    return tot
print(f"  exact two-sided binomial sign test on non-tied clusters "
      f"({k_neg} negative / {k_neg+k_pos}): p = {binom_p(k_pos, k_neg+k_pos):.3e}")

# item-level sign test
i_neg = sum(1 for v in item_net.values() if v < 0); i_pos = sum(1 for v in item_net.values() if v > 0)
print(f"  exact two-sided binomial sign test on non-tied items "
      f"({i_neg} negative / {i_neg+i_pos}): p = {binom_p(i_pos, i_neg+i_pos):.3e}")

# ---- what do the unanimous pro-A items look like vs unanimous pro-B?
meta = {}
for c in cells: meta[c["question_id"]] = c
def prof(ids, label):
    n = len(ids)
    if n == 0: return
    L = collections.Counter(meta[i]["correct_letter"] for i in ids)
    neg_ = sum(1 for i in ids if meta[i]["negated_stem"])
    ctx = sum(1 for i in ids if meta[i]["has_context"])
    ql = sorted(meta[i]["qlen"] for i in ids)
    print(f"  {label:<28} n={n:<4} letters={dict(sorted(L.items()))} "
          f"neg_stem={100.0*neg_/n:.0f}% has_ctx={100.0*ctx/n:.0f}% median_qlen={ql[n//2]}")
allids = list(item_net)
prof([i for i in allids if item_net[i] <= -3], "unanimous/near-unan. pro-A")
prof([i for i in allids if item_net[i] >= +3], "unanimous/near-unan. pro-B")
prof([i for i in allids if item_net[i] == 0],  "tied items")
prof(allids, "ALL items")

# ---- top-10 by |net| with ties broken by nothing: list every |net|=4 item
top4 = sorted([i for i in allids if abs(item_net[i]) == 4], key=lambda i: (item_net[i], i))
print(f"\nall {len(top4)} items at the influence ceiling (|net|=4), "
      f"i.e. all 4 models flipped the same way:")
print("   " + ", ".join(f"{i}({item_net[i]:+d})" for i in top4))

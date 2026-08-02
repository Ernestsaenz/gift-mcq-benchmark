"""How much independent information is in "160 specifications"?

Three questions:
  (1) How redundant are the 8 datasets (exclusion x outcome)?
  (2) Is 'median p = 9.05e-13' a property of the data or of B=10000?
  (3) How much of the 1e-53 .. 1e-2 p-value span is just "which level of the
      hierarchy did you pretend was independent"?
"""
import json, os, sys, math, random, collections, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sens_refute_curvep_lib as L

rows = json.load(open(os.path.join(HERE, "paired_clean.json")))
MINE = json.load(open(os.path.join(HERE, "sens_refute_curvep_out.json")))
res = MINE["results"]
MODELS = sorted(set(r["model"] for r in rows))

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


print("=" * 92)
print("(1) HOW MANY GENUINELY DIFFERENT DATASETS ARE BEHIND '160 SPECIFICATIONS'?")
print("=" * 92)
print("\n  the OUTCOME axis (lenient vs strict) changes exactly ONE cell:")
for ex in EXCL:
    a = subset(ex, "lenient"); b = subset(ex, "strict")
    da = 100.0 * sum(r["B_correct"] - r["A_correct"] for r in a) / len(a)
    db = 100.0 * sum(r["B_correct"] - r["A_correct"] for r in b) / len(b)
    print(f"    {ex:<12} N {len(a):>5} -> {len(b):>5} (+{len(b)-len(a)} cell, "
          f"{100*(len(b)-len(a))/len(a):.3f}% of data)   delta {da:+.4f} -> {db:+.4f} "
          f"(shift {abs(db-da):.4f} pp)")
print("    -> this axis doubles 80 specs to 160 for a one-cell (0.06-0.08%) change.")

print("\n  the EXCLUSION axis is a nested chain, not four independent choices:")
sets = {ex: set((r["question_id"], r["model"]) for r in subset(ex, "lenient")) for ex in EXCL}
order = ["primary", "notaA_only", "defect_only", "none"]
for a in order:
    line = []
    for b in order:
        ov = len(sets[a] & sets[b]) / len(sets[a] | sets[b])
        line.append(f"{ov:.3f}")
    print(f"    {a:<12} Jaccard vs [{'  '.join(f'{o[:9]:<9}' for o in order)}] = {'  '.join(line)}")
print(f"    primary subset of all others: "
      f"{all(sets['primary'] <= sets[o] for o in order)}")
print(f"    smallest pairwise Jaccard among the 4 exclusion sets: "
      f"{min(len(sets[a]&sets[b])/len(sets[a]|sets[b]) for a in order for b in order if a!=b):.3f}")
print("    -> every dataset shares >=76% of its cells with every other one.")

print("\n  distinct p-values among the 160 specs:")
ps = [r["p"] for r in res]
print(f"    distinct to 1e-15 : {len({round(p,15) for p in ps})}/160")
cnt = collections.Counter(round(p, 15) for p in ps)
for v, c in cnt.most_common(4):
    print(f"      p={v:.6e} appears {c} times")

print("\n" + "=" * 92)
print("(2) IS 'median p = 9.05e-13' A PROPERTY OF THE DATA, OR OF B?")
print("=" * 92)
nf = sum(1 for r in res if r["floored"])
print(f"  specs whose p is a resampling resolution floor: {nf}/160 ({100*nf/160:.1f}%)")
FISH = lambda B: L.fisher_combine([1.0/(B+1.0)]*4)[0]
print("\n  If B changes, these floored p change by construction (data untouched):")
print(f"    {'B':>9}  {'1/(B+1)':>12}  {'Fisher of 4 floors':>20}  {'-> reported median p':>22}")
for B in (100, 1000, 10000, 100000, 1000000):
    print(f"    {B:>9}  {1.0/(B+1):>12.4e}  {FISH(B):>20.4e}  {FISH(B):>22.4e}")
print(f"\n  reported median p (mine)      : {st.median(ps):.4e}")
print(f"  Fisher-of-4-floors at B=10000 : {FISH(10000):.4e}")
print(f"  identical: {abs(st.median(ps)-FISH(10000)) < 1e-18}")
print("  -> the headline median is a deterministic function of the resampling budget.")
print("     At B=1000 the same data would report 'median p = 3.9e-09';")
print("     at B=1e6 it would report 'median p = 2.97e-20'.  Nothing about the")
print("     experiment changed.")

# does the weakest floored bootstrap survive a 20x larger B?
print("\n  sanity: do the floors survive a 20x larger B?  (weakest per-model cell,")
print("  gemini-3.6-flash, primary/lenient, cluster bootstrap, B=200000)")
recs = subset("primary", "lenient")
bycl = collections.defaultdict(list)
for r in recs:
    if r["model"] == "google/gemini-3.6-flash":
        bycl[r["cluster"]].append(r)
keys = sorted(bycl)
agg = [(sum(x["B_correct"] - x["A_correct"] for x in bycl[k]), len(bycl[k])) for k in keys]
K = len(keys)
rng = random.Random(31337)
cross = 0
B = 200000
for _ in range(B):
    s = n = 0
    for _ in range(K):
        a, b = agg[rng.randrange(K)]
        s += a; n += b
    if s >= 0:
        cross += 1
print(f"    K={K}, resamples with mean >= 0: {cross}/{B}  -> raw p = {2*cross/B:.3e}, "
      f"still floored at 1/(B+1) = {1/(B+1):.3e}")
print("    -> the floor is not a near-miss; the p is simply BELOW the grid resolution")
print("       at every B, so its printed magnitude is pure bookkeeping.")

print("\n" + "=" * 92)
print("(3) THE p-VALUE SPAN IS THE HIERARCHY LEVEL, NOT THE EVIDENCE")
print("=" * 92)
print("  primary/lenient -- the SAME 1299 paired cells, same point estimate -15.55 pp:")
sel = [r for r in res if r["exclusion"] == "primary" and r["outcome"] == "lenient"]
for r in sorted(sel, key=lambda r: r["log10p"]):
    lbl = f"{r['unit']}/{r['inference']}/{r['pooling']}"
    fl = " [FLOORED]" if r["floored"] else ""
    print(f"    {lbl:<42} G/n={r['G']:<6} p=10^{r['log10p']:+8.2f}{fl}")
print("\n  the 32-order-of-magnitude spread is entirely 'what did you call independent':")
print("    1691 cells as iid Bernoulli        -> 1e-35")
print("    208 clusters                       -> 1e-13")
print("    4 models                           -> 1e-02")
print("  averaging p-values across those levels (the 'median p') has no interpretation.")

b = sum(1 for r in recs if r["A_correct"] == 1 and r["B_correct"] == 0)
c = sum(1 for r in recs if r["A_correct"] == 0 and r["B_correct"] == 1)
print(f"\n  the min-p spec (pooled exact McNemar) uses b={b}, c={c}, n_disc={b+c}")
print(f"    -> it treats 4 responses per item and ~6 items per cluster as {b+c}")
print(f"       independent coin flips.  Design effect ignored entirely.")

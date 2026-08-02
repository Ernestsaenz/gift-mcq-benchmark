import sys, collections, math, random
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_ref_nota2_lib import *

d = load()
models = sorted({r["model"] for r in d})
by_item = collections.defaultdict(list)
for r in d:
    by_item[r["question_id"]].append(r)

def strata_for(letter_of, with_model=True):
    """letter_of(item_rows) -> letter to test. exposure = A_selected==letter,
    outcome = B_selected==letter."""
    out = []
    for q, rs in by_item.items():
        lt = letter_of(rs)
        X, y = [], []
        for r in rs:
            v = [1.0 if r["A_selected"] == lt else 0.0]
            if with_model:
                v += [1.0 if r["model"] == m else 0.0 for m in models[1:]]
            X.append(v); y.append(1 if r["B_selected"] == lt else 0)
        out.append((X, y))
    return out

print("=== SAME ESTIMATOR, SAME ADJUSTMENT, applied to the real letter and to null letters ===")
print("    conditional logit; strata = question_id; + model fixed effects")
print(f"{'letter tested':42s} {'OR':>7s} {'SE':>7s} {'z':>7s} {'p':>10s} {'strata':>7s}")

res = clogit(strata_for(lambda rs: rs[0]["correct_letter"], True))
print(f"{'L = correct/NOTA slot (TEXT REPLACED)':42s} {math.exp(res['beta'][0]):7.3f} {res['se'][0]:7.3f} "
      f"{res['z'][0]:7.2f} {res['p'][0]:10.3g} {res['n_strata']:7d}")
real_or = math.exp(res["beta"][0])

placebo_ors = []
for k in range(3):
    def pick(rs, k=k):
        L = rs[0]["correct_letter"]
        return [x for x in "abcd" if x != L][k]
    rp = clogit(strata_for(pick, True))
    if rp:
        placebo_ors.append(math.exp(rp["beta"][0]))
        print(f"{'PLACEBO distractor #'+str(k+1)+' (TEXT IDENTICAL)':42s} {math.exp(rp['beta'][0]):7.3f} "
              f"{rp['se'][0]:7.3f} {rp['z'][0]:7.2f} {rp['p'][0]:10.3g} {rp['n_strata']:7d}")
print(f"\n  -> null transformation ORs {['%.2f'%x for x in placebo_ors]} vs 'knowledge' OR {real_or:.2f}")
print("     the effect advertised as knowledge is SMALLER than pure choice reproducibility")

# ---------------------------------------------------------------
# cluster bootstrap (208 paraphrase clusters) on MH OR and adjusted OR
# ---------------------------------------------------------------
print("\n=== cluster bootstrap over the 208 paraphrase clusters (2000 resamples) ===")
by_cluster = collections.defaultdict(list)
for q, rs in by_item.items():
    by_cluster[rs[0]["cluster"]].append(rs)
clus = list(by_cluster.values())
random.seed(20260731)

def mh_from_items(items):
    tabs = []
    for rs in items:
        a = sum(1 for r in rs if r["A_correct"] and r["B_correct"])
        b = sum(1 for r in rs if r["A_correct"] and not r["B_correct"])
        c = sum(1 for r in rs if not r["A_correct"] and r["B_correct"])
        e = sum(1 for r in rs if not r["A_correct"] and not r["B_correct"])
        tabs.append((a, b, c, e))
    m = mantel_haenszel(tabs)
    return m["or_mh"] if m else None

allitems = [rs for c in clus for rs in c]
pt = mh_from_items(allitems)
boot = []
for _ in range(2000):
    samp = [rs for _ in clus for rs in random.choice(clus)]
    v = mh_from_items(samp)
    if v and v == v and v != float("inf"):
        boot.append(v)
boot.sort()
lo, hi = boot[int(.025 * len(boot))], boot[int(.975 * len(boot))]
print(f"  MH OR point = {pt:.2f}   cluster-bootstrap 95% percentile CI = [{lo:.2f}, {hi:.2f}]  (n_ok={len(boot)})")
print(f"  claim's RBG CI (strata assumed independent)  = [3.17, 10.14]")

# ---------------------------------------------------------------
# fragility of the four within-model Fisher tests
# ---------------------------------------------------------------
print("\n=== fragility of the per-model tests: the A-wrong cell counts ===")
for m in models:
    s = [r for r in d if r["model"] == m]
    aw = [r for r in s if not r["A_correct"]]
    k = sum(r["B_correct"] for r in aw)
    a = sum(1 for r in s if r["A_correct"] and r["B_correct"])
    b = sum(1 for r in s if r["A_correct"] and not r["B_correct"])
    # flip one A-wrong cell from B-correct to B-wrong and back
    ps = []
    for delta in (-1, 0, 1):
        kk = k + delta
        if 0 <= kk <= len(aw):
            ps.append(fisher_exact_two_sided(a, b, kk, len(aw) - kk))
    print(f"  {m:28s} A-wrong n={len(aw):3d}  B-correct among them={k:3d}   "
          f"p range if ONE cell flips: {min(ps):.4g} .. {max(ps):.4g}")

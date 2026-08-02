#!/usr/bin/env python3
"""
sens_refute_exclusion_grid.py -- INDEPENDENT recomputation of the exclusion-grid
robustness claim.  Written from the data + dataset_meta.json only; does not import
sens_exclusion_grid.py.

Checks
  C1  flag integrity: does excl_item_defect reproduce the question_id list in
      dataset_meta.json?  does excl_nota_position_a == (correct_letter=='a')?
      is analysis_include EXACTLY  not(defect) and not(posA)?
  C2  composition of the four grid sets (items / cells / clusters)
  C3  pooled + per-model accA, accB, delta  (exact rational arithmetic where possible)
  C4  cluster bootstrap 95% percentile CI, 20000 reps, THREE independent seeds
  C5  cluster sign-flip permutation p, 20000 reps + exact-enumeration lower bound
  C6  cluster structure sanity (are clusters real? singleton fraction? does
      has_context leak into the cluster id?)
"""

import json, os, math, random
from collections import defaultdict, Counter
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "paired_clean.json")))
meta = json.load(open(os.path.join(HERE, "dataset_meta.json")))

SEEDS = [11, 4242, 987654321]
R = 20000

print("=" * 100)
print("C0  raw shape")
print("=" * 100)
print("records                :", len(rows))
models = sorted(set(r["model"] for r in rows))
print("models                 :", len(models), models)
items = sorted(set(r["question_id"] for r in rows))
print("distinct question_id   :", len(items))
print("clusters (all)         :", len(set(r["cluster"] for r in rows)))
bad = [r for r in rows if r["A_correct"] not in (0, 1) or r["B_correct"] not in (0, 1)]
print("non-binary A/B_correct :", len(bad))
# cells per item
percell = Counter(r["question_id"] for r in rows)
print("items with !=4 cells   :", {k: v for k, v in percell.items() if v != 4})
# is (item,model) unique?
dup = Counter((r["question_id"], r["model"]) for r in rows)
print("duplicate (item,model) :", sum(1 for v in dup.values() if v > 1))
# is cluster a function of item?
i2c = defaultdict(set)
for r in rows:
    i2c[r["question_id"]].add(r["cluster"])
print("items w/ >1 cluster id :", sum(1 for v in i2c.values() if len(v) > 1))

print()
print("=" * 100)
print("C1  flag integrity")
print("=" * 100)
meta_defect = set(meta["exclusions"]["administrative_legal_out_of_domain"]) | set(
    meta["exclusions"]["adjudicated_key_defect"])
flagged_defect = set(r["question_id"] for r in rows if r["excl_item_defect"])
print("meta lists            :", len(meta_defect), "question_ids")
print("flagged in data       :", len(flagged_defect), "question_ids")
print("meta-listed but ABSENT from paired data :", sorted(meta_defect - set(items)))
print("flagged but NOT in meta list            :", sorted(flagged_defect - meta_defect))
print("meta-listed, present in data, NOT flagged:",
      sorted((meta_defect & set(items)) - flagged_defect))
print("-> defect flag == meta list restricted to present items :",
      flagged_defect == (meta_defect & set(items)))

mismatch_p = [r["question_id"] for r in rows
              if r["excl_nota_position_a"] != (r["correct_letter"] == "a")]
print("rows where excl_nota_position_a != (correct_letter=='a') :", len(mismatch_p))
n_posA_items = len(set(r["question_id"] for r in rows if r["excl_nota_position_a"]))
print("items with excl_nota_position_a          :", n_posA_items,
      "(meta claims %s)" % meta["exclusions"]["nota_position_a_incoherent"]["n_items"])

mismatch_inc = [r for r in rows
                if r["analysis_include"] != (not r["excl_item_defect"] and not r["excl_nota_position_a"])]
print("rows where analysis_include != not(D) and not(P) :", len(mismatch_inc))
overlap = set(r["question_id"] for r in rows if r["excl_item_defect"] and r["excl_nota_position_a"])
print("items flagged by BOTH rules              :", len(overlap), sorted(overlap))

print()
print("=" * 100)
print("C6  cluster structure")
print("=" * 100)
csize_items = Counter()
for it, cs in i2c.items():
    csize_items[list(cs)[0]] += 1
sizes = Counter(csize_items.values())
print("cluster size (items per cluster) histogram:", dict(sorted(sizes.items())))
print("singleton clusters:", sizes.get(1, 0), "of", len(csize_items))
# does has_context vary within cluster / is it confounded with singletons?
ctx = defaultdict(set)
for r in rows:
    ctx[r["cluster"]].add(r["has_context"])
print("clusters with mixed has_context:", sum(1 for v in ctx.values() if len(v) > 1))
sing = [c for c, n in csize_items.items() if n == 1]
print("has_context among singleton clusters:", Counter(list(ctx[c])[0] for c in sing))
print("has_context among multi   clusters:",
      Counter(list(ctx[c])[0] for c in csize_items if csize_items[c] > 1 and len(ctx[c]) == 1))

# ------------------------------------------------------------------ grid
SETS = [
    ("S1_none",        lambda r: True),
    ("S2_drop_defect", lambda r: not r["excl_item_defect"]),
    ("S3_drop_posA",   lambda r: not r["excl_nota_position_a"]),
    ("S4_published",   lambda r: r["analysis_include"]),
]


def compose(sub):
    return (len(set(r["question_id"] for r in sub)), len(sub),
            len(set(r["cluster"] for r in sub)))


def stats(sub, model=None):
    n = sa = sb = 0
    for r in sub:
        if model is not None and r["model"] != model:
            continue
        n += 1
        sa += r["A_correct"]
        sb += r["B_correct"]
    return n, sa, sb


def cluster_pairs(sub, model=None):
    """cluster -> (n, sumA, sumB)"""
    t = defaultdict(lambda: [0, 0, 0])
    for r in sub:
        if model is not None and r["model"] != model:
            continue
        v = t[r["cluster"]]
        v[0] += 1
        v[1] += r["A_correct"]
        v[2] += r["B_correct"]
    return t


def boot_ci(t, seed, reps=R):
    keys = list(t.keys())
    arr = [tuple(t[k]) for k in keys]
    C = len(arr)
    rng = random.Random(seed)
    rr = rng.randrange
    out = []
    for _ in range(reps):
        n = sa = sb = 0
        for _ in range(C):
            x = arr[rr(C)]
            n += x[0]; sa += x[1]; sb += x[2]
        out.append((sb - sa) / n if n else 0.0)
    out.sort()

    def q(p):
        i = p * (len(out) - 1)
        lo, hi = math.floor(i), math.ceil(i)
        return out[lo] if lo == hi else out[lo] + (out[hi] - out[lo]) * (i - lo)
    mean = sum(out) / len(out)
    se = (sum((x - mean) ** 2 for x in out) / (len(out) - 1)) ** 0.5
    return q(0.025), q(0.975), se


def signflip_p(t, obs, seed, reps=R):
    d = [v[2] - v[1] for v in t.values()]
    N = sum(v[0] for v in t.values())
    nz = [x for x in d if x != 0]
    rng = random.Random(seed)
    ao = abs(obs) * N - 1e-9
    hit = 0
    gb = rng.getrandbits
    for _ in range(reps):
        s = 0
        for x in nz:
            s += x if gb(1) else -x
        if abs(s) >= ao:
            hit += 1
    # exact lower bound on attainable p: all-same-sign configurations
    exact_floor = 2.0 / (2 ** len(nz)) if len(nz) < 60 else 0.0
    return (hit + 1) / (reps + 1), len(nz), sum(d), N, exact_floor


print()
print("=" * 100)
print("C2/C3  composition + point estimates")
print("=" * 100)
print(f"{'set':<16} {'items':>6} {'cells':>6} {'clus':>5} {'accA':>8} {'accB':>8} {'delta':>9}  exact delta")
res = {}
for sid, filt in SETS:
    sub = [r for r in rows if filt(r)]
    ni, nc, ncl = compose(sub)
    n, sa, sb = stats(sub)
    delta = (sb - sa) / n
    res[sid] = dict(items=ni, cells=nc, clusters=ncl, n=n, sa=sa, sb=sb,
                    accA=sa / n, accB=sb / n, delta=delta, sub=sub)
    print(f"{sid:<16} {ni:>6} {nc:>6} {ncl:>5} {sa/n:>8.4f} {sb/n:>8.4f} {delta:>+9.4f}  "
          f"({sb}-{sa})/{n} = {Fraction(sb-sa,n)}")

print()
print("=" * 100)
print("C4/C5  cluster bootstrap CI (3 seeds x 20000) + sign-flip permutation p")
print("=" * 100)
for sid, filt in SETS:
    e = res[sid]
    t = cluster_pairs(e["sub"])
    line = f"{sid:<16} delta={e['delta']:+.4f}"
    print(line)
    for s in SEEDS:
        lo, hi, se = boot_ci(t, s)
        print(f"    seed={s:<11} 95% CI [{lo:+.4f}, {hi:+.4f}]  se={se:.5f}")
    p, nnz, tot, N, floor = signflip_p(t, e["delta"], 777)
    print(f"    sign-flip: nonzero clusters={nnz}  sum(B-A)={tot}  N={N}  "
          f"p={p:.6f}  min attainable p (R=20000)={1/(R+1):.6f}  exact 2/2^k floor={floor:.3e}")
    e["ci"] = (lo, hi)

print()
print("=" * 100)
print("HEADLINE: pooled delta range")
print("=" * 100)
ds = [res[s]["delta"] for s, _ in SETS]
print("deltas :", [f"{d:+.4f}" for d in ds])
print(f"range  : [{min(ds):+.4f}, {max(ds):+.4f}]  span={max(ds)-min(ds):.4f} "
      f"({100*(max(ds)-min(ds)):.2f} pts)")

# per-model accuracies for the published set, as a cross-check on the quoted accs
print()
print("=" * 100)
print("per-model (published set)")
print("=" * 100)
for m in models:
    n, sa, sb = stats(res["S4_published"]["sub"], m)
    print(f"  {m:<28} n={n:>4} accA={sa/n:.4f} accB={sb/n:.4f} delta={(sb-sa)/n:+.4f}")

"""REFUTATION pass on error-destination claim (a): item-level concentration.

Independent recomputation + proper nulls. Stdlib only.
"""
import json, collections, random, math

PAIRED = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
LET = ["a", "b", "c", "d"]

cells = [r for r in json.load(open(PAIRED)) if r["analysis_include"]]
models = sorted(set(c["model"] for c in cells))

print("=" * 78)
print("0. SANITY")
print("=" * 78)
print("cells", len(cells), "items", len(set(c["question_id"] for c in cells)))
print("null selections:", sum(1 for c in cells if not c["A_selected"]),
      sum(1 for c in cells if not c["B_selected"]))
print("selected letter outside abcd:",
      sum(1 for c in cells if c["A_selected"] not in LET or c["B_selected"] not in LET))
print("B scored wrong but selected correct_letter:",
      sum(1 for c in cells if c["B_correct"] == 0 and c["B_selected"] == c["correct_letter"]))
print("B scored right but selected != correct_letter:",
      sum(1 for c in cells if c["B_correct"] == 1 and c["B_selected"] != c["correct_letter"]))
print("correct_letter == 'a' anywhere:",
      sum(1 for c in cells if c["correct_letter"] == "a"))
# per-item correct_letter must be constant
byq = collections.defaultdict(set)
for c in cells:
    byq[c["question_id"]].add(c["correct_letter"])
print("items with inconsistent correct_letter:", sum(1 for v in byq.values() if len(v) > 1))


def agree_stats(sel_by_item):
    same = tot = 0
    dk = collections.Counter()
    unan = collections.Counter()
    unan_tot = collections.Counter()
    for q, sel in sel_by_item.items():
        k = len(sel)
        dk[k] += 1
        cnt = collections.Counter(sel)
        same += sum(v * (v - 1) // 2 for v in cnt.values())
        tot += k * (k - 1) // 2
        if k >= 2:
            unan_tot[k] += 1
            if len(cnt) == 1:
                unan[k] += 1
    return same, tot, dk, unan, unan_tot


def build(cond):
    d = collections.defaultdict(list)
    for c in cells:
        if not c[cond + "_correct"]:
            d[c["question_id"]].append((c["model"], c[cond + "_selected"]))
    return d


print()
print("=" * 78)
print("1. RECOMPUTE THE CLAIM (B errors)")
print("=" * 78)
B = build("B")
selB = {q: [s for _, s in v] for q, v in B.items()}
same, tot, dk, unan, unan_tot = agree_stats(selB)
print("items with >=1 B error:", len(B), " #erring models:", dict(sorted(dk.items())))
print(f"within-item pairwise agreement: {same}/{tot} = {same/tot:.4f}")
for k in sorted(unan_tot):
    print(f"  unanimity k={k}: {unan[k]}/{unan_tot[k]} = {unan[k]/unan_tot[k]:.3f}"
          f"   naive chance (1/3)^(k-1) = {(1/3)**(k-1):.3f}")

print()
print("Same for A errors (baseline: is this specific to the NOTA manipulation?)")
A = build("A")
selA = {q: [s for _, s in v] for q, v in A.items()}
sameA, totA, dkA, unanA, unanA_tot = agree_stats(selA)
print("items with >=1 A error:", len(A), " #erring models:", dict(sorted(dkA.items())))
print(f"within-item pairwise agreement: {sameA}/{totA} = {sameA/totA:.4f}")
for k in sorted(unanA_tot):
    print(f"  unanimity k={k}: {unanA[k]}/{unanA_tot[k]} = {unanA[k]/unanA_tot[k]:.3f}")

print()
print("=" * 78)
print("2. NULL A: independent draws from each MODEL's own letter marginal,")
print("   renormalised to the item's 3-survivor set. Preserves marginal bias,")
print("   destroys item identity. (analytic + permutation)")
print("=" * 78)
# model x letter marginal among that model's B errors
marg = collections.defaultdict(collections.Counter)
for c in cells:
    if not c["B_correct"]:
        marg[c["model"]][c["B_selected"]] += 1
for m in models:
    n = sum(marg[m].values())
    print(f"  {m:28s} n={n:4d} " + " ".join(f"{L}={marg[m][L]/n:.3f}" for L in LET))

# analytic expected agreement under Null A
exp_same = 0.0
for q, v in B.items():
    cl = byq[q].copy().pop()
    surv = [L for L in LET if L != cl]
    probs = []
    for m, _ in v:
        w = [marg[m][L] for L in surv]
        s = sum(w)
        probs.append([x / s for x in w])
    for i in range(len(probs)):
        for j in range(i + 1, len(probs)):
            exp_same += sum(probs[i][t] * probs[j][t] for t in range(3))
print(f"expected same-pairs under Null A = {exp_same:.2f}/{tot} = {exp_same/tot:.4f}"
      f"   (observed {same/tot:.4f})")

print()
print("=" * 78)
print("3. NULL B: within-model, within-stratum(correct_letter) SHUFFLE of")
print("   destinations across items. Exactly preserves each model's letter counts")
print("   and every item's erring-model set; destroys item identity only.")
print("=" * 78)
rng = random.Random(20260731)


def perm_test(cond, nperm=20000):
    d = build(cond)
    obs_same, obs_tot, _, uo, ut = agree_stats({q: [s for _, s in v] for q, v in d.items()})
    # pool: (model, correct_letter) -> list of destinations ; and slots
    slots = []
    pool = collections.defaultdict(list)
    for q, v in d.items():
        cl = byq[q].copy().pop()
        for m, s in v:
            slots.append((q, m, cl))
            pool[(m, cl)].append(s)
    ge = 0
    dist = []
    unan_ge = collections.Counter()
    for _ in range(nperm):
        p2 = {k: vv[:] for k, vv in pool.items()}
        for k in p2:
            rng.shuffle(p2[k])
        idx = collections.Counter()
        sim = collections.defaultdict(list)
        for (q, m, cl) in slots:
            key = (m, cl)
            sim[q].append(p2[key][idx[key]])
            idx[key] += 1
        s2, t2, _, u2, _ = agree_stats(sim)
        dist.append(s2 / t2)
        if s2 >= obs_same:
            ge += 1
        for k in ut:
            if u2[k] >= uo[k]:
                unan_ge[k] += 1
    mu = sum(dist) / len(dist)
    sd = math.sqrt(sum((x - mu) ** 2 for x in dist) / len(dist))
    print(f"[{cond}] observed agreement {obs_same}/{obs_tot} = {obs_same/obs_tot:.4f}")
    print(f"[{cond}] null mean {mu:.4f}  sd {sd:.4f}  "
          f"z={(obs_same/obs_tot-mu)/sd:.2f}  "
          f"permutation p (one-sided, {nperm} shuffles) = {(ge+1)/(nperm+1):.2e}")
    for k in sorted(ut):
        print(f"    unanimity k={k}: obs {uo[k]}/{ut[k]}  perm p = {(unan_ge[k]+1)/(nperm+1):.4f}")
    return mu, sd


perm_test("B")
print()
perm_test("A")

print()
print("=" * 78)
print("4. IS THE CONCENTRATION SPECIFIC TO B?  Restrict to 'induced' errors:")
print("   both models of the pair were CORRECT in A on that item.")
print("=" * 78)
# pairwise breakdown by whether each member's A was correct
Acorr = {(c["question_id"], c["model"]): c["A_correct"] for c in cells}
buckets = collections.Counter()
bsame = collections.Counter()
for q, v in B.items():
    for i in range(len(v)):
        for j in range(i + 1, len(v)):
            (m1, s1), (m2, s2) = v[i], v[j]
            a1, a2 = Acorr[(q, m1)], Acorr[(q, m2)]
            key = ("both A-correct" if a1 and a2 else
                   "one A-wrong" if a1 or a2 else "both A-wrong")
            buckets[key] += 1
            if s1 == s2:
                bsame[key] += 1
for k in ["both A-correct", "one A-wrong", "both A-wrong"]:
    n = buckets[k]
    if n:
        print(f"  {k:16s} pairs={n:4d}  agree={bsame[k]:4d}  = {bsame[k]/n:.4f}")

print()
print("   And: does the B destination simply REPRODUCE the A destination?")
rep = tot_ab = 0
for c in cells:
    if not c["B_correct"] and not c["A_correct"]:
        tot_ab += 1
        if c["A_selected"] == c["B_selected"]:
            rep += 1
print(f"  cells wrong in BOTH A and B: {tot_ab};  same letter chosen in A and B: "
      f"{rep} = {rep/tot_ab:.4f}")

print()
print("=" * 78)
print("5. MODEL-PAIR DECOMPOSITION (is one model pair carrying the effect?)")
print("=" * 78)
pp = collections.Counter(); ps = collections.Counter()
for q, v in B.items():
    for i in range(len(v)):
        for j in range(i + 1, len(v)):
            key = tuple(sorted([v[i][0], v[j][0]]))
            pp[key] += 1
            if v[i][1] == v[j][1]:
                ps[key] += 1
for k in sorted(pp, key=lambda x: -pp[x]):
    print(f"  {k[0][:22]:22s} x {k[1][:22]:22s} n={pp[k]:3d} agree={ps[k]:3d} = {ps[k]/pp[k]:.3f}")

print()
print("=" * 78)
print("6. CLUSTER LEAKAGE: are the 'items' independent? 325 items / 208 clusters")
print("=" * 78)
cl = collections.defaultdict(set)
for c in cells:
    cl[c["cluster"]].add(c["question_id"])
sz = collections.Counter(len(v) for v in cl.values())
print("cluster size distribution (items per cluster):", dict(sorted(sz.items())))
# items with >=2 erring models, grouped by cluster
multi = {q for q, v in B.items() if len(v) >= 2}
q2c = {c["question_id"]: c["cluster"] for c in cells}
cc = collections.Counter(q2c[q] for q in multi)
print("clusters contributing >=2 multi-error items:",
      sum(1 for v in cc.values() if v >= 2), "of", len(cc))

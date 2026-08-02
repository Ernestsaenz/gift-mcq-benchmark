"""REFUTATION pass 2: alternative explanations for item-level destination concentration."""
import json, collections, random, math, sqlite3, re, unicodedata

PAIRED = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"
LET = ["a", "b", "c", "d"]
IDX = {"a": 2, "b": 3, "c": 4, "d": 5}

cells = [r for r in json.load(open(PAIRED)) if r["analysis_include"]]
q2cl = {c["question_id"]: c["cluster"] for c in cells}
q2corr = {c["question_id"]: c["correct_letter"] for c in cells}

B = collections.defaultdict(list)
for c in cells:
    if not c["B_correct"]:
        B[c["question_id"]].append((c["model"], c["B_selected"], c["A_correct"]))

print("=" * 78)
print("A. HOW CONCENTRATED, IN EFFECTIVE-CHOICE TERMS?")
print("=" * 78)
# If models chose uniformly over m 'live' options per item, pairwise agreement = 1/m.
for k in (2, 3, 4):
    it = [v for v in B.values() if len(v) == k]
    same = tot = 0
    ndist = collections.Counter()
    for v in it:
        cnt = collections.Counter(s for _, s, _ in v)
        ndist[len(cnt)] += 1
        same += sum(x * (x - 1) // 2 for x in cnt.values())
        tot += k * (k - 1) // 2
    if tot:
        print(f"k={k} items={len(it):3d} agree={same}/{tot}={same/tot:.3f} "
              f"-> implied live options 1/p = {tot/same:.2f}   "
              f"#distinct destinations per item: {dict(sorted(ndist.items()))}")
allsame = alltot = 0
for v in B.values():
    k = len(v)
    cnt = collections.Counter(s for _, s, _ in v)
    allsame += sum(x * (x - 1) // 2 for x in cnt.values())
    alltot += k * (k - 1) // 2
print(f"pooled {allsame}/{alltot} = {allsame/alltot:.4f} -> implied live options "
      f"{alltot/allsame:.2f}  (a '2 plausible survivors' story predicts 0.50)")

print()
print("=" * 78)
print("B. IS A SURVIVOR OPTION DEGENERATE? (duplicate / meta option in the B arm)")
print("=" * 78)


def strip_acc(s):
    return "".join(ch for ch in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(ch) != "Mn")


con = sqlite3.connect(DB, uri=True)
opts = {}
for r in con.execute(
        "select q.question_id,q.correct_letter,q.option_a,q.option_b,q.option_c,q.option_d "
        "from questions q join datasets d on d.id=q.dataset_id where d.name='balanced_b_310726'"):
    opts[r[0]] = {L: r[IDX[L]] for L in LET}
con.close()
print("items pulled from B dataset:", len(opts), " overlap with analysis items:",
      len(set(opts) & set(q2corr)))

META = re.compile(r"(ninguna|todas las anteriores|todas son correctas|a y b|son correctas)",
                  re.I)
meta_surv = dup_surv = 0
meta_items = []
for q in B:
    if q not in opts:
        continue
    cl = q2corr[q]
    surv = [L for L in LET if L != cl]
    texts = [strip_acc(opts[q][L]).lower().strip() for L in surv]
    if any(META.search(t) for t in texts):
        meta_surv += 1
        meta_items.append(q)
    if len(set(texts)) < 3:
        dup_surv += 1
print(f"items with >=1 B error whose SURVIVOR set contains a meta/none-like option: "
      f"{meta_surv}/{len(B)}")
print(f"items whose 3 survivors are not all distinct strings: {dup_surv}/{len(B)}")
# check the NOTA slot really carries the NOTA text
nota_ok = sum(1 for q in B if q in opts and
              "ninguna" in strip_acc(opts[q][q2corr[q]]).lower())
print(f"items where the correct_letter slot in arm B holds 'Ninguna...': {nota_ok}/{len(B)}")

# agreement excluding items with a meta survivor
ms = set(meta_items)
s1 = t1 = s2 = t2 = 0
for q, v in B.items():
    k = len(v)
    cnt = collections.Counter(s for _, s, _ in v)
    a = sum(x * (x - 1) // 2 for x in cnt.values()); b = k * (k - 1) // 2
    if q in ms:
        s1 += a; t1 += b
    else:
        s2 += a; t2 += b
print(f"  agreement, items WITH meta survivor: {s1}/{t1}" + (f" = {s1/t1:.3f}" if t1 else ""))
print(f"  agreement, items WITHOUT meta survivor: {s2}/{t2}" + (f" = {s2/t2:.3f}" if t2 else ""))

print()
print("=" * 78)
print("C. INDUCED-ONLY SUBSET: both models correct in A, both wrong in B.")
print("   Permutation null restricted to those same pairs.")
print("=" * 78)
rng = random.Random(4242)


def agree_pairs(sel_by_item, filt=None):
    same = tot = 0
    for q, v in sel_by_item.items():
        for i in range(len(v)):
            for j in range(i + 1, len(v)):
                if filt and not filt(v[i], v[j]):
                    continue
                tot += 1
                if v[i][1] == v[j][1]:
                    same += 1
    return same, tot


both_ok = lambda x, y: x[2] == 1 and y[2] == 1
obs_s, obs_t = agree_pairs(B, both_ok)
print(f"observed (both A-correct pairs): {obs_s}/{obs_t} = {obs_s/obs_t:.4f}")

# shuffle destinations within (model, correct_letter) strata, keep A_correct attached to slot
slots, pool = [], collections.defaultdict(list)
for q, v in B.items():
    cl = q2corr[q]
    for m, s, ac in v:
        slots.append((q, m, cl, ac))
        pool[(m, cl)].append(s)
ge = 0
NP = 20000
vals = []
for _ in range(NP):
    p2 = {k: vv[:] for k, vv in pool.items()}
    for k in p2:
        rng.shuffle(p2[k])
    idx = collections.Counter()
    sim = collections.defaultdict(list)
    for (q, m, cl, ac) in slots:
        key = (m, cl)
        sim[q].append((m, p2[key][idx[key]], ac))
        idx[key] += 1
    s, t = agree_pairs(sim, both_ok)
    vals.append(s / t)
    if s >= obs_s:
        ge += 1
mu = sum(vals) / NP
sd = math.sqrt(sum((x - mu) ** 2 for x in vals) / NP)
print(f"null mean {mu:.4f} sd {sd:.4f}  z={(obs_s/obs_t-mu)/sd:.2f}  "
      f"permutation p = {(ge+1)/(NP+1):.2e}")

print()
print("=" * 78)
print("D. CLUSTER-BLOCK BOOTSTRAP (items within a cluster are near-duplicates)")
print("=" * 78)
by_cluster = collections.defaultdict(list)
for q, v in B.items():
    k = len(v)
    cnt = collections.Counter(s for _, s, _ in v)
    by_cluster[q2cl[q]].append((sum(x * (x - 1) // 2 for x in cnt.values()), k * (k - 1) // 2))
clus = list(by_cluster)
boot = []
for _ in range(20000):
    s = t = 0
    for _ in range(len(clus)):
        for a, b in by_cluster[clus[rng.randrange(len(clus))]]:
            s += a; t += b
    if t:
        boot.append(s / t)
boot.sort()
print(f"point estimate {allsame/alltot:.4f}   cluster-bootstrap 95% CI "
      f"[{boot[int(.025*len(boot))]:.4f}, {boot[int(.975*len(boot))]:.4f}]  "
      f"(clusters={len(clus)})")

print()
print("=" * 78)
print("E. EXACT BINOMIAL ON UNANIMITY vs the permutation null rate")
print("=" * 78)


def binom_sf(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


# null unanimity rate from shuffles, per k
unan_null = collections.Counter(); unan_n = collections.Counter()
for _ in range(2000):
    p2 = {k: vv[:] for k, vv in pool.items()}
    for k in p2:
        rng.shuffle(p2[k])
    idx = collections.Counter()
    sim = collections.defaultdict(list)
    for (q, m, cl, ac) in slots:
        key = (m, cl)
        sim[q].append(p2[key][idx[key]]); idx[key] += 1
    for q, v in sim.items():
        k = len(v)
        if k >= 2:
            unan_n[k] += 1
            if len(set(v)) == 1:
                unan_null[k] += 1
obs_u = {2: (38, 54), 3: (16, 26), 4: (7, 14)}
for k in (2, 3, 4):
    p0 = unan_null[k] / unan_n[k]
    kk, nn = obs_u[k]
    print(f"k={k}: obs {kk}/{nn}={kk/nn:.3f}  shuffle-null rate {p0:.3f} "
          f"(naive (1/3)^(k-1)={(1/3)**(k-1):.3f})  exact binomial p={binom_sf(kk,nn,p0):.3e}")

print()
print("=" * 78)
print("F. DOES THE B DESTINATION MATCH THE A-ARM ATTRACTOR? (item-level, cross-arm)")
print("=" * 78)
# For items where >=1 model erred in A and >=1 (different or same) erred in B,
# is the modal B destination == modal A destination?
Aerr = collections.defaultdict(list)
for c in cells:
    if not c["A_correct"]:
        Aerr[c["question_id"]].append(c["A_selected"])
hit = n = 0
for q, v in B.items():
    if q not in Aerr:
        continue
    mb = collections.Counter(s for _, s, _ in v).most_common(1)[0][0]
    ma = collections.Counter(Aerr[q]).most_common(1)[0][0]
    n += 1
    hit += (mb == ma)
print(f"items with errors in both arms: {n}; modal B destination == modal A destination: "
      f"{hit} = {hit/n:.3f}  (chance ~1/3)")

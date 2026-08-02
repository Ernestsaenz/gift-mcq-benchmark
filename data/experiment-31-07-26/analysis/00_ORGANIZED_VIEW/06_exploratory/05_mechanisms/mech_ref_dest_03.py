"""Part 3: the destination IS concentrated -- just not on the letter/position axis.
Tests the claim's own null (uniform over the 3 survivors) against item-specific
concentration, and asks what predicts the attractor."""
import json, math, collections, random, sqlite3, re, unicodedata, sys
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_ref_dest_01 import chi2sf, gof, cells, surv, L, Aerr, Berr

random.seed(1234)
print("\n" + "#" * 76)
print("PART 3")
print("#" * 76)

drop = [c for c in cells if c["A_correct"] and not c["B_correct"]]
both = [c for c in cells if not c["A_correct"] and not c["B_correct"]]

# ---------------------------------------------------------------- agreement
def agreement(rows, key, groupby="question_id"):
    g = collections.defaultdict(list)
    for c in rows:
        g[c[groupby]].append(c[key])
    same = tot = 0
    for _, v in g.items():
        cnt = collections.Counter(v)
        same += sum(x*(x-1)//2 for x in cnt.values())
        tot += len(v)*(len(v)-1)//2
    return same, tot, g

print("=" * 76)
print("C1. Within-item agreement on the destination, and its permutation null")
print("=" * 76)
for label, rows, key in [("B errors (all)   ", Berr, "B_selected"),
                         ("B errors (DROP)  ", drop, "B_selected"),
                         ("A errors         ", Aerr, "A_selected")]:
    same, tot, g = agreement(rows, key)
    kdist = collections.Counter(len(v) for v in g.values())
    R = 20000; ge = 0; vals = []
    for _ in range(R):
        gg = collections.defaultdict(list)
        for c in rows:
            gg[c["question_id"]].append(random.choice(surv(c)))
        s = sum(sum(x*(x-1)//2 for x in collections.Counter(v).values()) for v in gg.values())
        vals.append(s)
        if s >= same: ge += 1
    mu = sum(vals)/R
    sd = math.sqrt(sum((v-mu)**2 for v in vals)/R)
    print(f"   {label} groups={len(g):3d} kdist={dict(sorted(kdist.items()))}")
    print(f"      pairwise agreement = {same}/{tot} = {same/tot:.4f}   null mean = {mu/tot:.4f}")
    print(f"      permutation p = {(ge+1)/(R+1):.5f}   z = {(same-mu)/sd:+.2f}   "
          f"[Monte-Carlo permutation, {R} reps, destination drawn uniform over each item's 3 survivors]")

print("\n   Same, grouping by CLUSTER (near-duplicate items) instead of question_id:")
same, tot, g = agreement(Berr, "B_selected", "cluster")
print(f"      B errors: {same}/{tot} = {same/tot:.4f} over {len(g)} clusters (chance 0.3333)")

print("\n   Model-pair breakdown (B errors, items where both models erred):")
models = sorted(set(c["model"] for c in cells))
bym = collections.defaultdict(dict)
for c in Berr:
    bym[c["question_id"]][c["model"]] = c["B_selected"]
for i in range(len(models)):
    for j in range(i+1, len(models)):
        m1, m2 = models[i], models[j]
        n = s = 0
        for q, d in bym.items():
            if m1 in d and m2 in d:
                n += 1; s += (d[m1] == d[m2])
        if n:
            print(f"      {m1.split('/')[-1]:20s} vs {m2.split('/')[-1]:20s}  {s:3d}/{n:3d} = {s/n:.3f}")

# item-level: fraction of items where ALL erring models chose the same slot
allsame = sum(1 for q, v in agreement(Berr, "B_selected")[2].items()
              if len(v) >= 2 and len(set(v)) == 1)
multi = sum(1 for q, v in agreement(Berr, "B_selected")[2].items() if len(v) >= 2)
print(f"\n   items where >=2 models erred and ALL picked the identical slot: {allsame}/{multi} = {allsame/multi:.3f}")

# ---------------------------------------------------------------- text
print("\n" + "=" * 76)
print("C2. WHAT predicts the attractor? (option text, read-only DB)")
print("=" * 76)
DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"
con = sqlite3.connect(DB, uri=True)
IDX = {"a": 2, "b": 3, "c": 4, "d": 5}
Q = {}
for ds, k in (("balanced_a_310726", "A"), ("balanced_b_310726", "B")):
    for r in con.execute(
        "select q.question_id,q.correct_letter,q.option_a,q.option_b,q.option_c,q.option_d,"
        "q.question_text from questions q join datasets d on d.id=q.dataset_id where d.name=?", (ds,)):
        Q.setdefault(r[0], {})[k] = {"cl": r[1], "opts": {x: r[IDX[x]] for x in L}, "qt": r[6]}
con.close()
print(f"   loaded {len(Q)} question_ids from DB")
# sanity: B's correct option really is the NOTA string
nota = 0
for q, d in Q.items():
    if "B" in d and "ningun" in (d["B"]["opts"][d["B"]["cl"]] or "").lower():
        nota += 1
print(f"   items whose B correct slot contains 'ningun...': {nota}/{len(Q)}")

_STOP = set("""de la el los las un una unos unas y o u en a al del que se es son por para con sin
sobre como mas más menos su sus lo le les ha han hay ser esta este estos estas no ni si""".split())
def norm(s):
    s = "".join(ch for ch in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(ch) != "Mn")
    return [t for t in re.findall(r"[a-z0-9]+", s) if len(t) > 2 and t not in _STOP]
def jac(a, b):
    A, B = set(norm(a)), set(norm(b))
    return len(A & B)/len(A | B) if A and B else 0.0

# For each B error: rank the 3 survivors by (i) similarity to the REMOVED correct text,
# (ii) similarity to the stem, (iii) length. Is the chosen one the top-ranked?
def topshare(rows, scorer, key="B_selected"):
    hit = n = 0; ties = 0
    for c in rows:
        q = Q.get(c["question_id"])
        if not q or "A" not in q or "B" not in q: continue
        gold = q["A"]["opts"][c["correct_letter"]]
        sv = surv(c)
        sc = {x: scorer(q, c, x, gold) for x in sv}
        mx = max(sc.values())
        best = [x for x in sv if sc[x] == mx]
        if len(best) > 1: ties += 1
        n += 1
        hit += (c[key] in best) / len(best)
    return hit, n, ties

scorers = {
    "similarity to REMOVED correct text": lambda q, c, x, gold: jac(q["A"]["opts"][x], gold),
    "similarity to the STEM            ": lambda q, c, x, gold: jac(q["A"]["opts"][x], q["A"]["qt"]),
    "option LENGTH (chars)             ": lambda q, c, x, gold: len(q["A"]["opts"][x] or ""),
}
print("\n   P(model's B-error lands on the top-scoring survivor); chance = 1/3")
for name, f in scorers.items():
    hit, n, ties = topshare(Berr, f)
    se = math.sqrt((1/3)*(2/3)/n)
    z = (hit/n - 1/3)/se
    print(f"     {name}: {hit:.1f}/{n} = {hit/n:.4f}  z={z:+.2f}  "
          f"p={math.erfc(abs(z)/math.sqrt(2)):.3e}  (ties={ties})  [one-sample z on a proportion vs 1/3]")
print("   same, restricted to newly created (DROP) errors:")
for name, f in scorers.items():
    hit, n, ties = topshare(drop, f)
    se = math.sqrt((1/3)*(2/3)/n); z = (hit/n - 1/3)/se
    print(f"     {name}: {hit:.1f}/{n} = {hit/n:.4f}  z={z:+.2f}  p={math.erfc(abs(z)/math.sqrt(2)):.3e}")
print("   control -- condition A errors, same scorers (attractor map without NOTA):")
for name, f in scorers.items():
    hit, n, ties = topshare(Aerr, f, key="A_selected")
    se = math.sqrt((1/3)*(2/3)/n); z = (hit/n - 1/3)/se
    print(f"     {name}: {hit:.1f}/{n} = {hit/n:.4f}  z={z:+.2f}  p={math.erfc(abs(z)/math.sqrt(2)):.3e}")

# ---------------------------------------------------------------- NOTA aversion check
print("\n" + "=" * 76)
print("C3. Is there a blanket unwillingness to pick the NOTA slot?")
print("=" * 76)
nB = len(cells)
print(f"   models selected the NOTA slot in {sum(c['B_correct'] for c in cells)}/{nB} "
      f"= {sum(c['B_correct'] for c in cells)/nB:.3f} of B cells")
for m in models:
    r = [c for c in cells if c["model"] == m]
    print(f"     {m:26s} A acc={sum(x['A_correct'] for x in r)/len(r):.3f}  "
          f"B NOTA-select={sum(x['B_correct'] for x in r)/len(r):.3f}  "
          f"drop={-(sum(x['B_correct'] for x in r)-sum(x['A_correct'] for x in r))/len(r):+.3f}")

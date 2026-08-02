"""REFUTATION pass 3: is item-level convergence explained by the chosen distractor
being a near-paraphrase of the REMOVED correct answer (i.e. the answer is still there)?
That would reframe the mechanism but not the concentration itself."""
import json, collections, sqlite3, re, unicodedata, math, random

PAIRED = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"
LET = ["a", "b", "c", "d"]
IDX = {"a": 1, "b": 2, "c": 3, "d": 4}   # offsets into the SELECT below
_STOP = set("""de la el los las un una unos unas y o u en a al del que se es son por para con sin
sobre como mas más menos su sus lo le les ha han hay ser esta este estos estas the of no ni""".split())


def toks(s):
    s = "".join(ch for ch in unicodedata.normalize("NFD", (s or "").lower())
                if unicodedata.category(ch) != "Mn")
    return set(t for t in re.findall(r"[a-z0-9]+", s) if len(t) > 2 and t not in _STOP)


def jac(a, b):
    A, B = toks(a), toks(b)
    return len(A & B) / len(A | B) if A and B else 0.0


cells = [r for r in json.load(open(PAIRED)) if r["analysis_include"]]
q2corr = {c["question_id"]: c["correct_letter"] for c in cells}
con = sqlite3.connect(DB, uri=True)
A_opts, B_opts = {}, {}
for ds, tgt in (("balanced_a_310726", A_opts), ("balanced_b_310726", B_opts)):
    for r in con.execute(
            "select q.question_id,q.option_a,q.option_b,q.option_c,q.option_d "
            "from questions q join datasets d on d.id=q.dataset_id where d.name=?", (ds,)):
        tgt[r[0]] = {L: r[IDX[L]] for L in LET}
con.close()

B = collections.defaultdict(list)
for c in cells:
    if not c["B_correct"]:
        B[c["question_id"]].append(c["B_selected"])

print("=" * 78)
print("Similarity of the CHOSEN distractor to the REMOVED correct answer (arm-A text)")
print("=" * 78)
rows = []
for q, sel in B.items():
    if q not in A_opts:
        continue
    cl = q2corr[q]
    removed = A_opts[q][cl]
    surv = [L for L in LET if L != cl]
    mode, mc = collections.Counter(sel).most_common(1)[0]
    k = len(sel)
    unan = (len(set(sel)) == 1)
    # similarity of each survivor to the removed correct text; rank of the chosen one
    sims = {L: jac(B_opts[q][L], removed) for L in surv}
    order = sorted(surv, key=lambda L: -sims[L])
    rows.append((q, k, unan, mode, sims[mode], order.index(mode), max(sims.values())))

print(f"items scored: {len(rows)}")
for k in (1, 2, 3, 4):
    r = [x for x in rows if x[1] == k]
    if not r:
        continue
    top = sum(1 for x in r if x[5] == 0)
    print(f"  k={k} n={len(r):3d}  modal destination is the survivor MOST similar to the "
          f"removed answer: {top}/{len(r)} = {top/len(r):.3f}  (chance 1/3)  "
          f"mean jaccard={sum(x[4] for x in r)/len(r):.3f}")
un = [x for x in rows if x[2] and x[1] >= 2]
nu = [x for x in rows if not x[2] and x[1] >= 2]
print(f"  unanimous multi-model items  n={len(un):3d} top-sim {sum(1 for x in un if x[5]==0)/len(un):.3f} "
      f"mean jac {sum(x[4] for x in un)/len(un):.3f}")
print(f"  split      multi-model items  n={len(nu):3d} top-sim {sum(1 for x in nu if x[5]==0)/len(nu):.3f} "
      f"mean jac {sum(x[4] for x in nu)/len(nu):.3f}")

# Overall: is 'chosen == most similar survivor' above chance? binomial vs 1/3
allr = [x for x in rows]
kk = sum(1 for x in allr if x[5] == 0); nn = len(allr)
p = sum(math.comb(nn, i) * (1/3)**i * (2/3)**(nn-i) for i in range(kk, nn+1))
print(f"\nPooled: modal destination = most-similar-to-removed-answer survivor "
      f"{kk}/{nn} = {kk/nn:.3f}; exact binomial vs 1/3 (one-sided) p={p:.3e}")

print()
print("=" * 78)
print("Control: same statistic on items with NO B error (does lexical similarity")
print("predict destination, or is 'most similar survivor' just a generic magnet?)")
print("=" * 78)
# For every item, what fraction of A-arm errors land on the most-similar survivor?
Aerr = collections.defaultdict(list)
for c in cells:
    if not c["A_correct"]:
        Aerr[c["question_id"]].append(c["A_selected"])
kk2 = nn2 = 0
for q, sel in Aerr.items():
    if q not in A_opts:
        continue
    cl = q2corr[q]
    removed = A_opts[q][cl]          # in arm A this IS the correct option, still present
    surv = [L for L in LET if L != cl]
    sims = {L: jac(A_opts[q][L], removed) for L in surv}
    mode = collections.Counter(sel).most_common(1)[0][0]
    best = max(sims, key=lambda L: sims[L])
    nn2 += 1; kk2 += (mode == best)
p2 = sum(math.comb(nn2, i) * (1/3)**i * (2/3)**(nn2-i) for i in range(kk2, nn2+1))
print(f"A-arm errors landing on survivor most similar to the (present) correct option: "
      f"{kk2}/{nn2} = {kk2/nn2:.3f}  binomial vs 1/3 p={p2:.3e}")

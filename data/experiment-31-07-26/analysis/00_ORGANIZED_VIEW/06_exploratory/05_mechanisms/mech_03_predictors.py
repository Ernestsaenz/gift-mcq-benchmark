"""(c) What predicts WHICH distractor is chosen: length, position, A-condition
attraction, or lexical similarity to the deleted correct answer?"""
import sys, collections, random, math
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_lib import *

random.seed(7)
Q = load_questions()
cells = load_cells()
models = sorted(set(c["model"] for c in cells))
errsB = [c for c in cells if c["B_correct"] == 0]
errsA = [c for c in cells if c["A_correct"] == 0]

# map: item -> which letters were picked by which models in condition A (errors only)
A_pick = collections.defaultdict(dict)
for c in errsA:
    A_pick[c["question_id"]][c["model"]] = c["A_selected"]


def surv(qid):
    return [L for L in LETTERS if L != Q[qid]["B"]["correct_letter"]]


def feats(qid):
    """Per-surviving-alternative features for an item."""
    b = Q[qid]["B"]; a = Q[qid]["A"]
    removed = a["correct_text"]
    stem = a["qtext"]
    out = {}
    for L in surv(qid):
        t = b["opts"][L]
        out[L] = {
            "len": len(t),
            "jac_removed": jaccard(t, removed),
            "jac_stem": jaccard(t, stem),
            "text": t,
        }
    return out


FT = {q: feats(q) for q in set(c["question_id"] for c in cells)}


def rank_of(qid, L, key, reverse=True):
    """1 = extreme (largest if reverse) among the 3 survivors; ties -> mid-rank."""
    vals = [(FT[qid][x][key], x) for x in surv(qid)]
    vals.sort(key=lambda z: -z[0] if reverse else z[0])
    v = FT[qid][L][key]
    same = [i for i, (vv, _) in enumerate(vals) if vv == v]
    return sum(same) / len(same) + 1


def sign_report(name, ranks):
    n = len(ranks)
    mean = sum(ranks) / n
    sd = (sum((r - mean) ** 2 for r in ranks) / (n - 1)) ** 0.5
    # permutation null: rank of a uniformly random survivor = uniform{1,2,3}, mean 2
    ge = 0; NP = 20000
    for _ in range(NP):
        s = sum(random.choice((1.0, 2.0, 3.0)) for _ in range(n)) / n
        if abs(s - 2.0) >= abs(mean - 2.0) - 1e-12:
            ge += 1
    print(f"  {name:42s} mean rank={mean:.3f} (null 2.000) sd={sd:.2f} n={n} "
          f"two-sided perm p={(ge+1)/(NP+1):.5f}")
    return mean


print("=" * 78)
print("C1. OPTION LENGTH")
print("=" * 78)
print("Rank 1 = LONGEST of the three survivors.")
sign_report("B errors: length-rank of chosen", [rank_of(c["question_id"], c["B_selected"], "len") for c in errsB])
sign_report("A errors: length-rank of chosen", [rank_of(c["question_id"], c["A_selected"], "len") for c in errsA])
# absolute chars
ch = [FT[c["question_id"]][c["B_selected"]]["len"] for c in errsB]
allch = [FT[c["question_id"]][L]["len"] for c in errsB for L in surv(c["question_id"])]
print(f"  chosen mean length={sum(ch)/len(ch):.1f} chars   "
      f"all-survivor mean={sum(allch)/len(allch):.1f} chars")

print()
print("=" * 78)
print("C2. LEXICAL SIMILARITY TO THE DELETED CORRECT ANSWER")
print("=" * 78)
print("Rank 1 = most token-overlap (Jaccard, accent-stripped, stopwords dropped)")
print("         with the correct option TEXT that condition B removed.")
sign_report("B errors: similarity-rank of chosen", [rank_of(c["question_id"], c["B_selected"], "jac_removed") for c in errsB])
sign_report("A errors: similarity-rank of chosen", [rank_of(c["question_id"], c["A_selected"], "jac_removed") for c in errsA])
top = sum(1 for c in errsB if rank_of(c["question_id"], c["B_selected"], "jac_removed") == 1.0)
print(f"  B errors landing on the single most-similar survivor: {top}/{len(errsB)} = {top/len(errsB):.3f}")
topA = sum(1 for c in errsA if rank_of(c["question_id"], c["A_selected"], "jac_removed") == 1.0)
print(f"  A errors landing on that same survivor:               {topA}/{len(errsA)} = {topA/len(errsA):.3f}")

print()
print("=" * 78)
print("C3. SIMILARITY TO THE QUESTION STEM (topical-overlap heuristic)")
print("=" * 78)
sign_report("B errors: stem-similarity rank of chosen", [rank_of(c["question_id"], c["B_selected"], "jac_stem") for c in errsB])
sign_report("A errors: stem-similarity rank of chosen", [rank_of(c["question_id"], c["A_selected"], "jac_stem") for c in errsA])

print()
print("=" * 78)
print("C4. WAS THE DESTINATION ALREADY AN ATTRACTOR IN CONDITION A?")
print("=" * 78)
# leave-one-out: does ANOTHER model's condition-A error on this item point to the
# same letter this model picked in condition B?
hit = tot = 0
nulls = []
for c in errsB:
    q = c["question_id"]
    others = {m: L for m, L in A_pick[q].items() if m != c["model"]}
    if not others:
        continue
    tot += 1
    picks = set(others.values())
    hit += c["B_selected"] in picks
    nulls.append(len(picks) / 3.0)   # chance of hitting the set at random
exp = sum(nulls)
print(f"  B errors on items where >=1 OTHER model also erred in A:  n={tot}")
print(f"  B destination matches an other-model A destination: {hit} "
      f"(={hit/tot:.3f}); random-choice expectation {exp:.1f} (={exp/tot:.3f})")
# exact-ish binomial via Poisson-binomial normal approx + permutation
NP = 20000; ge = 0
for _ in range(NP):
    s = sum(1 for p in nulls if random.random() < p)
    if s >= hit:
        ge += 1
print(f"  permutation (uniform choice among survivors) p={(ge+1)/(NP+1):.5f}")

# same model: when a model erred in A AND in B on the same item, same letter?
same = tot2 = 0
for c in errsB:
    q = c["question_id"]
    if c["model"] in A_pick[q]:
        tot2 += 1
        same += A_pick[q][c["model"]] == c["B_selected"]
print(f"\n  SAME model erred in both A and B on the item: n={tot2}, "
      f"identical letter {same} (={same/tot2:.3f}) vs chance 0.333")

# the reverse framing: B errors split by whether the model had A correct
gp = collections.Counter()
for c in errsB:
    gp[c["A_correct"]] += 1
print(f"\n  B errors where the model had the item RIGHT in A: {gp[1]} "
      f"({gp[1]/len(errsB):.3f}); wrong in A too: {gp[0]} ({gp[0]/len(errsB):.3f})")
print("  (in the first group the model chose the correct LETTER in A, then in B")
print("   -- with NOTA sitting in that same letter -- moved off it.)")

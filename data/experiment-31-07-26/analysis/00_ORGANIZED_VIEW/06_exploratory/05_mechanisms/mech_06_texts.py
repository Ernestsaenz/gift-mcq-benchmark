"""What do the chosen distractors SAY? Unanimous-convergence exemplars plus a
lexical-marker test (absolutes/negations/hedges) on chosen vs unchosen survivors."""
import sys, collections, re, math, random
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_lib import *

random.seed(5)
Q = load_questions()
cells = load_cells()
errsB = [c for c in cells if c["B_correct"] == 0]
errsA = [c for c in cells if c["A_correct"] == 0]


def surv(qid):
    return [L for L in LETTERS if L != Q[qid]["B"]["correct_letter"]]


by_q = collections.defaultdict(dict)
for c in errsB:
    by_q[c["question_id"]][c["model"]] = c["B_selected"]

print("=" * 78)
print("UNANIMOUS 4/4 CONVERGENCE ITEMS -- what the models chose instead")
print("=" * 78)
unan = [(q, v) for q, v in by_q.items() if len(v) == 4 and len(set(v.values())) == 1]
print(f"{len(unan)} items where all four models erred and all four picked the same option.\n")
for q, v in unan:
    L = list(v.values())[0]
    a = Q[q]["A"]; b = Q[q]["B"]
    print(f"--- {q}  (NOTA sits at [{b['correct_letter']}]; all 4 models chose [{L}])")
    print(f"    P: {a['qtext'][:230]}")
    print(f"    DELETED correct answer: {a['correct_text'][:180]}")
    print(f"    CHOSEN [{L}]: {b['opts'][L][:180]}")
    for o in surv(q):
        if o != L:
            print(f"      not chosen [{o}]: {b['opts'][o][:120]}")
    print()

print("=" * 78)
print("EXEMPLARS: ALL FOUR MODELS CORRECT IN A, THEN CONVERGE ON ONE DISTRACTOR IN B")
print("=" * 78)
Acorr = collections.defaultdict(int)
for c in cells:
    Acorr[c["question_id"]] += c["A_correct"]
shown = 0
for q, v in by_q.items():
    if len(v) >= 3 and len(set(v.values())) == 1 and Acorr[q] == 4:
        L = list(v.values())[0]
        a = Q[q]["A"]; b = Q[q]["B"]
        print(f"--- {q}  4/4 right in A; {len(v)}/4 wrong in B, all on [{L}] "
              f"(NOTA at [{b['correct_letter']}])")
        print(f"    P: {a['qtext'][:230]}")
        print(f"    DELETED correct answer: {a['correct_text'][:180]}")
        print(f"    CHOSEN [{L}]: {b['opts'][L][:180]}")
        print()
        shown += 1
        if shown >= 6:
            break

print("=" * 78)
print("LEXICAL MARKERS: chosen vs unchosen surviving distractors")
print("=" * 78)
MARK = {
    "absolute (siempre/nunca/todos/unico/solo/exclusiv)":
        r"\b(siempre|nunca|todos?|todas?|unic[oa]s?|solo|solamente|exclusiv\w*|jamas|ningun\w*)\b",
    "negation (no/ni/sin)": r"\b(no|ni|sin)\b",
    "hedge (puede/suele/generalmente/habitual)":
        r"\b(puede\w*|suele\w*|generalmente|habitual\w*|frecuente\w*|posible\w*)\b",
    "numeric/dosage token": r"\d",
}
for name, pat in MARK.items():
    rx = re.compile(pat, re.I)
    ch = unch = nch = nunch = 0
    for c in errsB:
        q = c["question_id"]
        for L in surv(q):
            t = strip_acc(Q[q]["B"]["opts"][L])
            hit = bool(rx.search(t))
            if L == c["B_selected"]:
                nch += 1; ch += hit
            else:
                nunch += 1; unch += hit
    pc, pu = ch / nch, unch / nunch
    # permutation: reassign the chosen alternative uniformly within each set
    NP = 20000; ge = 0
    obs = pc - pu
    prep = []
    for c in errsB:
        q = c["question_id"]
        prep.append([bool(rx.search(strip_acc(Q[q]["B"]["opts"][L]))) for L in surv(q)])
    for _ in range(NP):
        a = b_ = 0
        for row in prep:
            i = random.randrange(3)
            a += row[i]
            b_ += sum(row) - row[i]
        d = a / len(prep) - b_ / (2 * len(prep))
        if abs(d) >= abs(obs) - 1e-12:
            ge += 1
    print(f"  {name:52s} chosen {pc:.3f}  unchosen {pu:.3f}  diff {obs:+.3f}  "
          f"perm p={(ge+1)/(NP+1):.5f}")

print()
print("=" * 78)
print("HOW OFTEN IS THE CHOSEN DISTRACTOR A NEAR-PARAPHRASE OF THE DELETED ANSWER?")
print("=" * 78)
hi = collections.Counter()
for c in errsB:
    q = c["question_id"]
    j = jaccard(Q[q]["B"]["opts"][c["B_selected"]], Q[q]["A"]["correct_text"])
    hi["j>=0.5" if j >= 0.5 else ("0.3<=j<0.5" if j >= 0.3 else "j<0.3")] += 1
print("  chosen-vs-deleted Jaccard bands:", dict(hi))
allj = [jaccard(Q[c["question_id"]]["B"]["opts"][L], Q[c["question_id"]]["A"]["correct_text"])
        for c in errsB for L in surv(c["question_id"])]
chj = [jaccard(Q[c["question_id"]]["B"]["opts"][c["B_selected"]], Q[c["question_id"]]["A"]["correct_text"])
       for c in errsB]
print(f"  mean Jaccard: chosen={sum(chj)/len(chj):.4f}  all survivors={sum(allj)/len(allj):.4f}")

print()
print("=" * 78)
print("HIGH-OVERLAP EXEMPLARS (chosen distractor closest to the deleted answer)")
print("=" * 78)
rows = sorted(errsB, key=lambda c: -jaccard(Q[c["question_id"]]["B"]["opts"][c["B_selected"]],
                                            Q[c["question_id"]]["A"]["correct_text"]))
seen = set()
n = 0
for c in rows:
    q = c["question_id"]
    if q in seen:
        continue
    seen.add(q)
    j = jaccard(Q[q]["B"]["opts"][c["B_selected"]], Q[q]["A"]["correct_text"])
    print(f"--- {q} Jaccard={j:.2f}  chosen by {len(by_q[q])}/4 models")
    print(f"    DELETED: {Q[q]['A']['correct_text'][:170]}")
    print(f"    CHOSEN : {Q[q]['B']['opts'][c['B_selected']][:170]}")
    n += 1
    if n >= 5:
        break

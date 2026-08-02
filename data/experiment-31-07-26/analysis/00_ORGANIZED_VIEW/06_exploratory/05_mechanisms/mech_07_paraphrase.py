"""Conditional near-paraphrase capture, A-vs-B contrast on identical choice sets,
and the easy-item control for a global NOTA aversion."""
import sys, collections, random, math
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_lib import *

random.seed(13)
Q = load_questions()
cells = load_cells()
models = sorted(set(c["model"] for c in cells))
errsB = [c for c in cells if c["B_correct"] == 0]
errsA = [c for c in cells if c["A_correct"] == 0]


def surv(qid):
    return [L for L in LETTERS if L != Q[qid]["B"]["correct_letter"]]


def jrem(qid, L):
    return jaccard(Q[qid]["B"]["opts"][L], Q[qid]["A"]["correct_text"])


print("=" * 78)
print("P1. WHEN A NEAR-PARAPHRASE OF THE DELETED ANSWER EXISTS, IS IT CHOSEN?")
print("=" * 78)
for thr in (0.4, 0.5, 0.6):
    # items whose survivor set contains exactly one option with jaccard >= thr
    qs = []
    for q in set(c["question_id"] for c in cells):
        hits = [L for L in surv(q) if jrem(q, L) >= thr]
        if len(hits) == 1:
            qs.append((q, hits[0]))
    qmap = dict(qs)
    nb = hb = 0
    for c in errsB:
        if c["question_id"] in qmap:
            nb += 1; hb += c["B_selected"] == qmap[c["question_id"]]
    na = ha = 0
    for c in errsA:
        if c["question_id"] in qmap:
            na += 1; ha += c["A_selected"] == qmap[c["question_id"]]
    pb, lob, hib = wilson(hb, nb)
    print(f"  threshold Jaccard>={thr}: {len(qs)} items have exactly one such survivor")
    print(f"    B errors on those items: {hb}/{nb} = {pb:.3f} land on it "
          f"[95% CI {lob:.3f}-{hib:.3f}]  (chance 0.333, binomial p="
          f"{binom_two_sided(hb, nb, 1/3.):.2e})")
    if na:
        pa, loa, hia = wilson(ha, na)
        print(f"    A errors on those items: {ha}/{na} = {pa:.3f} land on it "
              f"[95% CI {loa:.3f}-{hia:.3f}]  binomial p={binom_two_sided(ha, na, 1/3.):.3f}")
    print()

print("=" * 78)
print("P2. NUMERIC / DOSE-NEIGHBOUR ITEMS (options differing only in a number)")
print("=" * 78)
num = []
for q in set(c["question_id"] for c in cells):
    hits = [L for L in surv(q) if jrem(q, L) >= 0.8]
    if hits:
        num.append((q, hits))
print(f"  {len(num)} items have >=1 survivor sharing >=80% of content tokens with the")
print(f"  deleted answer (typically the same sentence with a different number/agent).")
n = h = 0
for c in errsB:
    for q, hits in num:
        if c["question_id"] == q:
            n += 1; h += c["B_selected"] in hits
if n:
    print(f"  B errors on those items land on such a twin: {h}/{n} = {h/n:.3f} "
          f"(chance ~{sum(len(hs) for _, hs in num)/(3*len(num)):.3f})")
na2 = ha2 = 0
for c in errsA:
    for q, hits in num:
        if c["question_id"] == q:
            na2 += 1; ha2 += c["A_selected"] in hits
if na2:
    print(f"  A errors on those items land on such a twin: {ha2}/{na2} = {ha2/na2:.3f}")
print("  examples:")
shown = 0
for q, hits in num:
    if any(c["question_id"] == q for c in errsB):
        print(f"    {q}: deleted \"{Q[q]['A']['correct_text'][:70]}\"  ->  "
              f"twin [{hits[0]}] \"{Q[q]['B']['opts'][hits[0]][:70]}\"")
        shown += 1
        if shown >= 8:
            break

print()
print("=" * 78)
print("P3. EASY-ITEM CONTROL: IS THERE A GLOBAL 'WON'T SAY NONE-OF-THE-ABOVE' FLOOR?")
print("=" * 78)
Acorr = collections.Counter()
for c in cells:
    Acorr[c["question_id"]] += c["A_correct"]
print(f"{'A-consensus (models right in A)':34s} {'items':>6s} {'cells':>6s} {'B acc':>7s} {'95% CI':>16s}")
for k in range(5):
    qs = set(q for q, v in Acorr.items() if v == k)
    sub = [c for c in cells if c["question_id"] in qs]
    if not sub:
        continue
    kk = sum(c["B_correct"] for c in sub)
    p, lo, hi = wilson(kk, len(sub))
    print(f"  {k}/4 right in A{'':20s} {len(qs):6d} {len(sub):6d} {p:7.3f} "
          f"[{lo:.3f},{hi:.3f}]")
qs4 = set(q for q, v in Acorr.items() if v == 4)
sub = [c for c in cells if c["question_id"] in qs4 and c["A_correct"] == 1]
print(f"\n  On the {len(qs4)} items every model answered correctly in A, condition-B "
      f"accuracy is {sum(c['B_correct'] for c in sub)/len(sub):.3f}.")
print("  A blanket refusal to emit the NOTA slot would cap this near 0; it does not.")
for m in models:
    s = [c for c in sub if c["model"] == m]
    print(f"    {m:28s} B acc on A-unanimous items = {sum(c['B_correct'] for c in s)/len(s):.3f} "
          f"(n={len(s)})")

print()
print("=" * 78)
print("P4. HOW MUCH OF THE DROP IS 'OLD ATTRACTOR AMPLIFIED'?")
print("=" * 78)
# Per item, the pooled modal A-error destination (any model). Then: of the
# A-correct -> B-wrong cells on items that HAVE such a mode, how many land on it?
mode = {}
for q in set(c["question_id"] for c in cells):
    cnt = collections.Counter(c["A_selected"] for c in errsA if c["question_id"] == q)
    if cnt:
        top, n = cnt.most_common(1)[0]
        if sum(1 for v in cnt.values() if v == n) == 1:
            mode[q] = top
drop = [c for c in errsB if c["A_correct"] == 1]
sub = [c for c in drop if c["question_id"] in mode and c["model"] not in
       {x["model"] for x in errsA if x["question_id"] == c["question_id"]}]
h = sum(1 for c in sub if c["B_selected"] == mode[c["question_id"]])
print(f"  Cells where the model was RIGHT in A, WRONG in B, and some OTHER model had a")
print(f"  unique modal A-error letter on that item: n={len(sub)}")
print(f"  B error lands on that pre-existing attractor: {h} ({h/len(sub):.3f}), chance 0.333, "
      f"binomial p={binom_two_sided(h, len(sub), 1/3.):.3e}")

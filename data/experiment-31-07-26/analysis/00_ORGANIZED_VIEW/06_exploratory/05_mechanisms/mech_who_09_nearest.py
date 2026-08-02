"""Is the option chosen in B the NEAREST SURVIVING SUBSTITUTE for the deleted answer?
If the drop were loss of a memorised-string cue we would expect the fallback to be
diffuse.  If it is forced substitution inside a 'one of these must be right' prior, the
fallback should land on the distractor most similar to the answer that was deleted.
"""
import difflib, re, unicodedata, collections, math, random
from mech_who_00_build import cells, items

random.seed(3)
STOP = set("de la el los las un una y o en con por para que del al se es son a".split())

def toks(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return {w for w in re.findall(r"[a-z0-9]+", s) if w not in STOP and len(w) > 2}

def jac(a, b):
    A, B = toks(a), toks(b)
    return len(A & B) / len(A | B) if A | B else 0.0

def seqr(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

for simname, sim in (("token Jaccard", jac), ("difflib ratio", seqr)):
    print("=" * 86)
    print(f"N-1. NEAREST-SUBSTITUTE TEST  (similarity = {simname})")
    res = {}
    for lab, rows, chosen in (
            ("LOST  (A+ -> B-): B choice vs deleted answer", [r for r in cells if r["lost"]], "B_selected"),
            ("A-wrong control:  A choice vs the correct answer",
             [r for r in cells if not r["A_correct"]], "A_selected"),
            ("both-wrong in B:  B choice vs deleted answer",
             [r for r in cells if not r["A_correct"] and not r["B_correct"]], "B_selected")):
        hit = n = 0; ranks = collections.Counter(); simsel = []; simother = []
        for r in rows:
            it = items[r["question_id"]]
            L = r["correct_letter"]
            dis = [k for k in "abcd" if k != L]
            s = {k: sim(it["correct_text"], it["options"][k]) for k in dis}
            ch = r[chosen]
            if ch not in s: continue
            n += 1
            order = sorted(dis, key=lambda k: -s[k])
            ranks[order.index(ch) + 1] += 1
            hit += int(order[0] == ch)
            simsel.append(s[ch]); simother += [s[k] for k in dis if k != ch]
        res[lab] = (hit, n, ranks, simsel, simother)
        print(f"  {lab}")
        print(f"     picked the distractor most similar to the deleted/true answer: "
              f"{hit}/{n} = {hit/n:.3f}   (chance = 0.333)")
        print(f"     rank of the chosen distractor by similarity: "
              f"{dict(sorted(ranks.items()))}")
        print(f"     mean similarity: chosen {sum(simsel)/len(simsel):.4f}  "
              f"vs not-chosen {sum(simother)/len(simother):.4f}")
        # exact binomial vs 1/3
        p = sum(math.comb(n, k) * (1/3) ** k * (2/3) ** (n - k) for k in range(hit, n + 1))
        print(f"     exact binomial vs p=1/3, one-sided: p = {p:.3e}")
    # difference between the LOST rate and the A-wrong control rate: two-proportion z
    (h1, n1, *_), (h2, n2, *_) = (res["LOST  (A+ -> B-): B choice vs deleted answer"],
                                  res["A-wrong control:  A choice vs the correct answer"])
    p1, p2 = h1 / n1, h2 / n2
    pp = (h1 + h2) / (n1 + n2)
    zz = (p1 - p2) / math.sqrt(pp * (1 - pp) * (1 / n1 + 1 / n2))
    print(f"  LOST vs A-wrong control: {p1:.3f} vs {p2:.3f}, two-proportion z = {zz:.2f}, "
          f"p = {2*(1-0.5*(1+math.erf(abs(zz)/math.sqrt(2)))):.3f}")
    print()

print("=" * 86)
print("N-2. PARALLEL-OPTION FAMILIES: how often is the deleted answer one of a pair of")
print("     options that differ only in one element (drug, number, timing)?")
hi = 0
for r in [x for x in cells if x["lost"]]:
    it = items[r["question_id"]]
    L = r["correct_letter"]
    s = seqr(it["correct_text"], it["options"][r["B_selected"]])
    hi += int(s >= 0.6)
print(f"     among the 247 lost cells the chosen distractor shares >=60% of its characters")
print(f"     with the deleted answer in {hi} cases ({hi/247:.1%})")

print()
print("=" * 86)
print("N-3. EXAMPLES: deleted answer vs the option taken instead")
seen = set()
ex = sorted([x for x in cells if x["lost"]],
            key=lambda r: -seqr(items[r["question_id"]]["correct_text"],
                                items[r["question_id"]]["options"][r["B_selected"]]))
for r in ex[:8]:
    it = items[r["question_id"]]
    if r["question_id"] in seen: continue
    seen.add(r["question_id"])
    s = seqr(it["correct_text"], it["options"][r["B_selected"]])
    print(f"\n  [{r['model']}] item {r['question_id']}  similarity {s:.2f}")
    print(f"     DELETED (true, present only in A): {it['correct_text'][:170]}")
    print(f"     CHOSEN IN B  (option {r['B_selected']}):            "
          f"{it['options'][r['B_selected']][:170]}")

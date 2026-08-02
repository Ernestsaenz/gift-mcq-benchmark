"""Find items whose ORIGINAL (condition A) options already contain a
none-of-the-above ('ninguna...') option, and whether it is the key or a distractor.
These give a natural baseline for NOTA acceptance, uncontaminated by the swap.
"""
import json
import unicodedata

OPTS = json.load(open("/private/tmp/claude-501/-Users-ernestsaenz-Programming-GIFT-abstract-dossier/a0613478-db50-4bbd-ba89-911fee14cc09/scratchpad/opts.json"))
ROWS = json.load(open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"))


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.split()).strip(" .")


NOTA_EXACT = norm("Ninguna de las respuestas anteriores es correcta.")

native = {}   # qid -> (letter, is_key, text)
for qid, r in OPTS["A"].items():
    for L in "abcd":
        n = norm(r[L])
        if n.startswith("ninguna de las") or n.startswith("ninguna de ellas") or n == NOTA_EXACT:
            native[qid] = (L, L == r["correct_letter"], r[L])

print("condition-A items with a native 'ninguna...' option:", len(native))
for qid, v in sorted(native.items()):
    inA = OPTS["A"][qid]
    print(f"  {qid}: letter={v[0]} is_key={v[1]} key={inA['correct_letter']} :: {v[2]}")

inc = [r for r in ROWS if r["analysis_include"]]
qids_inc = set(r["question_id"] for r in inc)
print("\nof those, in the 325-item analysis set:", sorted(q for q in native if q in qids_inc))

# also: check that in condition B the swapped slot really carries the string
mismatch = 0
checked = 0
for qid in qids_inc:
    b = OPTS["B"][qid]
    cl = b["correct_letter"]
    checked += 1
    if norm(b[cl]) != NOTA_EXACT:
        mismatch += 1
        if mismatch < 6:
            print("B slot not NOTA:", qid, cl, repr(b[cl][:80]))
print(f"\nB-arm swap check: {checked} analysis items, {mismatch} whose key slot is not the NOTA string")

# and check the three non-key options are identical A vs B (i.e. only the key text changed)
diff = 0
for qid in qids_inc:
    a, b = OPTS["A"][qid], OPTS["B"][qid]
    cl = a["correct_letter"]
    assert cl == b["correct_letter"], qid
    for L in "abcd":
        if L == cl:
            continue
        if norm(a[L]) != norm(b[L]):
            diff += 1
            if diff < 6:
                print("distractor differs:", qid, L, repr(a[L][:60]), "||", repr(b[L][:60]))
print(f"distractor-text differences A vs B: {diff}")

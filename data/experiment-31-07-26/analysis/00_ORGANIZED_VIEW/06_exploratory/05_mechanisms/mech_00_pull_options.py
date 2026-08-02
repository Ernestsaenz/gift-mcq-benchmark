"""Pull option/question text for the analysis items from the read-only DB.

Writes a JSON cache to the scratchpad so later mech_ scripts don't re-open the DB.
"""
import json
import sqlite3
import unicodedata

DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"
OUT = "/private/tmp/claude-501/-Users-ernestsaenz-Programming-GIFT-abstract-dossier/a0613478-db50-4bbd-ba89-911fee14cc09/scratchpad/opts.json"


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.split())


con = sqlite3.connect(DB, uri=True)
c = con.cursor()

out = {"A": {}, "B": {}}
for ds_id, arm in ((1, "A"), (2, "B")):
    for qid, qt, a, b, d_, e, cl, cot in c.execute(
        "select question_id,question_text,option_a,option_b,option_c,option_d,"
        "correct_letter,correct_option_text from questions where dataset_id=?",
        (ds_id,),
    ):
        out[arm][qid] = {
            "question_text": qt,
            "a": a, "b": b, "c": d_, "d": e,
            "correct_letter": cl,
            "correct_option_text": cot,
        }
con.close()

json.dump(out, open(OUT, "w"), ensure_ascii=False)
print("A items", len(out["A"]), "B items", len(out["B"]))

# --- does condition A already contain NOTA-style distractors? ---
PATS = ["ninguna de las", "ninguna de ellas", "todas las anteriores", "todas las respuestas",
        "ninguna es correcta", "ningun", "todas son correctas", "a y b son", "son correctas"]
hits = {p: 0 for p in PATS}
per_item = {}
for qid, r in out["A"].items():
    for L in "abcd":
        n = norm(r[L])
        for p in PATS:
            if p in n:
                hits[p] += 1
                per_item.setdefault(qid, []).append((L, r[L][:90], L == r["correct_letter"]))
print("pattern hits in condition A options:", hits)
print("condition-A items with any NOTA/aggregate-style option:", len(per_item))
for qid, v in list(per_item.items())[:25]:
    print(qid, v)

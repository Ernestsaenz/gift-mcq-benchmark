"""Independent pull of stems + shipped negated_stem flag. Read-only on the DB."""
import json, sqlite3, sys, unicodedata

DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"
PJ = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
OUT = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/mech_r02_stems.json"

recs = json.load(open(PJ))
recs = [r for r in recs if r.get("analysis_include")]
flag = {}
for r in recs:
    q = r["question_id"]
    f = bool(r["negated_stem"])
    if q in flag and flag[q] != f:
        sys.exit("flag inconsistent across cells for " + q)
    flag[q] = f
print("items in paired_clean (analysis_include):", len(flag))
print("cells:", len(recs))
print("flag True items:", sum(flag.values()))

con = sqlite3.connect(DB, uri=True)
cur = con.cursor()
ds = dict(cur.execute("select name,id from datasets").fetchall())
print("datasets:", ds)

def pull(name):
    did = ds[name]
    out = {}
    for qid, qt, a, b, c, d, cl in cur.execute(
        "select question_id,question_text,option_a,option_b,option_c,option_d,correct_letter "
        "from questions where dataset_id=?", (did,)):
        out[qid] = dict(question_text=qt, a=a, b=b, c=c, d=d, correct=cl)
    return out

A = pull("balanced_a_310726")
B = pull("balanced_b_310726")
print("A rows:", len(A), "B rows:", len(B))

missing = [q for q in flag if q not in A or q not in B]
print("missing from DB:", missing)

same = sum(1 for q in flag if A[q]["question_text"] == B[q]["question_text"])
print("stems byte-identical A vs B: %d/%d" % (same, len(flag)))

# also: raw bytes / normalisation check
nfc_diff = sum(1 for q in flag
               if unicodedata.normalize("NFC", A[q]["question_text"]) != A[q]["question_text"])
print("stems not NFC-normalised:", nfc_diff)

data = {q: dict(stem=A[q]["question_text"], flag=flag[q],
                correct=A[q]["correct"],
                optsA=[A[q][k] for k in "abcd"],
                optsB=[B[q][k] for k in "abcd"]) for q in sorted(flag)}
json.dump(data, open(OUT, "w"), ensure_ascii=False, indent=0)
print("wrote", OUT)

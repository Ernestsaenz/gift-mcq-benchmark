"""Build the who-recovers analysis table: paired cells + item text features from the DB."""
import json, sqlite3, os, re, unicodedata

BASE = os.path.dirname(os.path.abspath(__file__))
DB = "file:" + os.path.join(os.path.dirname(BASE), "experiment.sqlite") + "?mode=ro"

def norm(s):
    s = unicodedata.normalize("NFKD", s or "").lower()
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip()

con = sqlite3.connect(DB, uri=True)
ds = dict(con.execute("select name,id from datasets"))
QA, QB = {}, {}
for name, tgt in (("balanced_a_310726", QA), ("balanced_b_310726", QB)):
    for row in con.execute(
        "select question_id,question_text,option_a,option_b,option_c,option_d,"
        "correct_letter,correct_option_text,region,year,exam_part,specialty "
        "from questions where dataset_id=?", (ds[name],)):
        tgt[row[0]] = dict(zip(
            "question_id question_text option_a option_b option_c option_d "
            "correct_letter correct_option_text region year exam_part specialty".split(), row))

cells = [r for r in json.load(open(os.path.join(BASE, "paired_clean.json")))
         if r["analysis_include"]]

NOTA_RE = re.compile(r"ningun[ao]\s+de\s+la[s]?\s+(respuestas|opciones|anteriores)")
COMBO_RE = re.compile(r"(las\s+respuestas?\s+[a-d]\)?\s*(y|,)|todas\s+las\s+(respuestas|anteriores|opciones)|son\s+correctas)")
ALLOF_RE = re.compile(r"todas\s+(las\s+)?(respuestas\s+)?(las\s+)?(anteriores|opciones|son\s+correctas)")

items = {}
for r in cells:
    qid = r["question_id"]
    if qid in items:
        continue
    a, b = QA[qid], QB[qid]
    L = a["correct_letter"]
    opts = {k: a["option_" + k] for k in "abcd"}
    optsB = {k: b["option_" + k] for k in "abcd"}
    # verify design: B == A except the correct-letter slot which is NOTA
    same_others = all(norm(opts[k]) == norm(optsB[k]) for k in "abcd" if k != L)
    b_is_nota = bool(NOTA_RE.search(norm(optsB[L])))
    ctext = opts[L]
    lens = {k: len(v) for k, v in opts.items()}
    dis = [v for k, v in opts.items() if k != L]
    items[qid] = dict(
        question_id=qid, correct_letter=L,
        same_others=same_others, b_is_nota=b_is_nota,
        stem_len=len(a["question_text"]),
        correct_len=len(ctext),
        mean_distractor_len=sum(len(x) for x in dis) / 3.0,
        len_rank=sorted(lens.values(), reverse=True).index(lens[L]),  # 0 = longest
        is_longest=int(lens[L] == max(lens.values())),
        correct_is_combo=int(bool(COMBO_RE.search(norm(ctext)))),
        correct_is_allof=int(bool(ALLOF_RE.search(norm(ctext)))),
        distractor_has_nota=int(any(NOTA_RE.search(norm(x)) for x in dis)),
        distractor_has_combo=int(any(COMBO_RE.search(norm(x)) for x in dis)),
        region=a["region"], year=a["year"], exam_part=a["exam_part"],
        specialty=a["specialty"],
        correct_text=ctext, question_text=a["question_text"], options=opts,
        nota_text=optsB[L],
    )

# leave-one-model-out condition-A difficulty per item
byitem = {}
for r in cells:
    byitem.setdefault(r["question_id"], []).append(r)
for r in cells:
    peers = [x for x in byitem[r["question_id"]] if x["model"] != r["model"]]
    r["loo_A_acc"] = sum(x["A_correct"] for x in peers) / len(peers)
    r["loo_B_acc"] = sum(x["B_correct"] for x in peers) / len(peers)
    r["n_peers"] = len(peers)
    it = items[r["question_id"]]
    for k in ("stem_len correct_len mean_distractor_len len_rank is_longest "
              "correct_is_combo correct_is_allof distractor_has_nota distractor_has_combo "
              "region year exam_part specialty same_others b_is_nota").split():
        r[k] = it[k]
    r["lost"] = int(r["A_correct"] == 1 and r["B_correct"] == 0)
    r["gained"] = int(r["A_correct"] == 0 and r["B_correct"] == 1)

if __name__ == "__main__":
    print("cells", len(cells), "items", len(items))
    print("design check: all B==A except correct slot:",
          all(i["same_others"] for i in items.values()))
    print("design check: B correct slot is NOTA:",
          all(i["b_is_nota"] for i in items.values()))
    import collections
    print("correct letter:", collections.Counter(i["correct_letter"] for i in items.values()))
    print("correct_is_combo:", sum(i["correct_is_combo"] for i in items.values()))
    print("correct_is_allof:", sum(i["correct_is_allof"] for i in items.values()))
    print("distractor_has_nota:", sum(i["distractor_has_nota"] for i in items.values()))
    print("distractor_has_combo:", sum(i["distractor_has_combo"] for i in items.values()))
    print("is_longest:", sum(i["is_longest"] for i in items.values()), "/", len(items))
    print("nota texts:", collections.Counter(i["nota_text"] for i in items.values()).most_common(3))

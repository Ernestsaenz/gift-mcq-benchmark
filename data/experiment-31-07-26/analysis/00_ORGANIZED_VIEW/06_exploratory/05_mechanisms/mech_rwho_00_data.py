"""Independent rebuild of the who-recovers analysis table straight from the DB."""
import json, os, re, sqlite3, unicodedata

BASE = os.path.dirname(os.path.abspath(__file__))
DB = "file:" + os.path.join(os.path.dirname(BASE), "experiment.sqlite") + "?mode=ro"

MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]


def nrm(s):
    s = unicodedata.normalize("NFKD", s or "").lower()
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip()


def load():
    con = sqlite3.connect(DB, uri=True)
    ds = dict(con.execute("select name,id from datasets"))
    QA, QB = {}, {}
    cols = ("question_id question_text option_a option_b option_c option_d correct_letter "
            "correct_option_text region year exam_part specialty").split()
    for name, tgt in (("balanced_a_310726", QA), ("balanced_b_310726", QB)):
        for row in con.execute(
                "select " + ",".join(cols) + " from questions where dataset_id=?", (ds[name],)):
            tgt[row[0]] = dict(zip(cols, row))
    con.close()

    cells = [r for r in json.load(open(os.path.join(BASE, "paired_clean.json")))
             if r["analysis_include"]]

    keep = set(r["question_id"] for r in cells)
    item = {}
    for qid in sorted(keep):
        a = QA[qid]
        L = a["correct_letter"]
        o = {k: a["option_" + k] for k in "abcd"}
        dis = [o[k] for k in "abcd" if k != L]
        wl = lambda s: len(nrm(s).split())
        item[qid] = dict(
            correct_letter=L,
            correct_chars=len(o[L]),
            correct_words=wl(o[L]),
            mean_dis_chars=sum(len(x) for x in dis) / 3.0,
            mean_dis_words=sum(wl(x) for x in dis) / 3.0,
            max_dis_chars=max(len(x) for x in dis),
            is_longest=int(len(o[L]) == max(len(v) for v in o.values())),
            len_rank=sorted((len(v) for v in o.values()), reverse=True).index(len(o[L])),
            stem_chars=len(a["question_text"]),
            stem_words=wl(a["question_text"]),
            year=a["year"], region=a["region"], exam_part=a["exam_part"],
            specialty=a["specialty"],
            correct_text=o[L], stem=a["question_text"], options=o,
            nota_text=QB[qid]["option_" + L],
        )

    byq = {}
    for r in cells:
        byq.setdefault(r["question_id"], []).append(r)
    for r in cells:
        peers = [x for x in byq[r["question_id"]] if x["model"] != r["model"]]
        r["loo_A_acc"] = sum(x["A_correct"] for x in peers) / len(peers)
        r["loo_B_acc"] = sum(x["B_correct"] for x in peers) / len(peers)
        r["n_peers"] = len(peers)
        r.update({k: v for k, v in item[r["question_id"]].items()
                  if k not in ("correct_letter",)})
        r["lost"] = int(r["A_correct"] == 1 and r["B_correct"] == 0)
        r["gained"] = int(r["A_correct"] == 0 and r["B_correct"] == 1)
        # relative length of the correct option vs its own distractors
        r["len_ratio"] = r["correct_chars"] / max(r["mean_dis_chars"], 1.0)
        r["len_diff_w"] = r["correct_words"] - r["mean_dis_words"]
    return cells, item


cells, items = load()

if __name__ == "__main__":
    import collections
    print("cells", len(cells), "items", len(items))
    Ac = [r for r in cells if r["A_correct"]]
    print("A-correct cells", len(Ac), "lost", sum(r["lost"] for r in Ac),
          "clusters", len(set(r["cluster"] for r in Ac)))
    print("letter:", collections.Counter(r["correct_letter"] for r in cells))
    print("years:", collections.Counter(r["year"] for r in cells))
    print("is_longest items:", sum(items[q]["is_longest"] for q in items), "/", len(items))
    print("nota text unique:", len(set(items[q]["nota_text"] for q in items)))

"""Independent build of the P(lost | A correct) analysis frame straight from the DB."""
import json, sqlite3, os, re, math, unicodedata, collections

BASE = os.path.dirname(os.path.abspath(__file__))
DB = "file:" + os.path.join(os.path.dirname(BASE), "experiment.sqlite") + "?mode=ro"

MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").lower()
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip()


con = sqlite3.connect(DB, uri=True)
ds = dict(con.execute("select name,id from datasets"))
QA, QB = {}, {}
COLS = ("question_id question_text option_a option_b option_c option_d correct_letter "
        "correct_option_text region year exam_part specialty question_number").split()
for name, tgt in (("balanced_a_310726", QA), ("balanced_b_310726", QB)):
    for row in con.execute(
            "select " + ",".join(COLS) + " from questions where dataset_id=?", (ds[name],)):
        tgt[row[0]] = dict(zip(COLS, row))

cells = [r for r in json.load(open(os.path.join(BASE, "paired_clean.json")))
         if r["analysis_include"]]

NOTA_RE = re.compile(r"ningun[ao]\s+(de\s+)?la[s]?\s+(respuestas?|opciones|anteriores)|"
                     r"ningun[ao]\s+de\s+las\s+anteriores")
COMBO_RE = re.compile(r"(respuestas?\s+[a-d]\s*(y|,|\+)\s*[a-d])|son\s+correctas|"
                      r"son\s+ciertas|son\s+verdaderas")
ALLOF_RE = re.compile(r"todas\s+(las\s+)?(respuestas\s+|opciones\s+|anteriores\s+)?"
                      r"(son\s+correctas|anteriores|las\s+anteriores|son\s+ciertas)")
NUM_RE = re.compile(r"^[^a-z]*\d")
TOK = re.compile(r"[a-z0-9]+")


def toks(s):
    return set(TOK.findall(norm(s)))


items = {}
for r in cells:
    qid = r["question_id"]
    if qid in items:
        continue
    a, b = QA[qid], QB[qid]
    L = a["correct_letter"]
    opts = {k: a["option_" + k] for k in "abcd"}
    optsB = {k: b["option_" + k] for k in "abcd"}
    ct = opts[L]
    dis = [v for k, v in opts.items() if k != L]
    lens = {k: len(v) for k, v in opts.items()}
    stem_t = toks(a["question_text"])
    # stem-overlap of the correct option relative to the distractors: a surface
    # "matchability" cue that a recognition shortcut would exploit
    def ov(x):
        t = toks(x)
        return len(t & stem_t) / max(len(t), 1)
    items[qid] = dict(
        question_id=qid, correct_letter=L,
        same_others=all(norm(opts[k]) == norm(optsB[k]) for k in "abcd" if k != L),
        b_is_nota=bool(NOTA_RE.search(norm(optsB[L]))),
        stem_len=len(a["question_text"]),
        correct_len=len(ct),
        mean_distractor_len=sum(len(x) for x in dis) / 3.0,
        len_gap=len(ct) - sum(len(x) for x in dis) / 3.0,
        log_len_ratio=math.log(max(len(ct), 1)) - math.log(max(sum(len(x) for x in dis) / 3.0, 1)),
        len_rank=sorted(lens.values(), reverse=True).index(lens[L]),
        is_longest=int(lens[L] == max(lens.values())),
        is_shortest=int(lens[L] == min(lens.values())),
        correct_is_combo=int(bool(COMBO_RE.search(norm(ct)))),
        correct_is_allof=int(bool(ALLOF_RE.search(norm(ct)))),
        distractor_has_nota=int(any(NOTA_RE.search(norm(x)) for x in dis)),
        distractor_has_combo=int(any(COMBO_RE.search(norm(x)) for x in dis)),
        correct_is_numeric=int(bool(NUM_RE.match(norm(ct)))),
        n_opt_words=len(TOK.findall(norm(ct))),
        stem_overlap_correct=ov(ct),
        stem_overlap_gap=ov(ct) - sum(ov(x) for x in dis) / 3.0,
        nota_len=len(optsB[L]),
        nota_is_longest=int(len(optsB[L]) == max([len(optsB[k]) for k in "abcd"])),
        nota_is_shortest=int(len(optsB[L]) == min([len(optsB[k]) for k in "abcd"])),
        region=a["region"], year=a["year"], exam_part=a["exam_part"], specialty=a["specialty"],
        correct_text=ct, question_text=a["question_text"], options=opts, nota_text=optsB[L],
    )

byitem = collections.defaultdict(list)
for r in cells:
    byitem[r["question_id"]].append(r)
for r in cells:
    peers = [x for x in byitem[r["question_id"]] if x["model"] != r["model"]]
    r["loo_A_acc"] = sum(x["A_correct"] for x in peers) / len(peers)
    r["loo_B_acc"] = sum(x["B_correct"] for x in peers) / len(peers)
    r["n_peers"] = len(peers)
    r.update({k: v for k, v in items[r["question_id"]].items()
              if k not in ("options", "correct_text", "question_text", "nota_text")})
    r["lost"] = int(r["A_correct"] == 1 and r["B_correct"] == 0)
    r["gained"] = int(r["A_correct"] == 0 and r["B_correct"] == 1)
    r["picked_nota_B"] = int(r["B_selected"] == r["correct_letter"]) if r["B_selected"] else 0

if __name__ == "__main__":
    Ac = [r for r in cells if r["A_correct"] == 1]
    print("cells", len(cells), "items", len(items), "clusters", len(set(r["cluster"] for r in cells)))
    print("A-correct rows", len(Ac), " lost events", sum(r["lost"] for r in Ac),
          " clusters", len(set(r["cluster"] for r in Ac)))
    print("design check same_others:", all(i["same_others"] for i in items.values()))
    print("design check b_is_nota:", all(i["b_is_nota"] for i in items.values()))
    print("correct letter:", collections.Counter(i["correct_letter"] for i in items.values()))
    for f in ("correct_is_combo correct_is_allof distractor_has_nota distractor_has_combo "
              "is_longest is_shortest correct_is_numeric nota_is_longest nota_is_shortest").split():
        print(f"  {f:<24}{sum(i[f] for i in items.values()):>4} / {len(items)}")
    print("A-accuracy by model:")
    for m in MODELS:
        rows = [r for r in cells if r["model"] == m]
        print(f"  {m:<28} A={sum(r['A_correct'] for r in rows)/len(rows):.3f} "
              f"B={sum(r['B_correct'] for r in rows)/len(rows):.3f} n={len(rows)}")

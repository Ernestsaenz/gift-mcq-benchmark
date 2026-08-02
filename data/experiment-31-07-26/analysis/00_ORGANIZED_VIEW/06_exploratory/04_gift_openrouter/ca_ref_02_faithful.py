#!/usr/bin/env python
"""Field-by-field faithfulness audit of cross_arm_A.json against experiment.sqlite.

The who-benefits claim checked 4 fields. This checks every field that the DB can adjudicate.
"""
import json, collections, sqlite3

AN = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/"
DB = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite"
J = json.load(open(AN + "cross_arm_A.json"))
P = json.load(open(AN + "ca_ref_00_pull.json"))
gift = {tuple(k.split("|")[:2]): v for k, v in P["gift"].items()}
orr  = {tuple(k.split("|")[:2]): v for k, v in P["or"].items()}

con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
con.row_factory = sqlite3.Row
qmeta = {}
for r in con.execute("""SELECT q.question_id qid, q.region, q.year, q.exam_part, q.correct_letter,
                               q.question_text, q.option_a, q.option_b, q.option_c, q.option_d
                        FROM questions q JOIN datasets d ON d.id=q.dataset_id
                        WHERE d.name='balanced_a_310726'"""):
    qmeta[r["qid"]] = dict(r)
print("dataset balanced_a_310726 items:", len(qmeta))

cells = [c for c in J if c["analysis_include"]]

# which correctness flag reproduces gift_correct / or_correct?
for flag in ("letter_correct", "strict_correct", "lenient_correct", "text_correct"):
    mg = sum(1 for c in cells if gift[(c["question_id"], c["model"])][flag] != c["gift_correct"])
    mo = sum(1 for c in cells if orr[(c["question_id"], c["model"])][flag] != c["or_correct"])
    print("flag %-16s gift mismatches=%4d  or mismatches=%4d" % (flag, mg, mo))

# qlen definition candidates
for name, fn in (("question_text", lambda q: len(q["question_text"])),
                 ("stem+4opts", lambda q: len(q["question_text"]) + sum(len(q["option_" + x]) for x in "abcd")),
                 ("stem_stripped", lambda q: len(q["question_text"].strip()))):
    mm = sum(1 for c in cells if fn(qmeta[c["question_id"]]) != c["qlen"])
    print("qlen == %-14s mismatches=%d" % (name, mm))

# full field-by-field
mis = collections.Counter()
examples = collections.defaultdict(list)
for c in cells:
    q = qmeta[c["question_id"]]
    g = gift[(c["question_id"], c["model"])]
    o = orr[(c["question_id"], c["model"])]
    checks = [
        ("region", q["region"], c["region"]),
        ("year", q["year"], c["year"]),
        ("exam_part", q["exam_part"], c["exam_part"]),
        ("correct_letter", q["correct_letter"], c["correct_letter"]),
        ("gift_correct", g["letter_correct"], c["gift_correct"]),
        ("or_correct", o["letter_correct"], c["or_correct"]),
        ("gift_selected", g["selected_letter"], c["gift_selected"]),
        ("or_selected", o["selected_letter"], c["or_selected"]),
        ("gift_latency_ms", g["latency_ms"], c["gift_latency_ms"]),
        ("or_latency_ms", o["latency_ms"], c["or_latency_ms"]),
        ("gift_tokens_total", g["total_tokens"], c["gift_tokens"]),
        ("or_tokens_total", o["total_tokens"], c["or_tokens"]),
        ("gift_tokens_completion", g["completion_tokens"], c["gift_tokens"]),
        ("or_tokens_completion", o["completion_tokens"], c["or_tokens"]),
    ]
    for nm, db, js in checks:
        if db != js:
            mis[nm] += 1
            if len(examples[nm]) < 4:
                examples[nm].append((c["question_id"], c["model"], "db=%r" % (db,), "json=%r" % (js,)))
print("\n--- field mismatch counts over %d analysis cells ---" % len(cells))
for k in ["region", "year", "exam_part", "correct_letter", "gift_correct", "or_correct",
          "gift_selected", "or_selected", "gift_latency_ms", "or_latency_ms",
          "gift_tokens_total", "or_tokens_total", "gift_tokens_completion", "or_tokens_completion"]:
    print("  %-24s %5d" % (k, mis[k]))
    for e in examples[k]: print("        ", e)

# parse status of the analysed cells
ps = collections.Counter()
for c in cells:
    ps[("gift", gift[(c["question_id"], c["model"])]["parse_status"])] += 1
    ps[("or", orr[(c["question_id"], c["model"])]["parse_status"])] += 1
print("\nparse_status of analysed cells:", dict(ps))

# excluded 32 rows: are they exactly the defect items?
exc = sorted(set(c["question_id"] for c in J if not c["analysis_include"]))
print("\nexcluded item ids:", exc)
meta = json.load(open(AN + "dataset_meta.json"))
defect = set(meta["exclusions"]["administrative_legal_out_of_domain"]) | set(meta["exclusions"]["adjudicated_key_defect"])
print("excluded subset of documented 14-item defect list:", set(exc) <= defect)
print("excl_item_defect flag == not analysis_include:",
      all(c["excl_item_defect"] != c["analysis_include"] for c in J))

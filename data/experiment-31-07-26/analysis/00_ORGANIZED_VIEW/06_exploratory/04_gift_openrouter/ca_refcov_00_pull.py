"""ca_refcov_00: independent read-only pull + export inventory.
Refutation pass on the "coverage-bias" claim. Stdlib only.
"""
import sqlite3, json, os, hashlib

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.path.dirname(BASE), "experiment.sqlite")

MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]

out = {}

for f in ["cross_arm_A.json", "gift_coverage.json", "dataset_meta.json",
          "paired_clean.json"]:
    p = os.path.join(BASE, f)
    if os.path.exists(p):
        out.setdefault("md5", {})[f] = hashlib.md5(open(p, "rb").read()).hexdigest()

meta = json.load(open(os.path.join(BASE, "dataset_meta.json")))
out["meta_export_version"] = meta.get("export_version")
out["meta_exclusion_keys"] = sorted(meta["exclusions"].keys())
out["meta_counts"] = meta["counts"]
out["meta_superseded"] = meta.get("superseded_v1_counts")
out["md5_recorded_in_meta"] = meta.get("file_md5")

ca = json.load(open(os.path.join(BASE, "cross_arm_A.json")))
rows = None
if isinstance(ca, list):
    rows = ca
else:
    for k, v in ca.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            rows = v
            out["export_list_key"] = k
            break
inc = [r for r in rows if r.get("analysis_include")]
out["export"] = {
    "top_keys": sorted(ca.keys()) if isinstance(ca, dict) else "list",
    "n_rows": len(rows),
    "n_include": len(inc),
    "n_items_include": len(set(r["question_id"] for r in inc)),
    "n_clusters_include": len(set(r["cluster"] for r in inc)),
    "n_items_all": len(set(r["question_id"] for r in rows)),
    "row_keys": sorted(rows[0].keys()),
}
if isinstance(ca, dict):
    out["export"]["meta_block"] = {k: v for k, v in ca.items()
                                   if not isinstance(v, list)}

con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
con.row_factory = sqlite3.Row

items = {}
for r in con.execute("""
    SELECT q.id AS rid, q.question_id AS qid, q.region, q.year, q.exam_part,
           q.correct_letter, q.question_number, LENGTH(q.question_text) AS qlen
    FROM questions q JOIN datasets d ON d.id=q.dataset_id
    WHERE d.name='balanced_a_310726' ORDER BY q.id"""):
    items[r["qid"]] = dict(r)
for i, qid in enumerate(items):
    items[qid]["order_rid"] = i
out["n_items_datasetA"] = len(items)

cells = {}
dup = 0
n_rows_db = 0
for r in con.execute("""
    SELECT e.name AS exp, lc.model AS model, q.question_id AS qid,
           s.letter_correct AS lc_, s.strict_correct AS sc_,
           pa.parse_status AS ps, pa.selected_letter AS sel,
           pat.created_at AS att_created
    FROM scores s
    JOIN logical_calls lc ON lc.id=s.logical_call_id
    JOIN experiments e ON e.id=lc.experiment_id
    JOIN questions q ON q.id=lc.question_id
    JOIN parsed_answers pa ON pa.id=s.parsed_answer_id
    JOIN provider_attempts pat ON pat.id=pa.provider_attempt_id
    WHERE e.name IN ('expA_or_310726','expA_gift_310726')"""):
    n_rows_db += 1
    k = (r["exp"], r["model"], r["qid"])
    if k in cells:
        dup += 1
    cells[k] = {"lc": r["lc_"], "sc": r["sc_"], "ps": r["ps"],
                "sel": r["sel"], "t": r["att_created"]}
out["db_score_rows"] = n_rows_db
out["db_distinct_cells"] = len(cells)
out["db_duplicate_cells"] = dup

per = {}
ps_ = {}
for (exp, m, q), v in cells.items():
    per.setdefault(exp, {}).setdefault(m, 0)
    per[exp][m] += 1
    ps_.setdefault(exp, {}).setdefault(str(v["ps"]), 0)
    ps_[exp][str(v["ps"])] += 1
out["db_per_exp_model"] = per
out["db_parse_status"] = ps_

json.dump({"items": items,
           "cells": [{"exp": k[0], "model": k[1], "qid": k[2], **v}
                     for k, v in cells.items()]},
          open(os.path.join(BASE, "ca_refcov_grid.json"), "w"))

print(json.dumps(out, indent=1, sort_keys=True))

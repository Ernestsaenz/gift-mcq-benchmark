"""REFUTATION pass 1 on 'error-destinations': recount volumes, test whether the
'no nulls / no mis-scored NOTA' checks have any power, and pull the DB-side
ground truth for every included cell. Stdlib only. READ-ONLY on the DB."""
import json, sqlite3, collections, math, unicodedata, re

BASE = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26"
DB = f"file:{BASE}/experiment.sqlite?mode=ro"
PAIRED = f"{BASE}/analysis/paired_clean.json"
LET = ["a", "b", "c", "d"]

rows = json.load(open(PAIRED))
inc = [r for r in rows if r["analysis_include"]]

print("=" * 78)
print("0. RECOUNT FROM paired_clean.json (analysis_include==true)")
print("=" * 78)
nA = sum(1 - c["A_correct"] for c in inc)
nB = sum(1 - c["B_correct"] for c in inc)
print(f"cells={len(inc)}  items={len(set(c['question_id'] for c in inc))} "
      f"clusters={len(set(c['cluster'] for c in inc))} models={len(set(c['model'] for c in inc))}")
print(f"A errors={nA} ({nA/len(inc):.4%})   B errors={nB} ({nB/len(inc):.4%})")
for m in sorted(set(c["model"] for c in inc)):
    r = [c for c in inc if c["model"] == m]
    a = sum(1 - c["A_correct"] for c in r); b = sum(1 - c["B_correct"] for c in r)
    print(f"  {m:28s} n={len(r):4d} A_err={a:3d} B_err={b:3d} delta={b-a:+d}")

print()
print("expected cells if the design were complete: 325 items x 4 models =", 325 * 4)
byq = collections.Counter(c["question_id"] for c in inc)
short = {q: n for q, n in byq.items() if n != 4}
print("items NOT covered by all 4 models:", short)
allrows = collections.Counter((r["question_id"], r["model"]) for r in rows)
print("rows in the FULL paired file:", len(rows),
      " unique (item,model):", len(allrows))

print()
print("=" * 78)
print("1. DO THE 'NO NULL / NO MIS-SCORED NOTA' CHECKS HAVE ANY POWER?")
print("=" * 78)
bad = [c for c in inc if c["B_correct"] != int(c["B_selected"] == c["correct_letter"])]
badA = [c for c in inc if c["A_correct"] != int(c["A_selected"] == c["correct_letter"])]
print(f"rows where B_correct != (B_selected==correct_letter): {len(bad)}")
print(f"rows where A_correct != (A_selected==correct_letter): {len(badA)}")
print("-> if both are 0, the tests 'null selected' and 'B error picked the NOTA "
      "letter' are algebraic identities of the file, not empirical findings.")
print("   selected-letter alphabet A:", sorted(set(c["A_selected"] for c in inc)),
      " B:", sorted(set(c["B_selected"] for c in inc)))

print()
print("=" * 78)
print("2. DB GROUND TRUTH FOR THE SAME CELLS (OR arm)")
print("=" * 78)
con = sqlite3.connect(DB, uri=True)
con.row_factory = sqlite3.Row

# every parsed answer, every attempt, for the two OR experiments
q = """
select e.name exp, lc.model model, qq.question_id qid, lc.id lcid,
       pa.id paid, pa.attempt_index, pa.status_code, pa.finish_reason,
       pa.completion_tokens, pa.latency_ms,
       ps.id psid, ps.parse_status, ps.parse_method, ps.selected_letter,
       ps.selected_letter_raw, ps.selected_option_text, ps.selected_option_text_raw,
       ps.exact_text_match, ps.letter_text_conflict, ps.notes,
       sc.letter_correct, sc.text_correct, sc.strict_correct, sc.lenient_correct,
       sc.answer_text_matches_provided, qq.correct_letter
from provider_attempts pa
join logical_calls lc on lc.id = pa.logical_call_id
join experiments e on e.id = lc.experiment_id
join questions qq on qq.id = lc.question_id
left join parsed_answers ps on ps.provider_attempt_id = pa.id
left join scores sc on sc.parsed_answer_id = ps.id
where e.name in ('expA_or_310726','expB_or_310726')
order by e.name, lc.model, qq.question_id, pa.attempt_index
"""
att = [dict(r) for r in con.execute(q)]
print("provider attempts in OR arm:", len(att))
cond = {"expA_or_310726": "A", "expB_or_310726": "B"}
bykey = collections.defaultdict(list)
for r in att:
    bykey[(cond[r["exp"]], r["model"], r["qid"])].append(r)

inc_keys = set((c["question_id"], c["model"]) for c in inc)

# ---- 2a. attempts that produced NO answer (non-commitment), restricted to
#          the exact (item,model) cells used in the analysis
print()
print("2a. NON-ANSWERING ATTEMPTS ON THE ANALYSED CELLS")
tab = {}
for C in "AB":
    n_cell_any = 0
    n_att = 0
    n_fail_att = 0
    fail_cells = []
    for (qid, m) in inc_keys:
        a = bykey.get((C, m, qid), [])
        if not a:
            continue
        n_cell_any += 1
        n_att += len(a)
        f = [x for x in a if x["parse_status"] != "ok"]
        n_fail_att += len(f)
        if f:
            fail_cells.append((m, qid, len(f), len(a),
                               collections.Counter(x["finish_reason"] for x in f)))
    tab[C] = (n_cell_any, n_att, n_fail_att, fail_cells)
    print(f"  cond {C}: cells={n_cell_any} attempts={n_att} "
          f"non-answering attempts={n_fail_att} cells needing >=1 retry={len(fail_cells)} "
          f"({len(fail_cells)/n_cell_any:.2%})")
for C in "AB":
    per = collections.Counter(f[0] for f in tab[C][3])
    print(f"  cond {C} retry-cells by model: {dict(per)}")
    fr = collections.Counter()
    for f in tab[C][3]:
        fr.update(f[4])
    print(f"  cond {C} finish_reason of the non-answering attempts: {dict(fr)}")

json.dump({"attempts": att}, open(f"{BASE}/analysis/mech_ref_dest_attempts.json", "w"))
print("\ncached attempts ->", f"{BASE}/analysis/mech_ref_dest_attempts.json")

"""REFUTATION pass 2: are any B 'errors' actually NOTA selections that the
letter-only scorer counted as distractor picks?  Two routes:
  (i) the surviving distractor the model picked is ITSELF a none-of-the-above /
      catch-all option (native NOTA, 'todas las anteriores', 'a y b', ...);
  (ii) the model's free-text answer names the NOTA string but the parser bound a
       different letter (letter_text_conflict / text vs letter disagreement).
Stdlib only. READ-ONLY on the DB."""
import json, sqlite3, collections, re, unicodedata, math

BASE = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26"
DB = f"file:{BASE}/experiment.sqlite?mode=ro"
LET = ["a", "b", "c", "d"]
IDX = {"a": 0, "b": 1, "c": 2, "d": 3}

inc = [r for r in json.load(open(f"{BASE}/analysis/paired_clean.json"))
       if r["analysis_include"]]

con = sqlite3.connect(DB, uri=True)
opts = {"A": {}, "B": {}}
for ds, k in (("balanced_a_310726", "A"), ("balanced_b_310726", "B")):
    for r in con.execute(
        "select q.question_id,q.option_a,q.option_b,q.option_c,q.option_d,"
        "q.correct_letter,q.correct_option_text,q.question_text from questions q "
        "join datasets d on d.id=q.dataset_id where d.name=?", (ds,)):
        opts[k][r[0]] = {"a": r[1], "b": r[2], "c": r[3], "d": r[4],
                         "correct_letter": r[5], "correct_text": r[6], "qtext": r[7]}


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.split()).strip(" .")


NOTA = norm("Ninguna de las respuestas anteriores es correcta.")

print("=" * 78)
print("A. SANITY: does the B arm actually carry the NOTA string at the key slot?")
print("=" * 78)
qids = sorted(set(c["question_id"] for c in inc))
bad = [q for q in qids if norm(opts["B"][q][opts["B"][q]["correct_letter"]]) != NOTA]
print(f"analysis items={len(qids)}  key slot NOT the NOTA string: {len(bad)} {bad[:10]}")
dd = [(q, L) for q in qids for L in LET
      if L != opts["A"][q]["correct_letter"]
      and norm(opts["A"][q][L]) != norm(opts["B"][q][L])]
print(f"surviving-distractor texts that differ between A and B: {len(dd)} {dd[:10]}")

print()
print("=" * 78)
print("B. CATCH-ALL / NOTA-LIKE OPTIONS AMONG THE SURVIVING DISTRACTORS")
print("=" * 78)
PAT = [
    ("nota_ninguna", re.compile(r"^ningun[ao]\b")),
    ("nota_ninguna_mid", re.compile(r"\bningun[ao] de (las|los|ellas|ellos|estas|estos)\b")),
    ("todas_anteriores", re.compile(r"\btodas? (las|los)? ?(respuestas|anteriores|opciones|son correctas)")),
    ("son_correctas", re.compile(r"\bson correctas\b")),
    ("combo_ayb", re.compile(r"^(las respuestas? )?[abcd]( y | e |,)\s*[abcd]\b")),
]


def flags(t):
    n = norm(t)
    return [nm for nm, p in PAT if p.search(n)]


surv_flagged = collections.Counter()
item_has = collections.defaultdict(dict)
for q in qids:
    cl = opts["B"][q]["correct_letter"]
    for L in LET:
        if L == cl:
            continue
        f = flags(opts["B"][q][L])
        if f:
            item_has[q][L] = f
            surv_flagged[tuple(sorted(f))] += 1
print("surviving distractors matching a catch-all pattern:",
      sum(len(v) for v in item_has.values()), "over", len(item_has), "items")
for k, v in surv_flagged.most_common():
    print("   ", k, v)
for q in sorted(item_has)[:25]:
    for L, f in item_has[q].items():
        print(f"   {q} {L} {f} :: {opts['B'][q][L][:90]!r}")

print()
berr = [c for c in inc if not c["B_correct"]]
aerr = [c for c in inc if not c["A_correct"]]
hit_b = [c for c in berr if c["B_selected"] in item_has.get(c["question_id"], {})]
hit_a = [c for c in aerr if c["A_selected"] in item_has.get(c["question_id"], {})]
print(f"B errors landing on a catch-all surviving distractor: {len(hit_b)}/{len(berr)}"
      f" = {len(hit_b)/len(berr):.3%}")
print(f"A errors landing on the same options:                 {len(hit_a)}/{len(aerr)}"
      f" = {len(hit_a)/len(aerr):.3%}")
for c in hit_b[:20]:
    q = c["question_id"]
    print(f"   {q} {c['model']:26s} picked {c['B_selected']} :: "
          f"{opts['B'][q][c['B_selected']][:80]!r}")

print()
print("=" * 78)
print("C. TEXT-VS-LETTER DISAGREEMENT ON THE SCORED ATTEMPT")
print("=" * 78)
con.row_factory = sqlite3.Row
q = """
select e.name exp, lc.model model, qq.question_id qid, pa.attempt_index,
       ps.parse_status, ps.parse_method, ps.selected_letter, ps.selected_letter_raw,
       ps.selected_option_text, ps.selected_option_text_raw, ps.exact_text_match,
       ps.letter_text_conflict, ps.notes, sc.letter_correct, sc.text_correct,
       sc.strict_correct, sc.lenient_correct, sc.answer_text_matches_provided
from parsed_answers ps
join provider_attempts pa on pa.id = ps.provider_attempt_id
join logical_calls lc on lc.id = ps.logical_call_id
join experiments e on e.id = lc.experiment_id
join questions qq on qq.id = lc.question_id
left join scores sc on sc.parsed_answer_id = ps.id
where e.name in ('expA_or_310726','expB_or_310726') and ps.parse_status='ok'
"""
cond = {"expA_or_310726": "A", "expB_or_310726": "B"}
scored = {}
for r in con.execute(q):
    scored[(cond[r["exp"]], r["model"], r["qid"])] = dict(r)
print("scored ok answers pulled:", len(scored))

miss = [(c["question_id"], c["model"]) for c in inc
        if ("B", c["model"], c["question_id"]) not in scored
        or ("A", c["model"], c["question_id"]) not in scored]
print("analysis cells with no scored answer in the DB:", len(miss), miss[:5])

# consistency of paired_clean with the DB
mm = 0
for c in inc:
    for C in "AB":
        s = scored.get((C, c["model"], c["question_id"]))
        if s and s["selected_letter"] != c[f"{C}_selected"]:
            mm += 1
print("paired_clean selected letter != DB selected_letter:", mm)

for C, key in (("A", "A"), ("B", "B")):
    sub = [scored[(C, c["model"], c["question_id"])] for c in inc
           if (C, c["model"], c["question_id"]) in scored]
    print(f"\ncond {C}: n={len(sub)}")
    print("  parse_method:", dict(collections.Counter(s["parse_method"] for s in sub)))
    print("  letter_text_conflict:", dict(collections.Counter(s["letter_text_conflict"] for s in sub)))
    print("  exact_text_match:", dict(collections.Counter(s["exact_text_match"] for s in sub)))
    print("  answer_text_matches_provided:",
          dict(collections.Counter(s["answer_text_matches_provided"] for s in sub)))
    print("  letter_correct vs text_correct disagreements:",
          sum(1 for s in sub if s["letter_correct"] != s["text_correct"]))
    print("  strict vs lenient disagreements:",
          sum(1 for s in sub if s["strict_correct"] != s["lenient_correct"]))

print()
print("D. B ERRORS WHOSE FREE-TEXT ANSWER MENTIONS THE NOTA STRING")
nota_txt = 0
ex = []
for c in berr:
    s = scored.get(("B", c["model"], c["question_id"]))
    if not s:
        continue
    t = norm(s["selected_option_text_raw"] or "") + " || " + norm(s["selected_option_text"] or "")
    if "ningun" in t:
        nota_txt += 1
        ex.append((c["question_id"], c["model"], s["selected_letter"],
                   (s["selected_option_text_raw"] or "")[:100]))
print(f"  B errors whose parsed answer text contains 'ningun': {nota_txt}/{len(berr)}")
for e in ex[:15]:
    print("   ", e)

json.dump({"item_has": {k: v for k, v in item_has.items()}},
          open(f"{BASE}/analysis/mech_ref_dest_catchall.json", "w"))

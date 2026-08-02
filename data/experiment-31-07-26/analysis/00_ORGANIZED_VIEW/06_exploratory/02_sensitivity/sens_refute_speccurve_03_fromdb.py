"""Rebuild the paired cells straight from experiment.sqlite and test TWO axes the
160-spec grid never varies:

  (i)  the SCORING RULE  -- the DB stores letter_correct, text_correct,
       strict_correct and lenient_correct.  The published curve's "outcome" axis
       only toggles how ONE unparsed cell is handled; it never varies the rule
       that turns a response into a 0/1.
  (ii) construction defects other than position-a: items whose ORIGINAL options
       already contain a native "ninguna de ..." option (so arm B creates a
       duplicated / self-referential option set).
"""
import sqlite3, json, os, unicodedata, collections

HERE = os.path.dirname(os.path.abspath(__file__))
DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"
con = sqlite3.connect(DB, uri=True)
con.row_factory = sqlite3.Row

EXP = {"A": "expA_or_310726", "B": "expB_or_310726"}

q = """
SELECT e.name AS expname, qu.question_id AS qid, qu.correct_letter AS key,
       qu.option_a, qu.option_b, qu.option_c, qu.option_d,
       lc.model AS model, lc.run_index AS run,
       pa.parse_status AS pstatus, pa.selected_letter AS sel,
       pa.letter_text_conflict AS conflict,
       s.letter_correct AS letter_correct, s.text_correct AS text_correct,
       s.strict_correct AS strict_correct, s.lenient_correct AS lenient_correct
FROM logical_calls lc
JOIN experiments e   ON e.id = lc.experiment_id
JOIN questions   qu  ON qu.id = lc.question_id
LEFT JOIN parsed_answers pa ON pa.logical_call_id = lc.id
LEFT JOIN scores s          ON s.logical_call_id = lc.id
WHERE e.name IN (?, ?)
"""
raw = [dict(r) for r in con.execute(q, (EXP["A"], EXP["B"]))]
print("raw logical_calls rows pulled:", len(raw))
print("by experiment:", collections.Counter(r["expname"] for r in raw))
print("parse_status  :", collections.Counter(r["pstatus"] for r in raw))
print("letter_text_conflict:", collections.Counter(r["conflict"] for r in raw))

arm_of = {EXP["A"]: "A", EXP["B"]: "B"}
cells = {}
opts = {}
for r in raw:
    arm = arm_of[r["expname"]]
    cells.setdefault((r["qid"], r["model"]), {})[arm] = r
    opts.setdefault(arm, {})[r["qid"]] = r

# ---------------------------------------------------------------- 1. verify paired_clean
rows = json.load(open(os.path.join(HERE, "paired_clean.json")))
print("\n--- verify paired_clean.json against the DB (letter_correct scoring) ---")
bad_a = bad_b = missing = 0
for pr in rows:
    k = (pr["question_id"], pr["model"])
    c = cells.get(k)
    if not c or "A" not in c or "B" not in c:
        missing += 1
        continue
    if (c["A"]["letter_correct"] or 0) != pr["A_correct"]:
        bad_a += 1
    if (c["B"]["letter_correct"] or 0) != pr["B_correct"]:
        bad_b += 1
print(f"  cells not found in DB : {missing}")
print(f"  A_correct mismatches  : {bad_a}")
print(f"  B_correct mismatches  : {bad_b}")

# which paired cells exist in the DB with BOTH arms parsed
both_parsed = {k: v for k, v in cells.items()
               if "A" in v and "B" in v
               and v["A"]["pstatus"] == "ok" and v["B"]["pstatus"] == "ok"}
print("  DB cells with both arms parse_status=ok:", len(both_parsed))
print("  paired_clean rows                     :", len(rows))

# ---------------------------------------------------------------- 2. scoring-rule axis
meta_excl_defect = {r["question_id"] for r in rows if r["excl_item_defect"]}
notaA = {r["question_id"] for r in rows if r["excl_nota_position_a"]}
pc_keys = {(r["question_id"], r["model"]) for r in rows}


def delta(scorefield, keys):
    n = sA = sB = 0
    for k in keys:
        c = cells[k]
        a = c["A"][scorefield]
        b = c["B"][scorefield]
        if a is None or b is None:
            continue
        n += 1
        sA += a
        sB += b
    return 100.0 * (sB - sA) / n, n, 100.0 * sA / n, 100.0 * sB / n


print("\n--- (i) SCORING RULE axis, on the SAME 1299-cell primary analysis set ---")
primary_keys = [k for k in pc_keys
                if k[0] not in meta_excl_defect and k[0] not in notaA and k in cells]
print(f"    (primary set = {len(primary_keys)} cells)")
for f in ("letter_correct", "text_correct", "strict_correct", "lenient_correct"):
    d, n, aA, aB = delta(f, primary_keys)
    print(f"    {f:<18} N={n:>5}  accA={aA:>6.2f}  accB={aB:>6.2f}  delta={d:>8.3f}")

print("\n    same, on the full 'none' set:")
none_keys = [k for k in pc_keys if k in cells]
for f in ("letter_correct", "text_correct", "strict_correct", "lenient_correct"):
    d, n, aA, aB = delta(f, none_keys)
    print(f"    {f:<18} N={n:>5}  accA={aA:>6.2f}  accB={aB:>6.2f}  delta={d:>8.3f}")


# ---------------------------------------------------------------- 3. native NOTA
def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.split()).strip(" .")


NOTA = norm("Ninguna de las respuestas anteriores es correcta.")
native = {}
for qid, r in opts["A"].items():
    for L in "abcd":
        t = norm(r["option_" + L])
        if t.startswith("ninguna de la") or t.startswith("ninguna de ella") or t.startswith("ninguna de las anteriores") or t == NOTA:
            native[qid] = (L, L == r["key"], r["option_" + L])
            break
print(f"\n--- (ii) items whose ORIGINAL arm-A options already contain a native NOTA option: {len(native)} ---")
for qid, v in sorted(native.items())[:40]:
    print(f"    {qid}: slot={v[0]} is_key={v[1]} :: {v[2][:70]}")

nat_in_primary = {q for q in native if any(k[0] == q for k in primary_keys)}
print(f"    of which inside the 325-item primary set: {len(nat_in_primary)} -> {sorted(nat_in_primary)}")

if nat_in_primary:
    keys_excl = [k for k in primary_keys if k[0] not in nat_in_primary]
    keys_only = [k for k in primary_keys if k[0] in nat_in_primary]
    d0, n0, _, _ = delta("letter_correct", primary_keys)
    d1, n1, _, _ = delta("letter_correct", keys_excl)
    d2, n2, a2, b2 = delta("letter_correct", keys_only)
    print(f"    primary                       : N={n0} delta={d0:.3f}")
    print(f"    primary MINUS native-NOTA items: N={n1} delta={d1:.3f}")
    print(f"    the native-NOTA items alone    : N={n2} accA={a2:.2f} accB={b2:.2f} delta={d2:.3f}")

# ---------------------------------------------------------------- 4. b320 strict cell
print("\n--- b320 / z-ai/glm-5.2 (the cell the 'strict' outcome adds) ---")
for arm in ("A", "B"):
    c = cells.get(("b320", "z-ai/glm-5.2"), {}).get(arm)
    if c is None:
        print(f"    arm {arm}: NO logical_call row")
    else:
        print(f"    arm {arm}: parse_status={c['pstatus']!r} sel={c['sel']!r} key={c['key']!r} "
              f"letter_correct={c['letter_correct']}")

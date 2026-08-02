import sys, sqlite3, collections, math, re
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_ref_nota2_lib import *

d = load()
models = sorted({r["model"] for r in d})
DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"
con = sqlite3.connect(DB, uri=True)

# ---------------------------------------------------------------
# 1. Where do the A-ok / B-wrong cells go?  These are cells that PROVABLY had
#    the knowledge (they picked the true answer in A) and still refused NOTA.
# ---------------------------------------------------------------
aok_bwr = [r for r in d if r["A_correct"] and not r["B_correct"]]
print(f"=== cells with demonstrated knowledge (A correct) that still MISS B: n={len(aok_bwr)} ===")
print(f"    ({len(aok_bwr)} cells) vs the 45 A-wrong->B-correct cells the claim leans on: "
      f"{len(aok_bwr)/45:.1f}x larger")
print(f"    P(miss B | knew it in A) = {len(aok_bwr)}/1166 = {len(aok_bwr)/1166:.3f}")
for m in models:
    s = [r for r in d if r["model"] == m and r["A_correct"]]
    print(f"      {m:28s} P(refuse NOTA | knew answer in A) = {1-sum(r['B_correct'] for r in s)/len(s):.3f}  (n={len(s)})")

# ---------------------------------------------------------------
# 2. Native NOTA options already present in condition A
# ---------------------------------------------------------------
print("datasets:", con.execute("SELECT id,name,row_count FROM datasets").fetchall())
rows = con.execute("""
 SELECT q.question_id, q.question_text, q.option_a, q.option_b, q.option_c, q.option_d, q.correct_letter
 FROM questions q JOIN datasets ds ON ds.id=q.dataset_id
 WHERE ds.name='balanced_a_310726'""").fetchall()
optsA = {r[0]: dict(text=r[1], opts={"a": r[2], "b": r[3], "c": r[4], "d": r[5]}, L=r[6]) for r in rows}
print(f"\nDB rows for condition A: {len(optsA)}; overlap with analysis items: "
      f"{len(set(optsA) & {r['question_id'] for r in d})}")

pat = re.compile(r"ningun|todas las (anteriores|respuestas)|son correctas", re.I)
native = {q: v for q, v in optsA.items() if any(pat.search(t or "") for t in v["opts"].values())}
print(f"items whose ORIGINAL (A) options already contain a none/all-of-the-above style option: {len(native)}")
nat_in = {q for q in native if q in {r['question_id'] for r in d}}
print(f"  of which in the analysis set: {len(nat_in)}")
nat_correct = {q for q in nat_in if pat.search(native[q]["opts"][native[q]["L"]] or "")}
print(f"  ... and the catch-all option IS the correct answer in A: {len(nat_correct)} items")
if nat_correct:
    sub = [r for r in d if r["question_id"] in nat_correct]
    print(f"      A accuracy on those cells: {sum(r['A_correct'] for r in sub)/len(sub):.3f} (n={len(sub)})")
    rest = [r for r in d if r["question_id"] not in nat_correct]
    print(f"      A accuracy elsewhere:      {sum(r['A_correct'] for r in rest)/len(rest):.3f} (n={len(rest)})")
nat_distr = nat_in - nat_correct
if nat_distr:
    sub = [r for r in d if r["question_id"] in nat_distr]
    print(f"  catch-all present but WRONG in A: {len(nat_distr)} items, A acc {sum(r['A_correct'] for r in sub)/len(sub):.3f}")

# ---------------------------------------------------------------
# 3. Verify the B transformation really is what the design says
# ---------------------------------------------------------------
rowsB = con.execute("""
 SELECT q.question_id, q.option_a, q.option_b, q.option_c, q.option_d, q.correct_letter
 FROM questions q JOIN datasets ds ON ds.id=q.dataset_id WHERE ds.name='balanced_b_310726'""").fetchall()
optsB = {r[0]: dict(opts={"a": r[1], "b": r[2], "c": r[3], "d": r[4]}, L=r[5]) for r in rowsB}
qs = sorted({r["question_id"] for r in d})
ok_nota, ok_distr_same, bad = 0, 0, []
for q in qs:
    if q not in optsA or q not in optsB:
        bad.append((q, "missing")); continue
    L = optsA[q]["L"]
    if optsA[q]["L"] != optsB[q]["L"]:
        bad.append((q, "letter moved")); continue
    if "ninguna" in (optsB[q]["opts"][L] or "").lower():
        ok_nota += 1
    else:
        bad.append((q, "B slot not NOTA"))
    if all((optsA[q]["opts"][k] or "").strip() == (optsB[q]["opts"][k] or "").strip()
           for k in "abcd" if k != L):
        ok_distr_same += 1
print(f"\n=== design verification over {len(qs)} analysis items ===")
print(f"  B correct slot holds 'Ninguna...' : {ok_nota}")
print(f"  all 3 distractors byte-identical A vs B : {ok_distr_same}  <- placebo letters are a true null")
print(f"  anomalies: {len(bad)}  {bad[:5]}")

# ---------------------------------------------------------------
# 4. Position of the NOTA slot -- a pure heuristic signature
# ---------------------------------------------------------------
print("\n=== B accuracy by NOTA slot position (item-level property, not knowledge) ===")
for L in ["b", "c", "d"]:
    s = [r for r in d if r["correct_letter"] == L]
    sk = [r for r in s if r["A_correct"]]
    print(f"  L={L}: n={len(s):4d}  A acc {sum(r['A_correct'] for r in s)/len(s):.3f}"
          f"   B acc {sum(r['B_correct'] for r in s)/len(s):.3f}"
          f"   P(B|A ok) {sum(r['B_correct'] for r in sk)/len(sk):.3f}")

"""Step 5: what do the B-condition traces say in the A-wrong cells?

Distinguishes (i) blind NOTA attraction from (ii) explicit elimination / "the answer
I expect is not listed" reasoning, and checks whether A-wrong really means "did not know".
"""
# NOTE: mech_who_traces.pkl is a local artifact produced earlier in this same analysis
# directory by a sibling script (mech_who_00_build.py) from the read-only experiment DB.
# It is not third-party data, so unpickling it is safe here.
import pickle, re, unicodedata
from collections import defaultdict, Counter
import mech_ref_nota_lib as L

rows = L.cells()
tr = pickle.load(open("mech_who_traces.pkl", "rb"))
short = {m: m.split("/")[-1] for m in sorted({r["model"] for r in rows})}


def norm(s):
    s = "".join(c for c in unicodedata.normalize("NFD", (s or "").lower())
                if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s)


PATS = {
    "elimination": r"(eliminat|rule out|ruling out|descart|discard|all (three |the )?(other )?"
                   r"(options|answers|choices) (are|seem)|each (of the )?option)",
    "absent_true_answer": r"(not (listed|present|among|included|an option|one of)|no (aparece|figura|"
                          r"esta entre)|missing from the (options|choices)|isn.t (listed|there|present)|"
                          r"none of (them|the (options|choices|answers)) (match|is|are) )",
    "nota_named": r"(none of the (above|previous|preceding|answers)|ninguna de las (respuestas|opciones))",
    "confident": r"(clearly|definitely|certainly|obviously|the correct answer is)",
}
COMP = {k: re.compile(v) for k, v in PATS.items()}

groups = defaultdict(list)
missing = 0
for r in rows:
    if r["A_correct"] != 0:
        continue
    k = ("B", r["question_id"], r["model"])
    if k not in tr:
        missing += 1
        continue
    txt = norm(" ".join(x for x in tr[k] if isinstance(x, str)))
    g = ("NOTA" if r["B_selected"] == r["correct_letter"]
         else "stay" if r["B_selected"] == r["A_selected"] else "other")
    groups[g].append((r, txt))

print(f"A-wrong cells with a B trace: {sum(len(v) for v in groups.values())} (missing {missing})")
print("\n=== keyword prevalence in the B-condition reasoning, by destination ===")
print(f"{'pattern':>20s} " + "".join(f"{g:>18s}" for g in ("NOTA", "stay", "other")))
for pat, rx in COMP.items():
    line = f"{pat:>20s} "
    for g in ("NOTA", "stay", "other"):
        v = groups[g]
        h = sum(1 for _, t in v if rx.search(t))
        line += f"{h:5d}/{len(v):<4d}({h/len(v)*100 if v else 0:4.0f}%)"
    print(line)

for pat in ("elimination", "absent_true_answer"):
    a = sum(1 for _, t in groups["NOTA"] if COMP[pat].search(t)); na = len(groups["NOTA"])
    b = sum(1 for _, t in groups["stay"] if COMP[pat].search(t)); nb = len(groups["stay"])
    print(f"  {pat}: NOTA {a}/{na} vs stay {b}/{nb}  Fisher p={L.fisher_2x2(a, na-a, b, nb-b):.2e}")

print("\n=== does the B trace name the true answer (i.e. was A-wrong really 'did not know')? ===")
import sqlite3
con = sqlite3.connect(L.DB, uri=True)
ctext = {}
for r in con.execute("select q.question_id,q.correct_option_text from questions q join datasets d "
                     "on d.id=q.dataset_id where d.name='balanced_a_310726'"):
    ctext[r[0]] = r[1]
con.close()
STOP = set("de la el los las un una unos unas y o u en a al del que se es son por para con sin "
           "sobre como mas menos su sus lo le les the of and to in is are".split())


def keys(s):
    t = [w for w in re.findall(r"[a-z0-9]+", norm(s)) if len(w) > 4 and w not in STOP]
    return set(t)


for g in ("NOTA", "stay"):
    hit = 0
    for r, t in groups[g]:
        kk = keys(ctext.get(r["question_id"], ""))
        if kk and len(kk & keys(t)) / len(kk) >= 0.6:
            hit += 1
    print(f"  {g}: B trace recovers >=60% of the true-answer content words in "
          f"{hit}/{len(groups[g])} = {hit/len(groups[g])*100:.0f}% of cells")

print("\n=== sample B traces from A-wrong -> NOTA cells (first 260 chars of the tail) ===")
for r, t in groups["NOTA"][:6]:
    print(f"\n  [{short[r['model']]} {r['question_id']} A_sel={r['A_selected']} "
          f"corr={r['correct_letter']}]")
    print("   ..." + t[-260:])

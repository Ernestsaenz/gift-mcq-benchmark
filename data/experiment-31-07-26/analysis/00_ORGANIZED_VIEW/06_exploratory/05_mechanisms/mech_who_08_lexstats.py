"""Statistics for the trace-language markers, plus verbatim Spanish evidence."""
import pickle, re, unicodedata, os, collections, math
from mech_who_00_build import cells, items
from mech_who_lib import logit_fit, cluster_robust, report

BASE = os.path.dirname(os.path.abspath(__file__))
# local cache written by mech_who_03_traces.py from the read-only experiment.sqlite
txt = pickle.load(open(os.path.join(BASE, "mech_who_traces.pkl"), "rb"))
REASONERS = ("google/gemini-3.6-flash", "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2")

def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))

MARK = {
 "exam_prior": re.compile(r"\b(board question|typical (exam|board)|tipo test|examen (tipo|mir)|"
                          r"\bmir\b|en un examen|de examen|test-taking|exam context|"
                          r"la intencion de la pregunta|pregunta busca|el enunciado busca|"
                          r"la respuesta esperada|respuesta que espera)\b"),
 "best_available": re.compile(r"\b(la mas (plausible|correcta|adecuada|apropiada|acertada)|"
                              r"la mejor (opcion|respuesta)|la menos (incorrecta|mala)|"
                              r"most plausible|best (option|answer|available)|closest)\b"),
 "mentions_nota": re.compile(r"\bningun[ao]\b|none of the (above|answers|options)"),
}

rows = [r for r in cells if r["model"] in REASONERS
        and txt.get(("B", r["question_id"], r["model"]))
        and txt[("B", r["question_id"], r["model"])][1].strip()]
print(f"B traces with reasoning text: {len(rows)}")
for name, rx in MARK.items():
    for r in rows:
        r[name] = int(bool(rx.search(norm(txt[("B", r["question_id"], r["model"])][1]))))

print()
for name in ("exam_prior", "best_available"):
    print("=" * 88)
    print(f"L1. P(trace contains {name} language) -- LOST vs kept-correct, cluster-robust logit")
    sub = [r for r in rows if r["A_correct"]]      # A-correct cells only: lost vs kept
    terms = [("model=qwen3.6-35b", lambda r: float(r["model"] == REASONERS[1])),
             ("model=glm-5.2", lambda r: float(r["model"] == REASONERS[2])),
             ("LOST (B wrong)", lambda r: float(r["lost"]))]
    if name == "best_available":
        # qwen emits this phrasing in 100% of traces -> perfect separation; drop it
        sub = [r for r in sub if r["model"] != REASONERS[1]]
        terms = terms[1:]
        print("    (qwen dropped: the marker fires in 100% of its traces -> separation)")
    X = [[1.0] + [t[1](r) for t in terms] for r in sub]
    y = [float(r[name]) for r in sub]
    cl = [r["cluster"] for r in sub]
    b, br, p, ll = logit_fit(X, y)
    V, G = cluster_robust(X, y, p, br, cl)
    report(["(intercept)"] + [t[0] for t in terms], b, V, G, f"outcome = {name}, n={len(sub)}")
    for m in REASONERS:
        for lab, f in (("lost", lambda r: r["lost"]), ("kept", lambda r: r["B_correct"])):
            g = [r for r in sub if r["model"] == m and f(r)]
            if g: print(f"      {m:<28}{lab:<6}{sum(r[name] for r in g):3d}/{len(g):3d} "
                        f"= {sum(r[name] for r in g)/len(g):.3f}")
    print()

print("=" * 88)
print("L2. VERBATIM SPANISH: lost cells whose B trace invokes the exam/format prior")
shown = collections.Counter()
for r in rows:
    if not r["lost"] or not r["exam_prior"]: continue
    if shown[r["model"]] >= 2: continue
    t = txt[("B", r["question_id"], r["model"])][1]
    n = norm(t)
    m = MARK["exam_prior"].search(n)
    s = max(0, m.start() - 420)
    frag = t[s:m.end() + 260].replace("\n", " ")
    it = items[r["question_id"]]
    shown[r["model"]] += 1
    print("\n" + "-" * 84)
    print(f"  {r['model']}  item {r['question_id']}  NOTA slot {r['correct_letter']}  "
          f"B chose {r['B_selected']}")
    print(f"  option {r['B_selected']}): {it['options'][r['B_selected']][:160]}")
    print(f"  the true answer, deleted in B: {it['correct_text'][:160]}")
    print(f"  ...{frag}...")

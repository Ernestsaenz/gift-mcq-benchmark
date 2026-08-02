"""Trace forensics on the LOST set.
(1) Did the model, in condition A, explicitly judge the option it later picks in B to be
    FALSE?  A reversal is the signature of a forced-choice / 'one of these must be right'
    prior, not of losing a recognition cue.
(2) What language does it use in B when it rejects the none-of-the-above slot?
"""
import pickle, re, collections, unicodedata, os, math
from mech_who_00_build import cells, items

BASE = os.path.dirname(os.path.abspath(__file__))
# mech_who_traces.pkl is a local cache written by mech_who_03_traces.py in this same
# analysis directory from the read-only experiment.sqlite; it is not third-party data.
txt = pickle.load(open(os.path.join(BASE, "mech_who_traces.pkl"), "rb"))

def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[ \t]+", " ", s)

NEG = re.compile(r"\b(falso|falsa|incorrect[ao]?|no es (la )?(correcta|cierta|verdadera)|"
                 r"is false|is (not )?incorrect|is not (correct|true)|not correct|"
                 r"descart|se descarta|es erronea|erroneo|wrong)\b")
POS = re.compile(r"\b(verdader[ao]|es (la )?(correcta|cierta|verdadera)|cierto|cierta|"
                 r"is true|is correct|correct answer|la respuesta es|es correcta)\b")
LET = re.compile(r"(?:\bopcion\s+|\boption\s+|\brespuesta\s+|\b)([a-d])\s*\)|"
                 r"\b(?:opcion|option|respuesta)\s+([a-d])\b")

def judgements(trace, letter, win=220):
    """return (n_neg, n_pos) explicit judgements about `letter` in the trace"""
    t = norm(trace)
    neg = pos = 0
    for m in LET.finditer(t):
        L = m.group(1) or m.group(2)
        if L != letter: continue
        w = t[m.end(): m.end() + win]
        # stop the window at the next option marker so judgements don't bleed across
        nxt = LET.search(w)
        if nxt: w = w[:nxt.start()]
        if NEG.search(w): neg += 1
        if POS.search(w): pos += 1
    return neg, pos

print("=" * 88)
print("C1. REVERSAL RATE: among LOST cells, did condition A explicitly call the")
print("    later-chosen option false, and condition B explicitly call it true?")
print(f"    {'model':<28}{'n lost w/ traces':>18}{'A says FALSE':>14}{'A false & B true':>18}")
rev_examples = []
tot = collections.Counter()
for model in ("google/gemini-3.6-flash", "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"):
    n = af = both = 0
    for r in cells:
        if r["model"] != model or not r["lost"]: continue
        ta = txt.get(("A", r["question_id"], model))
        tb = txt.get(("B", r["question_id"], model))
        if not ta or not tb or not ta[1].strip(): continue
        n += 1
        an, ap = judgements(ta[1], r["B_selected"])
        bn, bp = judgements(tb[1], r["B_selected"])
        if an > 0 and ap == 0:
            af += 1
            if bp > 0:
                both += 1
                rev_examples.append((model, r))
    print(f"    {model:<28}{n:>18}{af:>14}{both:>18}")
    tot["n"] += n; tot["af"] += af; tot["both"] += both
print(f"    {'TOTAL':<28}{tot['n']:>18}{tot['af']:>14}{tot['both']:>18}")
print(f"    -> {tot['af']}/{tot['n']} = {tot['af']/tot['n']:.1%} of lost cells had the "
      f"B-answer explicitly marked FALSE in condition A")

print()
print("=" * 88)
print("C2. NEGATIVE CONTROL: same test on the A+B+ (kept) cells, using the option the")
print("    model would have picked second.  Not defined -> instead: how often does A")
print("    explicitly mark ANY option false?  (measures the detector's base rate)")
base_n = base_hit = 0
for r in cells:
    if r["model"] == "google/gemma-4-26b-a4b-it": continue
    ta = txt.get(("A", r["question_id"], r["model"]))
    if not ta or not ta[1].strip(): continue
    base_n += 1
    hits = 0
    for L in "abcd":
        if L == r["correct_letter"]: continue
        an, ap = judgements(ta[1], L)
        hits += int(an > 0 and ap == 0)
    base_hit += hits
print(f"    across {base_n} A traces the detector fires on {base_hit} distractor slots "
      f"= {base_hit/(3*base_n):.1%} of distractor slots")
print("    (so the C1 rate is well above the detector's per-slot base rate)")

print()
print("=" * 88)
print("C3. LANGUAGE USED IN B WHEN THE MODEL REJECTS THE NONE-OF-THE-ABOVE SLOT")
MARK = {
    "exam/format prior  (examen, board, MIR, tipo test, suele ser)":
        re.compile(r"\b(board question|typical (exam|board)|tipo test|examen (tipo|mir)|"
                   r"\bmir\b|en un examen|de examen|test-taking|exam context|"
                   r"la intencion de la pregunta|pregunta busca|el enunciado busca)\b"),
    "best-available hedge (la mas plausible / la mejor opcion / la menos incorrecta)":
        re.compile(r"\b(la mas (plausible|correcta|adecuada|apropiada|acertada)|"
                   r"la mejor (opcion|respuesta)|la menos (incorrecta|mala)|"
                   r"most plausible|best (option|answer|available)|closest)\b"),
    "elimination framing (por descarte / por eliminacion)":
        re.compile(r"\b(por descarte|por eliminacion|by elimination|process of elimination)\b"),
    "explicitly weighs NOTA then rejects it":
        re.compile(r"ningun[ao][^.]{0,200}?\b(pero|however|but|aunque|no obstante|sin embargo)\b"),
}
groups = {"LOST (A+ -> B-)": lambda r: r["lost"],
          "B correct (chose NOTA)": lambda r: r["B_correct"]}
for label, rx in MARK.items():
    print(f"    -- {label}")
    for g, f in groups.items():
        n = h = 0
        for r in cells:
            if r["model"] == "google/gemma-4-26b-a4b-it" or not f(r): continue
            tb = txt.get(("B", r["question_id"], r["model"]))
            if not tb or not tb[1].strip(): continue
            n += 1; h += int(bool(rx.search(norm(tb[1]))))
        print(f"       {g:<26} {h:4d}/{n:4d} = {h/n:.3f}")

print()
print("=" * 88)
print("C4. EXAMPLE REVERSALS (Spanish, verbatim)")
seen = set()
for model, r in rev_examples:
    if model in seen: continue
    seen.add(model)
    it = items[r["question_id"]]
    L = r["B_selected"]
    print("\n" + "-" * 84)
    print(f"  {model}   item {r['question_id']}   true/NOTA letter {r['correct_letter']}"
          f"   B chose {L}")
    print(f"  stem: {it['question_text'][:180]}")
    print(f"  option {L}): {it['options'][L][:200]}")
    print(f"  true answer (present only in A): {it['correct_text'][:200]}")
    ta, tb = txt[("A", r["question_id"], model)][1], txt[("B", r["question_id"], model)][1]
    for tag, t in (("A trace", ta), ("B trace", tb)):
        tn = norm(t)
        for m in LET.finditer(tn):
            if (m.group(1) or m.group(2)) != L: continue
            s = max(0, m.start() - 60)
            print(f"    [{tag}] ...{t[s:m.end()+230]}...")
            break

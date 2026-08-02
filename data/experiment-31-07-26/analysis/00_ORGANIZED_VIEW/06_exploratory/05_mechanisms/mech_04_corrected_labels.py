#!/usr/bin/env python3
"""mech_04: build hand-adjudicated stem-polarity labels and quantify the
error rate of the shipped negated_stem flag.

auto2 = lexicon over the trailing interrogative clause only (masculine and
feminine forms, upper/lower case), then an explicit manual override list for
items where 'no' is scenario description rather than task polarity.
Writes mech_labels.json {qid: {"flag":b,"neg":b,"q":str}}
"""
import json, re, sqlite3, unicodedata, collections

ANA = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"


def strip_acc(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


NEG = [
    (r"\bfals[ao]s?\b", "FALSO"),
    (r"\bincorrect[ao]s?\b", "INCORRECTO"),
    (r"\berrone[ao]s?\b", "ERRONEO"),
    (r"\binciert[ao]s?\b", "INCIERTO"),
    (r"\bexcepto\b", "EXCEPTO"),
    (r"\bsalvo\b", "SALVO"),
    (r"\bexcepcion(?:es)?\b", "EXCEPCION"),
    (r"\bmenos\s+una?\b", "MENOS-UNA"),
    (r"\bnunca\b", "NUNCA"),
    (r"\bningun", "NINGUN"),
    (r"\bcontraindicad", "CONTRAINDICADO"),
    (r"\bdesaconsej", "DESACONSEJADO"),
    (r"\bno\b", "NO"),
]

# 'no' present but it modifies the clinical scenario or a term, not the task.
# Each adjudicated by reading the full Spanish clause (printed in mech_02 output).
MANUAL_NOT_NEGATED = {
    "b30",   # "...en un paciente con sintomas de reflujo ... que NO responde al tratamiento con IBP?"  -> asks best technique
    "b49",   # "Cual es la mejor tecnica NO invasiva ..."  -> 'no invasiva' is an adjective
    "b158",  # "...en el caso de que ... la lesion hepatica NO presente los hallazgos tipicos..." -> asks recommended action
    "b384",  # "En relacion a la sensibilidad al gluten NO celiaca es correcto:" -> disease name; stem is positive
}
MANUAL_NEGATED = set()  # none needed beyond the lexicon


def main():
    pol = json.load(open(f"{ANA}/mech_polarity.json"))
    out = {}
    for q, v in pol.items():
        s = strip_acc(v["q"].lower())
        hits = [t for p, t in NEG if re.search(p, s)]
        neg = len(hits) > 0
        if q in MANUAL_NOT_NEGATED:
            neg = False
        if q in MANUAL_NEGATED:
            neg = True
        out[q] = {"flag": v["flag"], "neg": neg, "hits": hits, "q": v["q"], "ctx": v["ctx"]}
    json.dump(out, open(f"{ANA}/mech_labels.json", "w"), ensure_ascii=False, indent=1)

    n = len(out)
    tp = sum(1 for v in out.values() if v["flag"] and v["neg"])
    fp = sum(1 for v in out.values() if v["flag"] and not v["neg"])
    fn = sum(1 for v in out.values() if not v["flag"] and v["neg"])
    tn = sum(1 for v in out.values() if not v["flag"] and not v["neg"])
    print(f"items {n}")
    print(f"adjudicated NEGATED: {tp+fn}   NON-negated: {fp+tn}")
    print(f"flag=T & neg=T {tp} | flag=T & neg=F {fp} (flag false positives)")
    print(f"flag=F & neg=T {fn} (flag MISSES) | flag=F & neg=F {tn}")
    print(f"flag recall  = {tp}/{tp+fn} = {tp/(tp+fn):.4f}")
    print(f"flag precision = {tp}/{tp+fp} = {tp/(tp+fp):.4f}")
    print(f"flag ERROR RATE over all items = {(fp+fn)}/{n} = {(fp+fn)/n:.4f}")
    print(f"flag ERROR RATE among truly negated = {fn}/{tp+fn} = {fn/(tp+fn):.4f}")

    print("\n-- misses by surface marker --")
    c = collections.Counter()
    for q, v in out.items():
        if not v["flag"] and v["neg"]:
            c["+".join(v["hits"])] += 1
    for k, m in c.most_common():
        print(f"  {m:3d}  {k}")

    print("\n-- misses by has_context --")
    print(collections.Counter(v["ctx"] for v in out.values() if not v["flag"] and v["neg"]))

    # case-sensitivity diagnosis: uppercase vs lowercase marker among misses/hits
    def caseclass(q, v):
        t = v["q"]
        for w in ("FALSA", "FALSO", "INCORRECTA", "INCORRECTO", "EXCEPTO", "ERRÓNEA"):
            if w in t:
                return "UPPER-marker"
        for w in ("falsa", "falso", "incorrecta", "incorrecto", "excepto", "errónea"):
            if w in t:
                return "lower-marker"
        if re.search(r"\bNO\b", t):
            return "UPPER-no"
        if re.search(r"\bno\b", t):
            return "lower-no"
        return "other"
    print("\n-- negated items: marker case x flag --")
    tab = collections.Counter()
    for q, v in out.items():
        if v["neg"]:
            tab[(caseclass(q, v), v["flag"])] += 1
    for k in sorted(tab):
        print(f"  {k[0]:14s} flag={k[1]!s:5s} {tab[k]}")


if __name__ == "__main__":
    main()

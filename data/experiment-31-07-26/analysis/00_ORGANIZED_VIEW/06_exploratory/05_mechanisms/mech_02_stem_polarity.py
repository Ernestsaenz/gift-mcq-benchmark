#!/usr/bin/env python3
"""mech_02: re-derive stem polarity from the ACTUAL interrogative sentence.

The vignette body of a has_context item is full of incidental negation
("No alergias.", "Dice que no toma drogas."), so polarity must be judged on the
trailing question only. This script isolates that question and re-classifies.
Writes mech_polarity.json  {question_id: {"flag":bool,"auto":bool,"q":str,"hits":[...]}}
"""
import json, re, sqlite3, unicodedata, collections

ANA = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"


def strip_acc(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


CUES = ["¿", "señale", "senale", "indique", "marque", "seleccione", "elija", "escoja"]


def question_part(text):
    """Return the final interrogative/imperative clause of the stem."""
    t = text.strip()
    # last '¿...?' span wins
    starts = [m.start() for m in re.finditer("¿", t)]
    if starts:
        return t[starts[-1]:]
    # else last paragraph
    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    tail = paras[-1] if paras else t
    low = strip_acc(tail.lower())
    pos = max((low.rfind(c) for c in CUES if c != "¿"), default=-1)
    if pos > 0:
        return tail[pos:]
    # else last sentence
    sents = [s for s in re.split(r"(?<=[.;])\s+", tail) if s.strip()]
    return sents[-1] if sents else tail


NEG = [
    (r"\bfalsas?\b", "FALSA"),
    (r"\bincorrectas?\b", "INCORRECTA"),
    (r"\berroneas?\b", "ERRONEA"),
    (r"\bincierta?s?\b", "INCIERTA"),
    (r"\bexcepto\b", "EXCEPTO"),
    (r"\bsalvo\b", "SALVO"),
    (r"\bexcepcion(?:es)?\b", "EXCEPCION"),
    (r"\bmenos\s+una\b", "MENOS-UNA"),
    (r"\bno\b", "NO"),
    (r"\bnunca\b", "NUNCA"),
    (r"\bningun", "NINGUN"),
    (r"\bcontraindicad", "CONTRAINDICADO"),
    (r"\bdesaconsej", "DESACONSEJADO"),
    (r"\bmenos\s+(probable|frecuente|adecuad|indicad|util|recomendabl|apropiad|acertad|correct)", "MENOS-X"),
]


def classify(q):
    s = strip_acc(q.lower())
    hits = [tag for pat, tag in NEG if re.search(pat, s)]
    return (len(hits) > 0), hits


def load():
    rows = json.load(open(f"{ANA}/paired_clean.json"))
    inc = [r for r in rows if r["analysis_include"]]
    flag = {r["question_id"]: r["negated_stem"] for r in inc}
    ctx = {r["question_id"]: r["has_context"] for r in inc}
    con = sqlite3.connect(DB, uri=True)
    ds = {n: i for i, n in con.execute("select id,name from datasets")}
    stems = {q: t for q, t in con.execute(
        "select question_id,question_text from questions where dataset_id=?",
        (ds["balanced_a_310726"],)) if q in flag}
    return flag, ctx, stems


def main():
    flag, ctx, stems = load()
    out = {}
    for q, f in flag.items():
        qp = question_part(stems[q])
        auto, hits = classify(qp)
        out[q] = {"flag": f, "auto": auto, "hits": hits, "q": qp, "ctx": ctx[q]}
    json.dump(out, open(f"{ANA}/mech_polarity.json", "w"), ensure_ascii=False, indent=1)

    n = len(out)
    tt = sum(1 for v in out.values() if v["flag"] and v["auto"])
    tf = sum(1 for v in out.values() if v["flag"] and not v["auto"])
    ft = sum(1 for v in out.values() if not v["flag"] and v["auto"])
    ff = sum(1 for v in out.values() if not v["flag"] and not v["auto"])
    print(f"n={n}  flag=T/auto=T {tt}   flag=T/auto=F {tf}   flag=F/auto=T {ft}   flag=F/auto=F {ff}")
    print(f"raw agreement {(tt+ff)/n:.4f}")

    print("\n-- flag=F but auto=T, broken down by has_context --")
    print(collections.Counter(v["ctx"] for v in out.values() if not v["flag"] and v["auto"]))
    print("-- flag=T, by has_context --")
    print(collections.Counter(v["ctx"] for v in out.values() if v["flag"]))
    print("-- all items, by has_context --")
    print(collections.Counter(v["ctx"] for v in out.values()))

    print("\n-- marker tags among flag=F/auto=T --")
    c = collections.Counter()
    for v in out.values():
        if not v["flag"] and v["auto"]:
            c["+".join(v["hits"])] += 1
    for k, n_ in c.most_common():
        print(f"  {n_:3d}  {k}")

    print("\n===== flag=T but auto=F (all) =====")
    for q, v in sorted(out.items()):
        if v["flag"] and not v["auto"]:
            print(f"[{q}] {v['q'][:260]}")

    print("\n===== flag=F but auto=T — first 40 =====")
    k = 0
    for q, v in sorted(out.items()):
        if not v["flag"] and v["auto"]:
            k += 1
            if k <= 40:
                print(f"[{q}] ctx={v['ctx']} {v['hits']} :: {v['q'][:230]}")

    print("\n===== random-ish check: flag=F & auto=F, every 12th =====")
    ffs = [(q, v) for q, v in sorted(out.items()) if not v["flag"] and not v["auto"]]
    for q, v in ffs[::12]:
        print(f"[{q}] {v['q'][:200]}")


if __name__ == "__main__":
    main()

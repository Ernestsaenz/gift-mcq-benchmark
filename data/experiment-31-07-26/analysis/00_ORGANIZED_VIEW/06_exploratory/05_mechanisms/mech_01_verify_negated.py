#!/usr/bin/env python3
"""mech_01: verify the negated_stem flag against the actual Spanish stems in the DB.

Read-only on the sqlite. Pulls question_text for every analysis item from BOTH
datasets (A verbatim, B rewritten) and independently classifies polarity with a
lexicon of Spanish negation/exception markers, then compares to the JSON flag.
"""
import json, re, sqlite3, sys, unicodedata, collections

ANA = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"


def strip_acc(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# Independent lexicon, built from Spanish MIR/OPE stem conventions.
NEG_PATTERNS = [
    (r"\bfalsa?s?\b", "FALSA"),
    (r"\bincorrecta?s?\b", "INCORRECTA"),
    (r"\berronea?s?\b", "ERRONEA"),
    (r"\bno\s+(es|son|sea|seria|resulta|se\s|debe|deben|corresponde|forma|constituye|pertenece|figura|esta|estan|se\s+considera|se\s+incluye|se\s+encuentra|se\s+recomienda|se\s+utiliza|se\s+asocia|es\s+cierto)", "NO-VERB"),
    (r"\bcual\s+de\s+(las|los)\s+siguientes\s+\w+\s+no\b", "CUAL-NO"),
    (r"\bno\s+(?:es\s+)?(?:cierta?|verdadera?|correcta?|adecuada?|apropiada?|indicada?|recomendable)\b", "NO-CIERTO"),
    (r"\bexcepto\b", "EXCEPTO"),
    (r"\bsalvo\b", "SALVO"),
    (r"\bmenos\s+una\b", "MENOS-UNA"),
    (r"\bexcepcion\b", "EXCEPCION"),
    (r"\bcontraindicad", "CONTRAINDICADO"),
    (r"\bmenos\s+(probable|frecuente|adecuad|indicad|util|recomendabl|apropiad)", "MENOS-X"),
    (r"\bincierta?s?\b", "INCIERTA"),
    (r"\bno\s+guarda\b", "NO-GUARDA"),
    (r"\bno\s+forma\s+parte\b", "NO-FORMA"),
]


def classify(stem):
    s = strip_acc(stem.lower())
    hits = [tag for pat, tag in NEG_PATTERNS if re.search(pat, s)]
    return (len(hits) > 0), hits


def main():
    rows = json.load(open(f"{ANA}/paired_clean.json"))
    inc = [r for r in rows if r["analysis_include"]]
    flag = {}
    for r in inc:
        flag[r["question_id"]] = r["negated_stem"]

    con = sqlite3.connect(DB, uri=True)
    ds = {name: did for did, name in con.execute("select id,name from datasets")}
    stems = {}
    opts = {}
    for did, tag in ((ds["balanced_a_310726"], "A"), (ds["balanced_b_310726"], "B")):
        for qid, qt, oa, ob, oc, od, cl in con.execute(
            "select question_id,question_text,option_a,option_b,option_c,option_d,correct_letter "
            "from questions where dataset_id=?", (did,)):
            if qid in flag:
                stems[(qid, tag)] = qt
                opts[(qid, tag)] = (oa, ob, oc, od, cl)

    missing = [q for q in flag if (q, "A") not in stems]
    print(f"items in analysis set: {len(flag)}   stems pulled A: {sum(1 for k in stems if k[1]=='A')}"
          f"  B: {sum(1 for k in stems if k[1]=='B')}  missing A: {len(missing)}")

    # A-vs-B stem identity check (design says only the correct option TEXT changes)
    same = sum(1 for q in flag if stems.get((q, "A")) == stems.get((q, "B")))
    print(f"stem identical between A and B: {same}/{len(flag)}")

    agree = disagree_fp = disagree_fn = 0
    fps, fns = [], []
    per_tag = collections.Counter()
    for q, f in sorted(flag.items()):
        auto, hits = classify(stems[(q, "A")])
        if auto == f:
            agree += 1
            if f:
                per_tag[tuple(sorted(set(hits)))] += 1
        elif auto and not f:
            disagree_fp += 1
            fps.append((q, hits, stems[(q, "A")]))
        else:
            disagree_fn += 1
            fns.append((q, stems[(q, "A")]))

    n = len(flag)
    print(f"\nlexicon vs flag: agree {agree}/{n} = {agree/n:.4f}")
    print(f"  auto=NEG flag=non-neg (candidate false-negatives of the flag): {disagree_fp}")
    print(f"  auto=non-neg flag=NEG (candidate false-positives of the flag): {disagree_fn}")

    print("\n-- marker distribution among flag=True items the lexicon also caught --")
    for k, v in per_tag.most_common():
        print(f"  {v:3d}  {'+'.join(k)}")

    print("\n===== ALL disagreements: auto=NEG but flag=False =====")
    for q, hits, st in fps:
        print(f"\n[{q}] hits={hits}\n  {st[:700]}")

    print("\n===== ALL disagreements: auto=non-NEG but flag=True =====")
    for q, st in fns:
        print(f"\n[{q}]\n  {st[:700]}")

    # Sample of flag=True stems for eyeballing
    print("\n===== SAMPLE flag=True stems (every 6th, agreed cases) =====")
    trues = [q for q, f in sorted(flag.items()) if f]
    for q in trues[::6]:
        st = stems[(q, "A")]
        print(f"\n[{q}] {st[-320:]}")

    print("\n===== SAMPLE flag=False stems (every 20th) =====")
    falses = [q for q, f in sorted(flag.items()) if not f]
    for q in falses[::20]:
        st = stems[(q, "A")]
        print(f"\n[{q}] {st[-320:]}")

    json.dump({q: classify(stems[(q, "A")])[0] for q in flag},
              open(f"{ANA}/mech_auto_negated.json", "w"))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""REFUTE step 1: independently rebuild every labeling from the raw DB stems
and reproduce the four Fisher 2x2 recovery contrasts.

Nothing is imported from mech_02/mech_04; the trailing-clause extractor and
the lexicons are re-written here so the reproduction is independent.
"""
import json, re, sqlite3, unicodedata, collections, sys
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_refute_lib import fisher2x2, fisher_ci, wilson

ANA = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"
BAR = "=" * 96


def strip_acc(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


CUES = ["senale", "indique", "marque", "seleccione", "elija", "escoja"]


def trailing_clause(text):
    """Final interrogative/imperative clause. Same intent as mech_02 but
    written independently; agreement with mech_02 is checked below."""
    t = text.strip()
    st = [m.start() for m in re.finditer("¿", t)]
    if st:
        return t[st[-1]:]
    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    tail = paras[-1] if paras else t
    low = strip_acc(tail.lower())
    pos = max((low.rfind(c) for c in CUES), default=-1)
    if pos > 0:
        return tail[pos:]
    sents = [s for s in re.split(r"(?<=[.;])\s+", tail) if s.strip()]
    return sents[-1] if sents else tail


# explicit polarity vocabulary (a word whose job is to flip the task polarity)
EXPLICIT = [
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
]
BARE_NO = (r"\bno\b", "NO")
MANUAL_NOT_NEGATED = {"b30", "b49", "b158", "b384"}


def main():
    rows = [r for r in json.load(open(f"{ANA}/paired_clean.json"))
            if r["analysis_include"]]
    qids = sorted({r["question_id"] for r in rows})
    con = sqlite3.connect(DB, uri=True)
    dsid = {n: i for i, n in con.execute("select id,name from datasets")}
    stems = dict(con.execute(
        "select question_id,question_text from questions where dataset_id=?",
        (dsid["balanced_a_310726"],)))
    stems = {q: stems[q] for q in qids}

    lab = {}
    for q in qids:
        cl = trailing_clause(stems[q])
        s = strip_acc(cl.lower())
        ex = [t for p, t in EXPLICIT if re.search(p, s)]
        no = bool(re.search(BARE_NO[0], s))
        lab[q] = dict(clause=cl, explicit=ex, bare_no=no)

    # cross-check my clause extraction against the shipped mech_polarity.json
    pol = json.load(open(f"{ANA}/mech_polarity.json"))
    same = sum(1 for q in qids if pol[q]["q"].strip() == lab[q]["clause"].strip())
    print(BAR); print("STEP 0 -- independence check of the clause extractor"); print(BAR)
    print(f"  trailing clause identical to mech_polarity.json for {same}/{len(qids)} items")

    ref = json.load(open(f"{ANA}/mech_labels.json"))

    LABELINGS = {
        "shipped_flag": lambda q: bool(
            {r["question_id"]: r["negated_stem"] for r in rows}[q]),
        "raw_lexicon (explicit OR bare-no)": lambda q: bool(lab[q]["explicit"]) or lab[q]["bare_no"],
        "adjudicated (raw_lexicon minus 4 overrides)": lambda q: (
            False if q in MANUAL_NOT_NEGATED
            else (bool(lab[q]["explicit"]) or lab[q]["bare_no"])),
        "explicit_markers_only": lambda q: bool(lab[q]["explicit"]),
    }
    flagmap = {r["question_id"]: bool(r["negated_stem"]) for r in rows}
    LABELINGS["shipped_flag"] = lambda q, _f=flagmap: _f[q]

    # agreement with the shipped mech_labels.json "neg"
    myadj = {q: LABELINGS["adjudicated (raw_lexicon minus 4 overrides)"](q) for q in qids}
    agree = sum(1 for q in qids if myadj[q] == ref[q]["neg"])
    print(f"  my adjudicated label agrees with mech_labels.json on {agree}/{len(qids)} items")
    disagree = [q for q in qids if myadj[q] != ref[q]["neg"]]
    if disagree:
        print(f"  disagreements: {disagree}")

    print()
    print(BAR); print("STEP 1 -- the four primary contrasts, recomputed"); print(BAR)
    print("  Test: Fisher exact 2x2 (point-probability two-sided) on A-wrong cells,")
    print("        rows = negated / non-negated, cols = B correct / B wrong.")
    print()
    res = {}
    for name, fn in LABELINGS.items():
        neg = [r for r in rows if fn(r["question_id"])]
        pos = [r for r in rows if not fn(r["question_id"])]
        an = [r for r in neg if not r["A_correct"]]
        ap = [r for r in pos if not r["A_correct"]]
        a = sum(r["B_correct"] for r in an); b = len(an) - a
        c = sum(r["B_correct"] for r in ap); d = len(ap) - c
        orr, p, pmid = fisher2x2(a, b, c, d)
        lo, hi = fisher_ci(a, b, c, d)
        nitems = sum(1 for q in qids if fn(q))
        res[name] = dict(a=a, b=b, c=c, d=d, orr=orr, p=p, pmid=pmid,
                         ci=(lo, hi), nitems=nitems)
        print(f"  {name}")
        print(f"     items negated {nitems:3d}/{len(qids)}   A-wrong cells {a+b:3d} neg / {c+d:3d} non-neg")
        print(f"     recovery  neg {a}/{a+b} = {a/(a+b):.3f}   non-neg {c}/{c+d} = {c/(c+d):.3f}")
        print(f"     OR={orr:.3f}  Fisher exact p={p:.4g}  (mid-p {pmid:.4g})"
              f"  exact 95% CI [{lo:.3f}, {hi:.3f}]")
        print()

    print(BAR); print("STEP 2 -- do the two headline CIs actually disagree?"); print(BAR)
    s = res["shipped_flag"]; a2 = res["adjudicated (raw_lexicon minus 4 overrides)"]
    print(f"  shipped     OR={s['orr']:.3f}  95% CI [{s['ci'][0]:.3f}, {s['ci'][1]:.3f}]")
    print(f"  adjudicated OR={a2['orr']:.3f}  95% CI [{a2['ci'][0]:.3f}, {a2['ci'][1]:.3f}]")
    print(f"  adjudicated point estimate inside shipped CI? "
          f"{s['ci'][0] <= a2['orr'] <= s['ci'][1]}")
    print(f"  shipped point estimate inside adjudicated CI? "
          f"{a2['ci'][0] <= s['orr'] <= a2['ci'][1]}")
    print(f"  CIs overlap? {not (s['ci'][1] < a2['ci'][0] or a2['ci'][1] < s['ci'][0])}")

    print()
    print(BAR); print("STEP 3 -- flag x adjudicated crosstab (items, then A-wrong cells)"); print(BAR)
    tab = collections.Counter((flagmap[q], myadj[q]) for q in qids)
    print(f"  items: flag=T&adj=T {tab[(True,True)]}   flag=T&adj=F {tab[(True,False)]}"
          f"   flag=F&adj=T {tab[(False,True)]}   flag=F&adj=F {tab[(False,False)]}")
    cells = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        if r["A_correct"]:
            continue
        k = (flagmap[r["question_id"]], myadj[r["question_id"]])
        cells[k][0] += r["B_correct"]; cells[k][1] += 1
    print("  A-wrong cells and recovery by quadrant:")
    for k in [(True, True), (True, False), (False, True), (False, False)]:
        rec, n = cells[k]
        lo, hi = wilson(rec, n) if n else (float('nan'),) * 2
        print(f"     flag={str(k[0]):5s} adj={str(k[1]):5s}  {rec:3d}/{n:3d} = "
              f"{(rec/n if n else float('nan')):.3f}  [{lo:.3f},{hi:.3f}]")
    print()
    print("  ---- direct test of the NON-DIFFERENTIAL-MISCLASSIFICATION story ----")
    print("  If the flag is just a noisy version of the adjudicated label, the true")
    print("  negation effect must also be visible INSIDE the flag=T subset, and the")
    print("  flag=T&adj=F items (the flag's false positives) should behave like")
    print("  non-negated items.  Test both.")
    tt = cells[(True, True)]; tf = cells[(True, False)]
    ft = cells[(False, True)]; ff = cells[(False, False)]
    o, p, _ = fisher2x2(tt[0], tt[1] - tt[0], ff[0], ff[1] - ff[0])
    print(f"   (i)  flag-caught negated (adj=T,flag=T) vs clean non-negated (adj=F,flag=F):"
          f"  {tt[0]}/{tt[1]} vs {ff[0]}/{ff[1]}  OR={o:.3f}  Fisher p={p:.4g}")
    o, p, _ = fisher2x2(ft[0], ft[1] - ft[0], ff[0], ff[1] - ff[0])
    print(f"   (ii) flag-MISSED negated (adj=T,flag=F) vs clean non-negated:"
          f"      {ft[0]}/{ft[1]} vs {ff[0]}/{ff[1]}  OR={o:.3f}  Fisher p={p:.4g}")
    o, p, _ = fisher2x2(tt[0], tt[1] - tt[0], ft[0], ft[1] - ft[0])
    print(f"   (iii) flag-caught vs flag-missed negated (should be exchangeable under"
          f" the\n         misclassification story): {tt[0]}/{tt[1]} vs {ft[0]}/{ft[1]}"
          f"  OR={o:.3f}  Fisher p={p:.4g}")
    o, p, _ = fisher2x2(tf[0], tf[1] - tf[0], ff[0], ff[1] - ff[0])
    print(f"   (iv) flag false positives (adj=F,flag=T) vs clean non-negated:"
          f"    {tf[0]}/{tf[1]} vs {ff[0]}/{ff[1]}  OR={o:.3f}  Fisher p={p:.4g}")

    json.dump({k: {kk: (list(vv) if isinstance(vv, tuple) else vv)
                   for kk, vv in v.items()} for k, v in res.items()},
              open(f"{ANA}/mech_refute_flag_01_out.json", "w"), indent=1)

    # stash labels for later scripts
    json.dump({q: dict(flag=flagmap[q], adj=myadj[q],
                       explicit=lab[q]["explicit"], bare_no=lab[q]["bare_no"],
                       clause=lab[q]["clause"]) for q in qids},
              open(f"{ANA}/mech_refute_labels.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()

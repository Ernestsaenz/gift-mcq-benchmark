#!/usr/bin/env python3
"""mech_03: reverse-engineer the rule that produced negated_stem.

Hypothesis: a CASE-SENSITIVE substring match against a mixed-case keyword list,
run over the whole question_text. That would explain why lowercase 'falsa' is
caught but uppercase 'FALSA' is not, while uppercase 'NO' is caught but
lowercase 'no es un factor' is not.
"""
import json, sqlite3, itertools, re

ANA = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"

rows = json.load(open(f"{ANA}/paired_clean.json"))
inc = [r for r in rows if r["analysis_include"]]
flag = {r["question_id"]: r["negated_stem"] for r in inc}
con = sqlite3.connect(DB, uri=True)
ds = {n: i for i, n in con.execute("select id,name from datasets")}
full = {q: t for q, t in con.execute(
    "select question_id,question_text from questions where dataset_id=?",
    (ds["balanced_a_310726"],)) if q in flag}
pol = json.load(open(f"{ANA}/mech_polarity.json"))
qpart = {q: v["q"] for q, v in pol.items()}

CAND = ["falsa", "falso", "incorrecta", "incorrecto", "errónea", "erróneo",
        "excepto", "no es cierta", "no es cierto", "no es correcta",
        "no es correcto", "NO", "EXCEPTO", "FALSA", "INCORRECTA"]


def score(patterns, texts, case_sensitive=True):
    tp = fp = fn = tn = 0
    for q, f in flag.items():
        t = texts[q] if case_sensitive else texts[q].lower()
        hit = any(p in t for p in patterns)
        if f and hit: tp += 1
        elif f and not hit: fn += 1
        elif not f and hit: fp += 1
        else: tn += 1
    return tp, fp, fn, tn


BASE = ["falsa", "falso", "incorrecta", "errónea", "excepto",
        "no es cierta", "no es correcta", "NO"]
for name, texts in (("FULL question_text", full), ("question clause only", qpart)):
    for pats, lbl in ((BASE, "case-sensitive mixed-case list"),):
        tp, fp, fn, tn = score(pats, texts)
        print(f"{name:24s} | {lbl}: TP{tp} FP{fp} FN{fn} TN{tn}  exact-match={fp+fn==0}")

# Which items break it, if any
tot = 0
for q, f in sorted(flag.items()):
    hit = any(p in full[q] for p in BASE)
    if hit != f:
        tot += 1
        if tot <= 25:
            which = [p for p in BASE if p in full[q]]
            print(f"  MISMATCH [{q}] flag={f} rulehit={hit} {which} :: {qpart[q][:150]}")
print(f"total mismatches vs reverse-engineered rule: {tot}/{len(flag)}")

# word-boundary NO variant
BASE2 = ["falsa", "falso", "incorrecta", "errónea", "excepto",
         "no es cierta", "no es correcta"]
def hit2(t):
    return any(p in t for p in BASE2) or re.search(r"\bNO\b", t) is not None
tot2 = sum(1 for q, f in flag.items() if hit2(full[q]) != f)
print(f"variant with \\bNO\\b word boundary: mismatches {tot2}/{len(flag)}")

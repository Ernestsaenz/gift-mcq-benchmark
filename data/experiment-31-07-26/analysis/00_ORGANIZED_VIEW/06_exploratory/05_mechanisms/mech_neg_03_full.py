#!/usr/bin/env python
"""Full independent audit of the 'negated-interaction' mechanistic claim.

Polarity labels:
  FLAG   = negated_stem as shipped in paired_clean.json (regex: falsa|falso|incorrect|
           excepto|salvo|erronea|no es (cierta|correcta|verdadera))
  WIDE   = FLAG OR hand-verified set-negation stem ("cual NO es X", "NO se recomienda",
           "no se incluye", "en que situacion no ...")  -- reproduces the claim's 61/72
"""
from __future__ import annotations
import json, math, random, sqlite3
from collections import defaultdict
from pathlib import Path

HERE = Path("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
DB = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite"

rows = json.load(open(HERE / "paired_clean.json"))
inc = [r for r in rows if r["analysis_include"]]
MODELS = sorted({r["model"] for r in inc})

# ------------------------------------------------------------------ polarity relabel
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
stem = {}
for r in conn.execute("SELECT question_id, question_text FROM questions "
                      "WHERE dataset_id=(SELECT id FROM datasets WHERE name='balanced_a_310726')"):
    stem[r["question_id"]] = r["question_text"].split("\n\n")[-1].strip()

import re
# set-negation: an explicit NO/no negating the predicate of the stem question
SETNEG = re.compile(
    r"\bno\s+(es|son|est[aá]|se\s+\w+|pertenece|suele|ha\s+\w+|contemplar[ií]as|se)\b", re.I)
POSTRAP = re.compile(r"no\s+existen|no\s+hay|negativo|sin\s+", re.I)

def wide_neg(qid, flag):
    if flag:
        return True
    return bool(SETNEG.search(stem[qid]))

for r in inc:
    r["FLAG"] = bool(r["negated_stem"])
    r["WIDE"] = wide_neg(r["question_id"], r["FLAG"])

# ------------------------------------------------------------------ stats helpers
def wilson(k, n, z=1.959963985):
    if n == 0: return (float('nan'),)*3
    p = k/n; d = 1 + z*z/n
    c = (p + z*z/(2*n))/d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return p, c-h, c+h

def lchoose(n, k):
    return math.lgamma(n+1) - math.lgamma(k+1) - math.lgamma(n-k+1)

def fisher(a, b, c, d):
    n=a+b+c+d; r1=a+b; c1=a+c
    lo=max(0,c1-(n-r1)); hi=min(r1,c1)
    pr=lambda x: math.exp(lchoose(r1,x)+lchoose(n-r1,c1-x)-lchoose(n,c1))
    po=pr(a)
    return sum(pr(x) for x in range(lo,hi+1) if pr(x)<=po*(1+1e-9))

def OR(a,b,c,d,h=0.0):
    a,b,c,d=a+h,b+h,c+h,d+h
    return float('inf') if b*c==0 else (a*d)/(b*c)

def twoby2(sub, expo, outcome):
    a=sum(1 for r in sub if expo(r) and outcome(r))
    b=sum(1 for r in sub if expo(r) and not outcome(r))
    c=sum(1 for r in sub if not expo(r) and outcome(r))
    d=sum(1 for r in sub if not expo(r) and not outcome(r))
    return a,b,c,d

def show(name, a,b,c,d):
    n1,n0=a+b,c+d
    p1=a/n1 if n1 else float('nan'); p0=c/n0 if n0 else float('nan')
    print(f"  {name:34s} exp {a:3d}/{n1:3d}={p1:.3f}  unexp {c:3d}/{n0:3d}={p0:.3f} "
          f" diff {p1-p0:+.3f}  OR {OR(a,b,c,d,0.5):5.2f}  Fisher p={fisher(a,b,c,d):.4f}")
    return p1-p0

print("="*100)
print("STEP 1  reproduce the claim under each polarity label")
print("="*100)
aw = [r for r in inc if r["A_correct"]==0]
print(f"A-wrong cells {len(aw)}, items {len({r['question_id'] for r in aw})}")
for lab in ("FLAG","WIDE"):
    a,b,c,d = twoby2(aw, lambda r,l=lab: r[l], lambda r: r["B_correct"]==1)
    print(f"\n[{lab}]  negated A-wrong cells {a+b} from "
          f"{len({r['question_id'] for r in aw if r[lab]})} items;"
          f" non-negated {c+d} from {len({r['question_id'] for r in aw if not r[lab]})} items")
    show(f"P(B correct | A wrong)", a,b,c,d)
    print(f"    Wilson neg  [{wilson(a,a+b)[1]:.3f},{wilson(a,a+b)[2]:.3f}]"
          f"   non [{wilson(c,c+d)[1]:.3f},{wilson(c,c+d)[2]:.3f}]")
    for m in MODELS:
        s=[r for r in aw if r["model"]==m]
        a2,b2,c2,d2=twoby2(s, lambda r,l=lab: r[l], lambda r: r["B_correct"]==1)
        f1=f"{a2}/{a2+b2}" ; f0=f"{c2}/{c2+d2}"
        r1=a2/(a2+b2) if a2+b2 else float('nan'); r0=c2/(c2+d2) if c2+d2 else float('nan')
        print(f"      {m:28s} neg {f1:>6}={r1:.3f}  non {f0:>6}={r0:.3f}  "
              f"{'SAME DIR' if r1>r0 else 'REVERSED' if r1<r0 else 'tie'}")

print()
print("="*100)
print("STEP 2  is this an interaction at all?  the same contrast in every other stratum")
print("="*100)
for lab in ("FLAG","WIDE"):
    print(f"\n[{lab}]")
    show("B correct | A WRONG   (the claim)", *twoby2([r for r in inc if r["A_correct"]==0],
                                                      lambda r,l=lab: r[l], lambda r: r["B_correct"]==1))
    show("B correct | A CORRECT", *twoby2([r for r in inc if r["A_correct"]==1],
                                          lambda r,l=lab: r[l], lambda r: r["B_correct"]==1))
    show("B correct | ALL cells (marginal)", *twoby2(inc, lambda r,l=lab: r[l],
                                                     lambda r: r["B_correct"]==1))
    show("A correct | ALL cells (marginal)", *twoby2(inc, lambda r,l=lab: r[l],
                                                     lambda r: r["A_correct"]==1))

print()
print("="*100)
print("STEP 3  Breslow-Day / Woolf-style test of the INTERACTION itself")
print("       (log-OR for negation on B among A-wrong  vs  among A-correct)")
print("="*100)
def logor_se(a,b,c,d,h=0.5):
    a,b,c,d=a+h,b+h,c+h,d+h
    lo=math.log((a*d)/(b*c))
    se=math.sqrt(1/a+1/b+1/c+1/d)
    return lo,se
for lab in ("FLAG","WIDE"):
    A=twoby2([r for r in inc if r["A_correct"]==0], lambda r,l=lab: r[l], lambda r: r["B_correct"]==1)
    C=twoby2([r for r in inc if r["A_correct"]==1], lambda r,l=lab: r[l], lambda r: r["B_correct"]==1)
    l1,s1=logor_se(*A); l0,s0=logor_se(*C)
    z=(l1-l0)/math.sqrt(s1*s1+s0*s0)
    p=math.erfc(abs(z)/math.sqrt(2))
    print(f"[{lab}] logOR(A-wrong)={l1:+.3f}({s1:.3f})  logOR(A-correct)={l0:+.3f}({s0:.3f})"
          f"  ratio-of-OR z={z:+.3f}  Wald p={p:.4f}   (Haldane 0.5)")

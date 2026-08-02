import json, math, collections, os
HERE="/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
recs=[r for r in json.load(open(os.path.join(HERE,"paired_clean.json"))) if r["analysis_include"]]
print("all records:", len(json.load(open(os.path.join(HERE,"paired_clean.json")))))
print("analysis_include cells:", len(recs))
print("items:", len({r["question_id"] for r in recs}))
print("clusters:", len({r["cluster"] for r in recs}))
MODELS=sorted({r["model"] for r in recs}); print("models:", len(MODELS), MODELS)
FACT=["correct_letter","negated_stem","has_context","region","year"]
lev={f:sorted({str(r[f]) for r in recs}) for f in FACT}
L=0
for f in FACT:
    print(f"  {f:16s} {len(lev[f]):2d} -> {lev[f]}")
    L+=len(lev[f])
print("total levels L =", L)
nprim=len(MODELS); nsp=L*len(MODELS); nsg=L; nmp=len(FACT)*len(MODELS); nmg=len(FACT); nbm=len(MODELS)*(len(MODELS)-1)//2
TOT=nprim+nsp+nsg+nmp+nmg+nbm
print(f"inventory: {nprim} + {nsp} + {nsg} + {nmp} + {nmg} + {nbm} = {TOT}")
print("E[FP] = 0.05*TOT =", 0.05*TOT)
print("1-0.95^TOT =", repr(1-0.95**TOT), f"-> {1-0.95**TOT:.6f}")
print("share of family that is secondary:", (TOT-nprim)/TOT)
print("share of E[FP] from primary layer:", nprim*0.05/(0.05*TOT))
# per-model cells
for m in MODELS:
    rows=[r for r in recs if r["model"]==m]
    b=sum(1 for r in rows if r["A_correct"]==1 and r["B_correct"]==0)
    c=sum(1 for r in rows if r["A_correct"]==0 and r["B_correct"]==1)
    print(f"  {m:28s} n={len(rows)} b={b} c={c} disc={b+c}")
print("total discordant cells:", sum(1 for r in recs if r["A_correct"]!=r["B_correct"]))

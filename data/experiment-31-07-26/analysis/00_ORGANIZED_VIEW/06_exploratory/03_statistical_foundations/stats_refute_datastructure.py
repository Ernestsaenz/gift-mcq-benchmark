import json, collections, math
P='/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json'
raw=json.load(open(P))
if isinstance(raw,dict):
    print("TOP-LEVEL DICT keys:", list(raw.keys()))
    # try to find list
    for k,v in raw.items():
        if isinstance(v,list):
            print("  list key",k,len(v)); rows=v
else:
    rows=raw
print("records in file:", len(rows))
print("sample keys:", sorted(rows[0].keys()))
inc=[r for r in rows if r.get('analysis_include') is True]
print("analysis_include True:", len(inc))
print("analysis_include value types:", collections.Counter(repr(r.get('analysis_include')) for r in rows))

items=sorted({r['question_id'] for r in inc})
models=sorted({r['model'] for r in inc})
clusters={r['cluster'] for r in inc}
print("items:",len(items),"models:",len(models),"clusters:",len(clusters))
print("models list:",models)

cell=collections.Counter((r['question_id'],r['model']) for r in inc)
print("cells per (item,model) histogram:", collections.Counter(cell.values()))
mpi=collections.Counter()
for q in items:
    mpi[q]=len({m for (qq,m) in cell if qq==q})
print("models-per-item histogram:", collections.Counter(mpi.values()))
short=[q for q in items if mpi[q]!=len(models)]
print("items with <4 models:", short)
for q in short:
    have={r['model'] for r in inc if r['question_id']==q}
    print("  ",q,"cluster",{r['cluster'] for r in inc if r['question_id']==q},"has:",sorted(have),"MISSING:",sorted(set(models)-have))

# cluster consistency, analysis subset and full file
for name,rs in (("analysis",inc),("full",rows)):
    m=collections.defaultdict(set)
    for r in rs: m[r['question_id']].add(r['cluster'])
    bad={k:v for k,v in m.items() if len(v)!=1}
    print(f"{name}: items={len(m)} clusters={len({r['cluster'] for r in rs})} multi-cluster items={len(bad)}", bad if bad else "")

# per-model counts and accuracy
print()
print("per-model:")
tot=[0,0,0.0,0.0]
for mo in models:
    sub=[r for r in inc if r['model']==mo]
    n=len(sub)
    a=sum(r['A_correct'] for r in sub); b=sum(r['B_correct'] for r in sub)
    print(f"  {mo:28s} n={n} A={a}/{n}={a/n:.4f} B={b}/{n}={b/n:.4f} d={b/n-a/n:+.4f}")
    tot[0]+=n; tot[2]+=a; tot[3]+=b
N=len(inc); A=sum(r['A_correct'] for r in inc); B=sum(r['B_correct'] for r in inc)
print(f"  POOLED n={N} A={A}/{N}={A/N:.4f} B={B}/{N}={B/N:.4f} delta={B/N-A/N:+.4f}")

# A/B correct value domain
print("A_correct values:", collections.Counter(r['A_correct'] for r in inc), " B:", collections.Counter(r['B_correct'] for r in inc))

import json, math, collections, itertools, os
HERE=os.path.dirname(os.path.abspath(__file__))
recs=[r for r in json.load(open(os.path.join(HERE,'paired_clean.json'))) if r['analysis_include']]
MODELS=sorted({r['model'] for r in recs})
print("EXACT DECOMPOSITION  delta = pA*loss_rate - (1-pA)*gain_rate")
for m in MODELS:
    rs=[r for r in recs if r['model']==m]; n=len(rs)
    A=sum(r['A_correct'] for r in rs); B=sum(r['B_correct'] for r in rs)
    b=sum(1 for r in rs if r['A_correct']==1 and r['B_correct']==0)
    c=sum(1 for r in rs if r['A_correct']==0 and r['B_correct']==1)
    pA=A/n; lr=b/A; gr=c/(n-A)
    lhs=(A-B)/n; rhs=pA*lr-(1-pA)*gr
    print(f"  {m:28s} delta={lhs:.6f}  pA*lr-(1-pA)*gr={rhs:.6f}  diff={lhs-rhs:.2e}"
          f"   [A-wrong stratum n={n-A}]")

# CI width comparison: ceiling instability
print("\nSTRATUM SIZES that drive each metric")
for m in MODELS:
    rs=[r for r in recs if r['model']==m]; n=len(rs)
    A=sum(r['A_correct'] for r in rs)
    print(f"  {m:28s} A-right n={A:3d}   A-wrong n={n-A:3d}  "
          f"(gain-rate rests on {n-A} items)")

# subgroup sweep detail
def logc(n,k): return math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)
def mcp(b,c):
    n=b+c
    if n==0: return 1.0
    lo=sum(math.exp(logc(n,k)-n*math.log(2)) for k in range(0,b+1))
    hi=sum(math.exp(logc(n,k)-n*math.log(2)) for k in range(b,n+1))
    return min(1.0,2*min(lo,hi))
FACT={'correct_letter':lambda r:r['correct_letter'],'negated_stem':lambda r:r['negated_stem'],
      'has_context':lambda r:r['has_context'],'region':lambda r:r['region'],'year':lambda r:r['year']}
res=[]
for f,g in FACT.items():
    for lev in sorted({str(g(r)) for r in recs}):
        for m in MODELS:
            rs=[r for r in recs if r['model']==m and str(g(r))==lev]
            if not rs: continue
            b=sum(1 for r in rs if r['A_correct']==1 and r['B_correct']==0)
            c=sum(1 for r in rs if r['A_correct']==0 and r['B_correct']==1)
            res.append((f,lev,m,len(rs),mcp(b,c)))
pv=[r[4] for r in res]; m_=len(pv)
idx=sorted(range(m_),key=lambda i:pv[i])
# BH
bhadj=[None]*m_; run=1.0
for rank in range(m_-1,-1,-1):
    i=idx[rank]; run=min(run,min(1.0,pv[i]*m_/(rank+1))); bhadj[i]=run
# Holm
hadj=[None]*m_; run=0.0
for rank,i in enumerate(idx):
    run=max(run,min(1.0,(m_-rank)*pv[i])); hadj[i]=run
nom=[i for i in range(m_) if pv[i]<0.05]
print(f"\nSUBGROUP SWEEP: {m_} tests, {len(nom)} nominally sig at p<.05")
print(f"  killed by BH   : {sum(1 for i in nom if bhadj[i]>=0.05)} of {len(nom)}")
print(f"  killed by Holm : {sum(1 for i in nom if hadj[i]>=0.05)} of {len(nom)}")
small=[i for i in nom if res[i][3]<30]
print(f"  nominal hits sitting in cells with n<30: {len(small)}")
print(f"  of those, surviving BH: {sum(1 for i in small if bhadj[i]<0.05)}")
# per-factor nominal hit counts
cnt=collections.Counter(res[i][0] for i in nom)
print("  nominal hits by factor:", dict(cnt))
cntbh=collections.Counter(res[i][0] for i in nom if bhadj[i]<0.05)
print("  BH-surviving by factor:", dict(cntbh))
# region/year specifically = the weakest layer
for f in ['region','year']:
    tot=sum(1 for r in res if r[0]==f)
    nm=sum(1 for i in nom if res[i][0]==f)
    bhs=sum(1 for i in nom if res[i][0]==f and bhadj[i]<0.05)
    ns=[res[i][3] for i in range(m_) if res[i][0]==f]
    print(f"  {f}: {tot} tests, median cell n={sorted(ns)[len(ns)//2]}, "
          f"min n={min(ns)}, nominal {nm}, BH-surviving {bhs}")

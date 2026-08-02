import json, math, collections
d=json.load(open("ca_ref_pull.json")); items=d["items"]; rows=d["rows"]
MODELS=["google/gemini-3.6-flash","google/gemma-4-26b-a4b-it","qwen/qwen3.6-35b-a3b","z-ai/glm-5.2"]
allq=list(items)  # insertion / dataset order
orc={}; gc={}
for r in rows:
    (orc if r["exp"]=="expA_or_310726" else gc)[(r["model"],r["qid"])]=r["lc_"]
cov=set(q for q in allq if all((m,q) in gc for m in MODELS))
print("covered(all4 GIFT):",len(cov)," uncovered:",len(allq)-len(cov))
ship=set(json.load(open("gift_coverage.json"))["complete_all_models"])
print("matches gift_coverage.json:",cov==ship)

meta=json.load(open("dataset_meta.json"))["exclusions"]
v2=set(meta["out_of_domain_law"])|set(meta["adjudicated_key_defect"])
v1_law=["b205","b238","b331","b341","b343","b378","b385","b391","b401","b420","b430"]
v1=set(v1_law)|set(meta["adjudicated_key_defect"])
print("v2 defects:",len(v2)," v1 defects:",len(v1)," v1 subset of v2:",v1<=v2)

def wilson(k,n,z=1.959963985):
    if n==0: return (0,0)
    p=k/n; c=z*z/n
    ctr=(p+c/2)/(1+c); half=z*math.sqrt(p*(1-p)/n+c/(4*n))/(1+c)
    return ctr-half,ctr+half
def acc(qs):
    k=n=0
    for q in qs:
        for m in MODELS:
            v=orc.get((m,q))
            if v is None: continue
            n+=1; k+=v
    return k,n
def show(label,S):
    k,n=acc(S); lo,hi=wilson(k,n)
    print(f"{label:38s} items={len(S):3d} cells={n:4d} k={k:4d} {100*k/n:6.2f}%  [{100*lo:.2f},{100*hi:.2f}]")
    return k,n

print("\n=== RAW (no exclusions) ===")
kc,nc=show("covered 319",cov); ku,nu=show("uncovered",set(allq)-cov)
print(f"  gap = {100*(ku/nu-kc/nc):+.2f} pp")
print("\n=== v1 exclusions (14) - what the CLAIM used ===")
kc1,nc1=show("covered clean v1",cov-v1); ku1,nu1=show("uncovered clean v1",set(allq)-cov-v1)
print(f"  gap = {100*(ku1/nu1-kc1/nc1):+.2f} pp")
show("all clean v1",set(allq)-v1)
print("\n=== v2 exclusions (22) - CANONICAL ===")
kc2,nc2=show("covered clean v2",cov-v2); ku2,nu2=show("uncovered clean v2",set(allq)-cov-v2)
print(f"  gap = {100*(ku2/nu2-kc2/nc2):+.2f} pp")
show("all clean v2",set(allq)-v2)

# ---- cross-check against shipped cross_arm_A.json ----
ca=json.load(open("cross_arm_A.json"))
inc=[r for r in ca if r["analysis_include"]]
print("\ncross_arm_A.json: cells",len(ca),"include",len(inc),
      "items_inc",len(set(r['question_id'] for r in inc)),
      "clusters_inc",len(set(r['cluster'] for r in inc)))
# does shipped or_correct match my DB pull?
mm=sum(1 for r in ca if orc.get((r["model"],r["question_id"]))!=r["or_correct"])
mg=sum(1 for r in ca if gc.get((r["model"],r["question_id"]))!=r["gift_correct"])
print("shipped-vs-DB mismatches: or",mm,"gift",mg)
excl_items=set(r["question_id"] for r in ca if not r["analysis_include"])
print("items excluded inside cross_arm_A:",len(excl_items),"== cov&v2?",excl_items==(cov&v2))

print("\n=== ORDER STRUCTURE (dataset insertion order 0..473) ===")
o={q:i for i,q in enumerate(allq)}
co=sorted(o[q] for q in cov); uo=sorted(o[q] for q in set(allq)-cov)
def med(a): 
    n=len(a); return (a[n//2] if n%2 else (a[n//2-1]+a[n//2])/2)
print("covered   n=%d min=%d median=%s max=%d"%(len(co),co[0],med(co),co[-1]))
print("uncovered n=%d min=%d median=%s max=%d"%(len(uo),uo[0],med(uo),uo[-1]))
print("claim's 'median rank 211/396' uses lower-middle element:",co[len(co)//2],uo[len(uo)//2])
print("covered in first 250:",sum(1 for x in co if x<250),"/250   in 250-473:",sum(1 for x in co if x>=250),"/224")
print("\ncoverage by decile of dataset order:")
for b in range(10):
    lo_,hi_=b*47.4,(b+1)*47.4
    tot=[q for q in allq if lo_<=o[q]<hi_]
    c=sum(1 for q in tot if q in cov)
    k,n=acc(tot)
    print(f"  pos {int(lo_):3d}-{int(hi_):3d}: covered {c:3d}/{len(tot):3d} ({100*c/len(tot):5.1f}%)  OR acc {100*k/n:5.1f}%")
# longest true prefix
pref=0
for q in allq:
    if q in cov: pref+=1
    else: break
print("\nlongest UNBROKEN covered prefix:",pref,"items (of 319 covered)")
runs=[]; cur=None
for q in allq:
    s=q in cov
    if s!=cur: runs.append([s,0]); cur=s
    runs[-1][1]+=1
print("number of alternating covered/uncovered runs:",len(runs))
print("first 20 runs:",[(('C' if s else 'U'),n) for s,n in runs[:20]])

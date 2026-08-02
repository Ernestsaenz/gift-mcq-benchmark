"""Holm and BH applied to the OBSERVED 160-test family (same instantiation as
stats_refute_mult_02_fwer.py).  This is the quantity that bears on what may be
reported -- the claim never computes it for anything beyond the 4 primary tests."""
import json, math, os, itertools, collections
exec(open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/stats_refute_mult_02_fwer.py").read().split("# ---- observed (real data)")[0].replace('int(sys.argv[1]) if len(sys.argv)>1 else 20000','0'))

def run_family_p(bit):
    ps=[]; labs=[]
    for mi in range(4):
        mem=prim_mem[mi]; b=sum(bit[j] for j in mem)
        ps.append(mcp(b,len(mem)-b)); labs.append(("primary",MODELS[mi]))
    bc_pm={}
    for key in SUB_PM:
        mem=sub_pm.get(key,[]); n=len(mem); b=sum(bit[j] for j in mem)
        bc_pm[key]=(b,n-b); ps.append(mcp(b,n-b)); labs.append(("subgroup_permodel",f"{key[0]}={key[1]}|{MODELS[key[2]]}"))
    bc_po={}
    for key in SUB_PO:
        mem=sub_po.get(key,[]); n=len(mem); b=sum(bit[j] for j in mem)
        bc_po[key]=(b,n-b); ps.append(mcp(b,n-b)); labs.append(("subgroup_pooled",f"{key[0]}={key[1]}"))
    def homog(cells):
        cells=[(b,c) for b,c in cells if b+c>0]
        if len(cells)<2: return 1.0
        B=sum(b for b,_ in cells); C=sum(c for _,c in cells); N=B+C
        if B==0 or C==0: return 1.0
        x=0.0
        for b,c in cells:
            n=b+c; eb=n*B/N; ec=n*C/N; x+=(b-eb)**2/eb+(c-ec)**2/ec
        return chisq_sf(x,len(cells)-1)
    for f,mi in MOD_PM: ps.append(homog([bc_pm[(f,L,mi)] for L in lev[f]])); labs.append(("moderator_permodel",f"{f}|{MODELS[mi]}"))
    for f in MOD_PO:    ps.append(homog([bc_po[(f,L)] for L in lev[f]]));    labs.append(("moderator_pooled",f))
    for p in PAIRS:
        s=0.0; ss=0.0
        for q in pair_items[p]:
            d=item_cells[q]
            e0=(1 if bit[d[p[0]]] else -1) if p[0] in d else 0
            e1=(1 if bit[d[p[1]]] else -1) if p[1] in d else 0
            v=e0-e1; s+=v; ss+=v*v
        ps.append(norm_sf2(s/math.sqrt(ss)) if ss>0 else 1.0)
        labs.append(("between_model",f"{MODELS[p[0]].split('/')[-1]} vs {MODELS[p[1]].split('/')[-1]}"))
    return ps,labs

obs_bit=[1 if d[3]==1 else 0 for d in disc]
ps,labs=run_family_p(obs_bit); m=len(ps); assert m==160
idx=sorted(range(m),key=lambda i:ps[i])
holm=[0]*m; run=0.0
for r,i in enumerate(idx):
    run=max(run,min(1.0,(m-r)*ps[i])); holm[i]=run
bh=[0]*m; run=1.0
for r in range(m-1,-1,-1):
    i=idx[r]; run=min(run,min(1.0,ps[i]*m/(r+1))); bh[i]=run
lay=collections.defaultdict(lambda:[0,0,0,0])
for i in range(m):
    l=labs[i][0]; lay[l][0]+=1
    if ps[i]<0.05: lay[l][1]+=1
    if holm[i]<0.05: lay[l][2]+=1
    if bh[i]<0.05:  lay[l][3]+=1
print("Holm and BH across the FULL 160-test family (observed data):")
print(f"{'layer':22s} {'k':>4s} {'nominal p<.05':>14s} {'Holm<.05':>9s} {'BH<.05':>7s}")
T=[0,0,0,0]
for l in ["primary","subgroup_permodel","subgroup_pooled","moderator_permodel","moderator_pooled","between_model"]:
    a=lay[l]; print(f"{l:22s} {a[0]:4d} {a[1]:14d} {a[2]:9d} {a[3]:7d}")
    for k in range(4): T[k]+=a[k]
print(f"{'TOTAL':22s} {T[0]:4d} {T[1]:14d} {T[2]:9d} {T[3]:7d}")
print(f"\nBH bound on expected false discoveries among the {T[3]} BH-significant results:")
print(f"   <= 0.05 x {T[3]} = {0.05*T[3]:.2f}  (NOT 8; 8 is a global-null counterfactual")
print(f"   for a global null the data reject at p ~ 1e-12)")
print(f"\nAll 4 primary p-values x 160 (Bonferroni vs the WHOLE family):")
for i in range(4): print(f"   {labs[i][1]:28s} {ps[i]:.3e} -> {min(1,ps[i]*160):.3e}  "
                         f"{'survives' if ps[i]*160<0.05 else 'FAILS'}")

"""
Between-model robustness contrasts, done properly:
  (i)   cluster bootstrap, B=50000, percentile CI + CI-inversion p
  (ii)  Holm step-down over the 6 pairwise contrasts
  (iii) bootstrap max-|t| SIMULTANEOUS band (accounts for the correlation among the
        6 contrasts -- they all share models, so Bonferroni/Holm is conservative)
  (iv)  cluster SIGN-FLIP permutation test, an independent non-bootstrap method
Also: cluster sign-flip permutation p for each model's own A->B delta.
"""
import json, math, random, collections

PATH="/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
rows=[r for r in json.load(open(PATH)) if r.get("analysis_include") is True]
MODELS=["google/gemini-3.6-flash","z-ai/glm-5.2","qwen/qwen3.6-35b-a3b","google/gemma-4-26b-a4b-it"]
SHORT={"google/gemini-3.6-flash":"gemini","z-ai/glm-5.2":"glm-5.2",
       "qwen/qwen3.6-35b-a3b":"qwen3.6","google/gemma-4-26b-a4b-it":"gemma-4"}
MI={m:i for i,m in enumerate(MODELS)}
B=50000; SEED=20260731

tmp=collections.defaultdict(lambda:[0]*12)
for r in rows:
    i=MI[r["model"]]; v=tmp[r["cluster"]]
    v[3*i]+=1; v[3*i+1]+=r["A_correct"]; v[3*i+2]+=r["B_correct"]
CL=[tuple(v) for v in tmp.values()]; K=len(CL)

def deltas(A):
    return [100.0*(A[3*i+2]-A[3*i+1])/A[3*i] for i in range(4)]
tot=[0]*12
for c in CL:
    for j in range(12): tot[j]+=c[j]
OBS=deltas(tot)
PAIRS=[(i,j) for i in range(4) for j in range(i+1,4)]
OBSD={p:OBS[p[0]]-OBS[p[1]] for p in PAIRS}

def sdv(a):
    m=sum(a)/len(a); return math.sqrt(sum((x-m)**2 for x in a)/(len(a)-1))
def pctl(sv,p):
    n=len(sv); x=p/100*(n-1); lo=int(math.floor(x)); hi=min(lo+1,n-1)
    return sv[lo]+(x-lo)*(sv[hi]-sv[lo])

print(f"cluster bootstrap, K={K} clusters, B={B}, seed={SEED}")
rnd=random.Random(SEED)
rep={p:[] for p in PAIRS}
for _ in range(B):
    A=[0]*12
    for c in rnd.choices(CL,k=K):
        A[0]+=c[0];A[1]+=c[1];A[2]+=c[2];A[3]+=c[3];A[4]+=c[4];A[5]+=c[5]
        A[6]+=c[6];A[7]+=c[7];A[8]+=c[8];A[9]+=c[9];A[10]+=c[10];A[11]+=c[11]
    d=deltas(A)
    for p in PAIRS: rep[p].append(d[p[0]]-d[p[1]])

SE={p:sdv(rep[p]) for p in PAIRS}
CI={p:(pctl(sorted(rep[p]),2.5),pctl(sorted(rep[p]),97.5)) for p in PAIRS}
Praw={}
for p in PAIRS:
    v=rep[p]; ge=sum(1 for x in v if x>=0)/B; le=sum(1 for x in v if x<=0)/B
    Praw[p]=min(1.0, 2*min(ge,le))

# max-|t| simultaneous band over the 6 correlated contrasts
maxt=[]
for b in range(B):
    m=0.0
    for p in PAIRS:
        t=abs(rep[p][b]-OBSD[p])/SE[p]
        if t>m: m=t
    maxt.append(m)
maxt_sorted=sorted(maxt)
crit=pctl(maxt_sorted,95.0)
Padj_maxt={}
for p in PAIRS:
    t0=abs(OBSD[p])/SE[p]
    Padj_maxt[p]=sum(1 for x in maxt if x>=t0)/B

# Holm step-down on the raw bootstrap p-values
order=sorted(PAIRS,key=lambda p:Praw[p]); holm={}; run=0.0
for r_,p in enumerate(order):
    val=(len(PAIRS)-r_)*Praw[p]; run=max(run,val); holm[p]=min(1.0,run)

# cluster sign-flip permutation for each contrast: flip the sign of the whole cluster's
# contribution to (delta_i - delta_j). Valid under exchangeability of the two models.
def signflip_pair(i,j,nperm=50000,seed=99):
    per=[]
    for c in CL:
        ni,nj=c[3*i],c[3*j]
        si=(c[3*i+2]-c[3*i+1]); sj=(c[3*j+2]-c[3*j+1])
        per.append((si,ni,sj,nj))
    Ni=sum(x[1] for x in per); Nj=sum(x[3] for x in per)
    obs=abs(100.0*sum(x[0] for x in per)/Ni - 100.0*sum(x[2] for x in per)/Nj)
    rr=random.Random(seed); cnt=0
    for _ in range(nperm):
        ai=aj=0
        for si,ni,sj,nj in per:
            if rr.getrandbits(1): ai+=si; aj+=sj
            else:                 ai+=sj; aj+=si
        if abs(100.0*ai/Ni - 100.0*aj/Nj) >= obs-1e-12: cnt+=1
    return (cnt+1)/(nperm+1)

print()
print("="*112)
print("BETWEEN-MODEL DIFFERENCE IN A->B DELTA  (positive = first model MORE robust)")
print("="*112)
print(f"{'contrast':>22s} {'diff':>7s} {'SE':>6s} {'95% CI (percentile)':>21s} {'p_boot':>9s} {'p_Holm':>8s} {'p_maxT':>8s} {'p_perm':>8s} {'simultaneous 95%':>20s}")
res={}
for p in sorted(PAIRS,key=lambda q:Praw[q]):
    i,j=p; nm=f"{SHORT[MODELS[i]]} - {SHORT[MODELS[j]]}"
    lo,hi=CI[p]; d=OBSD[p]
    slo,shi=d-crit*SE[p], d+crit*SE[p]
    pp=signflip_pair(i,j)
    pb=f"{Praw[p]:.5f}" if Praw[p]>0 else f"<{1/B:.5f}"
    res[nm]={"diff":d,"se":SE[p],"lo":lo,"hi":hi,"p_boot":Praw[p],"p_holm":holm[p],
             "p_maxt":Padj_maxt[p],"p_perm":pp,"sim_lo":slo,"sim_hi":shi}
    print(f"{nm:>22s} {d:+7.2f} {SE[p]:6.3f}  [{lo:+7.2f},{hi:+7.2f}] {pb:>9s} {holm[p]:8.4f} {Padj_maxt[p]:8.4f} {pp:8.4f}  [{slo:+7.2f},{shi:+7.2f}]")
print(f"\n   max-|t| simultaneous critical value over the 6 correlated contrasts = {crit:.3f}"
      f"  (vs 1.960 pointwise, vs {2.638:.3f} Bonferroni z at 0.05/6)")
print(f"   p_perm = cluster sign-flip permutation, 50000 flips, (count+1)/(nperm+1); tests model exchangeability")

# per-model delta vs 0, cluster sign-flip
print()
print("="*112)
print("EACH MODEL'S OWN A->B DELTA vs 0 -- cluster sign-flip permutation (independent of the bootstrap)")
print("="*112)
for i,m in enumerate(MODELS):
    per=[(c[3*i+2]-c[3*i+1], c[3*i]) for c in CL]
    N=sum(x[1] for x in per); obs=abs(100.0*sum(x[0] for x in per)/N)
    rr=random.Random(1234+i); cnt=0; NP=50000
    for _ in range(NP):
        a=0
        for s,n in per:
            a += s if rr.getrandbits(1) else -s
        if abs(100.0*a/N) >= obs-1e-12: cnt+=1
    print(f"{SHORT[m]:12s} delta={OBS[i]:+7.2f}pp   cluster sign-flip p = {(cnt+1)/(NP+1):.6f}   (min attainable = {1/(NP+1):.6f})")

json.dump({"n_boot":B,"maxt_crit":crit,"contrasts":res},
          open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/prim_model_contrasts.json","w"),indent=1)
print("\nwrote prim_model_contrasts.json")

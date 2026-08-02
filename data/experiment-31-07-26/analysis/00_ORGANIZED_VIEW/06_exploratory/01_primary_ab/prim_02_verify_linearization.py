"""
Deterministic cross-check of the bootstrap SEs, plus the variance decomposition that
explains why the naive binomial SE is NOT anticonservative for per-model deltas.

delta = sum_u S_u / sum_u n_u  is a RATIO estimator over resampling units u.
Its linearization (cluster-robust / sandwich) variance is
    Var(delta) = [ sum_u (S_u - delta*n_u)^2 ] / N^2
with S_u = sum of d over the unit's cells, n_u = cells in the unit, N = sum n_u.
Multiply by m/(m-1) for the usual small-sample df correction (m = #units).
This is exact arithmetic -- if it matches the bootstrap, the bootstrap is right.
"""
import json, math, collections, random

PATH="/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
rows=[r for r in json.load(open(PATH)) if r.get("analysis_include") is True]
MODELS=["google/gemini-3.6-flash","z-ai/glm-5.2","qwen/qwen3.6-35b-a3b","google/gemma-4-26b-a4b-it"]
SHORT={"google/gemini-3.6-flash":"gemini-3.6-flash","z-ai/glm-5.2":"glm-5.2",
       "qwen/qwen3.6-35b-a3b":"qwen3.6-35b-a3b","google/gemma-4-26b-a4b-it":"gemma-4-26b-a4b-it"}
MI={m:i for i,m in enumerate(MODELS)}

def lin_se(units, fpc=True):
    """units: list of (S_u, n_u). Returns SE of the ratio estimator in pp."""
    N=sum(n for _,n in units); S=sum(s for s,_ in units); m=len(units)
    delta=S/N
    v=sum((s-delta*n)**2 for s,n in units)/(N*N)
    if fpc: v*= m/(m-1)
    return 100.0*math.sqrt(v), 100.0*delta

print("="*104)
print("A. LINEARIZATION (CLUSTER-ROBUST) SE  vs  BOOTSTRAP SE   -- deterministic check")
print("="*104)
boot=json.load(open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/prim_cluster_bootstrap_results.json"))
print(f"{'':20s} {'delta':>8s} {'SE_lin_clus':>11s} {'SE_boot_clus':>12s} {'SE_lin_item':>11s} {'SE_boot_item':>12s}")
for i,m in enumerate(MODELS):
    sub=[r for r in rows if MI[r['model']]==i]
    cl=collections.defaultdict(lambda:[0,0]); it=collections.defaultdict(lambda:[0,0])
    for r in sub:
        d=r["B_correct"]-r["A_correct"]
        cl[r["cluster"]][0]+=d; cl[r["cluster"]][1]+=1
        it[r["question_id"]][0]+=d; it[r["question_id"]][1]+=1
    sec,dl=lin_se([tuple(v) for v in cl.values()]); sei,_=lin_se([tuple(v) for v in it.values()])
    print(f"{SHORT[m]:20s} {dl:+8.2f} {sec:11.3f} {boot['cluster_boot'][SHORT[m]]['se']:12.3f} {sei:11.3f} {boot['item_boot_se'][SHORT[m]]:12.3f}")
cl=collections.defaultdict(lambda:[0,0]); it=collections.defaultdict(lambda:[0,0])
for r in rows:
    d=r["B_correct"]-r["A_correct"]
    cl[r["cluster"]][0]+=d; cl[r["cluster"]][1]+=1
    it[r["question_id"]][0]+=d; it[r["question_id"]][1]+=1
sec,dl=lin_se([tuple(v) for v in cl.values()]); sei,_=lin_se([tuple(v) for v in it.values()])
print(f"{'POOLED':20s} {dl:+8.2f} {sec:11.3f} {boot['cluster_boot']['pooled']['se']:12.3f} {sei:11.3f} {boot['item_boot_se']['pooled']:12.3f}")

print()
print("="*104)
print("B. WHY NAIVE BINOMIAL IS NOT ANTICONSERVATIVE PER MODEL: THE A/B PAIRING IS STRONGLY POSITIVE")
print("="*104)
print("   Var(pB-pA) = Var(pA)+Var(pB) - 2Cov.  The naive binomial SE drops the -2Cov term.")
print("   McNemar discordant cells: b = A right & B wrong, c = A wrong & B right.")
print(f"{'':20s} {'n':>5s} {'a(11)':>6s} {'b(10)':>6s} {'c(01)':>6s} {'d(00)':>6s} {'phi':>7s} {'SE_bin':>7s} {'SE_pair':>8s} {'pairing gain':>13s}")
for i,m in enumerate(MODELS):
    sub=[r for r in rows if MI[r['model']]==i]
    n=len(sub)
    a=sum(1 for r in sub if r["A_correct"]==1 and r["B_correct"]==1)
    b=sum(1 for r in sub if r["A_correct"]==1 and r["B_correct"]==0)
    c=sum(1 for r in sub if r["A_correct"]==0 and r["B_correct"]==1)
    dd=sum(1 for r in sub if r["A_correct"]==0 and r["B_correct"]==0)
    pA=(a+b)/n; pB=(a+c)/n
    cov=a/n-pA*pB
    phi=cov/math.sqrt(pA*(1-pA)*pB*(1-pB)) if pA not in(0,1) and pB not in(0,1) else float('nan')
    se_bin=100*math.sqrt(pA*(1-pA)/n+pB*(1-pB)/n)
    se_pair=100*math.sqrt((pA*(1-pA)+pB*(1-pB)-2*cov)/n)
    print(f"{SHORT[m]:20s} {n:5d} {a:6d} {b:6d} {c:6d} {dd:6d} {phi:+7.3f} {se_bin:7.3f} {se_pair:8.3f} {100*(1-se_pair/se_bin):12.1f}%")

print()
print("="*104)
print("C. VARIANCE DECOMPOSITION OF THE POOLED DELTA  (where the extra uncertainty actually lives)")
print("="*104)
n=len(rows); dall=[r["B_correct"]-r["A_correct"] for r in rows]
mu=sum(dall)/n
se_cell=100*math.sqrt(sum((x-mu)**2 for x in dall)/(n-1)/n)
print(f"   level 0  cell-independent (treat all {n} cells as iid)      SE = {se_cell:.3f} pp")
print(f"   level 1  + item x model crossing  (item bootstrap)          SE = {boot['item_boot_se']['pooled']:.3f} pp"
      f"   -> DEff = {(boot['item_boot_se']['pooled']/se_cell)**2:.3f}")
print(f"   level 2  + clinical-context clustering (cluster bootstrap)  SE = {boot['cluster_boot']['pooled']['se']:.3f} pp"
      f"   -> DEff = {(boot['cluster_boot']['pooled']['se']/se_cell)**2:.3f}")
print(f"   share of total variance inflation from item x model crossing: "
      f"{100*((boot['item_boot_se']['pooled']/se_cell)**2-1)/((boot['cluster_boot']['pooled']['se']/se_cell)**2-1):.1f}%")
print(f"   share from clinical clustering on top of that:                "
      f"{100*((boot['cluster_boot']['pooled']['se']/se_cell)**2-(boot['item_boot_se']['pooled']/se_cell)**2)/((boot['cluster_boot']['pooled']['se']/se_cell)**2-1):.1f}%")

print()
print("="*104)
print("D. THE 11 MULTI-ITEM CLUSTERS: do they pull the ratio-estimator variance up or down?")
print("="*104)
print("   contribution of unit u to Var is (S_u - delta*n_u)^2. A big cluster whose mean d")
print("   sits near the grand mean delta contributes almost nothing despite its size.")
cl=collections.defaultdict(lambda:[0,0])
for r in rows:
    cl[r["cluster"]][0]+=r["B_correct"]-r["A_correct"]; cl[r["cluster"]][1]+=1
N=sum(v[1] for v in cl.values()); delta=sum(v[0] for v in cl.values())/N
big=sorted(((c,v) for c,v in cl.items() if v[1]>4), key=lambda t:-t[1][1])
print(f"{'cluster':>8s} {'cells':>6s} {'items':>6s} {'mean d':>8s} {'grand d':>8s} {'resid/cell':>11s} {'Var share %':>12s}")
tot=sum((v[0]-delta*v[1])**2 for v in cl.values())
for c,v in big:
    print(f"{c:>8d} {v[1]:6d} {v[1]//4:6d} {v[0]/v[1]:+8.4f} {delta:+8.4f} {(v[0]-delta*v[1])/v[1]:+11.4f} {100*(v[0]-delta*v[1])**2/tot:12.2f}")
bigshare=sum((v[0]-delta*v[1])**2 for c,v in big)/tot
bigcells=sum(v[1] for c,v in big)/N
print(f"   the 11 multi-item clusters hold {100*bigcells:.1f}% of cells but supply {100*bigshare:.1f}% of the cluster-robust variance")

print()
print("="*104)
print("E. MONTE-CARLO STABILITY OF THE CLUSTER BOOTSTRAP (3 independent seeds, B=20000)")
print("="*104)
CL=[]; tmp=collections.defaultdict(lambda:[0]*12)
for r in rows:
    i=MI[r["model"]]; v=tmp[r["cluster"]]
    v[3*i]+=1; v[3*i+1]+=r["A_correct"]; v[3*i+2]+=r["B_correct"]
CL=[tuple(v) for v in tmp.values()]
def sdv(a):
    m=sum(a)/len(a); return math.sqrt(sum((x-m)**2 for x in a)/(len(a)-1))
def pctl(sv,p):
    nn=len(sv); x=p/100*(nn-1); lo=int(x); hi=min(lo+1,nn-1)
    return sv[lo]+(x-lo)*(sv[hi]-sv[lo])
print(f"{'seed':>10s} " + " ".join(f"{SHORT[m][:14]:>16s}" for m in MODELS) + f" {'POOLED':>16s}")
for seed in (20260731, 777, 4242):
    rnd=random.Random(seed); res=[[] for _ in range(5)]
    for _ in range(20000):
        A=[0]*12
        for c in rnd.choices(CL,k=len(CL)):
            A[0]+=c[0];A[1]+=c[1];A[2]+=c[2];A[3]+=c[3];A[4]+=c[4];A[5]+=c[5]
            A[6]+=c[6];A[7]+=c[7];A[8]+=c[8];A[9]+=c[9];A[10]+=c[10];A[11]+=c[11]
        for i in range(4): res[i].append(100.0*(A[3*i+2]-A[3*i+1])/A[3*i])
        res[4].append(100.0*((A[2]+A[5]+A[8]+A[11])-(A[1]+A[4]+A[7]+A[10]))/(A[0]+A[3]+A[6]+A[9]))
    cells=[]
    for i in range(5):
        sv=sorted(res[i]); cells.append(f"{sdv(res[i]):.3f}/[{pctl(sv,2.5):+.2f},{pctl(sv,97.5):+.2f}]")
    print(f"{seed:>10d} " + " ".join(f"{c:>16s}" for c in cells))
print("   (format: SE/[2.5%,97.5%];  MC error on an SE with B=20000 is ~SE/sqrt(2B) = 0.5% of the SE)")

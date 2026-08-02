import json, math, random
from collections import defaultdict
P='/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json'
rows=[r for r in json.load(open(P)) if r.get('analysis_include')]
N=len(rows)
byclu=defaultdict(list)
for r in rows: byclu[r['cluster']].append(r)
clus=sorted(byclu)
K=len(clus)

# ---------- 1. Design effect: naive-McNemar vs cluster-robust ----------
d=[r['B_correct']-r['A_correct'] for r in rows]
mean=sum(d)/N
n10=sum(1 for x in d if x==-1); n01=sum(1 for x in d if x==1)
se_naive=math.sqrt(n10+n01)/N                      # McNemar / iid-pair SE for the mean difference
# cluster-robust (sandwich) SE of the mean of d
S=[sum(r['B_correct']-r['A_correct'] for r in byclu[c]) for c in clus]
n_c=[len(byclu[c]) for c in clus]
var_cr=sum((S[i]-mean*n_c[i])**2 for i in range(K))/N**2
se_cr=math.sqrt(var_cr)
print("mean paired diff = %.4f"%mean)
print("SE  iid/McNemar          = %.5f  -> z=%.2f"%(se_naive,mean/se_naive))
print("SE  cluster-robust (%d clusters) = %.5f  -> z=%.2f"%(K,se_cr,mean/se_cr))
print("design effect (var ratio) = %.3f   SE inflation = %.3f"%((se_cr/se_naive)**2, se_cr/se_naive))
def norm_sf(z):
    return 0.5*math.erfc(abs(z)/math.sqrt(2))
print("naive two-sided normal p        = %.3g"%(2*norm_sf(mean/se_naive)))
print("cluster-robust two-sided p      = %.3g"%(2*norm_sf(mean/se_cr)))

# ---------- 2. Cluster-level permutation test (swap A/B labels per cluster) ----------
random.seed(7)
R=20000
obs=abs(mean)
ge=0
for _ in range(R):
    tot=0
    for i in range(K):
        tot += S[i] if random.getrandbits(1) else -S[i]
    if abs(tot/N)>=obs-1e-12: ge+=1
print("\ncluster-sign-flip permutation test (%d reps, whole clusters relabelled): %d/%d exceed obs"%(R,ge,R))
print("  permutation p < %.2g  (floor set by reps; theoretical floor 2^-%d)"%(3.0/R,K))

# ---------- 3. Is the flip process really one-directional? transition probabilities ----------
Ap=[r for r in rows if r['A_correct']==1]; Am=[r for r in rows if r['A_correct']==0]
p_lost=n10/len(Ap); p_gain=n01/len(Am)
print("\nP(lost | A correct) = %d/%d = %.4f"%(n10,len(Ap),p_lost))
print("P(gain | A wrong)   = %d/%d = %.4f"%(n01,len(Am),p_gain))
print("difference (gain-lost) = %+.4f"%(p_gain-p_lost))

# ---------- 4. Switch analysis: where do switchers land? ----------
sw_Ap=[r for r in Ap if r['B_selected']!=r['A_selected']]
sw_Am=[r for r in Am if r['B_selected']!=r['A_selected']]
hit=sum(1 for r in sw_Am if r['B_correct']==1)
print("\nswitch rate | A correct = %d/%d = %.4f   (every such switch is a LOSS by construction)"%(len(sw_Ap),len(Ap),len(sw_Ap)/len(Ap)))
print("switch rate | A wrong   = %d/%d = %.4f"%(len(sw_Am),len(Am),len(sw_Am)/len(Am)))
print("of A-wrong switchers, land on the NOTA/correct slot: %d/%d = %.4f  (chance among remaining 3 = 0.3333)"%(hit,len(sw_Am),hit/len(sw_Am)))

# ---------- 5. Cluster bootstrap for all the derived quantities ----------
B=4000
random.seed(20260731)
acc=defaultdict(list)
for _ in range(B):
    samp=[byclu[random.choice(clus)] for _ in clus]
    T=L=G=ap=am=swm=hitm=0
    for g in samp:
        for r in g:
            T+=1
            if r['A_correct']:
                ap+=1
                if not r['B_correct']: L+=1
            else:
                am+=1
                if r['B_correct']: G+=1
                if r['B_selected']!=r['A_selected']:
                    swm+=1
                    if r['B_correct']: hitm+=1
    acc['p_lost'].append(L/ap); acc['p_gain'].append(G/am)
    acc['diff'].append(G/am - L/ap)
    acc['lossfrac'].append(L/(L+G))
    acc['hitrate'].append(hitm/swm if swm else float('nan'))
def ci(v):
    v=sorted(x for x in v if x==x)
    f=lambda q:(lambda i,lo=None: None)(0) 
    def pct(q):
        i=q*(len(v)-1); lo=int(i); hi=min(lo+1,len(v)-1); fr=i-lo
        return v[lo]*(1-fr)+v[hi]*fr
    return pct(0.025),pct(0.975)
print("\ncluster bootstrap (4000 reps over %d clusters):"%K)
for k in ['p_lost','p_gain','diff','lossfrac','hitrate']:
    lo,hi=ci(acc[k]); print("  %-9s 95%% CI [%.4f, %.4f]"%(k,lo,hi))
neg=sum(1 for x in acc['diff'] if x<=0)
print("  bootstrap P(P(gain|A-) <= P(lost|A+)) = %.4f  -> two-sided p = %.4f"%(neg/B, 2*min(neg,B-neg)/B))

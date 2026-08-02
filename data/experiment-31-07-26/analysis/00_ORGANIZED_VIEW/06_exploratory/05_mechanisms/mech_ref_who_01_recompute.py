import json, math, random
from collections import Counter, defaultdict

P='/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json'
raw=json.load(open(P))
rows=[r for r in raw if r.get('analysis_include')]
print("raw cells",len(raw),"included",len(rows))
print("items",len(set(r['question_id'] for r in rows)),
      "clusters",len(set(r['cluster'] for r in rows)),
      "models",len(set(r['model'] for r in rows)))

# check uniqueness of (question_id, model)
c=Counter((r['question_id'],r['model']) for r in rows)
print("dup (qid,model) pairs:",sum(1 for k,v in c.items() if v>1))

a=sum(r['A_correct'] for r in rows); b=sum(r['B_correct'] for r in rows)
n11=sum(1 for r in rows if r['A_correct']==1 and r['B_correct']==1)
n10=sum(1 for r in rows if r['A_correct']==1 and r['B_correct']==0)  # lost
n01=sum(1 for r in rows if r['A_correct']==0 and r['B_correct']==1)  # gained
n00=sum(1 for r in rows if r['A_correct']==0 and r['B_correct']==0)
N=len(rows)
print("2x2  A+B+=%d lost=%d gained=%d A-B-=%d  sum=%d"%(n11,n10,n01,n00,n11+n10+n01+n00))
print("A acc %.4f  B acc %.4f  net %.4f"%(a/N,b/N,(b-a)/N))
print("P(lost|A correct)=%d/%d=%.4f"%(n10,a,n10/a))
print("P(gained|A wrong)=%d/%d=%.4f"%(n01,N-a,n01/(N-a)))
d=n10+n01
print("discordant=%d  P(loss|discordant)=%.4f"%(d,n10/d))

# ---- Exact McNemar: two-sided binomial, p=0.5, on discordant pairs
def logC(n,k):
    return math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)
def binom_two_sided_exact(k,n,p=0.5):
    # method of small p: sum of all outcomes with prob <= prob(k)
    lp=[logC(n,i)+i*math.log(p)+(n-i)*math.log(1-p) for i in range(n+1)]
    thr=lp[k]+1e-9
    return sum(math.exp(x) for x in lp if x<=thr)
pmc=binom_two_sided_exact(n01,d)
print("Exact McNemar (two-sided exact binomial on %d discordant pairs) p=%.3g"%(d,pmc))

# ---- Clopper-Pearson for P(loss|discordant)
def betainc_reg(a,b,x):
    if x<=0: return 0.0
    if x>=1: return 1.0
    lbeta=math.lgamma(a)+math.lgamma(b)-math.lgamma(a+b)
    front=math.exp(a*math.log(x)+b*math.log(1-x)-lbeta)/a
    f,c_,d_=1.0,1.0,0.0
    for i in range(0,300):
        m=i//2
        if i==0: num=1.0
        elif i%2==0: num=(m*(b-m)*x)/((a+2*m-1)*(a+2*m))
        else: num=-((a+m)*(a+b+m)*x)/((a+2*m)*(a+2*m+1))
        d_=1.0+num*d_
        if abs(d_)<1e-30: d_=1e-30
        d_=1.0/d_
        c_=1.0+num/c_
        if abs(c_)<1e-30: c_=1e-30
        f*=c_*d_
        if abs(1.0-c_*d_)<1e-14: break
    r=front*(f-1.0)
    if x < (a+1)/(a+b+2): return r
    return r  # (regularised via continued fraction, valid branch used below)
def betainc(a,b,x):
    # use symmetry for convergence
    if x < (a+1.0)/(a+b+2.0):
        return betainc_reg(a,b,x)
    else:
        return 1.0-betainc_reg(b,a,1.0-x)
def bisect_beta(a,b,target):
    lo,hi=0.0,1.0
    for _ in range(200):
        mid=(lo+hi)/2
        if betainc(a,b,mid)<target: lo=mid
        else: hi=mid
    return (lo+hi)/2
def clopper_pearson(k,n,alpha=0.05):
    lo=0.0 if k==0 else bisect_beta(k,n-k+1,alpha/2)
    hi=1.0 if k==n else bisect_beta(k+1,n-k,1-alpha/2)
    return lo,hi
print("Clopper-Pearson P(loss|discordant) 95%% CI: [%.4f, %.4f]"%clopper_pearson(n10,d))
print("Clopper-Pearson P(lost|A correct) 95%% CI: [%.4f, %.4f]"%clopper_pearson(n10,a))
print("Clopper-Pearson P(gained|A wrong) 95%% CI: [%.4f, %.4f]"%clopper_pearson(n01,N-a))

# ---- Cluster bootstrap on net accuracy diff
byclu=defaultdict(list)
for r in rows: byclu[r['cluster']].append(r)
clus=sorted(byclu)
random.seed(20260731)
B=4000
nets=[];lossfracs=[]
for _ in range(B):
    samp=[byclu[random.choice(clus)] for _ in clus]
    tot=0;da=0;db=0;L=0;G=0
    for g in samp:
        for r in g:
            tot+=1;da+=r['A_correct'];db+=r['B_correct']
            if r['A_correct']==1 and r['B_correct']==0: L+=1
            elif r['A_correct']==0 and r['B_correct']==1: G+=1
    nets.append((db-da)/tot)
    lossfracs.append(L/(L+G) if L+G else float('nan'))
nets.sort();lossfracs.sort()
def pct(v,q): 
    i=q*(len(v)-1); lo=int(i); hi=min(lo+1,len(v)-1); f=i-lo
    return v[lo]*(1-f)+v[hi]*f
print("cluster bootstrap (%d reps, resampling %d clusters) net acc diff 95%% CI [%.4f, %.4f]"%(B,len(clus),pct(nets,0.025),pct(nets,0.975)))
print("cluster bootstrap P(loss|discordant) 95%% CI [%.4f, %.4f]"%(pct(lossfracs,0.025),pct(lossfracs,0.975)))

"""MC stability of the percentile-CI-width %, and the paired-comparator framing."""
import json, math, random, collections
PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
rows = [r for r in json.load(open(PATH)) if r.get("analysis_include") is True]
MODELS = ["google/gemini-3.6-flash","z-ai/glm-5.2","qwen/qwen3.6-35b-a3b","google/gemma-4-26b-a4b-it"]
SHORT = {MODELS[0]:"gemini",MODELS[1]:"glm-5.2",MODELS[2]:"qwen3.6",MODELS[3]:"gemma-4"}
Z=1.959963984540054
def mean(a): return sum(a)/len(a)
def sd1(a):
    m=mean(a); return math.sqrt(sum((x-m)**2 for x in a)/(len(a)-1))
def sd0(a):
    m=mean(a); return math.sqrt(sum((x-m)**2 for x in a)/len(a))

CL=collections.defaultdict(lambda: collections.defaultdict(lambda:[0,0,0]))
CP=collections.defaultdict(lambda:[0,0,0])
for r in rows:
    v=CL[r["cluster"]][r["model"]]; v[0]+=1; v[1]+=r["A_correct"]; v[2]+=r["B_correct"]
    w=CP[r["cluster"]];             w[0]+=1; w[1]+=r["A_correct"]; w[2]+=r["B_correct"]
FLAT=[]
for c in sorted(CL):
    v=[]
    for m in MODELS: v.extend(CL[c][m])
    v.extend(CP[c]); FLAT.append(tuple(v))

def pct(sv,p):
    n=len(sv); x=p/100*(n-1); lo=int(math.floor(x)); hi=lo+1
    return sv[-1] if hi>=n else sv[lo]+(x-lo)*(sv[hi]-sv[lo])

def boot(nboot,seed):
    rnd=random.Random(seed); ch=rnd.choices; nU=len(FLAT)
    out=[[] for _ in range(5)]
    for _ in range(nboot):
        acc=[0]*15
        for u in ch(FLAT,k=nU):
            for j in range(15): acc[j]+=u[j]
        for i in range(5):
            n_,a_,b_=acc[3*i],acc[3*i+1],acc[3*i+2]
            out[i].append(100.0*(b_-a_)/n_)
    return out

# naive analytic SEs
NAIVE={}
for m in MODELS:
    R=[r for r in rows if r["model"]==m]; n=len(R)
    A=[r["A_correct"] for r in R]; B=[r["B_correct"] for r in R]
    d=[b-a for a,b in zip(A,B)]; pA=sum(A)/n; pB=sum(B)/n
    NAIVE[m]=(100*sd1(d)/math.sqrt(n), 100*math.sqrt(pA*(1-pA)/n+pB*(1-pB)/n))
alld=[r["B_correct"]-r["A_correct"] for r in rows]; N=len(alld)
pA=sum(r["A_correct"] for r in rows)/N; pB=sum(r["B_correct"] for r in rows)/N
NAIVE["pool"]=(100*sd1(alld)/math.sqrt(N), 100*math.sqrt(pA*(1-pA)/N+pB*(1-pB)/N))

SEEDS=[101,202,303,404,505]
print("MC spread of '% naive-binomial CI too wide' (percentile-width basis), B=20000, 5 seeds")
print(f"{'':10s} " + " ".join(f"{'s'+str(s):>8s}" for s in SEEDS) + f" {'spread':>8s} | {'SE-ratio basis':>15s}")
store={}
for s in SEEDS: store[s]=boot(20000,s)
keys=list(range(4))+["pool"]
for i in keys:
    lab = "POOLED" if i=="pool" else SHORT[MODELS[i]]
    key = "pool" if i=="pool" else MODELS[i]
    sp_,sb = NAIVE[key]
    idx = 4 if i=="pool" else i
    vals=[]
    for s in SEEDS:
        sv=sorted(store[s][idx]); wc=pct(sv,97.5)-pct(sv,2.5)
        vals.append(100*(1-2*Z*sb/wc))
    ses=[sd1(store[s][idx]) for s in SEEDS]
    se_basis=100*(1-sb/mean(ses))
    print(f"{lab:10s} " + " ".join(f"{v:8.2f}" for v in vals) +
          f" {max(vals)-min(vals):8.2f} | {se_basis:15.2f}")

print()
print("Cluster SE vs the DESIGN-CORRECT naive comparator (paired Wald), SE-ratio basis:")
print(f"{'':10s} {'SEclus':>8s} {'SEpair':>8s} {'clus/pair':>9s} {'paired Wald is':>34s}")
for i in keys:
    lab = "POOLED" if i=="pool" else SHORT[MODELS[i]]
    key = "pool" if i=="pool" else MODELS[i]
    sp_,sb = NAIVE[key]
    idx = 4 if i=="pool" else i
    sc = mean([sd1(store[s][idx]) for s in SEEDS])
    r=sc/sp_
    verdict = f"{100*(r-1):+.1f}% TOO NARROW" if r>1 else f"{100*(1-r):.1f}% too wide"
    print(f"{lab:10s} {sc:8.4f} {sp_:8.4f} {r:9.4f} {verdict:>34s}")

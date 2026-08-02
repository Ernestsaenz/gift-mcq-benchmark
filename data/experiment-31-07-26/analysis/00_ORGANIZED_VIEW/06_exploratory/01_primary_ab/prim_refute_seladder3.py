"""Per-model cluster/item SE ratio: MC stability + is gemma's 1.161 real?"""
import json, math, random, collections
PATH="/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
rows=[r for r in json.load(open(PATH)) if r.get("analysis_include") is True]
MODELS=["google/gemini-3.6-flash","z-ai/glm-5.2","qwen/qwen3.6-35b-a3b","google/gemma-4-26b-a4b-it"]
SHORT=["gemini","glm","qwen","gemma"]; MI={m:i for i,m in enumerate(MODELS)}; NM=4
def blank(): return [0]*12
iv=collections.defaultdict(blank); cv=collections.defaultdict(blank)
for r in rows:
    i=MI[r["model"]]
    for t in (iv[r["question_id"]],cv[r["cluster"]]):
        t[3*i]+=1; t[3*i+1]+=r["A_correct"]; t[3*i+2]+=r["B_correct"]
ITEMS=[tuple(v) for v in iv.values()]; CLUS=[tuple(v) for v in cv.values()]
def mean(a): return sum(a)/len(a)
def sd(a):
    m=mean(a); return math.sqrt(sum((x-m)**2 for x in a)/(len(a)-1))
def boot(U,nb,seed):
    rnd=random.Random(seed); n=len(U); per=[[] for _ in range(NM)]; ch=rnd.choices
    for _ in range(nb):
        a=[0]*12
        for c in ch(U,k=n):
            for j in range(12): a[j]+=c[j]
        for i in range(NM): per[i].append(100.0*(a[3*i+2]-a[3*i+1])/a[3*i])
    return per
print("per-model SE_clus/SE_item across 5 seed pairs, B=20000")
acc={i:[] for i in range(NM)}
for s in range(5):
    IP=boot(ITEMS,20000,700000+s); CP=boot(CLUS,20000,600000+s)
    out=[]
    for i in range(NM):
        r_=sd(CP[i])/sd(IP[i]); acc[i].append(r_); out.append("%s=%.3f"%(SHORT[i],r_))
    print("  ",", ".join(out))
print("  mean/sd:", ", ".join("%s %.3f+-%.3f"%(SHORT[i],mean(acc[i]),sd(acc[i])) for i in range(NM)))

# gemma: which clusters drive it? linearization contributions, gemma only
g=[r for r in rows if MI[r["model"]]==3]
N=len(g); d0=sum(r["B_correct"]-r["A_correct"] for r in g)/N
cc=collections.defaultdict(lambda:[0,0])
for r in g:
    cc[r["cluster"]][0]+=1; cc[r["cluster"]][1]+=r["B_correct"]-r["A_correct"]
tot=sum((S-d0*n)**2 for n,S in cc.values())
print("\ngemma: grand d=%.4f  top clusters by variance contribution"%d0)
for c,(n,S) in sorted(cc.items(),key=lambda kv:-((kv[1][1]-d0*kv[1][0])**2))[:6]:
    print("   cluster %-4s items=%2d meand=%+.4f contrib=%5.1f%%"%(c,n,S/n,100*(S-d0*n)**2/tot))

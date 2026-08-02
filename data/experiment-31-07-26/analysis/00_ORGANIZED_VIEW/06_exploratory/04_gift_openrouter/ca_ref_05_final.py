#!/usr/bin/env python
"""Final refutation recompute: old (superseded) vs current cross_arm_A export."""
import json, math, collections, random

AN = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/"
SP = "/private/tmp/claude-501/-Users-ernestsaenz-Programming-GIFT-abstract-dossier/a0613478-db50-4bbd-ba89-911fee14cc09/scratchpad/"
NEW = json.load(open(SP + "cross_arm_A.NEW.json"))
EXTRA = {"b213", "b293", "b361", "b396", "b407"}   # the 5 added exclusions inside coverage

def chi2sf1(x): return math.erfc(math.sqrt(x/2.0)) if x > 0 else 1.0
def lch(n,k): return math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)
def pmf(n,k): return math.exp(lch(n,k)-n*math.log(2.0))
def exact2(k,n):
    if n==0: return float('nan')
    pk=pmf(n,k); return min(1.0,sum(pmf(n,i) for i in range(n+1) if pmf(n,i)<=pk*(1+1e-12)))

def blk(rows,label):
    n=len(rows)
    if n==0: print("%-30s EMPTY"%label); return
    g=sum(r["gift_correct"] for r in rows); o=sum(r["or_correct"] for r in rows)
    b=sum(1 for r in rows if r["gift_correct"] and not r["or_correct"])
    c=sum(1 for r in rows if not r["gift_correct"] and r["or_correct"]); nd=b+c
    cu=((b-c)**2)/nd if nd else float('nan'); cc=((abs(b-c)-1)**2)/nd if nd else float('nan')
    print("%-30s it=%3d n=%4d | GIFT %6.2f%% (%4d) OR %6.2f%% (%4d) d=%+5.2fpp | b=%2d c=%2d | "
          "chi2u=%6.3f p=%.4f  chi2c=%6.3f p=%.4f  exact=%.4f"
          %(label,len(set(r["question_id"] for r in rows)),n,100.*g/n,g,100.*o/n,o,100.*(g-o)/n,
            b,c,cu,chi2sf1(cu),cc,chi2sf1(cc),exact2(b,nd)))

# reconstruct the SUPERSEDED analysis set: current include-set PLUS the 5 re-included items
cur = [r for r in NEW if r["analysis_include"]]
old = [r for r in NEW if r["analysis_include"] or r["question_id"] in EXTRA]
print("reconstructed OLD set: items=%d cells=%d clusters=%d"
      %(len(set(r["question_id"] for r in old)),len(old),len(set(r["cluster"] for r in old))))
print("CURRENT set          : items=%d cells=%d clusters=%d"
      %(len(set(r["question_id"] for r in cur)),len(cur),len(set(r["cluster"] for r in cur))))

print("\n=== POOLED ===")
blk(old,"SUPERSEDED (311 it/1244)")
blk(cur,"CURRENT    (306 it/1224)")
print("\n=== the 5 out-of-domain items that were removed ===")
five=[r for r in NEW if r["question_id"] in EXTRA]
blk(five,"5 admin-law/mgmt items")
for q in sorted(EXTRA):
    rs=sorted([r for r in five if r["question_id"]==q],key=lambda x:x["model"])
    print("   %-6s gift %s  or %s   (%s)"%(q,"".join(str(r["gift_correct"]) for r in rs),
        "".join(str(r["or_correct"]) for r in rs),", ".join(r["model"].split("/")[-1] for r in rs)))

print("\n=== PER MODEL ===")
for m in sorted(set(r["model"] for r in cur)):
    blk([r for r in old if r["model"]==m], m.split("/")[-1]+"  SUPERSEDED")
    blk([r for r in cur if r["model"]==m], m.split("/")[-1]+"  CURRENT")
    print()

def cluster_exact(rows):
    d=collections.defaultdict(int)
    for r in rows: d[r["cluster"]] += r["gift_correct"]-r["or_correct"]
    nz=[v for v in d.values() if v]; T=sum(d.values()); off=sum(abs(v) for v in nz)
    dist=[0.0]*(2*off+1); dist[off]=1.0
    for v in nz:
        nd=[0.0]*(2*off+1)
        for i,p in enumerate(dist):
            if p: nd[i+v]+=p*.5; nd[i-v]+=p*.5
        dist=nd
    return T,len(nz),sum(p for i,p in enumerate(dist) if abs(i-off)>=abs(T))
for rows,lab in ((old,"SUPERSEDED"),(cur,"CURRENT")):
    T,k,p=cluster_exact(rows)
    print("cluster arm-flip EXACT DP  %-12s nonzero-clusters=%d  T=%+d  two-sided p=%.5f"%(lab,k,T,p))

# cluster bootstrap CI on current set
cl=collections.defaultdict(list)
for r in cur: cl[r["cluster"]].append(r)
keys=list(cl); rng=random.Random(7); B=20000; ds=[]
for _ in range(B):
    g=o=n=0
    for _ in keys:
        for r in cl[keys[rng.randrange(len(keys))]]:
            n+=1; g+=r["gift_correct"]; o+=r["or_correct"]
    ds.append(100.*(g-o)/n)
ds.sort()
print("\nCURRENT cluster bootstrap B=%d: 95%% CI [%+.2f, %+.2f] pp ; P(diff<=0)=%.4f"
      %(B,ds[int(.025*B)],ds[int(.975*B)],sum(1 for d in ds if d<=0)/B))

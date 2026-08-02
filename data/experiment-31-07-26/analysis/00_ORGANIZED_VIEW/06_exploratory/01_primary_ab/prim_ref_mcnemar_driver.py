import math
from fractions import Fraction

def sf(x): return math.erfc(math.sqrt(x/2.0))
def log10_exact(b,c):
    n=b+c; k=min(b,c)
    s=sum(math.comb(n,i) for i in range(k+1))
    num=2*s; den=1<<n
    if num>=den: return 0.0
    return (math.log(num)-math.log(den))/math.log(10)
def log10_cc(b,c):
    n=b+c; X=(abs(b-c)-1.0)**2/n
    return math.log10(sf(X)), X

print("=== TEST 1: is p_cc > p_exact ALWAYS? grid over b>=c, 1<=b+c<=60 ===")
viol=[]; tot=0
for n in range(1,61):
    for c in range(0,n//2+1):
        b=n-c; tot+=1
        lc,X=log10_cc(b,c); le=log10_exact(b,c)
        if lc < le - 1e-12: viol.append((b,c,n,X,10**lc,10**le))
print("tables checked:",tot," anti-conservative (p_cc < p_exact):",len(viol))
for v in viol[:12]: print("   b=%d c=%d n=%d X2=%.4f p_cc=%.4e p_exact=%.4e"%v)

print("\n=== TEST 2: hold tail depth ~fixed (X2 ~ 19.3, gemini's), vary b+c ===")
print("%6s %5s %5s %9s %13s %13s %8s"%("b+c","b","c","X2","p_cc","p_exact","ratio"))
target=19.3143
for n in [35,70,140,280,560,1120]:
    best=None
    for c in range(0,n//2+1):
        b=n-c
        X=(abs(b-c)-1.0)**2/n
        if best is None or abs(X-target)<abs(best[0]-target): best=(X,b,c)
    X,b,c=best
    lc,_=log10_cc(b,c); le=log10_exact(b,c)
    print("%6d %5d %5d %9.4f %13.4e %13.4e %8.3f"%(n,b,c,X,10**lc,10**le,10**(lc-le)))

print("\n=== TEST 3: hold b+c FIXED at 100 (gemma's), vary tail depth |b-c| ===")
print("%6s %5s %5s %9s %13s %13s %10s"%("b+c","b","c","X2","p_cc","p_exact","ratio"))
n=100
for c in [40,35,30,25,18,12,6,2]:
    b=n-c
    lc,X=log10_cc(b,c); le=log10_exact(b,c)
    print("%6d %5d %5d %9.4f %13.4e %13.4e %10.3f"%(n,b,c,X,10**lc,10**le,10**(lc-le)))

print("\n=== TEST 4: observed tables, ratio vs b+c and vs X2 (rank correlation) ===")
obs=[("gemini",31,4),("glm",67,8),("qwen",67,15),("gemma",82,18),("POOLED",247,45)]
recs=[]
for name,b,c in obs:
    lc,X=log10_cc(b,c); le=log10_exact(b,c)
    recs.append((name,b+c,X,lc-le))
print("%-8s %6s %10s %12s"%("table","b+c","X2","log10 gap"))
for r in sorted(recs,key=lambda r:r[1]): print("%-8s %6d %10.4f %12.4f"%r)
def spearman(xs,ys):
    def rank(v):
        s=sorted(range(len(v)),key=lambda i:v[i]); r=[0]*len(v)
        for j,i in enumerate(s): r[i]=j+1
        return r
    rx,ry=rank(xs),rank(ys); nn=len(xs)
    d2=sum((rx[i]-ry[i])**2 for i in range(nn))
    return 1-6*d2/(nn*(nn*nn-1))
print("Spearman(gap, b+c) = %.3f"%spearman([r[1] for r in recs],[r[3] for r in recs]))
print("Spearman(gap, X2 ) = %.3f"%spearman([r[2] for r in recs],[r[3] for r in recs]))

print("\n=== TEST 5: smallest p_cc among the 5 tables vs conventional alphas ===")
pcc=[10**log10_cc(b,c)[0] for _,b,c in obs]
print("max p_cc across tables = %.4e ; alpha=0.05/0.01/0.001, Bonferroni 0.05/5=0.01 -> all reject: %s"%(
    max(pcc), all(p<0.01 for p in pcc)))

import math
from itertools import permutations
names=["gemini-3.6-flash","glm-5.2","qwen3.6-35b-a3b","gemma-4-26b-a4b-it"]
A=[318/325, 302/324, 288/325, 258/325]
D=[(318-291)/325,(302-243)/324,(288-236)/325,(258-194)/325]
SUB=[222/241,195/241,186/241,170/241]  # common-subset B acc (all-4-A-correct items)
def pear(x,y):
    n=len(x);mx=sum(x)/n;my=sum(y)/n
    sxy=sum((a-mx)*(b-my) for a,b in zip(x,y))
    sxx=sum((a-mx)**2 for a in x);syy=sum((b-my)**2 for b in y)
    return sxy/math.sqrt(sxx*syy) if sxx>0 and syy>0 else float('nan')
def rk(v):
    o=sorted(range(len(v)),key=lambda k:v[k]);r=[0]*len(v)
    for i,k in enumerate(o): r[k]=i+1
    return r
def exact_p(x,y,stat_fn):
    s=stat_fn(x,y); allp=list(permutations(range(len(x))))
    ge=sum(1 for p in allp if abs(stat_fn(x,[y[k] for k in p]))>=abs(s)-1e-12)
    return s, ge, len(allp)
print("FULL n=4:")
for lab,y in (("delta",D),("common-subset B acc",SUB)):
    r,ge,tot=exact_p(A,y,pear)
    rs,ges,_=exact_p(A,y,lambda a,b: pear(rk(a),rk(b)))
    print(f"  r(A_acc, {lab:<20}) = {r:+.4f}  exact perm p={ge}/{tot}={ge/tot:.4f}"
          f"   | Spearman={rs:+.3f} p={ges}/{tot}={ges/tot:.4f}")
print("\nLEAVE-ONE-MODEL-OUT r(A_acc, delta)  (n=3 each, r is unstable by construction):")
for i in range(4):
    x=[A[k] for k in range(4) if k!=i]; y=[D[k] for k in range(4) if k!=i]
    print(f"  drop {names[i]:<20} r = {pear(x,y):+.4f}")
print("\nLEAVE-ONE-MODEL-OUT r(A_acc, common-subset B acc):")
for i in range(4):
    x=[A[k] for k in range(4) if k!=i]; y=[SUB[k] for k in range(4) if k!=i]
    print(f"  drop {names[i]:<20} r = {pear(x,y):+.4f}")
print("\nThree non-gemini models only (baseline A spans 79.4%-93.2%):")
print(f"  A     = {[round(a*100,1) for a in A[1:]]}")
print(f"  delta = {[round(d*100,1) for d in D[1:]]}  -> r = {pear(A[1:],D[1:]):+.4f}")

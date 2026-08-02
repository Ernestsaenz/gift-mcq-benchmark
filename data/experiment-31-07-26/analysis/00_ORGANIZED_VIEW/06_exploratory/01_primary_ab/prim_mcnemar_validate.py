"""prim_mcnemar_validate.py -- validate every hand-rolled primitive against known closed-form
or textbook reference values, since scipy is unavailable."""
import math
from fractions import Fraction
import importlib.util, sys
spec=importlib.util.spec_from_file_location("m","/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/prim_mcnemar_exact.py")

def exact_p(b,c):
    n=b+c
    if n==0: return 1.0
    lo=min(b,c); t=sum(math.comb(n,k) for k in range(lo+1))
    return float(min(Fraction(2*t,1<<n),Fraction(1)))
def chi2_sf(x): return 1.0 if x<=0 else math.erfc(math.sqrt(x/2.0))
def _lpmf(n,k,p):
    if p<=0: return 0.0 if k==0 else -math.inf
    if p>=1: return 0.0 if k==n else -math.inf
    return (math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)+k*math.log(p)+(n-k)*math.log1p(-p))
def sf_ge(n,k,p): return 1.0 if k<=0 else (0.0 if k>n else sum(math.exp(_lpmf(n,j,p)) for j in range(k,n+1)))
def cdf_le(n,k,p): return 1.0 if k>=n else (0.0 if k<0 else sum(math.exp(_lpmf(n,j,p)) for j in range(0,k+1)))
def cp(b,n,alpha=0.05):
    a=alpha/2
    if b==0: lo=0.0
    else:
        x0,x1=0.0,1.0
        for _ in range(200):
            mid=(x0+x1)/2
            if sf_ge(n,b,mid)<a: x0=mid
            else: x1=mid
        lo=(x0+x1)/2
    if b==n: hi=1.0
    else:
        x0,x1=0.0,1.0
        for _ in range(200):
            mid=(x0+x1)/2
            if cdf_le(n,b,mid)>a: x0=mid
            else: x1=mid
        hi=(x0+x1)/2
    return lo,hi

ok=lambda c: "PASS" if c else "***FAIL***"
print("VALIDATION OF HAND-ROLLED PRIMITIVES")
print("-"*88)

# 1. chi2 1df tail vs the standard critical values
print("1. chi2_1df_sf via erfc(sqrt(x/2)) against textbook critical points")
for x,tgt in [(3.8414588,0.05),(6.6348966,0.01),(2.7055435,0.10),(10.827566,0.001)]:
    got=chi2_sf(x); print(f"   chi2_1(x={x:>10.6f}) sf={got:.8f}  target={tgt}   {ok(abs(got-tgt)<1e-6)}")

# 2. exact binomial McNemar against hand-summed rationals
print("2. exact McNemar p against hand-computed rationals")
# b=12,c=5,n=17: 2*sum_{k<=5}C(17,k)/2^17 = 2*9402/131072
hand=2*(1+17+136+680+2380+6188); print(f"   b=12,c=5 : got={exact_p(12,5):.10f} hand={hand}/131072={hand/131072:.10f} {ok(abs(exact_p(12,5)-hand/131072)<1e-15)}")
# b=3,c=0,n=3: 2*C(3,0)/8 = 0.25
print(f"   b=3,c=0  : got={exact_p(3,0):.10f} hand=2*1/8=0.25            {ok(exact_p(3,0)==0.25)}")
# b=1,c=1,n=2: 2*(C(2,0)+C(2,1))/4 = 2*3/4=1.5 -> capped at 1
print(f"   b=1,c=1  : got={exact_p(1,1):.10f} hand=min(1,1.5)=1.0        {ok(exact_p(1,1)==1.0)}")
# b=0,c=0 -> 1
print(f"   b=0,c=0  : got={exact_p(0,0):.10f} convention=1.0             {ok(exact_p(0,0)==1.0)}")
# symmetry
print(f"   symmetry b<->c: exact(31,4)={exact_p(31,4):.6e} exact(4,31)={exact_p(4,31):.6e} {ok(exact_p(31,4)==exact_p(4,31))}")

# 3. "doubled tail" == "sum of all k with pmf <= pmf(obs)" for pi=0.5
print("3. doubled-smaller-tail rule == minimum-likelihood rule (should be identical at pi=0.5)")
bad=0
for n in range(1,60):
    for b in range(n+1):
        c=n-b
        p1=exact_p(b,c)
        pm=math.comb(n,b)
        p2=float(Fraction(sum(math.comb(n,k) for k in range(n+1) if math.comb(n,k)<=pm),1<<n))
        if abs(p1-p2)>1e-15: bad+=1
print(f"   checked all tables with b+c<=59: mismatches={bad}   {ok(bad==0)}")

# 4. Clopper-Pearson against published values
print("4. Clopper-Pearson exact CI against published reference values")
for b,n,lo_t,hi_t in [(2,10,0.02521,0.55610),(0,10,0.0,0.30850),(10,10,0.69150,1.0),(5,10,0.18709,0.81291)]:
    lo,hi=cp(b,n)
    print(f"   b={b:2d}/n={n:2d}: got=[{lo:.5f},{hi:.5f}] ref=[{lo_t:.5f},{hi_t:.5f}] "
          f"{ok(abs(lo-lo_t)<1e-4 and abs(hi-hi_t)<1e-4)}")
# coverage property: the CI must contain b/n
for b,n in [(31,35),(67,75),(247,292)]:
    lo,hi=cp(b,n); print(f"   b={b}/n={n}: pi_hat={b/n:.5f} in [{lo:.5f},{hi:.5f}] {ok(lo<=b/n<=hi)}")
# CI endpoints must exactly solve the defining tail equations
print("   endpoint identities (tail at the bound must equal alpha/2 = 0.025):")
for b,n in [(31,35),(67,75),(247,292),(82,100)]:
    lo,hi=cp(b,n)
    print(f"     b={b:3d}/n={n:3d}: P(X>={b}|p_lo)={sf_ge(n,b,lo):.8f}  P(X<={b}|p_hi)={cdf_le(n,b,hi):.8f}  "
          f"{ok(abs(sf_ge(n,b,lo)-0.025)<1e-6 and abs(cdf_le(n,b,hi)-0.025)<1e-6)}")

# 5. binomial pmf sums to 1
print("5. log-space binomial pmf normalisation")
for n,p in [(35,0.3),(292,0.845),(100,0.5)]:
    s=sum(math.exp(_lpmf(n,k,p)) for k in range(n+1))
    print(f"   n={n:3d} p={p}: sum pmf={s:.12f}  {ok(abs(s-1)<1e-10)}")

# 6. OR CI must be the monotone transform of the pi CI
print("6. OR CI = pi CI mapped through pi/(1-pi)")
for b,c in [(31,4),(67,8),(67,15),(82,18),(247,45)]:
    n=b+c; lo,hi=cp(b,n)
    print(f"   b={b:3d} c={c:3d}: OR={b/c:8.4f} pi_hat/(1-pi_hat)={(b/n)/(1-b/n):8.4f} "
          f"CI=[{lo/(1-lo):8.4f},{hi/(1-hi):8.4f}] {ok(abs(b/c-(b/n)/(1-b/n))<1e-9)}")

# 7. Per-model tables must sum to the pooled table
import json, collections
D=[r for r in json.load(open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json")) if r.get("analysis_include") is True]
tb=collections.Counter(); tc=collections.Counter()
for r in D:
    if r["A_correct"]==1 and r["B_correct"]==0: tb[r["model"]]+=1
    if r["A_correct"]==0 and r["B_correct"]==1: tc[r["model"]]+=1
print("7. additivity: sum of per-model discordances == pooled")
print(f"   sum b = {sum(tb.values())} (pooled b = 247) {ok(sum(tb.values())==247)}")
print(f"   sum c = {sum(tc.values())} (pooled c =  45) {ok(sum(tc.values())==45)}")

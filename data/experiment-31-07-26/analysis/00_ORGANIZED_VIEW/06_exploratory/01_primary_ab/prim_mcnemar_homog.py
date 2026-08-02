"""prim_mcnemar_homog.py -- do the four models' conditional ORs differ?
Test H0: pi_m = b_m/(b_m+c_m) equal across the 4 models.
METHOD 1: Pearson chi2 of homogeneity on the 2x4 table of (b,c), df=3, tail via a
          hand-written regularised incomplete gamma (series + continued fraction).
METHOD 2: exact-conditional Monte Carlo permutation -- shuffle the b/c labels among the
          292 discordant pairs holding both margins fixed, seed fixed, R=200000.
Also: exact CI overlap and the minimum b+c needed for the exact test to ever reject."""
import json, math, random, collections

D=[r for r in json.load(open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json")) if r.get("analysis_include") is True]
SHORT={"google/gemini-3.6-flash":"gemini-3.6-flash","z-ai/glm-5.2":"glm-5.2",
       "qwen/qwen3.6-35b-a3b":"qwen3.6-35b-a3b","google/gemma-4-26b-a4b-it":"gemma-4-26b-a4b-it"}
ORDER=["gemini-3.6-flash","glm-5.2","qwen3.6-35b-a3b","gemma-4-26b-a4b-it"]
B={};C={}
for m in ORDER:
    rr=[r for r in D if SHORT[r["model"]]==m]
    B[m]=sum(1 for r in rr if r["A_correct"]==1 and r["B_correct"]==0)
    C[m]=sum(1 for r in rr if r["A_correct"]==0 and r["B_correct"]==1)

def gammainc_q(s,x):
    """Upper regularised incomplete gamma Q(s,x); series for x<s+1 else continued fraction."""
    if x<0 or s<=0: return float('nan')
    if x==0: return 1.0
    gln=math.lgamma(s)
    if x < s+1.0:
        ap=s; su=1.0/s; dl=su
        for _ in range(1000):
            ap+=1; dl*=x/ap; su+=dl
            if abs(dl)<abs(su)*1e-16: break
        return 1.0-su*math.exp(-x+s*math.log(x)-gln)
    b=x+1.0-s; c=1e300; d=1.0/b; h=d
    for i in range(1,1000):
        an=-i*(i-s); b+=2.0
        d=an*d+b;  d=1e-300 if abs(d)<1e-300 else d
        c=b+an/c;  c=1e-300 if abs(c)<1e-300 else c
        d=1.0/d; de=d*c; h*=de
        if abs(de-1.0)<1e-16: break
    return math.exp(-x+s*math.log(x)-gln)*h
def chi2_sf(x,df): return 1.0 if x<=0 else gammainc_q(df/2.0,x/2.0)
# sanity: 1-df must match the erfc identity
assert abs(chi2_sf(3.8414588,1)-0.05)<1e-7, chi2_sf(3.8414588,1)
assert abs(chi2_sf(7.8147279,3)-0.05)<1e-6, chi2_sf(7.8147279,3)
print("gamma-tail sanity: chi2_sf(3.8415,df=1)=%.8f  chi2_sf(7.8147,df=3)=%.8f  (both target 0.05)"
      % (chi2_sf(3.8414588,1),chi2_sf(7.8147279,3)))

tb=sum(B.values()); tc=sum(C.values()); N=tb+tc
pi=tb/N
print(f"\npooled b={tb} c={tc} n={N} pi_hat={pi:.5f}")
print(f"\n{'model':22s} {'b':>4s} {'c':>4s} {'n':>4s} {'pi=b/n':>8s} {'OR=b/c':>8s} {'E[b]':>7s} {'E[c]':>7s}")
X2=0.0
for m in ORDER:
    n=B[m]+C[m]; eb=n*pi; ec=n*(1-pi)
    X2 += (B[m]-eb)**2/eb + (C[m]-ec)**2/ec
    print(f"{m:22s} {B[m]:4d} {C[m]:4d} {n:4d} {B[m]/n:8.5f} {B[m]/C[m]:8.4f} {eb:7.2f} {ec:7.2f}")
p_h=chi2_sf(X2,3)
print(f"\nMETHOD 1 chi2 homogeneity: X2 = {X2:.5f}, df = 3, p = {p_h:.5f}")
mine=min(1 for _ in [0])  # noop
print(f"   smallest expected cell = {min(min((B[m]+C[m])*pi,(B[m]+C[m])*(1-pi)) for m in ORDER):.2f}"
      f"  (chi2 wants >=5; this is why we also permute)")

rng=random.Random(20260731); R=200000
labels=[1]*tb+[0]*tc
sizes=[B[m]+C[m] for m in ORDER]
def stat(lab):
    x=0.0; i=0
    for n in sizes:
        bb=sum(lab[i:i+n]); cc=n-bb; i+=n
        eb=n*pi; ec=n*(1-pi)
        x+=(bb-eb)**2/eb+(cc-ec)**2/ec
    return x
ge=0
for _ in range(R):
    rng.shuffle(labels)
    if stat(labels)>=X2-1e-12: ge+=1
p_perm=(ge+1)/(R+1)
print(f"METHOD 2 exact-conditional permutation (both margins fixed, R={R}, seed=20260731): p = {p_perm:.5f}")

print("\nExact 95% CI overlap for the four ORs (from prim_mcnemar_exact.py):")
CI={"gemini-3.6-flash":(7.7500,2.7400,30.2196),"glm-5.2":(8.3750,4.0150,20.1910),
    "qwen3.6-35b-a3b":(4.4667,2.5248,8.4202),"gemma-4-26b-a4b-it":(4.5556,2.7109,8.0653)}
lo_max=max(v[1] for v in CI.values()); hi_min=min(v[2] for v in CI.values())
for m in ORDER: print(f"   {m:22s} OR={CI[m][0]:7.4f}  95% CI [{CI[m][1]:7.4f}, {CI[m][2]:7.4f}]")
print(f"   common overlap region = [{lo_max:.4f}, {hi_min:.4f}]  -> all four CIs share values "
      f"{'YES' if lo_max<=hi_min else 'NO'}")

print("\nMinimum discordant pairs needed for the exact test to be able to reject:")
for a in (0.05,0.01,0.001):
    n=1
    while 2.0/(1<<n) >= a: n+=1
    print(f"   alpha={a:<6}: need b+c >= {n:2d}  (min attainable exact p = 2/2^n = {2.0/(1<<n):.6f})")

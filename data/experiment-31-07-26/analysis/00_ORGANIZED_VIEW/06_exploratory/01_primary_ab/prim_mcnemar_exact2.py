"""
prim_mcnemar_exact2.py -- refinements to prim_mcnemar_exact.py.

(A) Continuity-correction variants. The textbook formula (|b-c|-1)^2/(b+c) is
    pathological when |b-c| < 1 (i.e. b == c): it returns X2 = 1/n > 0 instead of 0.
    Compare naive vs clamped max(0,|b-c|-1).
(B) EXACT cluster-robust sign-flip permutation p-value by dynamic programming over
    integer counts -- not Monte Carlo. Each group g contributes d_g = b_g - c_g with
    sign +-1 at prob 1/2; the exact null distribution of S = sum(+-d_g) is a convolution,
    computed with exact integer counts over 2^G equally likely sign vectors.
(C) Design effect: Var_indep(b-c) = b+c  vs  Var_signflip(b-c) = sum_g d_g^2.
"""
import json, math, collections
from fractions import Fraction

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
SHORT = {"google/gemini-3.6-flash":"gemini-3.6-flash","z-ai/glm-5.2":"glm-5.2",
         "qwen/qwen3.6-35b-a3b":"qwen3.6-35b-a3b","google/gemma-4-26b-a4b-it":"gemma-4-26b-a4b-it"}
ORDER = ["gemini-3.6-flash","glm-5.2","qwen3.6-35b-a3b","gemma-4-26b-a4b-it"]

def chi2_1df_sf(x): return 1.0 if x <= 0 else math.erfc(math.sqrt(x/2.0))
def exact_p(b,c):
    n=b+c
    if n==0: return 1.0
    lo=min(b,c); t=sum(math.comb(n,k) for k in range(lo+1))
    p=Fraction(2*t,1<<n); return float(min(p,Fraction(1)))
def cc_naive(b,c):
    n=b+c
    if n==0: return float('nan'),1.0
    x=(abs(b-c)-1.0)**2/n; return x,chi2_1df_sf(x)
def cc_clamped(b,c):
    n=b+c
    if n==0: return float('nan'),1.0
    x=max(0.0,abs(b-c)-1.0)**2/n; return x,chi2_1df_sf(x)

raw=json.load(open(PATH)); D=[r for r in raw if r.get("analysis_include") is True]
for r in D: r["m"]=SHORT[r["model"]]

print("="*100); print("A. CONTINUITY-CORRECTION VARIANTS -- the naive formula misbehaves at b==c"); print("="*100)
print("Every 2x2 sub-table in the study with b == c (a table carrying literally zero directional")
print("evidence). Exact test correctly returns p = 1. The naive (|b-c|-1)^2/n does not.")
print(f"{'b':>3s} {'c':>3s} {'b+c':>4s} {'p_exact':>9s} {'X2_naive':>9s} {'p_naive':>9s} {'X2_clamped':>11s} {'p_clamped':>10s}")
for n2 in [(1,1),(2,2),(3,3),(5,5),(10,10)]:
    b,c=n2
    xn,pn=cc_naive(b,c); xc,pc=cc_clamped(b,c)
    print(f"{b:3d} {c:3d} {b+c:4d} {exact_p(b,c):9.5f} {xn:9.5f} {pn:9.5f} {xc:11.5f} {pc:10.5f}")

print()
print("Main tables under both CC variants (b != c everywhere, so the two agree exactly):")
print(f"{'model':22s} {'b':>4s} {'c':>4s} {'p_exact':>12s} {'p_cc_naive':>12s} {'p_cc_clamped':>13s}")
for m in ORDER+["POOLED"]:
    rr = D if m=="POOLED" else [r for r in D if r["m"]==m]
    b=sum(1 for r in rr if r["A_correct"]==1 and r["B_correct"]==0)
    c=sum(1 for r in rr if r["A_correct"]==0 and r["B_correct"]==1)
    print(f"{m:22s} {b:4d} {c:4d} {exact_p(b,c):12.4e} {cc_naive(b,c)[1]:12.4e} {cc_clamped(b,c)[1]:13.4e}")

print()
print("="*100); print("B. EXACT CLUSTER-ROBUST SIGN-FLIP TEST (dynamic programming, not Monte Carlo)"); print("="*100)
print("Null: within a group (item, or clinical cluster), the A/B labels are exchangeable.")
print("Statistic S = b - c. Group g contributes d_g = b_g - c_g, flipped +/- with prob 1/2.")
print("Exact two-sided p = P(|S| >= |S_obs|), computed by integer convolution over 2^G sign vectors.")

by_item=collections.defaultdict(list); by_clus=collections.defaultdict(list)
for r in D:
    by_item[r["question_id"]].append(r); by_clus[r["cluster"]].append(r)

def signflip_exact(groups, subset):
    ids=set(id(r) for r in subset); ds=[]
    for g,rs in groups.items():
        sel=[r for r in rs if id(r) in ids]
        if not sel: continue
        gb=sum(1 for r in sel if r["A_correct"]==1 and r["B_correct"]==0)
        gc=sum(1 for r in sel if r["A_correct"]==0 and r["B_correct"]==1)
        ds.append(gb-gc)
    obs=sum(ds); nz=[d for d in ds if d!=0]; G=len(nz); span=sum(abs(d) for d in nz)
    # dp[k] = number of sign vectors giving S = k - span   (integer counts, exact)
    dp=[0]*(2*span+1); dp[span]=1
    for d in nz:
        nxt=[0]*(2*span+1)
        for k,v in enumerate(dp):
            if v:
                nxt[k+d]+=v; nxt[k-d]+=v
        dp=nxt
    tot=1<<G
    ge=sum(v for k,v in enumerate(dp) if abs(k-span)>=abs(obs))
    p=Fraction(ge,tot)
    var=sum(d*d for d in nz)          # exact sign-flip null variance of S
    return float(p), obs, G, len(ds), var, span

print(f"{'model':22s} {'grouping':9s} {'b-c':>5s} {'G_nonzero':>10s} {'p_exact_indep':>14s} {'p_signflip_exact':>17s} "
      f"{'Var_indep':>10s} {'Var_flip':>9s} {'DEFF':>6s}")
for m in ORDER+["POOLED"]:
    rr = D if m=="POOLED" else [r for r in D if r["m"]==m]
    b=sum(1 for r in rr if r["A_correct"]==1 and r["B_correct"]==0)
    c=sum(1 for r in rr if r["A_correct"]==0 and r["B_correct"]==1)
    pind=exact_p(b,c)
    for lab,grp in (("item",by_item),("cluster",by_clus)):
        p,obs,G,ng,var,span=signflip_exact(grp,rr)
        deff=var/(b+c)
        print(f"{m:22s} {lab:9s} {obs:5d} {G:10d} {pind:14.4e} {p:17.4e} {b+c:10d} {var:9d} {deff:6.3f}")

print()
print("DEFF = Var_signflip / Var_independent. DEFF > 1 means discordances co-occur within the")
print("same item across models, so the naive pooled exact p is too small; DEFF < 1 the reverse.")

print()
print("="*100); print("C. HOW FAR APART ARE EXACT AND CHI2-CC?  (log10 units)"); print("="*100)
print(f"{'model':22s} {'b':>4s} {'c':>4s} {'b+c':>4s} {'p_exact':>12s} {'p_chi2cc':>12s} {'ratio':>10s} {'log10 ratio':>12s}")
for m in ORDER+["POOLED"]:
    rr = D if m=="POOLED" else [r for r in D if r["m"]==m]
    b=sum(1 for r in rr if r["A_correct"]==1 and r["B_correct"]==0)
    c=sum(1 for r in rr if r["A_correct"]==0 and r["B_correct"]==1)
    pe=exact_p(b,c); pc=cc_naive(b,c)[1]
    print(f"{m:22s} {b:4d} {c:4d} {b+c:4d} {pe:12.4e} {pc:12.4e} {pc/pe:10.2f} {math.log10(pc/pe):12.3f}")

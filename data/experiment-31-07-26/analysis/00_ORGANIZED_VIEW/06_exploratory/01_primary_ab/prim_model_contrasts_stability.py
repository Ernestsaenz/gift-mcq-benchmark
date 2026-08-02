#!/usr/bin/env python
"""Seed-stability of the Holm-adjusted bootstrap p-values, a normal-approx
cross-check, flip counts, and proportional-loss diagnostics. Stdlib only."""
import json, math, random
from collections import defaultdict

PATH = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
        "experiment-31-07-26/analysis/paired_clean.json")
rows = [r for r in json.load(open(PATH)) if r.get("analysis_include") is True]
MODELS = sorted({r["model"] for r in rows}); M = len(MODELS)
MIDX = {m: i for i, m in enumerate(MODELS)}
SHORT = {m: m.split("/")[-1] for m in MODELS}
PAIRS = [(i, j) for i in range(M) for j in range(i + 1, M)]

n = [0]*M; sa = [0]*M; sb = [0]*M
cl_n = defaultdict(lambda: [0]*M); cl_a = defaultdict(lambda: [0]*M); cl_b = defaultdict(lambda: [0]*M)
flips = defaultdict(lambda: [0, 0, 0, 0])   # A1B1, A1B0(loss), A0B1(gain), A0B0
for r in rows:
    i = MIDX[r["model"]]; c = r["cluster"]
    n[i] += 1; sa[i] += r["A_correct"]; sb[i] += r["B_correct"]
    cl_n[c][i] += 1; cl_a[c][i] += r["A_correct"]; cl_b[c][i] += r["B_correct"]
    k = 0 if (r["A_correct"] and r["B_correct"]) else 1 if r["A_correct"] else 2 if r["B_correct"] else 3
    flips[r["model"]][k] += 1
A = [sa[i]/n[i] for i in range(M)]; Bc = [sb[i]/n[i] for i in range(M)]
D = [A[i]-Bc[i] for i in range(M)]
CL = sorted(cl_n); K = len(CL)
CN = [cl_n[c] for c in CL]; CA = [cl_a[c] for c in CL]; CB = [cl_b[c] for c in CL]
obs = {p: D[p[0]]-D[p[1]] for p in PAIRS}

def pct(v,q):
    s=sorted(v); m=len(s); h=(m-1)*q; lo=int(math.floor(h)); hi=min(lo+1,m-1)
    return s[lo]+(h-lo)*(s[hi]-s[lo])
def sd(v):
    m=len(v); mu=sum(v)/m; return math.sqrt(sum((x-mu)**2 for x in v)/(m-1))
def bp(v):
    m=len(v); le=sum(1 for x in v if x<=0); ge=sum(1 for x in v if x>=0)
    return min(1.0, 2*min((le+1)/(m+1),(ge+1)/(m+1)))
def holm(ps):
    order=sorted(range(len(ps)), key=lambda k: ps[k]); out=[0]*len(ps); run=0.0
    for rk,k in enumerate(order):
        run=max(run, min(1.0,(len(ps)-rk)*ps[k])); out[k]=run
    return out
def norm_cdf(z): return 0.5*(1+math.erf(z/math.sqrt(2)))

print("SEED STABILITY OF HOLM-ADJUSTED BOOTSTRAP p (B=20000 per seed)")
print(f"{'contrast':<43}" + "".join(f"{'s'+str(s):>9}" for s in range(5)) + f"{'all<.05?':>10}")
store = {p: [] for p in PAIRS}
se_store = {p: [] for p in PAIRS}
for s in range(5):
    rng = random.Random(1000+s)
    bc = {p: [] for p in PAIRS}
    for b in range(20000):
        idx=[rng.randrange(K) for _ in range(K)]
        nn=[0]*M; aa=[0]*M; bb=[0]*M
        for t in idx:
            cn,ca,cb=CN[t],CA[t],CB[t]
            for i in range(M): nn[i]+=cn[i]; aa[i]+=ca[i]; bb[i]+=cb[i]
        d=[(aa[i]-bb[i])/nn[i] for i in range(M)]
        for p in PAIRS: bc[p].append(d[p[0]]-d[p[1]])
    ps=[bp(bc[p]) for p in PAIRS]; hp=holm(ps)
    for k,p in enumerate(PAIRS):
        store[p].append(hp[k]); se_store[p].append(sd(bc[p]))
for p in PAIRS:
    nm=f"{SHORT[MODELS[p[0]]]} - {SHORT[MODELS[p[1]]]}"
    ok="YES" if all(v<0.05 for v in store[p]) else ("NO" if all(v>=0.05 for v in store[p]) else "UNSTABLE")
    print(f"{nm:<43}" + "".join(f"{v:>9.4f}" for v in store[p]) + f"{ok:>10}")

print()
print("NORMAL-APPROXIMATION CROSS-CHECK  z = observed_contrast / bootstrap_SE")
ps2=[]
for p in PAIRS:
    se=sum(se_store[p])/len(se_store[p])
    z=obs[p]/se; pv=2*(1-norm_cdf(abs(z))); ps2.append(pv)
hp2=holm(ps2)
print(f"{'contrast':<43}{'diff_pp':>9}{'SE_pp':>8}{'z':>8}{'p_normal':>10}{'p_Holm':>9}")
for k,p in enumerate(PAIRS):
    se=sum(se_store[p])/len(se_store[p]); nm=f"{SHORT[MODELS[p[0]]]} - {SHORT[MODELS[p[1]]]}"
    print(f"{nm:<43}{obs[p]*100:>9.2f}{se*100:>8.2f}{obs[p]/se:>8.2f}{ps2[k]:>10.5f}{hp2[k]:>9.5f}")

print()
print("FLIP COUNTS (McNemar cells) and proportional loss")
print(f"{'model':<20}{'A1B1':>6}{'A1B0':>6}{'A0B1':>6}{'A0B0':>6}{'net_loss':>10}{'(A-B)/A':>9}")
for m in MODELS:
    f=flips[m]; i=MIDX[m]
    print(f"{SHORT[m]:<20}{f[0]:>6}{f[1]:>6}{f[2]:>6}{f[3]:>6}{f[1]-f[2]:>10}{D[i]/A[i]:>9.3f}")
print()
print("If degradation were a pure multiplicative hit on ability (B = c*A), delta")
print("would GROW with A. Observed (A-B)/A is the fraction of baseline-correct lost:")
for m in MODELS:
    i=MIDX[m]
    print(f"  {SHORT[m]:<20} A={A[i]*100:.1f}%  loses {D[i]/A[i]*100:.1f}% of its baseline-correct answers")

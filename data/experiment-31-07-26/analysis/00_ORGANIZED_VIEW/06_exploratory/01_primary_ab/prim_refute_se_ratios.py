"""
INDEPENDENT recomputation of the 'naive binomial SE is conservative' claim.
Pure stdlib. Own bootstrap, own CRVE, own ANOVA-ICC.
"""
import json, math, random, collections

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
rows = [r for r in json.load(open(PATH)) if r.get("analysis_include") is True]

MODELS = ["google/gemini-3.6-flash", "z-ai/glm-5.2", "qwen/qwen3.6-35b-a3b", "google/gemma-4-26b-a4b-it"]
SHORT = {"google/gemini-3.6-flash":"gemini", "z-ai/glm-5.2":"glm-5.2",
         "qwen/qwen3.6-35b-a3b":"qwen3.6", "google/gemma-4-26b-a4b-it":"gemma-4"}
Z = 1.959963984540054

def mean(a): return sum(a)/len(a)
def sd1(a):
    m=mean(a); return math.sqrt(sum((x-m)**2 for x in a)/(len(a)-1))
def sd0(a):
    m=mean(a); return math.sqrt(sum((x-m)**2 for x in a)/len(a))

print("cells=%d items=%d clusters=%d models=%d" % (
    len(rows), len(set(r["question_id"] for r in rows)),
    len(set(r["cluster"] for r in rows)), len(set(r["model"] for r in rows))))

# ---------------- per-model marginals, 2x2, phi, analytic SEs ----------------
print("\n" + "="*118)
print("A. PER-MODEL: marginals, McNemar 2x2 (a=both,b=A only,c=B only,d=neither), phi, analytic SEs")
print("="*118)
print(f"{'model':10s} {'n':>4s} {'A%':>7s} {'B%':>7s} {'delta':>8s} | {'a':>4s}{'b':>4s}{'c':>4s}{'d':>4s} | "
      f"{'phi':>7s} {'SEpair(n-1)':>11s} {'SEpair(n)':>9s} {'SEbin':>8s} {'pair/bin':>8s} {'cost%':>6s}")
per = {}
for m in MODELS:
    R = [r for r in rows if r["model"]==m]
    n = len(R)
    A = [r["A_correct"] for r in R]; B = [r["B_correct"] for r in R]
    d = [b-a for a,b in zip(A,B)]
    a11 = sum(1 for x,y in zip(A,B) if x==1 and y==1)
    b10 = sum(1 for x,y in zip(A,B) if x==1 and y==0)
    c01 = sum(1 for x,y in zip(A,B) if x==0 and y==1)
    d00 = sum(1 for x,y in zip(A,B) if x==0 and y==0)
    pA, pB = sum(A)/n, sum(B)/n
    den = math.sqrt((a11+b10)*(c01+d00)*(a11+c01)*(b10+d00))
    phi = (a11*d00 - b10*c01)/den if den else float('nan')
    se_pair_n1 = 100*sd1(d)/math.sqrt(n)
    se_pair_n0 = 100*sd0(d)/math.sqrt(n)
    se_bin = 100*math.sqrt(pA*(1-pA)/n + pB*(1-pB)/n)
    per[m] = dict(n=n, pA=pA, pB=pB, delta=100*(pB-pA), d=d, R=R,
                  a=a11,b=b10,c=c01,dd=d00, phi=phi,
                  se_pair_n1=se_pair_n1, se_pair_n0=se_pair_n0, se_bin=se_bin)
    print(f"{SHORT[m]:10s} {n:4d} {100*pA:7.2f} {100*pB:7.2f} {100*(pB-pA):+8.2f} | "
          f"{a11:4d}{b10:4d}{c01:4d}{d00:4d} | {phi:+7.3f} {se_pair_n1:11.4f} {se_pair_n0:9.4f} "
          f"{se_bin:8.4f} {se_pair_n1/se_bin:8.4f} {100*(1-se_pair_n0/se_bin):6.2f}")

# pooled (cell level)
alld = [r["B_correct"]-r["A_correct"] for r in rows]
N = len(alld)
pA = sum(r["A_correct"] for r in rows)/N; pB = sum(r["B_correct"] for r in rows)/N
POOL_DELTA = 100*(pB-pA)
POOL_PAIR = 100*sd1(alld)/math.sqrt(N)
POOL_BIN  = 100*math.sqrt(pA*(1-pA)/N + pB*(1-pB)/N)
print(f"{'POOLED':10s} {N:4d} {100*pA:7.2f} {100*pB:7.2f} {POOL_DELTA:+8.2f} |"
      f"{'':18s}| {'':7s} {POOL_PAIR:11.4f} {'':9s} {POOL_BIN:8.4f} {POOL_PAIR/POOL_BIN:8.4f}")

# ---------------- my own cluster bootstrap (independent seed / engine) ----------------
# unit = cluster; carries every cell it owns.
CL = collections.defaultdict(lambda: collections.defaultdict(lambda: [0,0,0]))  # cluster -> model -> [n,sA,sB]
CLPOOL = collections.defaultdict(lambda: [0,0,0])
for r in rows:
    v = CL[r["cluster"]][r["model"]]
    v[0]+=1; v[1]+=r["A_correct"]; v[2]+=r["B_correct"]
    w = CLPOOL[r["cluster"]]
    w[0]+=1; w[1]+=r["A_correct"]; w[2]+=r["B_correct"]
CLIST = sorted(CL.keys())
K = len(CLIST)
# flat arrays for speed: for each cluster, 15 slots (4 models x3 + pooled x3)
FLAT = []
for c in CLIST:
    v = []
    for m in MODELS: v.extend(CL[c][m])
    v.extend(CLPOOL[c])
    FLAT.append(tuple(v))

# also ITEM units (ignores clustering, keeps pairing) for the DEff decomposition
IT = collections.defaultdict(lambda: collections.defaultdict(lambda: [0,0,0]))
ITPOOL = collections.defaultdict(lambda: [0,0,0])
for r in rows:
    v = IT[r["question_id"]][r["model"]]
    v[0]+=1; v[1]+=r["A_correct"]; v[2]+=r["B_correct"]
    w = ITPOOL[r["question_id"]]; w[0]+=1; w[1]+=r["A_correct"]; w[2]+=r["B_correct"]
ILIST = sorted(IT.keys())
IFLAT = []
for q in ILIST:
    v = []
    for m in MODELS: v.extend(IT[q][m])
    v.extend(ITPOOL[q])
    IFLAT.append(tuple(v))

def boot(units, nboot, seed):
    rnd = random.Random(seed); ch = rnd.choices; nU = len(units)
    out = [[] for _ in range(5)]
    for _ in range(nboot):
        acc = [0]*15
        for u in ch(units, k=nU):
            for j in range(15): acc[j] += u[j]
        for i in range(5):
            n_, a_, b_ = acc[3*i], acc[3*i+1], acc[3*i+2]
            out[i].append(100.0*(b_-a_)/n_ if n_ else float('nan'))
    return out

NB = 40000
print("\nrunning independent cluster bootstrap: K=%d units, B=%d, seed=777 ..." % (K, NB))
BC = boot(FLAT, NB, 777)
print("running independent cluster bootstrap: replicate seed 12345 ...")
BC2 = boot(FLAT, NB, 12345)
print("running independent item bootstrap:    n=%d units, B=%d, seed=999 ..." % (len(IFLAT), NB))
BI = boot(IFLAT, NB, 999)

# ---------------- analytic cluster-robust (sandwich) SE, no resampling ----------------
def crve(model=None):
    """CRVE for the mean of d (or the ratio estimator over cells) clustered by cluster id."""
    if model is None:
        sel = rows
    else:
        sel = [r for r in rows if r["model"]==model]
    Ntot = len(sel)
    dbar = sum(r["B_correct"]-r["A_correct"] for r in sel)/Ntot
    g = collections.defaultdict(float)
    for r in sel:
        g[r["cluster"]] += (r["B_correct"]-r["A_correct"]) - dbar
    k = len(g)
    S = sum(u*u for u in g.values())
    var = S/(Ntot**2) * (k/(k-1))          # small-sample corrected CRVE
    var_nc = S/(Ntot**2)                    # uncorrected
    return 100*math.sqrt(var), 100*math.sqrt(var_nc), k, Ntot

# ---------------- ICC of per-item delta, one-way random effects ANOVA ----------------
def icc_of(model=None):
    sel = rows if model is None else [r for r in rows if r["model"]==model]
    g = collections.defaultdict(list)
    for r in sel: g[r["cluster"]].append(r["B_correct"]-r["A_correct"])
    Nn = len(sel); k = len(g); gm = sum(x for v in g.values() for x in v)/Nn
    SSB = sum(len(v)*(mean(v)-gm)**2 for v in g.values())
    SSW = sum(sum((x-mean(v))**2 for x in v) for v in g.values())
    MSB, MSW = SSB/(k-1), SSW/(Nn-k)
    m0 = (Nn - sum(len(v)**2 for v in g.values())/Nn)/(k-1)
    icc = (MSB-MSW)/(MSB+(m0-1)*MSW)
    return icc, m0, k, Nn, 1+(m0-1)*icc

print("\n" + "="*118)
print("B. SE COMPARISON  (SEs in pp).  cluster boot = MY run, B=%d, two seeds" % NB)
print("="*118)
print(f"{'':10s} {'SEclus1':>8s} {'SEclus2':>8s} {'CRVE':>8s} {'SEitem':>8s} {'SEpair':>8s} {'SEbin':>8s} | "
      f"{'clus/bin':>8s} {'CRVE/bin':>8s} {'clus/pair':>9s} {'clus/item':>9s} {'DEff_obs':>8s}")
keys = list(range(4)) + ["pool"]
res = {}
for i in keys:
    if i == "pool":
        lab = "POOLED"; sp_, sb = POOL_PAIR, POOL_BIN
        sc1, sc2, si = sd1(BC[4]), sd1(BC2[4]), sd1(BI[4])
        cr, crnc, k_, n_ = crve(None)
    else:
        m = MODELS[i]; lab = SHORT[m]
        sp_, sb = per[m]["se_pair_n1"], per[m]["se_bin"]
        sc1, sc2, si = sd1(BC[i]), sd1(BC2[i]), sd1(BI[i])
        cr, crnc, k_, n_ = crve(m)
    res[i] = dict(sc=sc1, sc2=sc2, cr=cr, si=si, sp=sp_, sb=sb)
    print(f"{lab:10s} {sc1:8.4f} {sc2:8.4f} {cr:8.4f} {si:8.4f} {sp_:8.4f} {sb:8.4f} | "
          f"{sc1/sb:8.4f} {cr/sb:8.4f} {sc1/sp_:9.4f} {sc1/si:9.4f} {(sc1/si)**2:8.4f}")

print("\n" + "="*118)
print("C. ICC / DESIGN EFFECT from one-way ANOVA on d, groups = clusters")
print("="*118)
print(f"{'':10s} {'k':>4s} {'N':>5s} {'m0':>7s} {'ICC':>8s} {'DEff_theory':>11s} {'DEff_bootstrap(clus/item)^2':>28s}")
for i in keys:
    m = None if i=="pool" else MODELS[i]
    lab = "POOLED" if i=="pool" else SHORT[m]
    icc, m0, k_, n_, deff = icc_of(m)
    print(f"{lab:10s} {k_:4d} {n_:5d} {m0:7.4f} {icc:+8.4f} {deff:11.4f} {(res[i]['sc']/res[i]['si'])**2:28.4f}")

print("\n" + "="*118)
print("D. 95% CI WIDTHS (pp) and the claim's '% too wide/narrow' figures")
print("="*118)
def pct(sv,p):
    n=len(sv); x=p/100*(n-1); lo=int(math.floor(x)); hi=lo+1
    return sv[-1] if hi>=n else sv[lo]+(x-lo)*(sv[hi]-sv[lo])
print(f"{'':10s} {'W_clusboot':>10s} {'W_Waldbin':>10s} {'W_Waldpair':>10s} | "
      f"{'bin vs boot':>12s} {'pair vs boot':>12s}   (negative = naive TOO WIDE)")
for i in keys:
    vals = BC[4] if i=="pool" else BC[i]
    sv = sorted(vals); wc = pct(sv,97.5)-pct(sv,2.5)
    sb, sp_ = res[i]['sb'], res[i]['sp']
    wb, wp = 2*Z*sb, 2*Z*sp_
    lab = "POOLED" if i=="pool" else SHORT[MODELS[i]]
    print(f"{lab:10s} {wc:10.3f} {wb:10.3f} {wp:10.3f} | {100*(1-wb/wc):11.2f}% {100*(1-wp/wc):11.2f}%")

print("\n" + "="*118)
print("E. DECOMPOSITION CHECK: does (pairing factor) x (clustering factor) = SEclus/SEbin ?")
print("="*118)
print(f"{'':10s} {'pair/bin':>9s} {'clusfactor_implied':>18s} {'DEff_implied':>12s} {'DEff_claimed_theory':>20s}")
for i in range(4):
    m = MODELS[i]
    pb = res[i]['sp']/res[i]['sb']
    implied = (res[i]['sc']/res[i]['sb'])/pb
    icc, m0, k_, n_, deff = icc_of(m)
    print(f"{SHORT[m]:10s} {pb:9.4f} {implied:18.4f} {implied**2:12.4f} {deff:20.4f}")

# ---------------- how many models have naive-bin wider? sign check + MC error ----------------
print("\n" + "="*118)
print("F. SIGN OF (SEclus - SEbin) PER MODEL, with bootstrap MC error on the SE (~SE/sqrt(2B))")
print("="*118)
for i in range(4):
    m = MODELS[i]
    mc = res[i]['sc']/math.sqrt(2*NB)
    print(f"{SHORT[m]:10s} SEclus={res[i]['sc']:.4f} (+-{mc:.4f} MC, seed2={res[i]['sc2']:.4f})  "
          f"SEbin={res[i]['sb']:.4f}  -> naive binomial is "
          f"{'WIDER (conservative)' if res[i]['sc']<res[i]['sb'] else 'NARROWER (anticonservative)'}")

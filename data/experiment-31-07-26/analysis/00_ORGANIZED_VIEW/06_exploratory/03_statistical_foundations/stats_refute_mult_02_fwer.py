"""Simulate the ENTIRE claimed 160-test family under a true global null, RESPECTING
the dependence the claim ignores.

Null construction: the exact conditional (sign-flip) null.  Every discordant pair's
direction is flipped by a fair coin; concordant pairs are inert.  This is exactly the
null that the exact McNemar test conditions on, so the simulation measures each
test's TRUE size as implemented.  Three flip granularities:
   cell    -- independent coin per (item,model) cell   (max independence)
   item    -- one coin per item, shared by all 4 models (crossed item x model design)
   cluster -- one coin per clinical cluster            (full nesting, as the design has)

All 160 tests are instantiated:
   4   primary            exact McNemar per model
   100 subgroup permodel  exact McNemar per (model, factor level)
   25  subgroup pooled    exact McNemar per factor level, models pooled
   20  moderator permodel chi-square homogeneity of loss/gain split across levels
   5   moderator pooled   same, models pooled
   6   between-model      paired z on per-item difference of (A-B) between two models
Chi-square and z p-values use asymptotic approximations (own incomplete-gamma /
erfc implementations) -- STATED, and their real size is what the simulation measures.
"""
import json, math, os, random, collections, itertools, sys
HERE="/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
recs=[r for r in json.load(open(os.path.join(HERE,"paired_clean.json"))) if r["analysis_include"]]
MODELS=sorted({r["model"] for r in recs}); MI={m:i for i,m in enumerate(MODELS)}
FACT=["correct_letter","negated_stem","has_context","region","year"]
lev={f:sorted({str(r[f]) for r in recs}) for f in FACT}
NREP=int(sys.argv[1]) if len(sys.argv)>1 else 20000
SEED=20260731

# ---- exact McNemar rejection region, precomputed per n_d -------------------
def logcomb(n,k): return math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)
def pmf(n,k): return math.exp(logcomb(n,k)-n*math.log(2.0))
def mcp(b,c):
    n=b+c
    if n==0: return 1.0
    lo=sum(pmf(n,k) for k in range(0,b+1)); hi=sum(pmf(n,k) for k in range(b,n+1))
    return min(1.0,2.0*min(lo,hi))
CRIT={}
def crit(n):
    if n not in CRIT: CRIT[n]=frozenset(b for b in range(n+1) if mcp(b,n-b)<0.05)
    return CRIT[n]

# ---- chi-square upper tail via regularized incomplete gamma ---------------
def gser(a,x):
    ap=a; s=1.0/a; d=s
    for _ in range(500):
        ap+=1; d*=x/ap; s+=d
        if abs(d)<abs(s)*1e-14: break
    return s*math.exp(-x+a*math.log(x)-math.lgamma(a))
def gcf(a,x):
    tiny=1e-300; b=x+1-a; c=1/tiny; d=1/b; h=d
    for i in range(1,500):
        an=-i*(i-a); b+=2
        d=an*d+b;  d=tiny if abs(d)<tiny else d
        c=b+an/c;  c=tiny if abs(c)<tiny else c
        d=1/d; de=d*c; h*=de
        if abs(de-1)<1e-14: break
    return math.exp(-x+a*math.log(x)-math.lgamma(a))*h
def chisq_sf(x,df):
    if x<=0: return 1.0
    a=df/2.0; z=x/2.0
    return 1.0-gser(a,z) if z<a+1 else gcf(a,z)
def norm_sf2(z):  # two-sided
    return math.erfc(abs(z)/math.sqrt(2.0))

# ---- discordant cells only (concordant pairs are inert under sign-flip) ---
disc=[]   # (model_idx, item, cluster, dir(+1 loss / -1 gain), factor level strings)
for r in recs:
    if r["A_correct"]!=r["B_correct"]:
        disc.append((MI[r["model"]], r["question_id"], r["cluster"],
                     1 if r["A_correct"]==1 else -1, tuple(str(r[f]) for f in FACT)))
ND=len(disc)
items=sorted({r["question_id"] for r in recs}); II={q:i for i,q in enumerate(items)}
clus=sorted({r["cluster"] for r in recs});      CI={c:i for i,c in enumerate(clus)}
unit={"cell":[j for j in range(ND)],
      "item":[II[d[1]] for d in disc],
      "cluster":[CI[d[2]] for d in disc]}
nunit={"cell":ND,"item":len(items),"cluster":len(clus)}

# ---- test membership over discordant-cell indices ------------------------
prim_mem=[[] for _ in MODELS]
sub_pm={}; sub_po={}
for j,(mi,q,cl,dr,levs) in enumerate(disc):
    prim_mem[mi].append(j)
    for fi,f in enumerate(FACT):
        sub_pm.setdefault((f,levs[fi],mi),[]).append(j)
        sub_po.setdefault((f,levs[fi]),[]).append(j)
SUB_PM=[(f,L,mi) for f in FACT for L in lev[f] for mi in range(4)]
SUB_PO=[(f,L)    for f in FACT for L in lev[f]]
assert len(SUB_PM)==100 and len(SUB_PO)==25
MOD_PM=[(f,mi) for f in FACT for mi in range(4)]; MOD_PO=list(FACT)
PAIRS=list(itertools.combinations(range(4),2)); assert len(PAIRS)==6

# per-item signed value lookup for between-model contrasts
item_cells=collections.defaultdict(dict)   # item -> model -> disc index
for j,(mi,q,cl,dr,levs) in enumerate(disc): item_cells[q][mi]=j
pair_items={p:[q for q,d in item_cells.items() if p[0] in d or p[1] in d] for p in PAIRS}

LAYER=(["primary"]*4+["subgroup_permodel"]*100+["subgroup_pooled"]*25+
       ["moderator_permodel"]*20+["moderator_pooled"]*5+["between_model"]*6)
assert len(LAYER)==160

def run_family(bit):
    """bit[j]=1 if discordant cell j counts as a LOSS (b) this draw. Returns 160 bools."""
    rej=[]
    # 1 primary
    for mi in range(4):
        mem=prim_mem[mi]; b=sum(bit[j] for j in mem)
        rej.append(b in crit(len(mem)))
    # 2 subgroup per model  (cache b,c for the moderator tests)
    bc_pm={}
    for key in SUB_PM:
        mem=sub_pm.get(key,[]); n=len(mem); b=sum(bit[j] for j in mem)
        bc_pm[key]=(b,n-b); rej.append(b in crit(n))
    # 3 subgroup pooled
    bc_po={}
    for key in SUB_PO:
        mem=sub_po.get(key,[]); n=len(mem); b=sum(bit[j] for j in mem)
        bc_po[key]=(b,n-b); rej.append(b in crit(n))
    # 4/5 moderator: chi-square homogeneity of loss/gain across levels
    def homog(cells):
        cells=[(b,c) for b,c in cells if b+c>0]
        if len(cells)<2: return False
        B=sum(b for b,_ in cells); C=sum(c for _,c in cells); N=B+C
        if B==0 or C==0: return False
        x=0.0
        for b,c in cells:
            n=b+c; eb=n*B/N; ec=n*C/N
            x+=(b-eb)**2/eb+(c-ec)**2/ec
        return chisq_sf(x,len(cells)-1)<0.05
    for f,mi in MOD_PM: rej.append(homog([bc_pm[(f,L,mi)] for L in lev[f]]))
    for f in MOD_PO:    rej.append(homog([bc_po[(f,L)]    for L in lev[f]]))
    # 6 between-model paired z on per-item difference
    for p in PAIRS:
        s=0.0; ss=0.0
        for q in pair_items[p]:
            d=item_cells[q]
            e0=(1 if bit[d[p[0]]] else -1) if p[0] in d else 0
            e1=(1 if bit[d[p[1]]] else -1) if p[1] in d else 0
            v=e0-e1; s+=v; ss+=v*v
        rej.append(norm_sf2(s/math.sqrt(ss))<0.05 if ss>0 else False)
    return rej

# ---- observed (real data) ------------------------------------------------
obs_bit=[1 if d[3]==1 else 0 for d in disc]
obs=run_family(obs_bit)
print(f"OBSERVED DATA: {sum(obs)} / 160 tests reject at nominal alpha=.05")
cnt=collections.Counter(l for l,r in zip(LAYER,obs) if r)
for l in ["primary","subgroup_permodel","subgroup_pooled","moderator_permodel","moderator_pooled","between_model"]:
    tot=LAYER.count(l); print(f"   {l:22s} {cnt[l]:3d} / {tot}")

# ---- null simulation -----------------------------------------------------
print(f"\nGLOBAL-NULL SIMULATION, {NREP} draws per flip granularity")
print(f"{'flip unit':10s} {'E[# reject]':>12s} {'P(>=1)':>9s} {'P(>=8)':>9s} {'mc se P(>=1)':>13s}   per-layer E[#]")
res={}
for gran in ["cell","item","cluster"]:
    u=unit[gran]; nu=nunit[gran]; rng=random.Random(SEED)
    tot=0; atleast1=0; atleast8=0; layer_sum=collections.Counter()
    for _ in range(NREP):
        s=[rng.getrandbits(1) for _ in range(nu)]
        bit=[s[u[j]] ^ (0 if obs_bit[j] else 1) for j in range(ND)]
        rj=run_family(bit); k=sum(rj)
        tot+=k
        if k>=1: atleast1+=1
        if k>=8: atleast8+=1
        for l,r in zip(LAYER,rj):
            if r: layer_sum[l]+=1
    p1=atleast1/NREP; se=math.sqrt(p1*(1-p1)/NREP)
    res[gran]=dict(E=tot/NREP,p1=p1,p8=atleast8/NREP,
                   layer={l:layer_sum[l]/NREP for l in set(LAYER)})
    lay=" ".join(f"{l.split('_')[0][:4]}={layer_sum[l]/NREP:.2f}" for l in
                 ["primary","subgroup_permodel","subgroup_pooled","moderator_permodel","moderator_pooled","between_model"])
    print(f"{gran:10s} {tot/NREP:12.3f} {p1:9.4f} {atleast8/NREP:9.4f} {se:13.4f}   {lay}")

print(f"\nCLAIM asserts: E[# false positives] = 8.0 , P(>=1) = 0.9997")
print(f"That is 1 - 0.95^160 = {1-0.95**160:.6f}, i.e. it assumes all 160 tests are")
print(f"INDEPENDENT and each has size EXACTLY .05.  Both premises fail here.")
json.dump({"nrep":NREP,"observed_rejections":sum(obs),"sim":res},
          open(os.path.join(HERE,"stats_refute_mult_fwer.json"),"w"), indent=1)

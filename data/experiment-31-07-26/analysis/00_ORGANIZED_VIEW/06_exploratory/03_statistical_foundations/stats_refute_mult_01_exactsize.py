"""Exact conditional size of every McNemar-based test in the claimed 160-test family.
The exact two-sided McNemar test conditions on n_d = b+c discordant pairs and refers
b to Bin(n_d, 1/2).  Its ACTUAL size is therefore the null probability mass of the
rejection region -- a discrete quantity that is strictly < 0.05 and is EXACTLY 0
whenever n_d <= 5.  No simulation, no approximation: pure binomial arithmetic."""
import json, math, os, collections
HERE="/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
recs=[r for r in json.load(open(os.path.join(HERE,"paired_clean.json"))) if r["analysis_include"]]
MODELS=sorted({r["model"] for r in recs})
FACT=["correct_letter","negated_stem","has_context","region","year"]
lev={f:sorted({str(r[f]) for r in recs}) for f in FACT}

def logcomb(n,k): return math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)
def pmf(n,k): return math.exp(logcomb(n,k)-n*math.log(2.0))
def mcp(b,c):
    n=b+c
    if n==0: return 1.0
    lo=sum(pmf(n,k) for k in range(0,b+1)); hi=sum(pmf(n,k) for k in range(b,n+1))
    return min(1.0,2.0*min(lo,hi))
_cs={}
def exact_size(n, alpha=0.05):
    """null P(reject) for exact two-sided McNemar with n discordant pairs"""
    if n in _cs: return _cs[n]
    s=sum(pmf(n,b) for b in range(n+1) if mcp(b,n-b)<alpha)
    _cs[n]=s; return s

tests=[]  # (layer, label, n_discordant)
by_model={m:[r for r in recs if r["model"]==m] for m in MODELS}
def nd(rows): return sum(1 for r in rows if r["A_correct"]!=r["B_correct"])

for m in MODELS: tests.append(("primary", f"{m}", nd(by_model[m])))
for f in FACT:
    for L in lev[f]:
        for m in MODELS:
            tests.append(("subgroup_permodel", f"{f}={L}|{m}", nd([r for r in by_model[m] if str(r[f])==L])))
for f in FACT:
    for L in lev[f]:
        tests.append(("subgroup_pooled", f"{f}={L}|pooled", nd([r for r in recs if str(r[f])==L])))

print("n_d=discordant pairs; exact size = true null rejection prob at nominal alpha=.05")
print(f"{'n_d':>5s} {'exact size':>12s}")
for n in [0,1,2,3,4,5,6,7,8,10,15,20,30,50,100,292]:
    print(f"{n:5d} {exact_size(n):12.6f}")
print()
lay=collections.defaultdict(list)
for l,lab,n in tests: lay[l].append((lab,n))
print(f"{'layer':22s} {'k tests':>8s} {'k with n_d<6':>13s} {'sum exact size':>15s} {'if each were .05':>17s}")
grand=0.0
for l in ["primary","subgroup_permodel","subgroup_pooled"]:
    ss=sum(exact_size(n) for _,n in lay[l]); grand+=ss
    dead=sum(1 for _,n in lay[l] if n<6)
    print(f"{l:22s} {len(lay[l]):8d} {dead:13d} {ss:15.4f} {0.05*len(lay[l]):17.4f}")
print(f"{'TOTAL (McNemar 129)':22s} {sum(len(lay[l]) for l in lay):8d} "
      f"{sum(1 for l in lay for _,n in lay[l] if n<6):13d} {grand:15.4f} {0.05*129:17.4f}")
print()
print("P(>=1 rejection) among the 129 McNemar tests if they were INDEPENDENT,")
print("using each test's own exact size instead of a blanket 0.05:")
prod=1.0
for l in lay:
    for _,n in lay[l]: prod*= (1.0-exact_size(n))
print(f"   1 - prod(1-size_i) = {1-prod:.6f}")
print(f"   claim's figure (blanket .05, 160 tests) = {1-0.95**160:.6f}")
print()
# distribution of subgroup cell sizes
ns=sorted(n for _,n in lay["subgroup_permodel"])
print("per-model subgroup discordant-pair counts n_d, sorted:")
print("  ", ns)
print(f"  median n_d = {ns[len(ns)//2]}, #with n_d==0 = {sum(1 for n in ns if n==0)}, "
      f"#with n_d<6 (size EXACTLY 0) = {sum(1 for n in ns if n<6)}")
json.dump({"exact_sizes":{l:[ [lab,n,exact_size(n)] for lab,n in lay[l]] for l in lay},
           "grand_expected_fp_mcnemar":grand},
          open(os.path.join(HERE,"stats_refute_mult_exactsize.json"),"w"), indent=1)

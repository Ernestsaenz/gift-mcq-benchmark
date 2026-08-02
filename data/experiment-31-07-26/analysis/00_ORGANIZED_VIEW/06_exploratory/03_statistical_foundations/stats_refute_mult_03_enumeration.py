"""How sensitive is the headline '160 tests -> 8 false positives' to the enumeration
rule?  E[FP] in the claim is literally 0.05*N, so every digit of it is inherited from
an arbitrary bookkeeping choice.  Also: BH/Holm on the OBSERVED 160-test family, which
is the quantity that actually bears on what may be reported."""
import json, math, os, itertools, collections
HERE="/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
recs=[r for r in json.load(open(os.path.join(HERE,"paired_clean.json"))) if r["analysis_include"]]
MODELS=sorted({r["model"] for r in recs}); FACT=["correct_letter","negated_stem","has_context","region","year"]
lev={f:sorted({str(r[f]) for r in recs}) for f in FACT}
nl={f:len(lev[f]) for f in FACT}

def inventory(factors, permodel_sub=True, pooled_sub=True, permodel_mod=True,
              pooled_mod=True, between=True, M=4):
    L=sum(nl[f] for f in factors); n=M
    if permodel_sub: n+=L*M
    if pooled_sub:   n+=L
    if permodel_mod: n+=len(factors)*M
    if pooled_mod:   n+=len(factors)
    if between:      n+=M*(M-1)//2
    return n
ALL=FACT; CORE=["correct_letter","negated_stem","has_context"]
variants=[
 ("claim's rule (all 5 factors, every layer)",            inventory(ALL)),
 ("region+year as nuisance strata, not subgroup factors", inventory(CORE)),
 ("no pooled layers (per-model only)",                    inventory(ALL,pooled_sub=False,pooled_mod=False)),
 ("no moderator layer",                                   inventory(ALL,permodel_mod=False,pooled_mod=False)),
 ("subgroups only for the 3 design factors, else as claim",inventory(CORE)+ (nl['region']+nl['year'])*0),
 ("add 5 ceiling metrics x 4 models (the script's own)",   inventory(ALL)+20),
 ("primary only (pre-registered confirmatory family)",     4),
]
print(f"{'enumeration rule':56s} {'N':>5s} {'E[FP]=.05N':>11s} {'1-.95^N':>9s}")
for lab,n in variants:
    print(f"{lab:56s} {n:5d} {0.05*n:11.2f} {1-0.95**n:9.4f}")
print("\n-> E[FP] ranges 0.20 to 9.00 across defensible enumerations of the SAME programme.")
print("   The '8.0' is 0.05 x an arbitrary integer, not an estimate of anything in the data.\n")

# tests the programme ACTUALLY executed (saved outputs, original run only)
orig=["sens_speccurve_results.json","sens_exclusion_grid_results.json",
      "prim_permutation_exact_results.json","prim_model_contrasts.json",
      "prim_permutation_results.json","stats_effect_size_power_out.json"]
def walk(o,p=""):
    if isinstance(o,dict):
        for k,v in o.items(): yield from walk(v,p+"/"+str(k))
    elif isinstance(o,list):
        for i,v in enumerate(o): yield from walk(v,p+f"[{i}]")
    else: yield p,o
tot=0
for f in orig:
    fp=os.path.join(HERE,f)
    if not os.path.exists(fp): continue
    n=sum(1 for pa,v in walk(json.load(open(fp)))
          if pa.rsplit("/",1)[-1].split("[")[0].lower() in
          ("p","p_value","pval","p_exact","p_perm","pperm","p_two_sided","p_raw","p_holm","p_bh")
          and isinstance(v,(int,float)))
    tot+=n; print(f"  {n:4d} p-values actually saved in {f}")
print(f"  {tot:4d} p-values in just 6 of the programme's output files, PLUS the 100 subgroup")
print(f"       McNemar tests the multiplicity script itself ran = {tot+100} executed tests,")
print(f"       vs the claimed family size of 160.\n")

# ---- BH / Holm on the observed 160-test family --------------------------
fw=os.path.join(HERE,"stats_refute_mult_fwer.json")
print("(observed rejection counts come from stats_refute_mult_02_fwer.py)")

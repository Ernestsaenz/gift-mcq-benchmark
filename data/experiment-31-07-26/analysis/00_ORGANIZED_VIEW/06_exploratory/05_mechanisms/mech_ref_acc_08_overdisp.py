"""Step 8: redo the item-clustering test with a MODEL-SPECIFIC (Poisson-binomial) null,
since models have different B-failure rates and a common-p binomial null is misspecified."""
import collections, random
from mech_ref_acc_lib import load_cells

cells = load_cells()
SHORT = {"google/gemini-3.6-flash":"gemini","z-ai/glm-5.2":"glm",
         "qwen/qwen3.6-35b-a3b":"qwen","google/gemma-4-26b-a4b-it":"gemma"}
MODELS=["gemini","glm","qwen","gemma"]
for r in cells: r["m"]=SHORT[r["model"]]
by_item=collections.defaultdict(dict)
for r in cells: by_item[r["question_id"]][r["m"]]=r

allA=[d for d in by_item.values() if len(d)==4 and all(r["A_correct"] for r in d.values())]
n=len(allA)
p={m: sum(1 for d in allA if not d[m]["B_correct"])/n for m in MODELS}
print(f"items where all 4 models were A-correct: {n}")
print("per-model B-failure rate on these items: "+", ".join(f"{m} {100*v:.1f}%" for m,v in p.items()))
obs=collections.Counter(sum(1 for r in d.values() if not r["B_correct"]) for d in allA)
print(f"{'#models failing B':>20} : "+" ".join(f"{i:>7}" for i in range(5)))
print(f"{'observed items':>20} : "+" ".join(f"{obs.get(i,0):>7}" for i in range(5)))
rng=random.Random(5); B=40000
acc=[[0]*5 for _ in range(B)]
ge_hi=0; ge_var=0
obs_hi=obs.get(3,0)+obs.get(4,0)
import statistics
obs_counts=[sum(1 for r in d.values() if not r["B_correct"]) for d in allA]
obs_var=statistics.pvariance(obs_counts)
means=[0.0]*5
for b in range(B):
    cs=[sum(1 for m in MODELS if rng.random()<p[m]) for _ in range(n)]
    c=collections.Counter(cs)
    for i in range(5): means[i]+=c.get(i,0)
    if c.get(3,0)+c.get(4,0) >= obs_hi: ge_hi+=1
    if statistics.pvariance(cs) >= obs_var: ge_var+=1
print(f"{'Poisson-binom null':>20} : "+" ".join(f"{means[i]/B:>7.1f}" for i in range(5)))
print(f"\nobserved items with >=3 of 4 models failing B: {obs_hi}")
print(f"Monte-Carlo P(>=3-failures count >= obs) = {(ge_hi+1)/(B+1):.4g}   (B={B})")
print(f"observed variance of per-item failure count = {obs_var:.3f}")
print(f"Monte-Carlo P(variance >= obs) = {(ge_var+1)/(B+1):.4g}")
print("method: Monte-Carlo Poisson-binomial null preserving each model's own B-failure rate.")

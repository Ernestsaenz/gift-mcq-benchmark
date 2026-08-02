import json, os
from collections import defaultdict
rows = json.load(open("paired_clean.json"))
clean = [r for r in rows if r.get("analysis_include") is True]

# 1. do A_correct/B_correct agree with (selected == correct_letter)?
badA = badB = nullA = nullB = 0
for r in clean:
    ca = r["correct_letter"]
    sa, sb = r.get("A_selected"), r.get("B_selected")
    if sa is None: nullA += 1
    elif (1 if str(sa).strip().lower()==str(ca).strip().lower() else 0) != r["A_correct"]: badA += 1
    if sb is None: nullB += 1
    elif (1 if str(sb).strip().lower()==str(ca).strip().lower() else 0) != r["B_correct"]: badB += 1
print("A_correct mismatches vs (A_selected==correct_letter):", badA, " nulls:", nullA)
print("B_correct mismatches vs (B_selected==correct_letter):", badB, " nulls:", nullB)

# 2. per-model coverage: which items are missing
items = sorted({r["question_id"] for r in clean})
bym = defaultdict(set)
for r in clean: bym[r["model"]].add(r["question_id"])
print("\nn items overall:", len(items))
for m in sorted(bym):
    miss = set(items) - bym[m]
    print(f"  {m:30s} n={len(bym[m])}  missing={sorted(miss)}")

# 3. what does the excluded glm row look like in the RAW file?
missing = set(items) - bym["z-ai/glm-5.2"]
for qid in missing:
    for r in rows:
        if r["question_id"]==qid and r["model"]=="z-ai/glm-5.2":
            print("\nRAW excluded glm row:", {k:r[k] for k in
                  ("question_id","model","analysis_include","excl_item_defect",
                   "excl_nota_position_a","A_correct","B_correct","A_selected","B_selected")})

# 4. sensitivity: if the excluded glm row were INCLUDED, does the table move?
for qid in missing:
    for r in rows:
        if r["question_id"]==qid and r["model"]=="z-ai/glm-5.2":
            print("   its (A,B) =", (r["A_correct"], r["B_correct"]),
                  "-> would land in cell",
                  "a" if (r["A_correct"],r["B_correct"])==(1,1) else
                  "b" if (r["A_correct"],r["B_correct"])==(1,0) else
                  "c" if (r["A_correct"],r["B_correct"])==(0,1) else "d")

# 5. any duplicate (question_id, model) cells that would double-count?
seen = defaultdict(int)
for r in clean: seen[(r["question_id"], r["model"])] += 1
dups = {k:v for k,v in seen.items() if v>1}
print("\nduplicate (item,model) cells:", len(dups))

# 6. binary purity
vals = {(r["A_correct"], r["B_correct"]) for r in clean}
print("distinct (A_correct,B_correct) pairs:", sorted(vals))

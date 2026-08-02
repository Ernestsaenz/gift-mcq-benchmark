import json, math
from fractions import Fraction
rows = json.load(open("paired_clean.json"))
print("all raw rows for b320:")
for r in rows:
    if r["question_id"]=="b320":
        print("  ", r["model"], "include=",r.get("analysis_include"),
              "defect=",r.get("excl_item_defect"), "posA=",r.get("excl_nota_position_a"),
              "(A,B)=",(r["A_correct"],r["B_correct"]))
print()
# worst-case: what if the missing glm b320 cell existed and was 'fixed' (c)?
def p(b,c):
    n=b+c; k=min(b,c)
    return float(Fraction(2*sum(math.comb(n,i) for i in range(k+1)), 2**n))
print("glm as reported      b=67 c=8  OR=%.4f p=%.4e" % (67/8, p(67,8)))
print("glm + missing as 'c' b=67 c=9  OR=%.4f p=%.4e" % (67/9, p(67,9)))
print("glm + missing as 'b' b=68 c=8  OR=%.4f p=%.4e" % (68/8, p(68,8)))

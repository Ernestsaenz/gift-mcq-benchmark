import json
from collections import Counter, defaultdict
P='/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json'
raw=json.load(open(P))
inc=[r for r in raw if r.get('analysis_include')]
exc=[r for r in raw if not r.get('analysis_include')]

def tab(rows):
    n11=sum(1 for r in rows if r['A_correct']==1 and r['B_correct']==1)
    n10=sum(1 for r in rows if r['A_correct']==1 and r['B_correct']==0)
    n01=sum(1 for r in rows if r['A_correct']==0 and r['B_correct']==1)
    n00=sum(1 for r in rows if r['A_correct']==0 and r['B_correct']==0)
    N=len(rows) or 1
    return n11,n10,n01,n00,N

print("=== SELECTED-LETTER SANITY (non-response / parse failure risk) ===")
print("A_selected values:",Counter(r['A_selected'] for r in raw))
print("B_selected values:",Counter(r['B_selected'] for r in raw))
# does correctness always equal (selected==correct_letter)?
bad=0
for r in raw:
    if (r['A_selected']==r['correct_letter'])!=bool(r['A_correct']): bad+=1
    if (r['B_selected']==r['correct_letter'])!=bool(r['B_correct']): bad+=1
print("cells where correct flag != (selected==correct_letter):",bad)

print()
print("=== EXCLUSION SENSITIVITY ===")
for name,rows in [("INCLUDED (analysis set)",inc),("EXCLUDED",exc),("ALL CELLS",raw)]:
    n11,n10,n01,n00,N=tab(rows)
    a=n11+n10;b=n11+n01
    print("%-24s N=%4d  A+B+=%3d lost=%3d gained=%3d A-B-=%3d | Aacc=%.4f Bacc=%.4f net=%+.4f  L:G=%.2f"%(
        name,N,n11,n10,n01,n00,a/N,b/N,(b-a)/N,(n10/n01 if n01 else float('inf'))))
# why excluded
print("excluded reasons:",Counter((r['excl_item_defect'],r['excl_nota_position_a']) for r in exc))
for flag in ['excl_item_defect','excl_nota_position_a']:
    sub=[r for r in raw if r[flag]]
    n11,n10,n01,n00,N=tab(sub)
    print("  %-22s N=%4d lost=%3d gained=%3d net=%+.4f"%(flag,N,n10,n01,((n11+n01)-(n11+n10))/(N or 1)))

print()
print("=== PER MODEL ===")
bym=defaultdict(list)
for r in inc: bym[r['model']].append(r)
for m in sorted(bym):
    n11,n10,n01,n00,N=tab(bym[m])
    a=n11+n10;b=n11+n01
    print("%-30s N=%3d lost=%3d gained=%2d  Aacc=%.3f Bacc=%.3f net=%+.4f  P(lost|A+)=%.3f P(gain|A-)=%.3f"%(
        m,N,n10,n01,a/N,b/N,(b-a)/N,n10/a if a else 0,n01/(N-a) if N-a else 0))

print()
print("=== LETTER STICKINESS (design: correct LETTER unchanged in B) ===")
same=sum(1 for r in inc if r['A_selected']==r['B_selected'])
print("B_selected==A_selected: %d/%d = %.4f"%(same,len(inc),same/len(inc)))
for lab,sub in [("A correct",[r for r in inc if r['A_correct']==1]),("A wrong",[r for r in inc if r['A_correct']==0])]:
    s=sum(1 for r in sub if r['A_selected']==r['B_selected'])
    print("  %-10s stickiness %d/%d = %.4f"%(lab,s,len(sub),s/len(sub)))
# NOTA-slot selection rate in B
nota=sum(1 for r in inc if r['B_selected']==r['correct_letter'])
print("B picks NOTA slot: %d/%d = %.4f   (A picks correct-letter slot: %.4f)"%(
    nota,len(inc),nota/len(inc),sum(r['A_correct'] for r in inc)/len(inc)))

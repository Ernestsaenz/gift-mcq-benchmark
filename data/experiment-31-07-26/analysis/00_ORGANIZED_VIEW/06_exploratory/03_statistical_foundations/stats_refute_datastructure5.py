import json, collections
A='/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
rows=json.load(open(A+'paired_clean.json'))
inc=[r for r in rows if r['analysis_include']]
cells=json.load(open(A+'mech_db_cells.json'))['cells']

# ---- sensitivity: what if the dropped b320/glm cell were scored A=incorrect, B=its observed value?
gb={ (c['exp'],c['qid']):c for c in cells if 'glm' in c['model'] and c['qid']=='b320'}
Braw=gb[('expB_or_310726','b320')]
print("b320 glm arm-B raw selected:",Braw['selected_letter'],"correct_letter: d -> B_correct =",int(Braw['selected_letter']=='d'))
Bval=int(Braw['selected_letter']=='d')

for mo in ['z-ai/glm-5.2']:
    sub=[r for r in inc if r['model']==mo]
    n=len(sub); a=sum(r['A_correct'] for r in sub); b=sum(r['B_correct'] for r in sub)
    print(f"\nAS-ANALYSED  {mo}: n={n} A={a/n:.4f} B={b/n:.4f} d={b/n-a/n:+.4f}")
    n2=n+1; a2=a+0; b2=b+Bval
    print(f"IF-SCORED-0  {mo}: n={n2} A={a2/n2:.4f} B={b2/n2:.4f} d={b2/n2-a2/n2:+.4f}")

N=len(inc); Aa=sum(r['A_correct'] for r in inc); Bb=sum(r['B_correct'] for r in inc)
print(f"\nPOOLED as-analysed n={N} A={Aa/N:.5f} B={Bb/N:.5f} delta={Bb/N-Aa/N:+.5f}")
N2=N+1; A2=Aa+0; B2=Bb+Bval
print(f"POOLED if-scored-0 n={N2} A={A2/N2:.5f} B={B2/N2:.5f} delta={B2/N2-A2/N2:+.5f}")
print(f"delta shift = {(B2/N2-A2/N2)-(Bb/N-Aa/N):+.5f}")

# ---- retry structure
print("\n--- retry structure in raw corpus ---")
ai=collections.Counter(c['attempt_index'] for c in cells)
print("attempt_index hist:",dict(sorted(ai.items())))
gt1=[c for c in cells if c['attempt_index']>1]
print("cells needing >1 attempt:",len(gt1),"of",len(cells))
print(" by model:",collections.Counter(c['model'] for c in gt1))
print(" by exp:",collections.Counter(c['exp'] for c in gt1))
print(" finish_reason among retried:",collections.Counter(c['finish_reason'] for c in gt1))
# do retried cells end up in the analysis set?
ret={(c['qid'],c['model']) for c in gt1}
inset=sum(1 for r in inc if (r['question_id'],r['model']) in ret)
print(" retried (qid,model) pairs present in analysis set:",inset)

try:
    cov=json.load(open(A+'gift_coverage.json'))
    print("\ngift_coverage.json:",json.dumps(cov,indent=1)[:1500])
except Exception as e: print("cov fail",e)

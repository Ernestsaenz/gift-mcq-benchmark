import json, collections
A='/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
d=json.load(open(A+'mech_db_cells.json'))
cells=d['cells']
print("raw cells:",len(cells))
print("exps:", collections.Counter(c['exp'] for c in cells))
print("attempt_index hist:", collections.Counter(c.get('attempt_index') for c in cells))
print("parse_status hist:", collections.Counter(c.get('parse_status') for c in cells))
print("status_code hist:", collections.Counter(c.get('status_code') for c in cells))

key=collections.Counter((c['exp'],c['model'],c['qid']) for c in cells)
print("rows per (exp,model,qid) hist:", collections.Counter(key.values()))
dups=[k for k,v in key.items() if v>1]
print("duplicate keys:", len(dups), dups[:5])

print("\n--- b320 raw rows ---")
b=[c for c in cells if c['qid']=='b320']
for c in sorted(b,key=lambda x:(x['exp'],x['model'])):
    print({k:c.get(k) for k in ('exp','model','attempt_index','status_code','parse_status','selected_letter','finish_reason','body_len','latency_ms','created_at')})
print("b320 raw row count:",len(b))

# does glm appear for b320 in ANY exp?
print("\nglm rows for b320:", [c['exp'] for c in cells if c['qid']=='b320' and 'glm' in c['model']])

# overall: per model per exp qid coverage
print("\nqids per (exp,model):")
cov=collections.defaultdict(set)
for c in cells: cov[(c['exp'],c['model'])].add(c['qid'])
for k in sorted(cov): print("  ",k,len(cov[k]))

# parse failures by model
pf=[c for c in cells if c.get('parse_status')!='ok']
print("\nnon-ok parse rows:", len(pf), collections.Counter((c['exp'],c['model'],c.get('parse_status')) for c in pf))

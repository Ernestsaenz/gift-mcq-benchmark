import json, collections
A='/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
rows=json.load(open(A+'paired_clean.json'))
allitems={r['question_id'] for r in rows}
for q in ('b343','b420','b430'):
    print(q,"present in paired_clean?", q in allitems)

# raw cell dump
try:
    cells=json.load(open(A+'mech_db_cells.json'))
    print("\nmech_db_cells type:", type(cells).__name__, len(cells))
    if isinstance(cells,dict): print(" keys:", list(cells.keys())[:10])
    sample = cells if isinstance(cells,list) else list(cells.values())[0]
    print(" sample record:", json.dumps(sample[0] if isinstance(sample,list) else sample, ensure_ascii=False)[:600])
except Exception as e:
    print("mech_db_cells load fail:",e)

import json, collections
P='/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json'
rows=json.load(open(P))
models=sorted({r['model'] for r in rows})
print("models(full):",models)

# b320 in FULL file
print("\n--- b320 rows in FULL file ---")
for r in rows:
    if r['question_id']=='b320':
        print({k:r[k] for k in ('question_id','model','cluster','correct_letter','analysis_include','excl_item_defect','excl_nota_position_a','A_correct','B_correct','A_selected','B_selected','A_tokens','B_tokens','A_latency_ms','B_latency_ms')})

# full-file balance
cellf=collections.Counter((r['question_id'],r['model']) for r in rows)
print("\nFULL cells per (item,model) hist:", collections.Counter(cellf.values()))
mpi=collections.defaultdict(set)
for r in rows: mpi[r['question_id']].add(r['model'])
h=collections.Counter(len(v) for v in mpi.values())
print("FULL models-per-item hist:", h)
short=sorted(q for q,v in mpi.items() if len(v)<4)
print("FULL items with <4 models:", short)
for q in short:
    print("  ",q,"missing:",sorted(set(models)-mpi[q]))
print("4*423 =",4*423, " actual:",len(rows), " deficit:",4*423-len(rows))

# exclusion flag breakdown
print("\n--- exclusion flags on the 392 excluded rows ---")
exc=[r for r in rows if not r['analysis_include']]
print(collections.Counter((r['excl_item_defect'],r['excl_nota_position_a']) for r in exc))
print("included rows with any excl flag set:",
      sum(1 for r in rows if r['analysis_include'] and (r['excl_item_defect'] or r['excl_nota_position_a'])))
# do the flags exactly determine analysis_include?
mism=[r['question_id'] for r in rows if r['analysis_include'] == bool(r['excl_item_defect'] or r['excl_nota_position_a'])]
print("rows where analysis_include != NOT(any flag):", len(mism), sorted(set(mism))[:10])

# meta exclusion lists vs data
meta=json.load(open('/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/dataset_meta.json'))
adm=set(meta['exclusions']['administrative_legal_out_of_domain']); adj=set(meta['exclusions']['adjudicated_key_defect'])
flagged_defect={r['question_id'] for r in rows if r['excl_item_defect']}
flagged_pos={r['question_id'] for r in rows if r['excl_nota_position_a']}
print("\nmeta defect lists union size:", len(adm|adj), "data excl_item_defect items:", len(flagged_defect),
      "equal?", (adm|adj)==flagged_defect, "diff:", sorted((adm|adj)^flagged_defect))
letters={r['correct_letter'] for r in rows if r['excl_nota_position_a']}
print("excl_nota_position_a items:", len(flagged_pos), "(meta says 91) letters seen:", letters)
allA={r['question_id'] for r in rows if str(r['correct_letter']).lower()=='a'}
print("items with correct_letter=='a':", len(allA), "== flagged_pos?", allA==flagged_pos)

# analysis-item count arithmetic
allitems={r['question_id'] for r in rows}
print("\nitems all:",len(allitems),"minus defect",len(flagged_defect),"minus posA",len(flagged_pos),
      "overlap:",len(flagged_defect&flagged_pos), "=>", len(allitems)-len(flagged_defect|flagged_pos))

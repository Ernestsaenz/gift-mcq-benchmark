"""Step 4: pull question + option text for the 24 harm cells so they can be read."""
import sys, os, json, sqlite3, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_lib import *

harm = json.load(open(os.path.join(BASE, 'ca_harm_cells.json')))
qids = sorted(set(r['question_id'] for r in harm), key=lambda s: int(s[1:]))

con = sqlite3.connect('file:%s?mode=ro&immutable=1' % DB, uri=True)
ds = dict(con.execute('select name,id from datasets'))
dsid = ds['balanced_a_310726']
q = {}
ph = ','.join('?' * len(qids))
for row in con.execute(
        'select question_id,question_text,option_a,option_b,option_c,option_d,correct_letter,'
        'region,year,exam_part,question_number,specialty from questions '
        'where dataset_id=? and question_id in (%s)' % ph, [dsid] + qids):
    q[row[0]] = row

by_q = collections.defaultdict(list)
for r in harm:
    by_q[r['question_id']].append(r)

out = []
for qid in qids:
    row = q[qid]
    opts = {'a': row[2], 'b': row[3], 'c': row[4], 'd': row[5]}
    cells = by_q[qid]
    print('=' * 100)
    print('%s  | %s %s %s | key=%s | qlen=%d | negated=%s has_context=%s | cluster=%s'
          % (qid, row[7], row[8], row[9], row[6], cells[0]['qlen'],
             cells[0]['negated_stem'], cells[0]['has_context'], cells[0]['cluster']))
    print('STEM: %s' % row[1])
    for L in 'abcd':
        mark = ' <-KEY' if L == row[6] else ''
        picked = [c['model'].split('/')[-1] for c in cells if c['gift_selected'] == L]
        pm = '  [GIFT->%s]' % ','.join(picked) if picked else ''
        print('   %s) %s%s%s' % (L, opts[L], mark, pm))
    for c in cells:
        print('   MODEL %-22s GIFT picked %s (WRONG)  OR picked %s (right)  gift_tok=%s or_tok=%s gift_ms=%s'
              % (c['model'].split('/')[-1], c['gift_selected'], c['or_selected'],
                 c['gift_tokens'], c['or_tokens'], c['gift_latency_ms']))
    out.append({'qid': qid, 'stem': row[1], 'opts': opts, 'key': row[6],
                'region': row[7], 'year': row[8], 'exam_part': row[9],
                'cells': [{'model': c['model'], 'gift': c['gift_selected'], 'or': c['or_selected']} for c in cells]})

json.dump(out, open(os.path.join(BASE, 'ca_harm_texts.json'), 'w'), ensure_ascii=False, indent=1)

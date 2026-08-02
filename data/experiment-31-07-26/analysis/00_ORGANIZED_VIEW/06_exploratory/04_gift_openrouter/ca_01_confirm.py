"""Step 1: reproduce the observed table, enumerate the retrieval-harm cells."""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_lib import *

rows_all = load(include_only=False)
rows = load()
print('rows total %d  analysis_include %d' % (len(rows_all), len(rows)))
print('items %d  clusters %d  models %d' % (
    len(set(r['question_id'] for r in rows)),
    len(set(r['cluster'] for r in rows)),
    len(set(r['model'] for r in rows))))

# sanity: any missing gift/or correctness?
bad = [r for r in rows if r['gift_correct'] is None or r['or_correct'] is None]
print('cells with null correctness:', len(bad))

def table(rs):
    a = sum(1 for r in rs if r['gift_correct'] == 1 and r['or_correct'] == 1)
    b = sum(1 for r in rs if r['gift_correct'] == 1 and r['or_correct'] == 0)  # GIFT-only right
    c = sum(1 for r in rs if r['gift_correct'] == 0 and r['or_correct'] == 1)  # OR-only right = HARM
    d = sum(1 for r in rs if r['gift_correct'] == 0 and r['or_correct'] == 0)
    return a, b, c, d

print()
hdr = '%-24s %5s %7s %7s %7s   %4s %4s   %8s %8s %10s'
print(hdr % ('model', 'n', 'GIFT%', 'OR%', 'diff_pp', 'b', 'c', 'chi2', 'p_chi2', 'p_exact'))
by_model = collections.defaultdict(list)
for r in rows:
    by_model[r['model']].append(r)

for m in sorted(by_model, key=lambda k: -(sum(x['gift_correct'] for x in by_model[k]) / len(by_model[k]))):
    rs = by_model[m]
    a, b, c, d = table(rs)
    n = len(rs)
    g = sum(x['gift_correct'] for x in rs) / n
    o = sum(x['or_correct'] for x in rs) / n
    x2, px2 = mcnemar_chi2(b, c)
    print(hdr % (m.split('/')[-1], n, '%.1f' % (100 * g), '%.1f' % (100 * o),
                 '%+.2f' % (100 * (g - o)), b, c, '%.3f' % x2, '%.4f' % px2,
                 '%.4f' % mcnemar_exact(b, c)))

a, b, c, d = table(rows)
n = len(rows)
g = sum(x['gift_correct'] for x in rows) / n
o = sum(x['or_correct'] for x in rows) / n
x2, px2 = mcnemar_chi2(b, c)
print(hdr % ('POOLED', n, '%.1f' % (100 * g), '%.1f' % (100 * o), '%+.2f' % (100 * (g - o)),
             b, c, '%.3f' % x2, '%.4f' % px2, '%.4f' % mcnemar_exact(b, c)))
print('2x2 concordance: both-right %d  GIFTonly %d  ORonly %d  both-wrong %d' % (a, b, c, d))

harm = [r for r in rows if r['gift_correct'] == 0 and r['or_correct'] == 1]
help_ = [r for r in rows if r['gift_correct'] == 1 and r['or_correct'] == 0]
json.dump(harm, open(os.path.join(BASE, 'ca_harm_cells.json'), 'w'), ensure_ascii=False, indent=1)
json.dump(help_, open(os.path.join(BASE, 'ca_help_cells.json'), 'w'), ensure_ascii=False, indent=1)
print('\nharm cells %d written; help cells %d written' % (len(harm), len(help_)))
print('harm distinct items %d ; help distinct items %d' % (
    len(set(r['question_id'] for r in harm)), len(set(r['question_id'] for r in help_))))
print('harm items:', sorted(set(r['question_id'] for r in harm), key=lambda s: int(s[1:])))

#!/usr/bin/env python
"""Independent recomputation of the 'position artifact' claim.

ARTIFACT = mean(d | key=='a') - mean(d | key in b,c,d),  d = B_correct - A_correct.
Stdlib only.
"""
import json, collections, os

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, 'paired_clean.json')))

def art(rows):
    a  = [r['B_correct'] - r['A_correct'] for r in rows if r['correct_letter'] == 'a']
    na = [r['B_correct'] - r['A_correct'] for r in rows if r['correct_letter'] != 'a']
    if not a or not na:
        return None
    ma, mn = sum(a)/len(a), sum(na)/len(na)
    return ma, mn, ma-mn, len(a), len(na)

print('=== FULL unfiltered set (n=%d cells) ===' % len(D))
ma, mn, art_full, na_, nn_ = art(D)
print('delta(a)      = %+.4f pp  (%d cells)' % (100*ma, na_))
print('delta(b,c,d)  = %+.4f pp  (%d cells)' % (100*mn, nn_))
print('ARTIFACT      = %+.6f pp' % (100*art_full))

print()
print('--- baseline (arm A) accuracy by key slot, full set ---')
for lab, sel in (('a', lambda r: r['correct_letter']=='a'),
                 ('bcd', lambda r: r['correct_letter']!='a')):
    rr = [r for r in D if sel(r)]
    A = sum(r['A_correct'] for r in rr)/len(rr)
    B = sum(r['B_correct'] for r in rr)/len(rr)
    print('  key=%-3s  n=%4d   A=%.4f   B=%.4f   d=%+.4f' % (lab, len(rr), A, B, B-A))

print()
print('--- per letter ---')
for L in 'abcd':
    rr = [r for r in D if r['correct_letter']==L]
    A = sum(r['A_correct'] for r in rr)/len(rr)
    B = sum(r['B_correct'] for r in rr)/len(rr)
    print('  %s  n=%4d  A=%.4f  B=%.4f  d=%+.4f pp' % (L, len(rr), A, B, 100*(B-A)))

print()
print('--- per model ---')
for m in sorted(set(r['model'] for r in D)):
    rr = [r for r in D if r['model']==m]
    o = art(rr)
    print('  %-28s d(a)=%+7.3f d(bcd)=%+7.3f ART=%+8.3f  (na=%d nn=%d)'
          % (m, 100*o[0], 100*o[1], 100*o[2], o[3], o[4]))

print()
print('=== defect-item exclusion applied (excl_item_defect==False) ===')
sub = [r for r in D if not r['excl_item_defect']]
o = art(sub)
print('n=%d  delta(a)=%+.4f  delta(bcd)=%+.4f  ARTIFACT=%+.6f' % (len(sub),100*o[0],100*o[1],100*o[2]))

print()
print('=== structure ===')
items = collections.defaultdict(list)
for r in D: items[r['question_id']].append(r)
print('items=%d  cells/item hist=%s' % (len(items), collections.Counter(len(v) for v in items.values())))
ia = set(q for q,v in items.items() if v[0]['correct_letter']=='a')
print('items with key a = %d ; non-a = %d' % (len(ia), len(items)-len(ia)))
# check letter constant within item
bad = [q for q,v in items.items() if len(set(x['correct_letter'] for x in v))>1]
print('items with inconsistent correct_letter:', len(bad))
# cluster constant within item?
badc = [q for q,v in items.items() if len(set(x['cluster'] for x in v))>1]
print('items with inconsistent cluster:', len(badc))

clu = collections.defaultdict(set)
for r in D: clu[r['cluster']].add(r['question_id'])
print('clusters=%d  items/cluster hist=%s' % (len(clu), sorted(collections.Counter(len(v) for v in clu.values()).items())))
mixed = [c for c,v in clu.items() if len(set(1 if q in ia else 0 for q in v))>1]
print('clusters containing BOTH a and non-a items: %d' % len(mixed))
print('items inside those mixed clusters: %d' % sum(len(clu[c]) for c in mixed))

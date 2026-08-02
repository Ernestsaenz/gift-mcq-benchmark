"""Step 11: the position trend and the Illes-Balears effect are the same variable
(Balears occupies the front of the run). Separate them: does the trend survive WITHIN
each block? And is the real variable 'shared-stem clinical case' rather than either?"""
import sys, os, json, sqlite3, collections, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_lib import *

rows = load()
con = sqlite3.connect('file:%s?mode=ro&immutable=1' % DB, uri=True)
dsid = dict(con.execute('select name,id from datasets'))['balanced_a_310726']
order = {r[0]: r[1] for r in con.execute('select question_id,id from questions where dataset_id=?', (dsid,))}
covered = sorted(set(r['question_id'] for r in rows), key=lambda q: order[q])
pos = {q: i for i, q in enumerate(covered)}


def trend(rs, yf, B=30000, seed=1, label=''):
    xs = [pos[r['question_id']] for r in rs]
    ys = [yf(r) for r in rs]
    if len(set(ys)) < 2:
        print('  %-42s (degenerate: all outcomes identical)' % label); return
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    r0 = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    rng = random.Random(seed); yy = ys[:]; cnt = 0
    for _ in range(B):
        rng.shuffle(yy)
        if abs(sum((x - mx) * (y - my) for x, y in zip(xs, yy)) / den) >= abs(r0) - 1e-12:
            cnt += 1
    print('  %-42s n=%4d  r=%+.4f  perm p=%.5f' % (label, len(rs), r0, (cnt + 1) / (B + 1)))


HARM = lambda r: 1 if (not r['gift_correct'] and r['or_correct']) else 0
bal = [r for r in rows if r['region'] == 'Illes Balears']
oth = [r for r in rows if r['region'] != 'Illes Balears']
print('=== Does the position trend survive WITHIN each block? ===')
print('  positions: Balears %d..%d ; others %d..%d'
      % (min(pos[r['question_id']] for r in bal), max(pos[r['question_id']] for r in bal),
         min(pos[r['question_id']] for r in oth), max(pos[r['question_id']] for r in oth)))
trend(rows, HARM, label='HARM ~ position, ALL')
trend(bal, HARM, label='HARM ~ position, WITHIN Illes Balears')
trend(oth, HARM, label='HARM ~ position, WITHIN non-Balears')
trend(oth, lambda r: 1 - r['gift_correct'], label='GIFT error ~ position, WITHIN non-Balears')
trend(oth, lambda r: 1 - r['or_correct'], label='OR error ~ position, WITHIN non-Balears')
trend(bal, lambda r: r['gift_latency_ms'], label='gift_latency ~ position, WITHIN Balears')
trend(oth, lambda r: r['gift_latency_ms'], label='gift_latency ~ position, WITHIN non-Balears')

print('\n  block means:')
for lab, rs in [('Illes Balears', bal), ('non-Balears', oth)]:
    n = len(rs)
    b = sum(1 for r in rs if r['gift_correct'] and not r['or_correct'])
    c = sum(1 for r in rs if not r['gift_correct'] and r['or_correct'])
    print('    %-16s n=%4d GIFT %.4f OR %.4f  b=%2d c=%2d  harm %.2f%%  net %+.2fpp  McNemar exact p=%.4f'
          % (lab, n, sum(r['gift_correct'] for r in rs) / n, sum(r['or_correct'] for r in rs) / n,
             b, c, 100 * c / n, 100 * (b - c) / n, mcnemar_exact(b, c)))

# ---- is the real variable 'shared-stem clinical case block'? ----
print('\n=== Shared-stem clinical case blocks (exam_part starting "caso") vs standalone ===')
casos = [r for r in rows if str(r['exam_part']).startswith('caso')]
stand = [r for r in rows if not str(r['exam_part']).startswith('caso')]
for lab, rs in [('caso-* (shared stem)', casos), ('standalone', stand)]:
    n = len(rs)
    b = sum(1 for r in rs if r['gift_correct'] and not r['or_correct'])
    c = sum(1 for r in rs if not r['gift_correct'] and r['or_correct'])
    print('  %-22s n=%4d GIFT %.4f OR %.4f b=%2d c=%2d harm %.2f%% net %+.2fpp exact p=%.4f'
          % (lab, n, sum(r['gift_correct'] for r in rs) / n, sum(r['or_correct'] for r in rs) / n,
             b, c, 100 * c / n, 100 * (b - c) / n, mcnemar_exact(b, c)))
cc = sum(1 for r in casos if not r['gift_correct'] and r['or_correct'])
sc = sum(1 for r in stand if not r['gift_correct'] and r['or_correct'])
print('  Fisher exact on harm rate caso vs standalone: p=%.4f'
      % fisher_exact_2x2(cc, len(casos) - cc, sc, len(stand) - sc))

print('\n  cross-tab: caso-* by region (are the two variables the same thing?)')
ct = collections.Counter((r['region'], str(r['exam_part']).startswith('caso')) for r in rows)
for reg in sorted(set(r['region'] for r in rows)):
    print('    %-24s caso %4d  standalone %4d' % (reg, ct[(reg, True)], ct[(reg, False)]))

# ---- has_context is the third alias; check the three-way ----
print('\n=== has_context (the supplied flag) vs caso-* vs harm ===')
print('  has_context TRUE on caso cells: %d/%d ; on standalone: %d/%d'
      % (sum(1 for r in casos if r['has_context']), len(casos),
         sum(1 for r in stand if r['has_context']), len(stand)))
for lab, rs in [('has_context', [r for r in rows if r['has_context']]),
                ('no context', [r for r in rows if not r['has_context']])]:
    n = len(rs)
    b = sum(1 for r in rs if r['gift_correct'] and not r['or_correct'])
    c = sum(1 for r in rs if not r['gift_correct'] and r['or_correct'])
    print('  %-14s n=%4d harm %2d (%.2f%%) b=%2d net %+.2fpp exact p=%.4f'
          % (lab, n, c, 100 * c / n, b, 100 * (b - c) / n, mcnemar_exact(b, c)))

# ---- stratified test: harm rate by position quartile WITHIN standalone items only ----
print('\n=== Position quartile WITHIN standalone (non-caso) cells only ===')
sp = sorted(set(r['question_id'] for r in stand), key=lambda q: pos[q])
sidx = {q: i for i, q in enumerate(sp)}
QQ = collections.defaultdict(list)
for r in stand:
    QQ[sidx[r['question_id']] * 4 // len(sp)].append(r)
for k in sorted(QQ):
    rs = QQ[k]
    c = sum(1 for r in rs if not r['gift_correct'] and r['or_correct'])
    b = sum(1 for r in rs if r['gift_correct'] and not r['or_correct'])
    print('    Q%d n=%4d harm %2d (%.2f%%) help %2d  ORacc %.4f  GIFTacc %.4f'
          % (k + 1, len(rs), c, 100 * c / len(rs), b,
             sum(r['or_correct'] for r in rs) / len(rs), sum(r['gift_correct'] for r in rs) / len(rs)))
xs = [sidx[r['question_id']] for r in stand]
ys = [HARM(r) for r in stand]
mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
r0 = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
rng = random.Random(4); yy = ys[:]; cnt = 0; B = 50000
for _ in range(B):
    rng.shuffle(yy)
    if abs(sum((x - mx) * (y - my) for x, y in zip(xs, yy)) / den) >= abs(r0) - 1e-12:
        cnt += 1
print('    r(position-within-standalone, HARM) = %+.4f ; perm p = %.5f' % (r0, (cnt + 1) / (B + 1)))

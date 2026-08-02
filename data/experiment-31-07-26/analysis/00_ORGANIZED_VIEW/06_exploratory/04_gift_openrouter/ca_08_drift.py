"""Step 8: the harm rate climbs monotonically through the run. Is that GIFT degrading,
or items getting harder? OpenRouter on the SAME items is the control -- it was run
separately, complete, and is unaffected by GIFT's load-shedding."""
import sys, os, json, sqlite3, collections, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_lib import *

rows = load()
con = sqlite3.connect('file:%s?mode=ro&immutable=1' % DB, uri=True)
dsid = dict(con.execute('select name,id from datasets'))['balanced_a_310726']
order = {r[0]: r[1] for r in con.execute('select question_id,id from questions where dataset_id=?', (dsid,))}
covered = sorted(set(r['question_id'] for r in rows), key=lambda q: order[q])
pos = {q: i for i, q in enumerate(covered)}

print('=== Quartile of dataset order, within the 311 analysed items ===')
print('%-6s %6s %8s %8s %9s %6s %6s %8s' % ('quart', 'cells', 'GIFTacc', 'ORacc', 'net_pp', 'b', 'c', 'b/c'))
Q = collections.defaultdict(list)
for r in rows:
    Q[pos[r['question_id']] * 4 // len(covered)].append(r)
for k in sorted(Q):
    rs = Q[k]
    n = len(rs)
    g = sum(r['gift_correct'] for r in rs) / n
    o = sum(r['or_correct'] for r in rs) / n
    b = sum(1 for r in rs if r['gift_correct'] and not r['or_correct'])
    c = sum(1 for r in rs if not r['gift_correct'] and r['or_correct'])
    print('%-6s %6d %8.4f %8.4f %+9.2f %6d %6d %8s'
          % ('Q%d' % (k + 1), n, g, o, 100 * (g - o), b, c, '%.2f' % (b / c) if c else 'inf'))

print('\n  -> OpenRouter accuracy is the control: it was run to completion, in its own')
print('     process, so any trend in ORacc is item difficulty, and any GIFT-specific')
print('     divergence is the GIFT run degrading.')

# trend tests
def trend_p(yvals, label, B=30000, seed=1):
    xs = [pos[r['question_id']] for r in rows]
    mx = sum(xs) / len(xs)
    my = sum(yvals) / len(yvals)
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in yvals))
    if den == 0:
        return None
    r0 = sum((x - mx) * (y - my) for x, y in zip(xs, yvals)) / den
    rng = random.Random(seed)
    yy = yvals[:]
    cnt = 0
    for _ in range(B):
        rng.shuffle(yy)
        v = sum((x - mx) * (y - my) for x, y in zip(xs, yy)) / den
        if abs(v) >= abs(r0) - 1e-12:
            cnt += 1
    print('  r(position, %-18s) = %+.4f   permutation p = %.5f' % (label, r0, (cnt + 1) / (B + 1)))
    return r0

print('\n=== Trend tests (cell-level, permutation on the outcome, B=200000) ===')
trend_p([1 - r['gift_correct'] for r in rows], 'GIFT error')
trend_p([1 - r['or_correct'] for r in rows], 'OR error   ')
trend_p([1 if (not r['gift_correct'] and r['or_correct']) else 0 for r in rows], 'HARM')
trend_p([1 if (r['gift_correct'] and not r['or_correct']) else 0 for r in rows], 'HELP')
trend_p([r['gift_correct'] - r['or_correct'] for r in rows], 'GIFT-minus-OR')

# cluster-level permutation for the paired difference (respects item clustering)
print('\n=== Cluster-permutation trend on the PAIRED difference (whole clusters shuffled) ===')
clusters = collections.defaultdict(list)
for i, r in enumerate(rows):
    clusters[r['cluster']].append(i)
ck = list(clusters.keys())
xs = [pos[r['question_id']] for r in rows]
mx = sum(xs) / len(xs)
diff = [r['gift_correct'] - r['or_correct'] for r in rows]
md = sum(diff) / len(diff)
den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - md) ** 2 for y in diff))
r0 = sum((x - mx) * (y - md) for x, y in zip(xs, diff)) / den
rng = random.Random(77)
B = 10000
cnt = 0
for _ in range(B):
    perm = list(ck); rng.shuffle(perm)
    dd = [0.0] * len(rows)
    for s, t in zip(ck, perm):
        sv = [diff[i] for i in clusters[s]]
        ti = clusters[t]
        for j in range(min(len(sv), len(ti))):
            dd[ti[j]] = sv[j]
    v = sum((x - mx) * (y - md) for x, y in zip(xs, dd)) / den
    if abs(v) >= abs(r0) - 1e-12:
        cnt += 1
print('  r = %+.4f ; cluster-permutation p = %.5f (B=%d)' % (r0, (cnt + 1) / (B + 1), B))

# latency drift -- direct evidence the GIFT service was degrading
print('\n=== GIFT latency by quartile (direct service-health evidence) ===')
print('%-6s %12s %12s %12s' % ('quart', 'gift_med_ms', 'or_med_ms', 'ratio'))
for k in sorted(Q):
    g = sorted(r['gift_latency_ms'] for r in Q[k] if r['gift_latency_ms'])
    o = sorted(r['or_latency_ms'] for r in Q[k] if r['or_latency_ms'])
    print('%-6s %12.0f %12.0f %12.2f' % ('Q%d' % (k + 1), g[len(g) // 2], o[len(o) // 2],
                                         g[len(g) // 2] / o[len(o) // 2]))
trend_p([r['gift_latency_ms'] for r in rows], 'gift_latency', B=20000)
trend_p([r['or_latency_ms'] for r in rows], 'or_latency  ', B=20000)

# does the trend survive adjusting for the observable difficulty proxies?
print('\n=== Stratified check: harm rate by quartile WITHIN OR-correct cells only ===')
print('  (conditions on the item being answerable, removing raw difficulty drift)')
for k in sorted(Q):
    rs = [r for r in Q[k] if r['or_correct']]
    h = sum(1 for r in rs if not r['gift_correct'])
    lo, hi = wilson(h, len(rs))
    print('    Q%d  harm %2d / OR-right %4d = %.2f%%  [%.2f, %.2f]'
          % (k + 1, h, len(rs), 100 * h / len(rs), 100 * lo, 100 * hi))
ys = [1 if not r['gift_correct'] else 0 for r in rows if r['or_correct']]
xs2 = [pos[r['question_id']] for r in rows if r['or_correct']]
mx2 = sum(xs2) / len(xs2); my2 = sum(ys) / len(ys)
den2 = math.sqrt(sum((x - mx2) ** 2 for x in xs2) * sum((y - my2) ** 2 for y in ys))
r2 = sum((x - mx2) * (y - my2) for x, y in zip(xs2, ys)) / den2
rng = random.Random(9); yy = ys[:]; cnt = 0; B = 30000
for _ in range(B):
    rng.shuffle(yy)
    if abs(sum((x - mx2) * (y - my2) for x, y in zip(xs2, yy)) / den2) >= abs(r2) - 1e-12:
        cnt += 1
print('    r(position, GIFT error | OR right) = %+.4f ; permutation p = %.5f' % (r2, (cnt + 1) / (B + 1)))

# region confound: dataset order is largely region-blocked
print('\n=== Is position just region? mean position by region ===')
byreg = collections.defaultdict(list)
for r in rows:
    byreg[r['region']].append(pos[r['question_id']])
for reg, v in sorted(byreg.items(), key=lambda kv: sum(kv[1]) / len(kv[1])):
    print('    %-24s n=%3d mean position %6.1f (of %d)' % (reg, len(v), sum(v) / len(v), len(covered)))

"""Step 7: (a) effort ratio across all four outcome cells -- is the harm-cell token bloat
retrieval-specific or just a difficulty marker? (b) quantify the 83%-coverage caveat."""
import sys, os, json, sqlite3, collections, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_lib import *

rows = load()


def bucket(r):
    if r['gift_correct'] and r['or_correct']:
        return 'both_right'
    if r['gift_correct'] and not r['or_correct']:
        return 'help (GIFT only)'
    if not r['gift_correct'] and r['or_correct']:
        return 'HARM (OR only)'
    return 'both_wrong'


print('=== (a) gift_tokens / or_tokens by outcome bucket, pooled and per model ===')
print('%-22s %-18s %5s %10s %10s' % ('model', 'bucket', 'n', 'median', 'mean'))
for m in [None] + sorted(set(r['model'] for r in rows)):
    rs = [r for r in rows if (m is None or r['model'] == m) and r['or_tokens']]
    for bkt in ['both_right', 'help (GIFT only)', 'HARM (OR only)', 'both_wrong']:
        v = sorted(r['gift_tokens'] / r['or_tokens'] for r in rs if bucket(r) == bkt)
        if not v:
            continue
        print('%-22s %-18s %5d %10.3f %10.3f' % ((m or 'POOLED').split('/')[-1], bkt, len(v),
                                                 v[len(v) // 2], sum(v) / len(v)))
    print()

# the decisive contrast: HARM vs HELP (both are discordant -> matched on "one arm struggled")
print('  DECISIVE CONTRAST -- harm vs help (both discordant, so item difficulty is matched):')
rng = random.Random(41)
for m in [None] + sorted(set(r['model'] for r in rows)):
    rs = [r for r in rows if (m is None or r['model'] == m) and r['or_tokens']]
    h = [r['gift_tokens'] / r['or_tokens'] for r in rs if bucket(r).startswith('HARM')]
    l = [r['gift_tokens'] / r['or_tokens'] for r in rs if bucket(r).startswith('help')]
    if len(h) < 1 or len(l) < 1:
        print('  %-22s harm n=%d help n=%d -- too few' % ((m or 'POOLED').split('/')[-1], len(h), len(l)))
        continue
    mh, ml = sorted(h)[len(h) // 2], sorted(l)[len(l) // 2]
    obs = mh - ml
    pool = h + l
    k = len(h)
    B = 100000
    cnt = 0
    for _ in range(B):
        rng.shuffle(pool)
        s1, s2 = sorted(pool[:k]), sorted(pool[k:])
        if abs(s1[len(s1) // 2] - s2[len(s2) // 2]) >= abs(obs) - 1e-12:
            cnt += 1
    print('  %-22s harm med %.3f (n=%2d) vs help med %.3f (n=%2d)  perm p=%.4f'
          % ((m or 'POOLED').split('/')[-1], mh, len(h), ml, len(l), (cnt + 1) / (B + 1)))

# ---- cluster-bootstrap CI on the harm rate and on the net contrast ----
print('\n=== Cluster bootstrap (183 clusters resampled, B=20000) ===')


def harmrate(rs):
    return sum(1 for r in rs if not r['gift_correct'] and r['or_correct']) / len(rs) if rs else None


def netdiff(rs):
    n = len(rs)
    if not n:
        return None
    return (sum(r['gift_correct'] for r in rs) - sum(r['or_correct'] for r in rs)) / n


def bc_ratio(rs):
    b = sum(1 for r in rs if r['gift_correct'] and not r['or_correct'])
    c = sum(1 for r in rs if not r['gift_correct'] and r['or_correct'])
    return (b / c) if c else None


for name, fn in [('harm rate (c/N)', harmrate), ('net diff (GIFT-OR)', netdiff), ('b/c ratio', bc_ratio)]:
    d = cluster_bootstrap(rows, fn, B=20000)
    lo, hi = ci(d)
    print('  %-20s point %.4f   95%% cluster-bootstrap CI [%.4f, %.4f]'
          % (name, fn(rows), lo, hi))

# ---- (b) COVERAGE CAVEAT ----
print('\n=== (b) Coverage caveat: what the 83% prefix does to the harm count ===')
con = sqlite3.connect('file:%s?mode=ro&immutable=1' % DB, uri=True)
dsid = dict(con.execute('select name,id from datasets'))['balanced_a_310726']
exp = {r[1]: r[0] for r in con.execute("select id,name from experiments")}
print('  experiments:', exp)

# OpenRouter condition-A results over the FULL 474-item dataset
sql = """
select q.question_id, lc.model, pa.selected_letter, q.correct_letter, q.region
from logical_calls lc
join questions q on q.id = lc.question_id
join parsed_answers pa on pa.logical_call_id = lc.id
join experiments e on e.id = lc.experiment_id
where e.name = 'expA_or_310726' and pa.parse_status='ok' and q.dataset_id=?
"""
orall = collections.defaultdict(dict)
for qid, model, sel, key, region in con.execute(sql, (dsid,)):
    orall[qid][model] = (1 if sel == key else 0, region)
print('  OR condition-A items with >=1 parsed cell: %d' % len(orall))

covered = set(r['question_id'] for r in rows)
gift_all = set()
sqlg = """
select distinct q.question_id from logical_calls lc
join questions q on q.id=lc.question_id
join parsed_answers pa on pa.logical_call_id=lc.id
join experiments e on e.id=lc.experiment_id
where e.name='expA_gift_310726' and pa.parse_status='ok' and q.dataset_id=?"""
for (qid,) in con.execute(sqlg, (dsid,)):
    gift_all.add(qid)

# excluded-defect items, from the cross_arm file
allrows = load(include_only=False)
defect = set(r['question_id'] for r in allrows if r.get('excl_item_defect'))
eligible = set(orall) - defect
missing = eligible - covered
print('  eligible (non-defect) OR items %d ; GIFT-analysed %d ; NOT analysed %d'
      % (len(eligible), len(covered), len(missing)))


def or_acc(items):
    k = t = 0
    for q in items:
        for m, (ok, _) in orall[q].items():
            k += ok; t += 1
    return k, t, (k / t if t else float('nan'))

kc, tc, pc = or_acc(covered)
km, tm, pm = or_acc(missing)
print('  OR accuracy on the %d analysed items   : %.4f (%d/%d)' % (len(covered), pc, kc, tc))
print('  OR accuracy on the %d un-analysed items: %.4f (%d/%d)' % (len(missing), pm, km, tm))
print('  difficulty gap: %+.2f pp  (Fisher p=%.3e)'
      % (100 * (pc - pm), fisher_exact_2x2(kc, tc - kc, km, tm - km)))

print('\n  Projection of the harm count onto the full dataset.')
print('  Harm requires OR right AND GIFT wrong. Anchoring on the observed conditionals:')
p_or_right_cov = pc
p_harm_given_or_right = 24 / (1117 + 24)
print('    P(harm | OR right), observed on analysed items = %.5f  (24/1141)' % p_harm_given_or_right)
print('    OR-right cells available on the un-analysed items = %d' % km)
print('    -> if the SAME conditional held there, expected extra harm cells = %.1f'
      % (km * p_harm_given_or_right))
print('    -> total projected harm over 474 items = %.1f (vs 24 observed on the prefix)'
      % (24 + km * p_harm_given_or_right))
print('  BUT that conditional is the thing most likely to move: the un-analysed items are')
print('  where OR itself falls to %.1f%%, and GIFT was never measured there at all.' % (100 * pm))

# how much would the harm rate have to rise on the missing items to erase the +1.8pp?
b, c = 46, 24
print('\n  Break-even sensitivity. Observed b=46 c=24 over 1244 cells.')
n_miss_cells = tm  # OR-parsed cells on missing items (approx the cells GIFT never ran)
print('    un-analysed OR cells (the cells GIFT never ran) = %d' % n_miss_cells)
for extra_c_minus_b in (0, 22, 30, 40, 60):
    tot = (b - c) - extra_c_minus_b
    print('    if GIFT lost a NET %2d more cells than it won there: pooled net = %+3d cells '
          '= %+.2fpp over %d cells' % (extra_c_minus_b, tot, 100 * tot / (1244 + n_miss_cells),
                                       1244 + n_miss_cells))
print('    -> the observed +22-cell margin is erased by a net loss of 22 cells on the')
print('       %d un-run cells, i.e. a %.1f%% net swing. Nothing in this dataset constrains it.'
      % (n_miss_cells, 100 * 22 / n_miss_cells))

# ---- prefix position trend: did GIFT degrade over the run? ----
print('\n=== Position-in-run trend (load-shedding / drift check) ===')
qnum = {}
for r in con.execute('select question_id,id from questions where dataset_id=?', (dsid,)):
    qnum[r[0]] = r[1]
srt = sorted(covered, key=lambda q: qnum[q])
pos = {q: i for i, q in enumerate(srt)}
quart = collections.defaultdict(lambda: [0, 0, 0])
for r in rows:
    qi = pos[r['question_id']] * 4 // len(srt)
    quart[qi][0] += 1
    quart[qi][1] += (1 if (not r['gift_correct'] and r['or_correct']) else 0)
    quart[qi][2] += (1 if (r['gift_correct'] and not r['or_correct']) else 0)
print('  quartile of dataset order | cells | harm | help | harm rate')
for k in sorted(quart):
    n, h, l = quart[k]
    print('    Q%d %6d %6d %6d   %.2f%%' % (k + 1, n, h, l, 100 * h / n))
# Spearman-ish: point-biserial of position vs harm, permutation
xs = [pos[r['question_id']] for r in rows]
ys = [1 if (not r['gift_correct'] and r['or_correct']) else 0 for r in rows]
mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
rr = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
rng = random.Random(8)
yy = ys[:]
B = 100000
cnt = 0
for _ in range(B):
    rng.shuffle(yy)
    v = sum((x - mx) * (y - my) for x, y in zip(xs, yy)) / den
    if abs(v) >= abs(rr) - 1e-12:
        cnt += 1
print('  point-biserial r(position, harm) = %+.4f ; permutation p = %.4f' % (rr, (cnt + 1) / (B + 1)))

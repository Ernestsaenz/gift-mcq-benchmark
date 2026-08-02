"""Step 9: agreement at the level of the CHOSEN LETTER (4 categories), per model,
against a marginal-independence chance baseline. Pooled kappa can be inflated by
mixing models of different ability, so everything is repeated within model."""
import sys, os, json, collections, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_lib import *

rows = load()
L = 'abcd'


def kappa_letters(rs):
    n = len(rs)
    obs = sum(1 for r in rs if r['gift_selected'] == r['or_selected']) / n
    mg = collections.Counter(r['gift_selected'] for r in rs)
    mo = collections.Counter(r['or_selected'] for r in rs)
    exp = sum((mg[x] / n) * (mo[x] / n) for x in L)
    return obs, exp, (obs - exp) / (1 - exp), n


def kappa_correct(rs):
    n = len(rs)
    obs = sum(1 for r in rs if r['gift_correct'] == r['or_correct']) / n
    pg = sum(r['gift_correct'] for r in rs) / n
    po = sum(r['or_correct'] for r in rs) / n
    exp = pg * po + (1 - pg) * (1 - po)
    return obs, exp, (obs - exp) / (1 - exp), n


print('=== Cohen kappa, CORRECTNESS (2 categories) ===')
print('%-22s %6s %9s %9s %9s %22s' % ('model', 'n', 'obs_agr', 'chance', 'kappa', '95% cluster-boot CI'))
for m in [None] + sorted(set(r['model'] for r in rows)):
    rs = [r for r in rows if m is None or r['model'] == m]
    o, e, k, n = kappa_correct(rs)
    d = cluster_bootstrap(rs, lambda s: kappa_correct(s)[2] if len(set(x['gift_correct'] for x in s)) > 1 else None, B=5000)
    lo, hi = ci(d)
    print('%-22s %6d %9.4f %9.4f %9.4f %11.3f, %.3f' % ((m or 'POOLED').split('/')[-1], n, o, e, k, lo, hi))

print('\n=== Cohen kappa, SELECTED LETTER (4 categories) ===')
print('%-22s %6s %9s %9s %9s %22s' % ('model', 'n', 'obs_agr', 'chance', 'kappa', '95% cluster-boot CI'))
for m in [None] + sorted(set(r['model'] for r in rows)):
    rs = [r for r in rows if m is None or r['model'] == m]
    o, e, k, n = kappa_letters(rs)
    d = cluster_bootstrap(rs, lambda s: kappa_letters(s)[2], B=5000)
    lo, hi = ci(d)
    print('%-22s %6d %9.4f %9.4f %9.4f %11.3f, %.3f' % ((m or 'POOLED').split('/')[-1], n, o, e, k, lo, hi))

print('\n=== Error-sharing decomposition ===')
b = sum(1 for r in rows if r['gift_correct'] and not r['or_correct'])
c = sum(1 for r in rows if not r['gift_correct'] and r['or_correct'])
d_ = sum(1 for r in rows if not r['gift_correct'] and not r['or_correct'])
print('  cells where at least one arm erred: %d' % (b + c + d_))
print('    both erred          %3d  (%.1f%%)' % (d_, 100 * d_ / (b + c + d_)))
print('    only OR erred       %3d  (%.1f%%)' % (b, 100 * b / (b + c + d_)))
print('    only GIFT erred     %3d  (%.1f%%)' % (c, 100 * c / (b + c + d_)))
print('  share of GIFT errors that OR also made: %d/%d = %.1f%%' % (d_, c + d_, 100 * d_ / (c + d_)))
print('  share of OR errors that GIFT also made: %d/%d = %.1f%%' % (d_, b + d_, 100 * d_ / (b + d_)))
bw = [r for r in rows if not r['gift_correct'] and not r['or_correct']]
same = sum(1 for r in bw if r['gift_selected'] == r['or_selected'])
print('  of the %d both-wrong cells, %d (%.1f%%) chose the IDENTICAL distractor' % (len(bw), same, 100 * same / len(bw)))
print('  -> so of all %d GIFT errors, %d (%.1f%%) are letter-identical to an OR error'
      % (c + d_, same, 100 * same / (c + d_)))

print('\n  per model:')
print('%-22s %8s %8s %10s %14s' % ('model', 'GIFTerr', 'shared', 'sameletter', '%sameletter'))
for m in sorted(set(r['model'] for r in rows)):
    rs = [r for r in rows if r['model'] == m]
    ge = [r for r in rs if not r['gift_correct']]
    sh = [r for r in ge if not r['or_correct']]
    sl = [r for r in sh if r['gift_selected'] == r['or_selected']]
    print('%-22s %8d %8d %10d %13.1f%%' % (m.split('/')[-1], len(ge), len(sh), len(sl),
                                           100 * len(sl) / len(ge) if ge else 0))

print('\n=== Does GIFT prefer a systematically DIFFERENT letter than OR overall? ===')
mg = collections.Counter(r['gift_selected'] for r in rows)
mo = collections.Counter(r['or_selected'] for r in rows)
mk = collections.Counter(r['correct_letter'] for r in rows)
print('  key letters : ', {x: mk[x] for x in L})
print('  GIFT picks  : ', {x: mg[x] for x in L})
print('  OR picks    : ', {x: mo[x] for x in L})
# marginal homogeneity across the paired 4x4 (Stuart-Maxwell via Bhapkar-free
# permutation: swap the arm labels within cell, which is the exact exchangeability null)
rng = random.Random(21)
obs = sum(abs(mg[x] - mo[x]) for x in L)
B = 200000
cnt = 0
pairs = [(r['gift_selected'], r['or_selected']) for r in rows]
for _ in range(B):
    g = collections.Counter(); o = collections.Counter()
    for a_, b_ in pairs:
        if rng.random() < 0.5:
            g[a_] += 1; o[b_] += 1
        else:
            g[b_] += 1; o[a_] += 1
    if sum(abs(g[x] - o[x]) for x in L) >= obs:
        cnt += 1
print('  L1 distance between the two letter marginals = %d ; arm-swap permutation p = %.4f (B=%d)'
      % (obs, (cnt + 1) / (B + 1), B))
print('  (null = the arm label is exchangeable within each cell; this is the exact')
print('   marginal-homogeneity test for the paired 4x4 letter table)')

# the same, restricted to WRONG picks only
print('\n  restricted to cells where the arm was WRONG (does GIFT err toward a different letter?):')
gw = collections.Counter(r['gift_selected'] for r in rows if not r['gift_correct'])
ow = collections.Counter(r['or_selected'] for r in rows if not r['or_correct'])
print('    GIFT wrong picks:', {x: gw[x] for x in L}, ' n=%d' % sum(gw.values()))
print('    OR   wrong picks:', {x: ow[x] for x in L}, ' n=%d' % sum(ow.values()))
# offset relative to the key removes the key-position confound
go = collections.Counter(('abcd'.index(r['gift_selected']) - 'abcd'.index(r['correct_letter'])) % 4
                         for r in rows if not r['gift_correct'])
oo = collections.Counter(('abcd'.index(r['or_selected']) - 'abcd'.index(r['correct_letter'])) % 4
                         for r in rows if not r['or_correct'])
print('    GIFT wrong OFFSET from key:', {k: go[k] for k in (1, 2, 3)})
print('    OR   wrong OFFSET from key:', {k: oo[k] for k in (1, 2, 3)})
# chi2 homogeneity on the 2x3 offset table (independent samples approximation)
tot1, tot2 = sum(go[k] for k in (1, 2, 3)), sum(oo[k] for k in (1, 2, 3))
x2 = 0.0
for k in (1, 2, 3):
    col = go[k] + oo[k]
    for obs_, tot in ((go[k], tot1), (oo[k], tot2)):
        e = col * tot / (tot1 + tot2)
        if e > 0:
            x2 += (obs_ - e) ** 2 / e
print('    chi2(2) on the 2x3 offset table = %.3f  p = %.4f' % (x2, math.exp(-x2 / 2)))
print('    (independence approximation; the two error sets overlap in %d both-wrong cells,'
      % sum(1 for r in rows if not r['gift_correct'] and not r['or_correct']))
print('     so the true p is larger -- treat this only as "no visible difference")')

"""Step 3: are GIFT and OpenRouter errors correlated? Do they land on the same
distractor? Agreement vs a chance baseline; permutation test of the independence
null with the item/cluster dependence preserved."""
import sys, os, json, collections, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_lib import *

rows = load()
N = len(rows)
a = sum(1 for r in rows if r['gift_correct'] and r['or_correct'])
b = sum(1 for r in rows if r['gift_correct'] and not r['or_correct'])
c = sum(1 for r in rows if not r['gift_correct'] and r['or_correct'])
d = sum(1 for r in rows if not r['gift_correct'] and not r['or_correct'])
print('2x2 on correctness  a(both right)=%d b(GIFT only)=%d c(OR only)=%d d(both wrong)=%d  N=%d' % (a, b, c, d, N))

pg = (a + b) / N
po = (a + c) / N
print('marginals: GIFT acc %.4f  OR acc %.4f' % (pg, po))

# --- 1. Correctness agreement vs chance ---
obs_agree = (a + d) / N
exp_agree = pg * po + (1 - pg) * (1 - po)
kappa = (obs_agree - exp_agree) / (1 - exp_agree)
print('\n[A] CORRECTNESS AGREEMENT')
print('  observed agreement (a+d)/N      = %.4f  (%d/%d)' % (obs_agree, a + d, N))
print('  chance agreement from marginals = %.4f' % exp_agree)
print('  Cohen kappa                     = %.4f' % kappa)

# phi / odds ratio on the 2x2
phi = (a * d - b * c) / math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
orat = (a * d) / (b * c) if b * c else float('inf')
print('  phi (tetrachoric-free corr)     = %.4f' % phi)
print('  odds ratio                      = %.1f' % orat)
print('  Fisher exact p (independence)   = %.3e' % fisher_exact_2x2(a, b, c, d))

# error-conditional statements
print('  P(GIFT wrong)                   = %.4f' % ((c + d) / N))
print('  P(GIFT wrong | OR wrong)        = %.4f  (%d/%d)' % (d / (b + d), d, b + d))
print('  P(OR wrong)                     = %.4f' % ((b + d) / N))
print('  P(OR wrong | GIFT wrong)        = %.4f  (%d/%d)' % (d / (c + d), d, c + d))
print('  lift on error co-occurrence     = %.2fx' % ((d / (b + d)) / ((c + d) / N)))

# --- 2. permutation test of independence that respects clustering ---
# Null: GIFT's correctness vector is exchangeable with respect to OR's *within model*,
# permuting whole clusters so within-cluster dependence is preserved.
def perm_p(rows, B=20000, seed=99):
    rng = random.Random(seed)
    by_model = collections.defaultdict(list)
    for r in rows:
        by_model[r['model']].append(r)
    obs = 0
    for m, rs in by_model.items():
        obs += sum(1 for r in rs if r['gift_correct'] == r['or_correct'])
    cnt = 0
    for _ in range(B):
        tot = 0
        for m, rs in by_model.items():
            clusters = collections.defaultdict(list)
            for r in rs:
                clusters[r['cluster']].append(r)
            keys = list(clusters.keys())
            gift_blocks = [[x['gift_correct'] for x in clusters[k]] for k in keys]
            rng.shuffle(gift_blocks)
            for k, blk in zip(keys, gift_blocks):
                ors = [x['or_correct'] for x in clusters[k]]
                for i in range(min(len(blk), len(ors))):
                    if blk[i] == ors[i]:
                        tot += 1
        if tot >= obs:
            cnt += 1
    return obs, (cnt + 1) / (B + 1)

obs_ag, p_perm = perm_p(rows)
print('  cluster-permutation p (agreement >= observed, B=20000, whole GIFT clusters')
print('    reshuffled against OR within model): p = %.5f   observed agreements = %d' % (p_perm, obs_ag))

# --- 3. item-level: do the two arms fail on the SAME items? ---
print('\n[B] ITEM-LEVEL ERROR CORRELATION (4 models per item)')
items = collections.defaultdict(list)
for r in rows:
    items[r['question_id']].append(r)
ge = {q: sum(1 - x['gift_correct'] for x in v) for q, v in items.items()}
oe = {q: sum(1 - x['or_correct'] for x in v) for q, v in items.items()}
qs = sorted(items)
xs = [ge[q] for q in qs]
ys = [oe[q] for q in qs]
mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
r_p = num / den
print('  Pearson r of per-item error counts (n=%d items, 0-4 each) = %.4f' % (len(qs), r_p))
# permutation on items
rng = random.Random(5)
cnt = 0
B = 200000
yy = ys[:]
for _ in range(B):
    rng.shuffle(yy)
    n2 = sum((x - mx) * (y - my) for x, y in zip(xs, yy))
    if abs(n2 / den) >= abs(r_p) - 1e-12:
        cnt += 1
print('  permutation p (item labels shuffled, B=%d) = %.5f' % (B, (cnt + 1) / (B + 1)))
n_gift_err_items = sum(1 for q in qs if ge[q] > 0)
n_or_err_items = sum(1 for q in qs if oe[q] > 0)
n_both = sum(1 for q in qs if ge[q] > 0 and oe[q] > 0)
print('  items with >=1 GIFT error %d ; >=1 OR error %d ; both %d ; expected-if-independent %.1f'
      % (n_gift_err_items, n_or_err_items, n_both, n_gift_err_items * n_or_err_items / len(qs)))
print('  Fisher exact p on item-level error co-occurrence = %.3e'
      % fisher_exact_2x2(n_both, n_gift_err_items - n_both, n_or_err_items - n_both,
                         len(qs) - n_gift_err_items - n_or_err_items + n_both))

# --- 4. SELECTED-LETTER agreement (the sharper question) ---
print('\n[C] SELECTED-LETTER AGREEMENT')
sel = [r for r in rows if r['gift_selected'] and r['or_selected']]
print('  cells with both letters recorded: %d/%d' % (len(sel), N))
same = sum(1 for r in sel if r['gift_selected'] == r['or_selected'])
print('  identical letter chosen: %d/%d = %.4f' % (same, len(sel), same / len(sel)))

bothwrong = [r for r in sel if not r['gift_correct'] and not r['or_correct']]
sw = sum(1 for r in bothwrong if r['gift_selected'] == r['or_selected'])
print('  among BOTH-WRONG cells (n=%d): same distractor %d = %.3f' % (len(bothwrong), sw, sw / len(bothwrong)))
# chance baseline for same distractor: if each picks uniformly among the 3 wrong letters
print('    chance if uniform over the 3 wrong options = 0.333')
# empirical chance: shuffle GIFT wrong letters across the both-wrong cells (respecting that
# the correct letter is excluded per item)
rng = random.Random(11)
B = 200000
cnt = 0
gsel = [r['gift_selected'] for r in bothwrong]
osel = [r['or_selected'] for r in bothwrong]
corr = [r['correct_letter'] for r in bothwrong]
for _ in range(B):
    tot = 0
    for i in range(len(bothwrong)):
        # draw GIFT's wrong letter uniformly from the letters != correct
        opts = [x for x in 'abcd' if x != corr[i]]
        if rng.choice(opts) == osel[i]:
            tot += 1
    if tot >= sw:
        cnt += 1
print('    Monte-Carlo p vs uniform-wrong-letter null (B=%d): p = %.5f' % (B, (cnt + 1) / (B + 1)))
binom_p = sum(math.comb(len(bothwrong), k) * (1 / 3) ** k * (2 / 3) ** (len(bothwrong) - k)
              for k in range(sw, len(bothwrong) + 1))
print('    exact binomial one-sided p (p0=1/3): %.3e' % binom_p)

# --- 5. where does GIFT go when it is wrong and OR is right? ---
print('\n[D] DESTINATION OF THE 24 HARM ERRORS')
harm = [r for r in rows if not r['gift_correct'] and r['or_correct']]
pos = collections.Counter()
for r in harm:
    ci_ = 'abcd'.index(r['correct_letter'])
    si = 'abcd'.index(r['gift_selected']) if r['gift_selected'] in 'abcd' else None
    pos[r['gift_selected']] += 1
print('  GIFT selected letters on harm cells:', dict(sorted(pos.items())))
print('  correct letters on harm cells:', dict(sorted(collections.Counter(r['correct_letter'] for r in harm).items())))
off = collections.Counter(('abcd'.index(r['gift_selected']) - 'abcd'.index(r['correct_letter'])) % 4
                          for r in harm if r['gift_selected'] in 'abcd')
print('  offset (selected-correct) mod 4 on harm cells:', dict(sorted(off.items())))
# same for the 46 help cells: where does OR go when GIFT is right
help_ = [r for r in rows if r['gift_correct'] and not r['or_correct']]
off2 = collections.Counter(('abcd'.index(r['or_selected']) - 'abcd'.index(r['correct_letter'])) % 4
                           for r in help_ if r['or_selected'] in 'abcd')
print('  offset for the 46 help cells (OR wrong):', dict(sorted(off2.items())))
# and for both-wrong
off3 = collections.Counter(('abcd'.index(r['gift_selected']) - 'abcd'.index(r['correct_letter'])) % 4
                           for r in bothwrong if r['gift_selected'] in 'abcd')
print('  offset for both-wrong GIFT:', dict(sorted(off3.items())))
print('  letter distribution of GIFT wrong picks (all %d GIFT errors):' % (c + d),
      dict(sorted(collections.Counter(r['gift_selected'] for r in rows if not r['gift_correct']).items())))
print('  letter distribution of OR   wrong picks (all %d OR errors):' % (b + d),
      dict(sorted(collections.Counter(r['or_selected'] for r in rows if not r['or_correct']).items())))

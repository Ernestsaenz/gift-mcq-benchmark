"""Step 2: is there a feature signature to the 24 retrieval-harm cells?
Every comparison is harm-cells vs. the 1244-cell base, plus a like-for-like test
restricted to the 70 discordant cells (harm vs help) which conditions away item
difficulty in the same way McNemar does."""
import sys, os, json, collections, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_lib import *

rows = load()
harm = [r for r in rows if r['gift_correct'] == 0 and r['or_correct'] == 1]
help_ = [r for r in rows if r['gift_correct'] == 1 and r['or_correct'] == 0]
disc = harm + help_


def rate(rs, f):
    n = len(rs)
    k = sum(1 for r in rs if f(r))
    return k, n, (k / n if n else float('nan'))


FEATS = [
    ('negated_stem', lambda r: bool(r['negated_stem'])),
    ('has_context', lambda r: bool(r['has_context'])),
    ('qlen>=median(all)', None),
    ('qlen top quartile', None),
]

med_q = sorted(r['qlen'] for r in rows)[len(rows) // 2]
q75 = pctile(sorted(r['qlen'] for r in rows), 0.75)
FEATS[2] = ('qlen>=%d (median)' % med_q, lambda r: r['qlen'] >= med_q)
FEATS[3] = ('qlen>=%d (p75)' % int(q75), lambda r: r['qlen'] >= q75)

print('=== Feature prevalence: harm cells vs all cells vs help cells ===')
print('%-24s %14s %14s %14s   %10s %10s' % ('feature', 'harm(n=24)', 'all(n=1244)', 'help(n=46)',
                                            'p_vs_all', 'p_harm_help'))
for name, f in FEATS:
    kh, nh, ph = rate(harm, f)
    ka, na, pa = rate(rows, f)
    kl, nl, pl = rate(help_, f)
    # Fisher: harm vs the rest of the 1244
    p1 = fisher_exact_2x2(kh, nh - kh, ka - kh, (na - nh) - (ka - kh))
    p2 = fisher_exact_2x2(kh, nh - kh, kl, nl - kl)
    print('%-24s %6d/%3d %4.1f%% %6d/%4d %4.1f%% %6d/%3d %4.1f%%   %10.4f %10.4f'
          % (name, kh, nh, 100 * ph, ka, na, 100 * pa, kl, nl, 100 * pl, p1, p2))

print()
print('qlen: mean/median  harm %.0f/%.0f   all %.0f/%.0f   help %.0f/%.0f'
      % (sum(r['qlen'] for r in harm) / len(harm), sorted(r['qlen'] for r in harm)[len(harm) // 2],
         sum(r['qlen'] for r in rows) / len(rows), med_q,
         sum(r['qlen'] for r in help_) / len(help_), sorted(r['qlen'] for r in help_)[len(help_) // 2]))

# permutation test on mean qlen, harm vs help, labels shuffled within discordant set
import random
rng = random.Random(7)
obs = sum(r['qlen'] for r in harm) / len(harm) - sum(r['qlen'] for r in help_) / len(help_)
vals = [r['qlen'] for r in disc]
nh = len(harm)
cnt = 0
B = 200000
for _ in range(B):
    rng.shuffle(vals)
    d = sum(vals[:nh]) / nh - sum(vals[nh:]) / (len(vals) - nh)
    if abs(d) >= abs(obs) - 1e-9:
        cnt += 1
print('mean qlen harm-minus-help = %+.1f chars ; permutation p = %.4f (B=%d, labels shuffled within the 70 discordant cells)'
      % (obs, (cnt + 1) / (B + 1), B))

print()
print('=== By model ===')
print('%-22s %5s %5s %5s %8s' % ('model', 'harm', 'help', 'bothW', 'harm_rate_per_311'))
for m in sorted(set(r['model'] for r in rows)):
    h = sum(1 for r in harm if r['model'] == m)
    l = sum(1 for r in help_ if r['model'] == m)
    bw = sum(1 for r in rows if r['model'] == m and r['gift_correct'] == 0 and r['or_correct'] == 0)
    lo, hi = wilson(h, 311)
    print('%-22s %5d %5d %5d   %.2f%% [%.2f,%.2f]' % (m.split('/')[-1], h, l, bw,
                                                      100 * h / 311, 100 * lo, 100 * hi))

print()
print('=== By region ===')
reg_all = collections.Counter(r['region'] for r in rows)
reg_h = collections.Counter(r['region'] for r in harm)
reg_l = collections.Counter(r['region'] for r in help_)
print('%-22s %6s %6s %6s %9s' % ('region', 'cells', 'harm', 'help', 'harm_rate'))
for reg, n in reg_all.most_common():
    print('%-22s %6d %6d %6d %8.2f%%' % (reg, n, reg_h[reg], reg_l[reg], 100 * reg_h[reg] / n))

print()
print('=== By correct_letter (is GIFT losing on a particular key?) ===')
kl_all = collections.Counter(r['correct_letter'] for r in rows)
kl_h = collections.Counter(r['correct_letter'] for r in harm)
kl_l = collections.Counter(r['correct_letter'] for r in help_)
for k in 'abcd':
    print('  key %s: cells %4d  harm %2d (%.2f%%)  help %2d' % (k, kl_all[k], kl_h[k],
                                                                100 * kl_h[k] / kl_all[k] if kl_all[k] else 0, kl_l[k]))

print()
print('=== By year / exam_part ===')
for field in ('year', 'exam_part'):
    ca = collections.Counter(r[field] for r in rows)
    ch = collections.Counter(r[field] for r in harm)
    print(' ', field)
    for k, n in sorted(ca.items(), key=lambda kv: str(kv[0])):
        print('    %-12s cells %4d harm %2d  %.2f%%' % (str(k), n, ch[k], 100 * ch[k] / n))

print()
print('=== Clustering of harm cells across items ===')
c = collections.Counter(r['question_id'] for r in harm)
print(' items hit by >1 model:', {k: v for k, v in c.items() if v > 1})
cc = collections.Counter(r['cluster'] for r in harm)
print(' clusters hit by >1 harm cell:', {k: v for k, v in cc.items() if v > 1})
print(' distinct clusters among harm cells: %d' % len(cc))

print()
print('=== Latency / tokens on harm cells vs all ===')
for f in ('gift_latency_ms', 'or_latency_ms', 'gift_tokens', 'or_tokens'):
    ah = [r[f] for r in harm if r[f] is not None]
    aa = [r[f] for r in rows if r[f] is not None]
    print('  %-16s harm mean %9.0f median %8.0f | all mean %9.0f median %8.0f'
          % (f, sum(ah) / len(ah), sorted(ah)[len(ah) // 2], sum(aa) / len(aa), sorted(aa)[len(aa) // 2]))

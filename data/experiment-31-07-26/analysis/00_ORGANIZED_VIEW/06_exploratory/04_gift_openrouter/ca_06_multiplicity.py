"""Step 6: the named-source signal survives multiplicity? and is it a HARM signal or just
a DIFFICULTY signal? Plus the law-item exclusion audit."""
import sys, os, json, sqlite3, collections, re, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_lib import *

rows = load()
con = sqlite3.connect('file:%s?mode=ro&immutable=1' % DB, uri=True)
dsid = dict(con.execute('select name,id from datasets'))['balanced_a_310726']
Q = {r[0]: r[1:] for r in con.execute(
    'select question_id,question_text,option_a,option_b,option_c,option_d,correct_letter,question_number,id '
    'from questions where dataset_id=?', (dsid,))}

SOC = re.compile(r'\b(ESGE|ECCO|AASLD|EASL|ACG|AGA|ASGE|OMS|WHO|NICE|SEPD|GETECCU|GETAID|'
                 r'ESPEN|ESMO|NCCN|Rutgeerts|Praga|BISAP|Ranson|APACHE|Child|MELD|Maddrey|'
                 r'Baveno|Rockall|Blatchford|Milan|Barcelona|BCLC|Vienna|Montreal|Roma\s*IV|'
                 r'Los\s*Angeles|Forrest|Mayo|Harvey|Bristol)\b', re.I)
LEY = re.compile(r'\b(ley|art[ií]culo|real\s+decreto|estatuto|constituci[oó]n|BOE|'
                 r'normativa|reglamento|derechos\s+y\s+obligaciones)\b', re.I)
named = {q for q in Q if SOC.search(' '.join(x or '' for x in Q[q][:5]))}
law = {q for q in Q if LEY.search(' '.join(x or '' for x in Q[q][:5]))}


def tab(rs):
    a = sum(1 for r in rs if r['gift_correct'] and r['or_correct'])
    b = sum(1 for r in rs if r['gift_correct'] and not r['or_correct'])
    c = sum(1 for r in rs if not r['gift_correct'] and r['or_correct'])
    d = sum(1 for r in rs if not r['gift_correct'] and not r['or_correct'])
    return a, b, c, d


print('=== named-source items: is it harm, or just difficulty? ===')
for lab, rs in [('named-source', [r for r in rows if r['question_id'] in named]),
                ('other', [r for r in rows if r['question_id'] not in named])]:
    a, b, c, d = tab(rs)
    n = len(rs)
    print('  %-14s n=%4d  GIFT acc %.3f  OR acc %.3f   b(GIFTonly)=%2d c(HARM)=%2d  '
          'McNemar exact p=%.4f  diff=%+.2fpp'
          % (lab, n, (a + b) / n, (a + c) / n, b, c, mcnemar_exact(b, c), 100 * (b - c) / n))
print('  -> if the harm rate rises on named-source items only because BOTH arms err more,')
print('     the b:c ratio would be unchanged. Compare the two rows above.')

# ---- max-statistic permutation across the whole feature family (FWER control) ----
print('\n=== FWER over the 10-feature family, max-|z| permutation (B=20000) ===')
FEATS = {
    'named_source': lambda r: r['question_id'] in named,
    'law': lambda r: r['question_id'] in law,
    'negated_stem': lambda r: bool(r['negated_stem']),
    'has_context': lambda r: bool(r['has_context']),
    'qlen_ge_median': None,
    'qlen_ge_p75': None,
    'key_is_a': lambda r: r['correct_letter'] == 'a',
    'key_is_c': lambda r: r['correct_letter'] == 'c',
    'year_ge_2021': lambda r: r['year'] >= 2021,
    'illes_balears': lambda r: r['region'] == 'Illes Balears',
}
med_q = sorted(r['qlen'] for r in rows)[len(rows) // 2]
q75 = pctile(sorted(r['qlen'] for r in rows), 0.75)
FEATS['qlen_ge_median'] = lambda r: r['qlen'] >= med_q
FEATS['qlen_ge_p75'] = lambda r: r['qlen'] >= q75

harm_flag = [1 if (not r['gift_correct'] and r['or_correct']) else 0 for r in rows]


def zstat(flags, hf):
    n1 = sum(flags)
    n0 = len(flags) - n1
    if n1 == 0 or n0 == 0:
        return 0.0
    h1 = sum(h for f, h in zip(flags, hf) if f)
    h0 = sum(hf) - h1
    p1, p0 = h1 / n1, h0 / n0
    p = sum(hf) / len(hf)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n0))
    return 0.0 if se == 0 else (p1 - p0) / se


flagsets = {k: [1 if f(r) else 0 for r in rows] for k, f in FEATS.items()}
obs = {k: zstat(v, harm_flag) for k, v in flagsets.items()}
maxobs = max(abs(v) for v in obs.values())

# permute the harm labels by whole cluster (preserves item/cluster dependence)
rng = random.Random(2026)
clusters = collections.defaultdict(list)
for i, r in enumerate(rows):
    clusters[r['cluster']].append(i)
ckeys = list(clusters.keys())
B = 20000
maxnull = []
per_feat_ge = collections.Counter()
for _ in range(B):
    perm = list(ckeys)
    rng.shuffle(perm)
    hf = [0] * len(rows)
    for src, dst in zip(ckeys, perm):
        srcvals = [harm_flag[i] for i in clusters[src]]
        dsti = clusters[dst]
        for j in range(min(len(srcvals), len(dsti))):
            hf[dsti[j]] = srcvals[j]
    zs = {k: abs(zstat(v, hf)) for k, v in flagsets.items()}
    mx = max(zs.values())
    maxnull.append(mx)
    for k in FEATS:
        if mx >= abs(obs[k]) - 1e-9:
            per_feat_ge[k] += 1
maxnull.sort()
print('%-18s %8s %14s %14s' % ('feature', 'z', 'p_unadj', 'p_FWER(maxT)'))
for k in sorted(FEATS, key=lambda x: -abs(obs[x])):
    p_un = 2 * norm_sf(abs(obs[k]))
    p_fw = (per_feat_ge[k] + 1) / (B + 1)
    print('%-18s %8.2f %14.4f %14.4f' % (k, obs[k], p_un, p_fw))
print('  (cluster-permutation of the harm label; family of %d features; maxT step-down not applied)'
      % len(FEATS))

print('\n=== LAW-item audit vs RUN_STATUS ("11 administrative-law questions dropped") ===')
allrows = load(include_only=False)
law_in = sorted([q for q in set(r['question_id'] for r in rows) if q in law], key=lambda s: int(s[1:]))
print('  law-regex items still analysis_include=true: %d -> %s' % (len(law_in), law_in))
for q in law_in:
    print('    %-6s %s' % (q, (Q[q][0] or '')[:150].replace('\n', ' ')))
lrows = [r for r in rows if r['question_id'] in law]
a, b, c, d = tab(lrows)
print('  those items: %d cells, GIFT acc %.3f OR acc %.3f, b=%d c=%d' % (len(lrows), (a + b) / len(lrows),
                                                                        (a + c) / len(lrows), b, c))

print('\n=== SENSITIVITY: drop the law items and recompute the pooled contrast ===')
keep = [r for r in rows if r['question_id'] not in law]
a, b, c, d = tab(keep)
n = len(keep)
print('  n=%d  GIFT %.4f  OR %.4f  diff %+.2fpp  b=%d c=%d  McNemar exact p=%.4f'
      % (n, (a + b) / n, (a + c) / n, 100 * (b - c) / n, b, c, mcnemar_exact(b, c)))

print('\n=== Paired effort ratio: does GIFT burn tokens relative to OR on harm cells? ===')
print('%-22s %22s %22s %9s' % ('model', 'median gift/or harm', 'median gift/or other', 'perm_p'))
rng = random.Random(17)
for m in sorted(set(r['model'] for r in rows)):
    rs = [r for r in rows if r['model'] == m and r['or_tokens']]
    h = [r['gift_tokens'] / r['or_tokens'] for r in rs if not r['gift_correct'] and r['or_correct']]
    o = [r['gift_tokens'] / r['or_tokens'] for r in rs if not (not r['gift_correct'] and r['or_correct'])]
    if not h:
        print('%-22s   (no harm cells)' % m.split('/')[-1]); continue
    mh = sorted(h)[len(h) // 2]
    mo = sorted(o)[len(o) // 2]
    pool = h + o
    k = len(h)
    B2 = 50000
    cnt = 0
    obsd = mh - mo
    for _ in range(B2):
        rng.shuffle(pool)
        s1 = sorted(pool[:k]); s2 = sorted(pool[k:])
        dd = s1[len(s1) // 2] - s2[len(s2) // 2]
        if abs(dd) >= abs(obsd) - 1e-12:
            cnt += 1
    print('%-22s %22.3f %22.3f %9.4f' % (m.split('/')[-1], mh, mo, (cnt + 1) / (B2 + 1)))

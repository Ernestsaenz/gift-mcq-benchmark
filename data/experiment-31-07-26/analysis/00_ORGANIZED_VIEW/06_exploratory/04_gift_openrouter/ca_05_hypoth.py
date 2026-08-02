"""Step 5: turn what the harm texts look like into a pre-specified classifier applied to
ALL 311 items, so the 'guideline lookup' impression can be tested rather than asserted."""
import sys, os, json, sqlite3, collections, re, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_lib import *

rows = load()
con = sqlite3.connect('file:%s?mode=ro&immutable=1' % DB, uri=True)
dsid = dict(con.execute('select name,id from datasets'))['balanced_a_310726']
Q = {}
for r in con.execute('select question_id,question_text,option_a,option_b,option_c,option_d,'
                     'correct_letter,question_number from questions where dataset_id=?', (dsid,)):
    Q[r[0]] = {'stem': r[1], 'a': r[2], 'b': r[3], 'c': r[4], 'd': r[5],
               'key': r[6], 'qnum': r[7]}
print('questions in dataset A: %d ; in analysis set: %d'
      % (len(Q), len(set(r['question_id'] for r in rows))))

# ---- classifiers, applied blind to every item ----
SOC = re.compile(r'\b(ESGE|ECCO|AASLD|EASL|ACG|AGA|ASGE|OMS|WHO|NICE|SEPD|GETECCU|GETAID|'
                 r'ESPEN|ESMO|NCCN|Rutgeerts|Praga|BISAP|Ranson|APACHE|Child|MELD|Maddrey|'
                 r'Baveno|Rockall|Blatchford|Milan|Barcelona|BCLC|Vienna|Montreal|Roma\s*IV|'
                 r'Los\s*Angeles|Forrest|Mayo|Harvey|Bristol)\b', re.I)
GUIA = re.compile(r'\b(gu[ií]a|gu[ií]as|guideline|consenso|recomendaci[oó]n|recomendaciones|'
                  r'recomienda|seg[uú]n\s+(la|las|el|los|lo)|protocolo|documento\s+de\s+posicionamiento)\b', re.I)
NUMTHRESH = re.compile(r'(\d+\s*(mm|cm|mg|g/|ml|meses|a[nñ]os|semanas|d[ií]as|horas|%|puntos)|'
                       r'\b[<>≤≥]\s*\d)', re.I)
LEY = re.compile(r'\b(ley|art[ií]culo|real\s+decreto|estatuto|constituci[oó]n|BOE|'
                 r'normativa|reglamento|derechos\s+y\s+obligaciones)\b', re.I)
YEARCITE = re.compile(r'\b(19|20)\d{2}\b')


def feats(qid):
    d = Q[qid]
    full = ' '.join([d['stem'], d['a'], d['b'], d['c'], d['d']])
    return {
        'named_source': bool(SOC.search(full)),
        'guideline_lang': bool(GUIA.search(full)),
        'num_threshold': bool(NUMTHRESH.search(full)),
        'law': bool(LEY.search(full)),
        'year_cited': bool(YEARCITE.search(d['stem'])),
        'guideline_lookup': bool(SOC.search(full)) or bool(GUIA.search(full)),
    }


F = {q: feats(q) for q in set(r['question_id'] for r in rows)}
harm = [r for r in rows if not r['gift_correct'] and r['or_correct']]
help_ = [r for r in rows if r['gift_correct'] and not r['or_correct']]

print('\n=== Blind classifier applied to all %d cells; harm rate by feature ===' % len(rows))
print('%-18s %18s %18s   %9s %8s   %10s' % ('feature', 'harm/cells (=1)', 'harm/cells (=0)',
                                            'RR', 'p_fisher', 'p_harmVhelp'))
for name in ['named_source', 'guideline_lang', 'guideline_lookup', 'num_threshold', 'law', 'year_cited']:
    n1 = [r for r in rows if F[r['question_id']][name]]
    n0 = [r for r in rows if not F[r['question_id']][name]]
    h1 = sum(1 for r in n1 if not r['gift_correct'] and r['or_correct'])
    h0 = sum(1 for r in n0 if not r['gift_correct'] and r['or_correct'])
    p1 = h1 / len(n1) if n1 else float('nan')
    p0 = h0 / len(n0) if n0 else float('nan')
    rr = p1 / p0 if p0 else float('inf')
    pf = fisher_exact_2x2(h1, len(n1) - h1, h0, len(n0) - h0)
    # harm vs help conditional test within discordant cells
    hh1 = sum(1 for r in help_ if F[r['question_id']][name])
    ph = fisher_exact_2x2(h1, len(harm) - h1, hh1, len(help_) - hh1)
    print('%-18s %7d/%5d %5.2f%% %7d/%5d %5.2f%%   %9.2f %8.4f   %10.4f'
          % (name, h1, len(n1), 100 * p1, h0, len(n0), 100 * p0, rr, pf, ph))

print('\n  prevalence of guideline_lookup in the 311 items: %d (%.1f%%)'
      % (sum(1 for q in F if F[q]['guideline_lookup']),
         100 * sum(1 for q in F if F[q]['guideline_lookup']) / len(F)))
print('  LAW items still inside the analysis set:',
      sorted([q for q in F if F[q]['law']], key=lambda s: int(s[1:])))

# ---- native "ninguna de las anteriores" option present in condition A ----
NOTA = re.compile(r'ninguna\s+de\s+(las|los)\s+(anteriores|respuestas)', re.I)
nota_items = {q for q in F if any(NOTA.search(Q[q][L] or '') for L in 'abcd')}
print('\n  items with a NATIVE "ninguna de las anteriores" option: %d' % len(nota_items))
nrows = [r for r in rows if r['question_id'] in nota_items]
hn = sum(1 for r in nrows if not r['gift_correct'] and r['or_correct'])
orows = [r for r in rows if r['question_id'] not in nota_items]
ho = sum(1 for r in orows if not r['gift_correct'] and r['or_correct'])
print('  harm rate with native-NOTA %d/%d=%.2f%% vs without %d/%d=%.2f%% (Fisher p=%.4f)'
      % (hn, len(nrows), 100 * hn / len(nrows), ho, len(orows), 100 * ho / len(orows),
         fisher_exact_2x2(hn, len(nrows) - hn, ho, len(orows) - ho)))
# did GIFT flee INTO the NOTA option more than OR?
gn = sum(1 for r in nrows if NOTA.search(Q[r['question_id']][r['gift_selected']] or ''))
on = sum(1 for r in nrows if NOTA.search(Q[r['question_id']][r['or_selected']] or ''))
print('  on those items GIFT chose the NOTA option %d/%d times, OR chose it %d/%d'
      % (gn, len(nrows), on, len(nrows)))

# ---- within-model effort: are harm cells the ones GIFT worked hardest on? ----
print('\n=== Within-model effort on harm cells (removes the model confound) ===')
print('%-22s %28s %28s %10s' % ('model', 'gift_tokens harm (n)', 'gift_tokens non-harm (n)', 'perm_p'))
rng = random.Random(3)
for m in sorted(set(r['model'] for r in rows)):
    rs = [r for r in rows if r['model'] == m]
    h = [r['gift_tokens'] for r in rs if not r['gift_correct'] and r['or_correct']]
    nh = [r['gift_tokens'] for r in rs if not (not r['gift_correct'] and r['or_correct'])]
    if not h:
        print('%-22s   (no harm cells)' % m.split('/')[-1]); continue
    obs = sum(h) / len(h) - sum(nh) / len(nh)
    pool = h + nh
    k = len(h)
    B = 50000
    cnt = 0
    for _ in range(B):
        rng.shuffle(pool)
        d = sum(pool[:k]) / k - sum(pool[k:]) / (len(pool) - k)
        if abs(d) >= abs(obs) - 1e-9:
            cnt += 1
    print('%-22s %20.0f (%2d) %24.0f (%3d) %10.4f'
          % (m.split('/')[-1], sum(h) / len(h), len(h), sum(nh) / len(nh), len(nh), (cnt + 1) / (B + 1)))

# ---- is GIFT's harm error the crowd-favourite distractor or an idiosyncratic one? ----
print('\n=== On the 24 harm cells, how popular is the letter GIFT picked? ===')
byq = collections.defaultdict(list)
for r in rows:
    byq[r['question_id']].append(r)
pop_or, pop_gift = [], []
for r in harm:
    peers = [x for x in byq[r['question_id']] if x['model'] != r['model']]
    pop_or.append(sum(1 for x in peers if x['or_selected'] == r['gift_selected']))
    pop_gift.append(sum(1 for x in peers if x['gift_selected'] == r['gift_selected']))
print('  # of the other 3 models whose OR answer equals GIFT\'s wrong pick: mean %.2f  dist %s'
      % (sum(pop_or) / len(pop_or), dict(sorted(collections.Counter(pop_or).items()))))
print('  # of the other 3 models whose GIFT answer equals GIFT\'s wrong pick: mean %.2f  dist %s'
      % (sum(pop_gift) / len(pop_gift), dict(sorted(collections.Counter(pop_gift).items()))))
print('  (0 for both would mean GIFT invented a private answer; >0 means it landed on a')
print('   distractor the un-retrieved models were already drawn to)')

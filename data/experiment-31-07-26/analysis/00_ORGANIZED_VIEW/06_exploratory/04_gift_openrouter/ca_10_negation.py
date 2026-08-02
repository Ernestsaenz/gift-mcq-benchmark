"""Step 10: reading the 24 harm stems suggested a lot of 'senale la INCORRECTA/FALSA/excepto'
items. The supplied negated_stem flag only marks 5 of 24. Rebuild the flag from the raw
stem text, cross-check it against the supplied one, and re-test."""
import sys, os, json, sqlite3, collections, re, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_lib import *

rows = load()
con = sqlite3.connect('file:%s?mode=ro&immutable=1' % DB, uri=True)
dsid = dict(con.execute('select name,id from datasets'))['balanced_a_310726']
STEM = {r[0]: r[1] for r in con.execute(
    'select question_id,question_text from questions where dataset_id=?', (dsid,))}

NEG = re.compile(
    r'(incorrect[ao]|\bfalsas?\b|\bfalso\b|no\s+es\s+(correct|ciert|verdader)|'
    r'\bexcepto\b|\bsalvo\b|no\s+est[aá]\s+(recomendad|indicad)|'
    r'\bNO\s+(es|est[aá]|se\s+(recomienda|debe|considera|incluye)|debe|deber|resulta|'
    r'corresponde|forma|figura|constituye|suele)\b|'
    r'cu[aá]l\s+(de\s+(las|los)\s+siguientes\s+)?NO\b|'
    r'menos\s+(probable|frecuente|indicad|apropiad)|'
    r'no\s+(es\s+)?propi[ao]|es\s+err[oó]ne|se[nñ]ale\s+la\s+(falsa|incorrecta))', re.I)

# The operative question is the tail of the stem, after the clinical vignette.
# Take the last sentence that ends in '?' or ':' (or the final line) so that ordinary
# vignette prose like "No se observan lesiones" cannot fire the negation detector.
def operative(q):
    t = (STEM[q] or '').strip()
    parts = [s for s in re.split(r'(?<=[?:])\s+|\n', t) if s.strip()]
    tail = parts[-1] if parts else t
    # if the last fragment is very short (e.g. an orphan line), take the last two
    if len(tail) < 25 and len(parts) >= 2:
        tail = parts[-2] + ' ' + tail
    return tail


def neg(q):
    return bool(NEG.search(operative(q)))


auto = {}
p = os.path.join(BASE, 'mech_auto_negated.json')
if os.path.exists(p):
    auto = json.load(open(p))

qids = sorted(set(r['question_id'] for r in rows), key=lambda s: int(s[1:]))
supplied = {r['question_id']: bool(r['negated_stem']) for r in rows}
mine = {q: neg(q) for q in qids}
print('=== negation-flag cross-check on the %d analysed items ===' % len(qids))
agree = sum(1 for q in qids if supplied[q] == mine[q])
print('  supplied negated_stem TRUE: %d ; my regex TRUE: %d ; agree on %d/%d (%.1f%%)'
      % (sum(supplied.values()), sum(mine.values()), agree, len(qids), 100 * agree / len(qids)))
only_mine = [q for q in qids if mine[q] and not supplied[q]]
only_sup = [q for q in qids if supplied[q] and not mine[q]]
print('  flagged by me only (%d): %s' % (len(only_mine), only_mine[:25]))
print('  flagged by supplied only (%d): %s' % (len(only_sup), only_sup[:25]))
if auto:
    ov = [q for q in qids if q in auto]
    ag2 = sum(1 for q in ov if bool(auto[q]) == mine[q])
    ag3 = sum(1 for q in ov if bool(auto[q]) == supplied[q])
    print('  overlap with mech_auto_negated.json: %d items; my regex agrees %d (%.1f%%), '
          'supplied agrees %d (%.1f%%)' % (len(ov), ag2, 100 * ag2 / len(ov), ag3, 100 * ag3 / len(ov)))

for q in only_mine[:12]:
    print('    +%-6s %s' % (q, (STEM[q] or '')[:110].replace('\n', ' ')))
print('  --- flagged by supplied but not by me:')
for q in only_sup[:12]:
    print('    -%-6s %s' % (q, (STEM[q] or '')[-160:].replace('\n', ' ')))


def tab(rs):
    return (sum(1 for r in rs if r['gift_correct'] and r['or_correct']),
            sum(1 for r in rs if r['gift_correct'] and not r['or_correct']),
            sum(1 for r in rs if not r['gift_correct'] and r['or_correct']),
            sum(1 for r in rs if not r['gift_correct'] and not r['or_correct']))


print('\n=== harm rate by negation flag (three definitions) ===')
print('%-22s %6s %26s %26s %10s' % ('flag', '', 'NEGATED', 'NOT negated', 'p_fisher'))
defs = [('supplied negated_stem', lambda r: bool(r['negated_stem'])),
        ('my regex', lambda r: mine[r['question_id']])]
if auto:
    defs.append(('mech_auto_negated', lambda r: bool(auto.get(r['question_id'], False))))
for name, f in defs:
    n1 = [r for r in rows if f(r)]
    n0 = [r for r in rows if not f(r)]
    a1, b1, c1, d1 = tab(n1)
    a0, b0, c0, d0 = tab(n0)
    pf = fisher_exact_2x2(c1, len(n1) - c1, c0, len(n0) - c0)
    print('%-22s %6s  harm %2d/%4d=%5.2f%% b=%2d  harm %2d/%4d=%5.2f%% b=%2d %10.4f'
          % (name, '', c1, len(n1), 100 * c1 / len(n1), b1, c0, len(n0), 100 * c0 / len(n0), b0, pf))
    print('%-22s %6s  GIFT-OR net %+.2fpp (n=%d)      GIFT-OR net %+.2fpp (n=%d)'
          % ('', '', 100 * (b1 - c1) / len(n1), len(n1), 100 * (b0 - c0) / len(n0), len(n0)))

print('\n=== which of the 24 harm cells sit on a negated stem, by my regex? ===')
harm = [r for r in rows if not r['gift_correct'] and r['or_correct']]
hn = [r for r in harm if mine[r['question_id']]]
print('  %d / %d = %.1f%%   (supplied flag said %d)' % (len(hn), len(harm), 100 * len(hn) / len(harm),
                                                        sum(1 for r in harm if r['negated_stem'])))
print('  negated harm items:', sorted(set(r['question_id'] for r in hn), key=lambda s: int(s[1:])))
help_ = [r for r in rows if r['gift_correct'] and not r['or_correct']]
hl = [r for r in help_ if mine[r['question_id']]]
print('  negated help cells: %d / %d = %.1f%%' % (len(hl), len(help_), 100 * len(hl) / len(help_)))
print('  harm-vs-help Fisher p = %.4f' % fisher_exact_2x2(len(hn), len(harm) - len(hn),
                                                          len(hl), len(help_) - len(hl)))
print('  base rate of negated stems across all cells: %.1f%%'
      % (100 * sum(1 for r in rows if mine[r['question_id']]) / len(rows)))

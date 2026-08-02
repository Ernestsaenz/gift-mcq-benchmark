#!/usr/bin/env python
"""ca_lat_05: how the 83%-prefix coverage bias moves the cost-effectiveness ratio,
and whether GIFT's failure rate degrades as the run gets longer."""
import json, math, random, sqlite3, datetime as dt
from collections import defaultdict

BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
DB = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite'
rows = [r for r in json.load(open(BASE + 'cross_arm_A.json')) if r['analysis_include']]
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)


def quant(xs, p):
    s = sorted(xs); n = len(s)
    if n == 1: return float(s[0])
    h = (n - 1) * p; lo = int(math.floor(h)); hi = min(lo + 1, n - 1)
    return s[lo] + (h - lo) * (s[hi] - s[lo])


# --- recovery / breakage rates conditional on the OpenRouter outcome ---
or_wrong = [r for r in rows if not r['or_correct']]
or_right = [r for r in rows if r['or_correct']]
rec = sum(r['gift_correct'] for r in or_wrong) / len(or_wrong)
brk = 1 - sum(r['gift_correct'] for r in or_right) / len(or_right)
print('=== CONDITIONAL BEHAVIOUR OF THE RETRIEVAL ARM (analysed 1244 cells) ===')
print('  cells OR got WRONG: %d -> GIFT recovered %d  (recovery rate %.1f%%)'
      % (len(or_wrong), sum(r['gift_correct'] for r in or_wrong), 100 * rec))
print('  cells OR got RIGHT: %d -> GIFT broke %d      (breakage rate %.1f%%)'
      % (len(or_right), sum(1 for r in or_right if not r['gift_correct']), 100 * brk))
print('  implied delta = p_wrong*recovery - p_right*breakage')

# cluster bootstrap on (recovery, breakage) and on the transported delta at OR accuracy 82.9%
byc = defaultdict(list)
for r in rows: byc[r['cluster']].append(r)
keys = list(byc); rng = random.Random(20260731)
OR_UNCOV = 0.829   # RUN_STATUS / recomputed: OpenRouter accuracy on the never-reached items
reps_obs, reps_tr = [], []
for _ in range(20000):
    s = []
    for _ in range(len(keys)): s.extend(byc[keys[rng.randrange(len(keys))]])
    w = [r for r in s if not r['or_correct']]; g = [r for r in s if r['or_correct']]
    if not w or not g: continue
    rc = sum(r['gift_correct'] for r in w) / len(w)
    bk = 1 - sum(r['gift_correct'] for r in g) / len(g)
    reps_obs.append(100 * (len(w) / len(s) * rc - len(g) / len(s) * bk))
    reps_tr.append(100 * ((1 - OR_UNCOV) * rc - OR_UNCOV * bk))
obs = 100 * (len(or_wrong) / len(rows) * rec - len(or_right) / len(rows) * brk)
tr = 100 * ((1 - OR_UNCOV) * rec - OR_UNCOV * brk)
print('  observed delta on the covered prefix : %+.2f pp  [%.2f, %.2f]  (cluster bootstrap, B=20000)'
      % (obs, quant(reps_obs, .025), quant(reps_obs, .975)))
print('  TRANSPORTED to the never-reached items (assumes the same recovery/breakage rates,')
print('  which is an ASSUMPTION, not a measurement): %+.2f pp  [%.2f, %.2f]'
      % (tr, quant(reps_tr, .025), quant(reps_tr, .975)))
print('  -> under that assumption the seconds-per-extra-correct would fall by a factor %.2f'
      % (obs / tr if tr else float('nan')))

# --- does the GIFT failure rate degrade with run length? ---
print('\n=== GIFT RELIABILITY OVER THE 8h45m RUN (all attempts, chronological octiles) ===')
att = list(c.execute('''select pa.created_at, pa.status_code from provider_attempts pa
                        join logical_calls lc on lc.id=pa.logical_call_id
                        join experiments e on e.id=lc.experiment_id
                        where e.name='expA_gift_310726' order by pa.created_at'''))
t0 = dt.datetime.fromisoformat(att[0][0])
nb = 8; per = len(att) // nb
print('%5s %7s %10s %12s' % ('bin', 'n', 'hrs_mid', 'fail_rate%'))
fr = []
for i in range(nb):
    seg = att[i * per:(i + 1) * per] if i < nb - 1 else att[i * per:]
    f = sum(1 for a in seg if a[1] != 200) / len(seg)
    fr.append(f)
    mid = (dt.datetime.fromisoformat(seg[len(seg) // 2][0]) - t0).total_seconds() / 3600
    print('%5d %7d %10.2f %12.1f' % (i + 1, len(seg), mid, 100 * f))
# permutation test for monotone trend: Spearman of (attempt order, is_fail)
X = list(range(len(att))); Y = [0 if a[1] == 200 else 1 for a in att]
n = len(X); mx = (n - 1) / 2.0; my = sum(Y) / n
den = math.sqrt(sum((x - mx) ** 2 for x in X) * sum((y - my) ** 2 for y in Y))
rho = sum((x - mx) * (y - my) for x, y in zip(X, Y)) / den
rng2 = random.Random(5); sh = list(Y); cnt = 0; NP = 10000
for _ in range(NP):
    rng2.shuffle(sh)
    if abs(sum((x - mx) * (y - my) for x, y in zip(X, sh)) / den) >= abs(rho): cnt += 1
print('trend in failure rate across the run: point-biserial/Spearman rho = %+.4f, '
      'permutation p = %.4g (10k shuffles, two-sided)' % (rho, (cnt + 1) / (NP + 1)))

json.dump(dict(recovery=rec, breakage=brk, delta_obs=obs, delta_obs_ci=[quant(reps_obs, .025), quant(reps_obs, .975)],
               delta_transported=tr, delta_tr_ci=[quant(reps_tr, .025), quant(reps_tr, .975)],
               fail_rate_bins=fr, fail_trend_rho=rho, fail_trend_p=(cnt + 1) / (NP + 1)),
          open(BASE + 'ca_lat_05_coverage_sens.json', 'w'), indent=1)

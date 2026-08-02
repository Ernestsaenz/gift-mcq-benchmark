#!/usr/bin/env python
"""Pull scored-attempt latency + timestamps for BOTH arms, all 474 items, from the DB.
Explicit experiment names (never LIKE 'expA%'); reach the scored attempt via
scores -> parsed_answers.provider_attempt_id -> provider_attempts.
Also pull the *non-scored* attempts (retries / api_failed) so GIFT's true wall-clock
cost per delivered answer can be compared with its scored-attempt latency.
"""
import json, sqlite3

DB = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite'
BASE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/'
con = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)

SCORED = """
SELECT e.name, lc.model, q.question_id, pa.latency_ms, pa.created_at,
       pa.total_tokens, pa.attempt_index, s.letter_correct
FROM scores s
JOIN parsed_answers p  ON p.id = s.parsed_answer_id
JOIN provider_attempts pa ON pa.id = p.provider_attempt_id
JOIN logical_calls lc  ON lc.id = s.logical_call_id
JOIN experiments e     ON e.id = lc.experiment_id
JOIN questions q       ON q.id = lc.question_id
WHERE e.name = ?
"""
ALL_ATT = """
SELECT e.name, lc.model, q.question_id, pa.latency_ms, pa.status_code,
       pa.error_type, pa.attempt_index, pa.created_at
FROM provider_attempts pa
JOIN logical_calls lc ON lc.id = pa.logical_call_id
JOIN experiments e    ON e.id = lc.experiment_id
JOIN questions q      ON q.id = lc.question_id
WHERE e.name = ?
"""

out = {'scored': {}, 'attempts': {}}
for exp in ('expA_or_310726', 'expA_gift_310726'):
    rs = [dict(zip(['exp','model','qid','latency_ms','created_at','tokens','attempt_index','correct'], r))
          for r in con.execute(SCORED, (exp,))]
    out['scored'][exp] = rs
    ra = [dict(zip(['exp','model','qid','latency_ms','status_code','error_type','attempt_index','created_at'], r))
          for r in con.execute(ALL_ATT, (exp,))]
    out['attempts'][exp] = ra
    print(exp, 'scored', len(rs), 'attempts', len(ra))

# question order in dataset
qorder = {}
for r in con.execute("""SELECT q.question_id, q.id FROM questions q
                        JOIN datasets d ON d.id=q.dataset_id
                        WHERE d.name='balanced_a_310726' ORDER BY q.id"""):
    qorder[r[0]] = len(qorder)
out['order'] = qorder
print('dataset items', len(qorder))
json.dump(out, open(BASE + 'ca_ref_lat_03_pull.json', 'w'))

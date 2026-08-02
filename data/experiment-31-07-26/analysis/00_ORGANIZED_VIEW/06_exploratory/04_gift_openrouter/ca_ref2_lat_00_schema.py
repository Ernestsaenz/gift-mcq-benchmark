#!/usr/bin/env python
"""ca_ref2_lat_00: what does gift_latency_ms actually measure? Schema + provenance."""
import sqlite3, json
DB = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite'
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)
for (n,) in c.execute("select name from sqlite_master where type='table' order by name"):
    cols = [r[1] for r in c.execute("pragma table_info(%s)" % n)]
    cnt = c.execute("select count(*) from %s" % n).fetchone()[0]
    print('== %-22s n=%-8d %s' % (n, cnt, cols))

print('\n-- experiments --')
for r in c.execute("select id,name,count(*) from experiments group by 1,2"):
    print(r)

print('\n-- one GIFT provider_attempt raw --')
row = c.execute("""select pa.* from provider_attempts pa join logical_calls lc on lc.id=pa.logical_call_id
                   join experiments e on e.id=lc.experiment_id where e.name='expA_gift_310726'
                   and pa.status_code=200 limit 1""").fetchone()
cols = [d[0] for d in c.execute("select * from provider_attempts limit 1").description]
for k, v in zip(cols, row):
    s = str(v)
    print('  %-24s %s' % (k, s[:400] + ('...' if len(s) > 400 else '')))

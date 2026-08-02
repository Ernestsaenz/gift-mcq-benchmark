#!/usr/bin/env python
"""ca_lat_00: wall-clock and reliability accounting for the two arms, from provider_attempts."""
import sqlite3, json, datetime as dt

DB = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite'
c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)


def ts(s):
    return dt.datetime.fromisoformat(s)


out = {}
for exp in ['expA_gift_310726', 'expA_or_310726', 'expB_or_310726']:
    rows = list(c.execute('''select pa.created_at, pa.status_code, pa.error_type, pa.latency_ms,
                                    lc.model, lc.id
                             from provider_attempts pa
                             join logical_calls lc on lc.id=pa.logical_call_id
                             join experiments e on e.id=lc.experiment_id
                             where e.name=? order by pa.created_at''', (exp,)))
    times = sorted(ts(r[0]) for r in rows)
    span = (times[-1] - times[0]).total_seconds()
    # gap structure: contiguous bursts separated by >5min idle
    bursts = []
    start = times[0]; prev = times[0]
    for t in times[1:]:
        if (t - prev).total_seconds() > 300:
            bursts.append((start, prev)); start = t
        prev = t
    bursts.append((start, prev))
    busy = sum((b - a).total_seconds() for a, b in bursts)
    n_ok = sum(1 for r in rows if r[1] == 200)
    n_fail = len(rows) - n_ok
    lat_sum = sum(r[3] for r in rows if r[3] is not None)
    calls = set(r[5] for r in rows)
    ok_calls = set(r[5] for r in rows if r[1] == 200)
    out[exp] = dict(
        n_attempts=len(rows), n_ok=n_ok, n_fail=n_fail,
        n_logical_calls=len(calls), n_calls_with_success=len(ok_calls),
        first=str(times[0]), last=str(times[-1]),
        span_s=span, busy_s=busy, n_bursts=len(bursts),
        bursts=[(str(a), str(b), (b - a).total_seconds()) for a, b in bursts],
        sum_latency_s=lat_sum / 1000.0,
    )
    print('==', exp)
    print('  attempts %d (ok %d, failed %d)  logical calls %d, with success %d'
          % (len(rows), n_ok, n_fail, len(calls), len(ok_calls)))
    print('  first %s  last %s  span %.0f s = %.2f h' % (times[0], times[-1], span, span / 3600))
    print('  busy (bursts sep by >5min idle): %.0f s = %.2f h in %d bursts' % (busy, busy / 3600, len(bursts)))
    for a, b in bursts:
        print('     burst %s -> %s  %.1f min' % (a, b, (b - a).total_seconds() / 60))
    print('  sum of per-attempt latency: %.0f s = %.2f h' % (lat_sum / 1000, lat_sum / 3.6e6))
    # error type breakdown
    et = {}
    for r in rows:
        if r[1] != 200:
            k = (r[1], r[2]); et[k] = et.get(k, 0) + 1
    if et:
        print('  failures:', et)

json.dump(out, open('/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/ca_lat_00_wallclock.json', 'w'), indent=1)

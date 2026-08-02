"""Independent recomputation of the leave-one-cluster-out jackknife claim.

Stdlib only. Method notes printed inline.
"""
import json, collections, random, math

P = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json'
D = json.load(open(P))


def pooled_delta(rows):
    n = len(rows)
    s = sum(r['B_correct'] - r['A_correct'] for r in rows)
    return 100.0 * s / n, s, n


def loo_cluster(rows, keyf=lambda r: r['cluster']):
    full, S, N = pooled_delta(rows)
    groups = collections.defaultdict(list)
    for r in rows:
        groups[keyf(r)].append(r)
    out = []
    for g, rr in groups.items():
        sg = sum(r['B_correct'] - r['A_correct'] for r in rr)
        ng = len(rr)
        dwo = 100.0 * (S - sg) / (N - ng)
        out.append((g, ng, dwo, dwo - full))
    out.sort(key=lambda t: abs(t[3]), reverse=True)
    return full, out


def report(label, rows, keyf=lambda r: r['cluster']):
    full, out = loo_cluster(rows, keyf)
    shifts = [t[3] for t in out]
    dwos = [t[2] for t in out]
    print(f'--- {label}: N={len(rows)} groups={len(out)}')
    print(f'    full delta      = {full:.4f} pp')
    print(f'    delta_wo range  = [{min(dwos):.4f}, {max(dwos):.4f}]  span={max(dwos)-min(dwos):.4f} pp')
    print(f'    max |shift|     = {max(abs(s) for s in shifts):.4f} pp')
    print(f'    |shift|>1.0 pp  : {sum(1 for s in shifts if abs(s) > 1.0)}')
    print(f'    |shift|>0.5 pp  : {sum(1 for s in shifts if abs(s) > 0.5)}')
    print(f'    sign flips      : {sum(1 for d in dwos if (d > 0) != (full > 0))}')
    print('    top 5 by |shift|:')
    for g, ng, dwo, sh in out[:5]:
        print(f'      group={g!r:>8} n={ng:>4} delta_wo={dwo:8.4f} shift={sh:+.4f}')
    return full, out


inc = [r for r in D if r['analysis_include']]
print('=' * 70)
print('PRIMARY: analysis_include==true, group = cluster, cells pooled over models')
report('analysis set / cluster', inc)

# ---- alternative leave-one-out units --------------------------------------
print()
print('=' * 70)
print('ALTERNATIVE LEAVE-ONE-OUT UNITS (same jackknife arithmetic)')
report('analysis set / ITEM (question_id)', inc, lambda r: r['question_id'])
report('analysis set / MODEL', inc, lambda r: r['model'])
report('analysis set / REGION', inc, lambda r: r['region'])
report('analysis set / REGION x YEAR', inc, lambda r: (r['region'], r['year']))
report('analysis set / EXAM (region,year,part)', inc,
       lambda r: (r['region'], r['year'], r['exam_part']))

# ---- exclusion-set sensitivity --------------------------------------------
print()
print('=' * 70)
print('LOO UNDER OTHER EXCLUSION SETS')
sets = {
    'unfiltered (all 1691)': [r for r in D],
    'defect-only excluded (nota_a kept)': [r for r in D if not r['excl_item_defect']],
    'nota_a-only excluded (defects kept)': [r for r in D if not r['excl_nota_position_a']],
}
for lab, rows in sets.items():
    report(lab + ' / cluster', rows)

# ---- cluster-level (unweighted) estimator ---------------------------------
print()
print('=' * 70)
print('ESTIMATOR SENSITIVITY: cluster-mean (each cluster weighted equally)')
groups = collections.defaultdict(list)
for r in inc:
    groups[r['cluster']].append(r)
cmeans = {g: 100.0 * sum(x['B_correct'] - x['A_correct'] for x in rr) / len(rr)
          for g, rr in groups.items()}
K = len(cmeans)
full_cm = sum(cmeans.values()) / K
print(f'    cluster-mean delta (unweighted) = {full_cm:.4f} pp  (K={K})')
shifts = []
for g in cmeans:
    dwo = (sum(cmeans.values()) - cmeans[g]) / (K - 1)
    shifts.append((g, len(groups[g]), dwo, dwo - full_cm))
shifts.sort(key=lambda t: abs(t[3]), reverse=True)
print(f'    max |shift| = {max(abs(t[3]) for t in shifts):.4f} pp ; >1pp: '
      f'{sum(1 for t in shifts if abs(t[3])>1.0)}')
for g, ng, dwo, sh in shifts[:5]:
    print(f'      cluster={g} n={ng} delta_wo={dwo:8.4f} shift={sh:+.4f}')

# ---- what the shifts CAN be: leverage bound -------------------------------
print()
print('=' * 70)
print('LEVERAGE STRUCTURE (why shifts are mechanically small)')
sizes = sorted((len(rr) for rr in groups.values()), reverse=True)
print('    cluster cell-count: max=%d, top10=%s, median=%d, mean=%.2f' % (
    sizes[0], sizes[:10], sizes[len(sizes) // 2], sum(sizes) / len(sizes)))
full, S, N = pooled_delta(inc)
# max attainable |shift| for a cluster of size n if its delta were +-100
print('    max attainable |shift| for the LARGEST cluster if its own delta were')
n = sizes[0]
for extreme in (100.0, -100.0):
    dwo = 100.0 * (S - extreme * n / 100.0) / (N - n)
    print(f'      {extreme:+.0f} pp -> delta_wo={dwo:.4f}, shift={dwo-full:+.4f} pp')

# ---- cluster bootstrap CI, for the "16% of CI width" arithmetic -----------
print()
print('=' * 70)
print('CLUSTER BOOTSTRAP CI (resample clusters with replacement, B=20000, seed=20260731)')
rng = random.Random(20260731)
gl = list(groups.values())
pre = [(sum(x['B_correct'] - x['A_correct'] for x in rr), len(rr)) for rr in gl]
B = 20000
boot = []
K = len(pre)
for _ in range(B):
    s = 0
    n = 0
    for _ in range(K):
        a, b = pre[rng.randrange(K)]
        s += a
        n += b
    boot.append(100.0 * s / n)
boot.sort()


def pct(v, q):
    i = q * (len(v) - 1)
    lo = int(math.floor(i))
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (i - lo)


lo, hi = pct(boot, 0.025), pct(boot, 0.975)
print(f'    full delta = {full:.4f} pp; 95% cluster-bootstrap CI = [{lo:.4f}, {hi:.4f}]'
      f'  width={hi-lo:.4f} pp')
full_c, out_c = loo_cluster(inc)
dwos = [t[2] for t in out_c]
span = max(dwos) - min(dwos)
print(f'    LOO span = {span:.4f} pp = {100*span/(hi-lo):.1f}% of CI width')

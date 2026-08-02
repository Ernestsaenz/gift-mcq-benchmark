"""Independent refutation recompute of the cluster-bootstrap claim.
Stdlib only. No numpy/scipy/pandas.
"""
import json, math, random, collections, os

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, 'paired_clean.json')))
inc = [r for r in rows if r['analysis_include']]

MODELS = sorted(set(r['model'] for r in inc))
CLUSTERS = sorted(set(r['cluster'] for r in inc))

# ---------- point estimates ----------
print('=' * 78)
print('POINT ESTIMATES (clean subset, analysis_include == true)')
print('=' * 78)
print('rows=%d items=%d clusters=%d models=%d' % (
    len(inc), len(set(r['question_id'] for r in inc)), len(CLUSTERS), len(MODELS)))

obs = {}
for m in MODELS + ['POOLED']:
    sub = inc if m == 'POOLED' else [r for r in inc if r['model'] == m]
    n = len(sub)
    a = sum(r['A_correct'] for r in sub)
    b = sum(r['B_correct'] for r in sub)
    dA, dB = 100.0 * a / n, 100.0 * b / n
    obs[m] = dict(n=n, A=dA, B=dB, delta=dB - dA, a=a, b=b)
    print('%-24s n=%4d  A %6.2f%% (%d)  B %6.2f%% (%d)  delta %+7.3f pp'
          % (m, n, dA, a, dB, b, dB - dA))

# discordance detail (for context)
print()
for m in MODELS:
    sub = [r for r in inc if r['model'] == m]
    b01 = sum(1 for r in sub if r['A_correct'] == 0 and r['B_correct'] == 1)
    b10 = sum(1 for r in sub if r['A_correct'] == 1 and r['B_correct'] == 0)
    print('%-24s  A1B0=%3d  A0B1=%3d  net=%+d' % (m, b10, b01, b01 - b10))

# ---------- cluster bootstrap ----------
by_cluster = collections.defaultdict(list)
for r in inc:
    by_cluster[r['cluster']].append(r)

# Pre-reduce each cluster to per-model (n, sumA, sumB) plus pooled totals.
red = {}
for c in CLUSTERS:
    d = {}
    for m in MODELS:
        s = [r for r in by_cluster[c] if r['model'] == m]
        d[m] = (len(s), sum(r['A_correct'] for r in s), sum(r['B_correct'] for r in s))
    d['POOLED'] = (len(by_cluster[c]),
                   sum(r['A_correct'] for r in by_cluster[c]),
                   sum(r['B_correct'] for r in by_cluster[c]))
    red[c] = d


def percentile_linear(sorted_vals, q):
    """numpy-style 'linear' interpolation percentile. q in [0,1]."""
    n = len(sorted_vals)
    h = (n - 1) * q
    lo = math.floor(h)
    hi = math.ceil(h)
    if lo == hi:
        return sorted_vals[int(h)]
    return sorted_vals[lo] + (h - lo) * (sorted_vals[hi] - sorted_vals[lo])


def run_boot(B, seed, label):
    rng = random.Random(seed)
    keys = MODELS + ['POOLED']
    reps = {k: [] for k in keys}
    for _ in range(B):
        draw = rng.choices(CLUSTERS, k=len(CLUSTERS))
        acc = {k: [0, 0, 0] for k in keys}  # n, sumA, sumB
        for c in draw:
            rc = red[c]
            for k in keys:
                n, sa, sb = rc[k]
                t = acc[k]
                t[0] += n; t[1] += sa; t[2] += sb
        for k in keys:
            n, sa, sb = acc[k]
            reps[k].append(100.0 * (sb - sa) / n if n else float('nan'))
    print()
    print('=' * 78)
    print('CLUSTER BOOTSTRAP  %s  (B=%d, seed=%s, %d clusters w/ replacement)'
          % (label, B, seed, len(CLUSTERS)))
    print('=' * 78)
    print('%-24s %8s %8s %8s %9s %9s %9s' %
          ('model', 'delta', 'SE(pop)', 'SE(n-1)', 'lo2.5', 'hi97.5', 'bias'))
    out = {}
    for k in keys:
        v = reps[k]
        mean = sum(v) / len(v)
        var0 = sum((x - mean) ** 2 for x in v) / len(v)
        var1 = sum((x - mean) ** 2 for x in v) / (len(v) - 1)
        sv = sorted(v)
        lo = percentile_linear(sv, 0.025)
        hi = percentile_linear(sv, 0.975)
        pge0 = sum(1 for x in v if x >= 0)
        out[k] = dict(delta=obs[k]['delta'], se=math.sqrt(var1), se0=math.sqrt(var0),
                      lo=lo, hi=hi, bias=mean - obs[k]['delta'], pge0=pge0, B=B)
        print('%-24s %8.3f %8.3f %8.3f %9.3f %9.3f %+9.4f   #(delta*>=0)=%d/%d'
              % (k, obs[k]['delta'], math.sqrt(var0), math.sqrt(var1), lo, hi,
                 mean - obs[k]['delta'], pge0, B))
    return out


# Exact-seed replication attempt (claimed seed / RNG / call pattern)
res_claim = run_boot(20000, 20260731, 'claimed seed')
# Independent seeds -> Monte Carlo stability of the reported numbers
res_b = run_boot(20000, 777, 'independent seed 777')
res_c = run_boot(20000, 424242, 'independent seed 424242')
res_big = run_boot(200000, 20260731, 'high-B stability check')

# ---------- cluster sign-flip permutation ----------
print()
print('=' * 78)
print('CLUSTER SIGN-FLIP PERMUTATION (50000 flips, statistic = sum of cluster totals)')
print('=' * 78)


def signflip(key, B=50000, seed=99):
    rng = random.Random(seed)
    tot = [red[c][key][2] - red[c][key][1] for c in CLUSTERS]  # sum(B-A) per cluster
    T = abs(sum(tot))
    ge = 0
    for _ in range(B):
        s = 0
        for t in tot:
            s += t if rng.getrandbits(1) else -t
        if abs(s) >= T:
            ge += 1
    p = (1 + ge) / (B + 1)
    return T, ge, p


for k in MODELS + ['POOLED']:
    T, ge, p = signflip(k)
    print('%-24s |T_obs|=%5d  #{|T*|>=|T|}=%d/50000  p=(1+%d)/50001 = %.6f'
          % (k, T, ge, ge, p))

json.dump({'obs': obs, 'boot_claimseed': res_claim, 'boot_777': res_b,
           'boot_424242': res_c, 'boot_200k': res_big},
          open(os.path.join(HERE, 'prim_refute_clusterboot_out.json'), 'w'), indent=1)
print('\nwrote prim_refute_clusterboot_out.json')

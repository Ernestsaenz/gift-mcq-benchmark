"""Follow-ups: (1) sign-flip tail probability, analytic + long run;
(2) design effect vs naive independent-cell SE."""
import json, math, random, collections, os

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, 'paired_clean.json')))
inc = [r for r in rows if r['analysis_include']]
MODELS = sorted(set(r['model'] for r in inc))
CLUSTERS = sorted(set(r['cluster'] for r in inc))

by_c = collections.defaultdict(list)
for r in inc:
    by_c[r['cluster']].append(r)


def totals(key):
    out = []
    for c in CLUSTERS:
        sub = by_c[c] if key == 'POOLED' else [r for r in by_c[c] if r['model'] == key]
        out.append(sum(r['B_correct'] - r['A_correct'] for r in sub))
    return out


def erfc_tail(z):
    return 0.5 * math.erfc(z / math.sqrt(2.0))


print('=' * 78)
print('SIGN-FLIP NULL: analytic normal approx vs long Monte Carlo (B=2,000,000)')
print('=' * 78)
print('%-24s %7s %8s %8s %10s %14s' %
      ('model', '|T_obs|', 'sd_null', 'z', 'p_normal', 'p_MC(2e6)'))
for k in MODELS + ['POOLED']:
    t = totals(k)
    T = abs(sum(t))
    sd = math.sqrt(sum(x * x for x in t))
    z = T / sd
    p_norm = 2 * erfc_tail(z)
    rng = random.Random(12345)
    B = 2000000
    ge = 0
    nz = [x for x in t if x != 0]
    for _ in range(B):
        s = 0
        for x in nz:
            s += x if rng.getrandbits(1) else -x
        if abs(s) >= T:
            ge += 1
    p_mc = (1 + ge) / (B + 1)
    print('%-24s %7d %8.2f %8.3f %10.2e   %d/%d = %.3e'
          % (k, T, sd, z, p_norm, ge, B, p_mc))

print()
print('=' * 78)
print('DESIGN EFFECT: cluster-bootstrap SE vs naive independent-cell (McNemar) SE')
print('=' * 78)
boot_se = {'google/gemini-3.6-flash': 1.806, 'z-ai/glm-5.2': 2.412,
           'qwen/qwen3.6-35b-a3b': 2.501, 'google/gemma-4-26b-a4b-it': 3.327,
           'POOLED': 1.619}
for k in MODELS + ['POOLED']:
    sub = inc if k == 'POOLED' else [r for r in inc if r['model'] == k]
    n = len(sub)
    d = [r['B_correct'] - r['A_correct'] for r in sub]
    mean = sum(d) / n
    var = sum((x - mean) ** 2 for x in d) / n
    se_naive = 100.0 * math.sqrt(var / n)
    print('%-24s naive SE %6.3f   cluster-boot SE %6.3f   ratio %5.2f   deff %5.2f'
          % (k, se_naive, boot_se[k], boot_se[k] / se_naive,
             (boot_se[k] / se_naive) ** 2))

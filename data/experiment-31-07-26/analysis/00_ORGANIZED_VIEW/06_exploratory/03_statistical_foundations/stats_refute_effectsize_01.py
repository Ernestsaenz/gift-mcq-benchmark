"""REFUTATION recompute of the effect-size-and-power claim.
Stdlib only. Cluster bootstrap over the 208 clinical-context clusters.
"""
import json, math, random, collections

P = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json'
rows = [r for r in json.load(open(P)) if r.get('analysis_include')]

# ---------- 1. pooled 2x2 ----------
n11 = sum(1 for r in rows if r['A_correct'] == 1 and r['B_correct'] == 1)
n10 = sum(1 for r in rows if r['A_correct'] == 0 and r['B_correct'] == 1)   # A wrong -> B right
n01 = sum(1 for r in rows if r['A_correct'] == 1 and r['B_correct'] == 0)   # A right -> B wrong
n00 = sum(1 for r in rows if r['A_correct'] == 0 and r['B_correct'] == 0)
N = len(rows)
disc = n10 + n01
pA = sum(r['A_correct'] for r in rows) / N
pB = sum(r['B_correct'] for r in rows) / N
RD = pB - pA
print(f'N={N} n11={n11} n10={n10} n01={n01} n00={n00} disc={disc} ({disc/N:.4f})')
print(f'pA={pA:.6f} pB={pB:.6f} RD={RD:.6f}')

# ---------- 2. effect sizes ----------
def cohen_h(p1, p2):
    return 2*math.asin(math.sqrt(p1)) - 2*math.asin(math.sqrt(p2))

p10 = n10 / disc                 # share of discordant pairs going A-wrong -> B-right
g = p10 - 0.5                    # Cohen's g (sign test)
OR = n10 / n01
h = cohen_h(pB, pA)
print(f'p10(disc share)={p10:.6f}  Cohen g={g:.6f}  OR={OR:.6f}  ratio={n01/n10:.4f}x  Cohen h={h:.6f}')

# ---------- 3. Clopper-Pearson exact CI on p10 -> g and OR CIs ----------
def lchoose(n, k):
    return math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)

def binom_cdf(k, n, p):
    """P(X <= k)"""
    if p <= 0: return 1.0
    if p >= 1: return 0.0 if k < n else 1.0
    return sum(math.exp(lchoose(n, i)+i*math.log(p)+(n-i)*math.log(1-p))
               for i in range(0, k+1))

def binom_sf(k, n, p):
    """P(X >= k)"""
    return 1.0 - binom_cdf(k-1, n, p) if k > 0 else 1.0

k, n = n10, disc
# Clopper-Pearson: lower solves P(X>=k|p)=0.025 ; upper solves P(X<=k|p)=0.025
def bisect(f, target, lo=0.0, hi=1.0, incr=True):
    for _ in range(200):
        mid = (lo+hi)/2
        v = f(mid)
        if (v < target) == incr: lo = mid
        else: hi = mid
    return (lo+hi)/2

cp_lo = 0.0 if k == 0 else bisect(lambda p: binom_sf(k, n, p), 0.025, incr=True)
cp_hi = 1.0 if k == n else bisect(lambda p: binom_cdf(k, n, p), 0.025, incr=False)
print(f'Clopper-Pearson p10 CI = [{cp_lo:.6f}, {cp_hi:.6f}]')
print(f'  -> exact g  CI = [{cp_lo-0.5:.4f}, {cp_hi-0.5:.4f}]')
print(f'  -> exact OR CI = [{cp_lo/(1-cp_lo):.4f}, {cp_hi/(1-cp_hi):.4f}]')

# ---------- 4. cluster bootstrap ----------
byclu = collections.defaultdict(list)
for r in rows: byclu[r['cluster']].append(r)
clusters = sorted(byclu)
K = len(clusters)
print(f'clusters={K}')

def stats_from(sample):
    a = sum(1 for r in sample if r['A_correct'] == 0 and r['B_correct'] == 1)
    b = sum(1 for r in sample if r['A_correct'] == 1 and r['B_correct'] == 0)
    m = len(sample)
    qA = sum(r['A_correct'] for r in sample)/m
    qB = sum(r['B_correct'] for r in sample)/m
    d = a+b
    out = {'RD': qB-qA, 'h': cohen_h(qB, qA)}
    out['g'] = (a/d - 0.5) if d else float('nan')
    out['OR'] = (a/b) if b else float('nan')
    out['logOR'] = math.log(a/b) if (a and b) else float('nan')
    return out

random.seed(20260731)
B = 20000
acc = collections.defaultdict(list)
for _ in range(B):
    samp = []
    for _ in range(K):
        samp.extend(byclu[clusters[random.randrange(K)]])
    s = stats_from(samp)
    for key, v in s.items():
        if v == v: acc[key].append(v)

def pct(v, q):
    v = sorted(v); i = q*(len(v)-1)
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return v[lo] + (i-lo)*(v[hi]-v[lo])

def sd(v):
    m = sum(v)/len(v)
    return math.sqrt(sum((x-m)**2 for x in v)/(len(v)-1))

print(f'\ncluster bootstrap B={B}')
for key in ['RD', 'g', 'OR', 'h', 'logOR']:
    v = acc[key]
    print(f'  {key:6s} 95% CI [{pct(v,0.025):.4f}, {pct(v,0.975):.4f}]  bootSE={sd(v):.4f}  n={len(v)}')

# naive McNemar SE on RD for comparison
se_naive = math.sqrt(disc - (n10-n01)**2/N)/N
print(f'  naive (independent-pairs) SE on RD = {se_naive:.4f}; '
      f'design-effect on SE = {sd(acc["RD"])/se_naive:.3f}')

# ---------- 5. per model ----------
print('\nper model:')
bym = collections.defaultdict(list)
for r in rows: bym[r['model']].append(r)
for m in sorted(bym):
    s = stats_from(bym[m])
    a = sum(1 for r in bym[m] if r['A_correct'] == 0 and r['B_correct'] == 1)
    b = sum(1 for r in bym[m] if r['A_correct'] == 1 and r['B_correct'] == 0)
    print(f'  {m:28s} n={len(bym[m])} n10={a} n01={b} g={s["g"]:+.4f} OR={s["OR"]:.4f} '
          f'h={s["h"]:+.4f} RD={s["RD"]:+.4f}')

# ---------- 6. DOES THE CEILING DEFLATE h? direct test ----------
print('\n--- Is Cohen h "deflated by the high A-condition ceiling"? ---')
print('Hold RD fixed at the observed -0.15550 and slide the A baseline:')
for base in [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.8976, 0.95, 0.99]:
    if base + RD <= 0: continue
    print(f'  pA={base:.4f} pB={base+RD:.4f}  h={cohen_h(base+RD, base):+.4f}  '
          f"|d(2asin sqrt p)/dp| at pA = {1/math.sqrt(base*(1-base)):.3f}")
print('Hold the DISCORDANT SPLIT (g, OR) fixed and slide the ceiling:')
print('  g and OR depend only on n10/n01 and are invariant to n11/n00 --> they')
print('  literally cannot respond to the baseline at all.')

# ---------- 7. are g and OR independent "families"? ----------
print('\n--- Are g and OR two independent effect-size families? ---')
print(f'  OR = p10/(1-p10) with p10 = g+0.5 :  {(g+0.5)/(1-(g+0.5)):.6f} vs observed OR {OR:.6f}')
print('  => one-to-one monotone transform of the SAME statistic p10. Not corroboration.')

# ---------- 8. h vs the paired alternative: arcsine on the paired scale ----------
print('\n--- what an unpaired h ignores ---')
print(f'  h uses only the marginals (pA,pB); it is identical for ANY (n11,n10,n01,n00)')
print(f'  with the same margins. Check: margins pA={pA:.4f},pB={pB:.4f} are compatible with')
lo_disc = abs(n10 - n01)
print(f'  discordance anywhere from {lo_disc} to {min(int(pA*N)+int((1-pB)*N), N)} pairs;')
print(f'  observed {disc}. g/OR change wildly across that range, h does not move at all.')
for extra in [0, 100, 300, 500]:
    a2, b2 = n10+extra, n01+extra
    print(f'    if n10={a2} n01={b2} (same margins): g={a2/(a2+b2)-0.5:+.4f} OR={a2/b2:.4f} h={h:+.4f}')

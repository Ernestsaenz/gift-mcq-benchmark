"""Independent recomputation of the cluster-bootstrap claim (refutation pass).

Uses Python's Mersenne Twister (random.Random), NOT the claim's 64-bit LCG,
and several independent seeds, so any agreement is not an artefact of a shared
generator.  BCa reimplemented from Efron & Tibshirani (1993) eq. 14.10.
"""
import json, os, math, collections, random, statistics

BASE = os.path.dirname(os.path.abspath(__file__))
rows = [r for r in json.load(open(os.path.join(BASE, 'cross_arm_A.json')))
        if r.get('analysis_include')]

MODELS = sorted({r['model'] for r in rows})
CLUSTERS = sorted({r['cluster'] for r in rows})
KEYS = MODELS + ['POOLED']
ALPHA = 0.05
B = 20000

subsets = {m: [r for r in rows if r['model'] == m] for m in MODELS}
subsets['POOLED'] = rows

# ---------------------------------------------------------------- descriptives
print("=== descriptives ===")
desc = {}
for k in KEYS:
    sub = subsets[k]
    a = sum(1 for r in sub if r['gift_correct'] and r['or_correct'])
    b = sum(1 for r in sub if r['gift_correct'] and not r['or_correct'])
    c = sum(1 for r in sub if not r['gift_correct'] and r['or_correct'])
    d = len(sub) - a - b - c
    n = len(sub)
    g, o = (a + b) / n, (a + c) / n
    desc[k] = dict(n=n, a=a, b=b, c=c, d=d, g=g, o=o, rd=g - o)
    print(f"{k:26s} n={n:5d} GIFT={100*g:6.2f} OR={100*o:6.2f} RD={100*(g-o):+6.2f}pp b={b:3d} c={c:3d}")

# ------------------------------------------------------- normal helpers (own)
SQRT2 = math.sqrt(2.0)
def Phi(x): return 0.5 * (1.0 + math.erf(x / SQRT2))
def Phinv(p):
    # Acklam-style rational approximation + one Halley refinement (independent of ca_prim_lib)
    if p <= 0: return -math.inf
    if p >= 1: return math.inf
    a=[-3.969683028665376e+01,2.209460984245205e+02,-2.759285104469687e+02,
       1.383577518672690e+02,-3.066479806614716e+01,2.506628277459239e+00]
    b=[-5.447609879822406e+01,1.615858368580409e+02,-1.556989798598866e+02,
       6.680131188771972e+01,-1.328068155288572e+01]
    c=[-7.784894002430293e-03,-3.223964580411365e-01,-2.400758277161838e+00,
       -2.549732539343734e+00,4.374664141464968e+00,2.938163982698783e+00]
    d=[7.784695709041462e-03,3.224671290700398e-01,2.445134137142996e+00,
       3.754408661907416e+00]
    pl, ph = 0.02425, 1-0.02425
    if p < pl:
        q = math.sqrt(-2*math.log(p))
        x = (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    elif p <= ph:
        q = p-0.5; r = q*q
        x = (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    else:
        q = math.sqrt(-2*math.log(1-p))
        x = -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    e = Phi(x) - p
    u = e * math.sqrt(2*math.pi) * math.exp(x*x/2)
    x = x - u/(1 + x*u/2)
    return x

def pct(sv, q):
    n = len(sv)
    idx = q*(n-1); lo = math.floor(idx); hi = math.ceil(idx)
    if lo == hi: return sv[int(lo)]
    w = idx-lo
    return sv[int(lo)]*(1-w) + sv[int(hi)]*w

# ------------------------------------------------------------ cluster bootstrap
by_cluster = collections.defaultdict(list)
for r in rows:
    by_cluster[r['cluster']].append(r)
clus = [by_cluster[c] for c in CLUSTERS]
K = len(clus)

pre = {}
for k in KEYS:
    pre[k] = [(sum(r['gift_correct'] for r in cl if k == 'POOLED' or r['model'] == k),
               sum(r['or_correct']   for r in cl if k == 'POOLED' or r['model'] == k),
               sum(1 for r in cl if k == 'POOLED' or r['model'] == k)) for cl in clus]

def run_boot(seed, B=B):
    rng = random.Random(seed)
    out = {k: [] for k in KEYS}
    for _ in range(B):
        idxs = [rng.randrange(K) for _ in range(K)]
        for k in KEYS:
            arr = pre[k]; gs = os_ = ns = 0
            for i in idxs:
                g, o, n = arr[i]; gs += g; os_ += o; ns += n
            if ns: out[k].append((gs-os_)/ns)
    for k in KEYS: out[k].sort()
    return out

jack = {}
for k in KEYS:
    arr = pre[k]
    tg = sum(x[0] for x in arr); to = sum(x[1] for x in arr); tn = sum(x[2] for x in arr)
    jack[k] = [((tg-g)-(to-o))/(tn-n) for g,o,n in arr if tn-n > 0]

def bca(bs, theta, jv, alpha=ALPHA):
    Bn = len(bs)
    nb = sum(1 for v in bs if v < theta)
    frac = min(max(nb/Bn, 1/(2*Bn)), 1-1/(2*Bn))
    z0 = Phinv(frac)
    jbar = sum(jv)/len(jv); dd = [jbar-v for v in jv]
    num = sum(x**3 for x in dd); den = 6.0*(sum(x*x for x in dd)**1.5)
    acc = num/den if den else 0.0
    za, zb = Phinv(alpha/2), Phinv(1-alpha/2)
    def adj(z):
        dn = 1 - acc*(z0+z)
        return 0.5 if dn == 0 else Phi(z0 + (z0+z)/dn)
    return pct(bs, adj(za)), pct(bs, adj(zb)), z0, acc

print("\n=== cluster bootstrap, Mersenne Twister, 5 independent seeds ===")
SEEDS = [11, 2718, 31415, 777001, 20260731]
allres = collections.defaultdict(list)
for s in SEEDS:
    bo = run_boot(s)
    for k in KEYS:
        bs = bo[k]; th = desc[k]['rd']
        lo, hi = pct(bs, ALPHA/2), pct(bs, 1-ALPHA/2)
        blo, bhi, z0, acc = bca(bs, th, jack[k])
        m = statistics.fmean(bs)
        se = statistics.stdev(bs)
        n_le0 = sum(1 for v in bs if v <= 0.0)
        pb = min(1.0, 2*min(n_le0+1, len(bs)-n_le0+1)/(len(bs)+1))
        allres[k].append(dict(seed=s, lo=100*lo, hi=100*hi, blo=100*blo, bhi=100*bhi,
                              se=100*se, bias=100*(m-th), z0=z0, a=acc, p=pb))

for k in KEYS:
    print(f"\n-- {k}  RD={100*desc[k]['rd']:+.4f}pp")
    for r in allres[k]:
        print(f"   seed={r['seed']:<9} pct95=({r['lo']:+6.3f},{r['hi']:+6.3f})  "
              f"BCa95=({r['blo']:+6.3f},{r['bhi']:+6.3f})  SE={r['se']:.4f}  "
              f"bias={r['bias']:+.4f}  z0={r['z0']:+.4f} a={r['a']:+.5f} p={r['p']:.4f}")
    los = [r['lo'] for r in allres[k]]; his = [r['hi'] for r in allres[k]]
    print(f"   across-seed pct-lower range [{min(los):+.3f},{max(los):+.3f}]  "
          f"upper [{min(his):+.3f},{max(his):+.3f}]")

# -------------------------------------------------- naive SE and design effect
print("\n=== naive cell-independent SE and design effect ===")
for k in KEYS:
    b, c, n = desc[k]['b'], desc[k]['c'], desc[k]['n']
    var = (b + c - (b-c)**2/n)/n**2
    nse = 100*math.sqrt(var)
    bse = statistics.fmean([r['se'] for r in allres[k]])
    print(f"{k:26s} naive SE={nse:.4f}pp  boot SE={bse:.4f}pp  DEFF(var)={(bse/nse)**2:.3f}  "
          f"ratio SE={bse/nse:.3f}")

# design effect for ACCURACY (marginal), same cluster bootstrap, for comparison
print("\n=== design effect for the MARGINAL accuracies (same cluster bootstrap) ===")
def boot_acc(seed, which, B=6000):
    rng = random.Random(seed)
    vals = {k: [] for k in KEYS}
    prea = {}
    for k in KEYS:
        prea[k] = [(sum(r[which] for r in cl if k=='POOLED' or r['model']==k),
                    sum(1 for r in cl if k=='POOLED' or r['model']==k)) for cl in clus]
    for _ in range(B):
        idxs = [rng.randrange(K) for _ in range(K)]
        for k in KEYS:
            arr = prea[k]; s=0; n=0
            for i in idxs:
                x,y = arr[i]; s+=x; n+=y
            if n: vals[k].append(s/n)
    return vals

for which in ('gift_correct','or_correct'):
    va = boot_acc(99, which)
    for k in KEYS:
        p = sum(r[which] for r in subsets[k])/len(subsets[k])
        nse = 100*math.sqrt(p*(1-p)/len(subsets[k]))
        bse = 100*statistics.stdev(va[k])
        print(f"{which:14s} {k:26s} naive={nse:.4f} boot={bse:.4f} DEFF={(bse/nse)**2:.3f}")

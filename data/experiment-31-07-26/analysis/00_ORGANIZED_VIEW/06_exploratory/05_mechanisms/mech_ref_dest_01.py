"""Independent recomputation of the error-destination claim. Stdlib only.

Claim under test:
 (a) Destination is NOT concentrated by position or letter; positional structure at most
     marginal and IDENTICAL to condition A; the 2x4 A-vs-B letter test is a "flat null",
     meaning condition B introduced NO new positional signature at all.
"""
import json, math, collections, random, sys

PAIRED = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
L = ["a", "b", "c", "d"]

# ---------------- my own chi-square upper tail (regularized upper incomplete gamma) ------
def _gser(a, x):
    ap, s, d = a, 1.0 / a, 1.0 / a
    for _ in range(10000):
        ap += 1.0
        d *= x / ap
        s += d
        if abs(d) < abs(s) * 1e-16:
            break
    return s * math.exp(-x + a * math.log(x) - math.lgamma(a))

def _gcf(a, x):
    tiny = 1e-300
    b, c, d = x + 1.0 - a, 1.0 / tiny, 1.0 / (x + 1.0 - a)
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny: d = tiny
        c = b + an / c
        if abs(c) < tiny: c = tiny
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-16:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h

def gammaq(a, x):
    if x <= 0: return 1.0
    if x < a + 1.0: return 1.0 - _gser(a, x)
    return _gcf(a, x)

def chi2sf(x2, df):
    """Pearson chi-square upper tail. Method: regularized upper incomplete gamma Q(df/2, X2/2)
    via Lentz continued fraction / series (Numerical Recipes gammq)."""
    if x2 <= 0: return 1.0
    return max(0.0, min(1.0, gammaq(df / 2.0, x2 / 2.0)))

# validation against tabulated 0.05 / 0.01 critical points
TAB = {1: (3.8415, 6.6349), 2: (5.9915, 9.2103), 3: (7.8147, 11.3449),
       4: (9.4877, 13.2767), 5: (11.0705, 15.0863), 6: (12.5916, 16.8119),
       9: (16.9190, 21.6660), 12: (21.0261, 26.2170)}
print("chi2sf validation (should be .0500 / .0100):")
for df, (c5, c1) in sorted(TAB.items()):
    print(f"   df={df:2d}  sf({c5})={chi2sf(c5,df):.5f}  sf({c1})={chi2sf(c1,df):.5f}")

def gof(obs, exp):
    x2 = sum((o - e) ** 2 / e for o, e in zip(obs, exp) if e > 0)
    return x2, len(obs) - 1

def gtest(obs, exp):
    """Likelihood-ratio G^2 = 2*sum O ln(O/E) -- second method, robust check on Pearson."""
    g = 2.0 * sum(o * math.log(o / e) for o, e in zip(obs, exp) if o > 0 and e > 0)
    return g, len(obs) - 1

# ---------------- data ----------------
cells = [r for r in json.load(open(PAIRED)) if r["analysis_include"]]
print(f"\ncells={len(cells)} items={len(set(c['question_id'] for c in cells))} "
      f"clusters={len(set(c['cluster'] for c in cells))} models={len(set(c['model'] for c in cells))}")
models = sorted(set(c["model"] for c in cells))
assert all(c["correct_letter"] != "a" for c in cells), "NOTA slot 'a' present"

Aerr = [c for c in cells if not c["A_correct"]]
Berr = [c for c in cells if not c["B_correct"]]
print(f"A errors={len(Aerr)}  B errors={len(Berr)}")

def surv(c):
    return [x for x in L if x != c["correct_letter"]]

# =========================================================================
print("\n" + "=" * 76)
print("R1. REPRODUCE THE CLAIM'S NUMBERS")
print("=" * 76)

def letter_gof(rows, key):
    obs = collections.Counter(); exp = collections.Counter()
    for c in rows:
        obs[c[key]] += 1
        for x in surv(c):
            exp[x] += 1.0 / 3.0
    o = [obs[x] for x in L]; e = [exp[x] for x in L]
    x2, df = gof(o, e); g, _ = gtest(o, e)
    return o, e, x2, df, g

oB, eB, x2B, dfB, gB = letter_gof(Berr, "B_selected")
print("B-error destination by absolute letter:")
for x, o, e in zip(L, oB, eB):
    print(f"   {x}  obs={o:4d}  exp={e:7.2f}  obs/exp={o/e:.2f}")
print(f"   Pearson X2={x2B:.2f} df={dfB} p={chi2sf(x2B,dfB):.3e}   [Pearson chi-square GOF]")
print(f"   LR G2   ={gB:.2f} df={dfB} p={chi2sf(gB,dfB):.3e}   [likelihood-ratio G-test GOF]")

oA, eA, x2A, dfA, gA = letter_gof(Aerr, "A_selected")
print("A-error destination by absolute letter:")
for x, o, e in zip(L, oA, eA):
    print(f"   {x}  obs={o:4d}  exp={e:7.2f}  obs/exp={o/e:.2f}")
print(f"   Pearson X2={x2A:.2f} df={dfA} p={chi2sf(x2A,dfA):.3e}   [Pearson chi-square GOF]")

def rank_gof(rows, key):
    r = collections.Counter()
    for c in rows:
        r[surv(c).index(c[key])] += 1
    n = sum(r.values()); o = [r[i] for i in range(3)]
    x2, df = gof(o, [n / 3.0] * 3)
    return o, n, x2, df

oRB, nRB, x2RB, dfRB = rank_gof(Berr, "B_selected")
oRA, nRA, x2RA, dfRA = rank_gof(Aerr, "A_selected")
print(f"B rank among survivors: {oRB} n={nRB}  X2={x2RB:.2f} df={dfRB} p={chi2sf(x2RB,dfRB):.3e}  [Pearson GOF vs uniform 1/3]")
print(f"A rank among survivors: {oRA} n={nRA}  X2={x2RA:.2f} df={dfRA} p={chi2sf(x2RA,dfRA):.3e}  [Pearson GOF vs uniform 1/3]")

# 2x4 independence
tot = sum(oA) + sum(oB); colt = [oA[j] + oB[j] for j in range(4)]; rowt = [sum(oA), sum(oB)]
x2c = sum((r[j] - rowt[i] * colt[j] / tot) ** 2 / (rowt[i] * colt[j] / tot)
          for i, r in enumerate([oA, oB]) for j in range(4) if colt[j] > 0)
print(f"2x4 A-vs-B letter independence: X2={x2c:.2f} df=3 p={chi2sf(x2c,3):.3e}  [Pearson chi-square test of independence]")

# =========================================================================
print("\n" + "=" * 76)
print("R2. POWER OF THE 2x4 'FLAT NULL' -- can it detect anything?")
print("=" * 76)
# Under H0 the 2x4 has nA=133, nB=335. Simulate: how big a shift in B's profile is
# needed for the 2x4 to reach p<.05 with 80% power?  Monte Carlo, method: parametric
# bootstrap from multinomial(A-profile) vs multinomial(shifted B-profile).
random.seed(20260731)
pA_prof = [o / sum(oA) for o in oA]
def draw(n, p):
    out = [0] * len(p)
    for _ in range(n):
        u = random.random(); acc = 0.0
        for j, pj in enumerate(p):
            acc += pj
            if u <= acc:
                out[j] += 1; break
        else:
            out[-1] += 1
    return out

def x2_2x4(r0, r1):
    t = sum(r0) + sum(r1); ct = [r0[j] + r1[j] for j in range(4)]; rt = [sum(r0), sum(r1)]
    s = 0.0
    for i, r in enumerate([r0, r1]):
        for j in range(4):
            e = rt[i] * ct[j] / t
            if e > 0: s += (r[j] - e) ** 2 / e
    return s

for shift in [0.0, 0.05, 0.075, 0.10, 0.125, 0.15, 0.20]:
    # move `shift` of B's mass from letter 'b' into letter 'a' (a plausible NOTA-avoidance drift)
    pB = list(pA_prof); pB[0] += shift; pB[1] -= shift
    if pB[1] < 0: continue
    hits = 0; R = 4000
    for _ in range(R):
        if x2_2x4(draw(133, pA_prof), draw(335, pB)) > 7.8147:
            hits += 1
    print(f"   shift={shift:.3f} (letter-a share {pA_prof[0]:.3f}->{pB[0]:.3f})  power={hits/R:.3f}  [Monte-Carlo power, 4000 reps, Pearson 2x4 at alpha=.05]")

# =========================================================================
print("\n" + "=" * 76)
print("R3. THE TEST THE CLAIM DID NOT RUN: destination CONDITIONAL on NOTA position")
print("=" * 76)
# The pooled marginal averages over NOTA position and can cancel opposing shifts.
# 3x3 table: NOTA slot (b/c/d) x rank of destination among survivors.
tab = {k: [0, 0, 0] for k in ["b", "c", "d"]}
for c in Berr:
    tab[c["correct_letter"]][surv(c).index(c["B_selected"])] += 1
print("   rows = NOTA slot, cols = rank among the 3 survivors (1st,2nd,3rd)")
rows = ["b", "c", "d"]
mat = [tab[k] for k in rows]
for k, r in zip(rows, mat):
    n = sum(r)
    print(f"   NOTA={k}  n={n:4d}  counts={r}  frac=[{r[0]/n:.3f} {r[1]/n:.3f} {r[2]/n:.3f}]")
t = sum(sum(r) for r in mat); ct = [sum(mat[i][j] for i in range(3)) for j in range(3)]
rt = [sum(r) for r in mat]
x2h = sum((mat[i][j] - rt[i] * ct[j] / t) ** 2 / (rt[i] * ct[j] / t)
          for i in range(3) for j in range(3) if rt[i] * ct[j] > 0)
print(f"   homogeneity of rank profile across NOTA slots: X2={x2h:.2f} df=4 p={chi2sf(x2h,4):.3e}  [Pearson chi-square test of homogeneity]")

# joint GOF over the 9 cells vs uniform-within-row
exp9 = [rt[i] / 3.0 for i in range(3) for _ in range(3)]
obs9 = [mat[i][j] for i in range(3) for j in range(3)]
x29 = sum((o - e) ** 2 / e for o, e in zip(obs9, exp9) if e > 0)
print(f"   joint GOF (all 9 cells vs uniform-within-NOTA-slot): X2={x29:.2f} df=6 p={chi2sf(x29,6):.3e}  [Pearson chi-square GOF]")

# same conditional table for A errors
tabA = {k: [0, 0, 0] for k in ["b", "c", "d"]}
for c in Aerr:
    tabA[c["correct_letter"]][surv(c).index(c["A_selected"])] += 1
matA = [tabA[k] for k in rows]
rtA = [sum(r) for r in matA]
print("   --- A errors, same table ---")
for k, r in zip(rows, matA):
    n = sum(r)
    print(f"   NOTA={k}  n={n:4d}  counts={r}  frac=[{r[0]/n:.3f} {r[1]/n:.3f} {r[2]/n:.3f}]" if n else f"   NOTA={k} n=0")
expA9 = [rtA[i] / 3.0 for i in range(3) for _ in range(3)]
obsA9 = [matA[i][j] for i in range(3) for j in range(3)]
x2A9 = sum((o - e) ** 2 / e for o, e in zip(obsA9, expA9) if e > 0)
print(f"   joint GOF A: X2={x2A9:.2f} df=6 p={chi2sf(x2A9,6):.3e}  [Pearson chi-square GOF]")

# =========================================================================
print("\n" + "=" * 76)
print("R4. ADJACENCY: is the destination next to the NOTA slot?")
print("=" * 76)
pos = {x: i for i, x in enumerate(L)}
adj = collections.Counter(); adje = collections.Counter()
for c in Berr:
    d = abs(pos[c["B_selected"]] - pos[c["correct_letter"]])
    adj[d] += 1
    for x in surv(c):
        adje[abs(pos[x] - pos[c["correct_letter"]])] += 1.0 / 3.0
ks = sorted(adje)
o = [adj[k] for k in ks]; e = [adje[k] for k in ks]
for k, oo, ee in zip(ks, o, e):
    print(f"   |dist to NOTA|={k}  obs={oo:4d} exp={ee:7.2f} obs/exp={oo/ee:.2f}")
x2ad, dfad = gof(o, e)
print(f"   X2={x2ad:.2f} df={dfad} p={chi2sf(x2ad,dfad):.3e}  [Pearson chi-square GOF vs availability-weighted uniform]")

# =========================================================================
print("\n" + "=" * 76)
print("R5. ITEM-LEVEL CONCENTRATION (do the 4 models land on the SAME distractor?)")
print("=" * 76)
byitem = collections.defaultdict(list)
for c in Berr:
    byitem[c["question_id"]].append(c["B_selected"])
same = tot_p = 0
for q, s in byitem.items():
    cnt = collections.Counter(s)
    same += sum(v * (v - 1) // 2 for v in cnt.values())
    tot_p += len(s) * (len(s) - 1) // 2
print(f"   items with >=1 B error: {len(byitem)}; within-item pairwise agreement "
      f"{same}/{tot_p} = {same/tot_p:.4f}  (chance under independent-uniform-over-3 = 0.3333)")
# permutation test: reshuffle destinations within model, respecting each item's survivor set
def agree_stat(assign):
    bi = collections.defaultdict(list)
    for c, sel in zip(Berr, assign):
        bi[c["question_id"]].append(sel)
    s = 0
    for q, v in bi.items():
        cnt = collections.Counter(v)
        s += sum(x * (x - 1) // 2 for x in cnt.values())
    return s
obs_stat = same
R = 4000
ge = 0
for _ in range(R):
    a = [random.choice(surv(c)) for c in Berr]
    if agree_stat(a) >= obs_stat:
        ge += 1
print(f"   permutation p (destination drawn uniform over each item's 3 survivors, "
      f"{R} reps) = {(ge+1)/(R+1):.4f}  [Monte-Carlo permutation test]")

# same for A errors
byitemA = collections.defaultdict(list)
for c in Aerr:
    byitemA[c["question_id"]].append(c["A_selected"])
sameA = totA = 0
for q, s in byitemA.items():
    cnt = collections.Counter(s)
    sameA += sum(v * (v - 1) // 2 for v in cnt.values())
    totA += len(s) * (len(s) - 1) // 2
print(f"   A errors: within-item pairwise agreement {sameA}/{totA} = {sameA/totA:.4f}")

# =========================================================================
print("\n" + "=" * 76)
print("R6. CLUSTER-ROBUST GOF (models are not independent within item)")
print("=" * 76)
# design-based Wald on the 3 rank proportions, clustering by question_id.
def cluster_wald(rows, key, p0=(1/3, 1/3, 1/3), clus="question_id"):
    n = len(rows)
    y = []
    for c in rows:
        v = [0.0, 0.0, 0.0]; v[surv(c).index(c[key])] = 1.0
        y.append(v)
    ph = [sum(v[j] for v in y) / n for j in range(3)]
    g = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
    for c, v in zip(rows, y):
        for j in range(3):
            g[c[clus]][j] += v[j] - ph[j]
    G = len(g)
    V = [[0.0] * 3 for _ in range(3)]
    for s in g.values():
        for i in range(3):
            for j in range(3):
                V[i][j] += s[i] * s[j]
    fac = G / (G - 1.0) / (n * n)
    V = [[V[i][j] * fac for j in range(3)] for i in range(3)]
    # drop last category -> 2x2
    d = [ph[0] - p0[0], ph[1] - p0[1]]
    M = [[V[0][0], V[0][1]], [V[1][0], V[1][1]]]
    det = M[0][0] * M[1][1] - M[0][1] * M[1][0]
    Mi = [[M[1][1] / det, -M[0][1] / det], [-M[1][0] / det, M[0][0] / det]]
    W = sum(d[i] * Mi[i][j] * d[j] for i in range(2) for j in range(2))
    # naive multinomial X2 for comparison
    x2n = sum((ph[j] * n - n / 3.0) ** 2 / (n / 3.0) for j in range(3))
    return ph, W, x2n, G

ph, W, x2n, G = cluster_wald(Berr, "B_selected")
print(f"   B rank proportions {['%.4f'%x for x in ph]}  clusters(items)={G}")
print(f"   naive Pearson X2={x2n:.2f} df=2 p={chi2sf(x2n,2):.3e}")
print(f"   cluster-robust Wald  W={W:.2f} df=2 p={chi2sf(W,2):.3e}  [design-based Wald, "
      f"item-clustered sandwich covariance]")
print(f"   design effect (naive/robust) = {x2n/W:.3f}")

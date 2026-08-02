"""Part 2: decompose the B-error pool. The claim pools ALL B errors, but ~40% of them
are cells that were ALREADY wrong in A -- if those simply repeat their A choice, the
'A-vs-B letter profiles are identical' result is manufactured by construction."""
import json, math, collections, random
import sys
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_ref_dest_01 import chi2sf, gof, cells, surv, L, Aerr, Berr, cluster_wald

random.seed(7)
print("\n" + "#" * 76)
print("PART 2")
print("#" * 76)

both = [c for c in cells if not c["A_correct"] and not c["B_correct"]]
drop = [c for c in cells if c["A_correct"] and not c["B_correct"]]
rec  = [c for c in cells if not c["A_correct"] and c["B_correct"]]
ok   = [c for c in cells if c["A_correct"] and c["B_correct"]]
print(f"A ok/B ok={len(ok)}  A ok/B wrong (DROP)={len(drop)}  "
      f"A wrong/B ok (RECOVER)={len(rec)}  A wrong/B wrong (BOTH)={len(both)}")
print(f"  -> the 335 pooled B errors = {len(drop)} newly created + {len(both)} pre-existing")

# --------------------------------------------------------------------------
print("\n" + "=" * 76)
print("P1. Do the 'BOTH wrong' cells just repeat their condition-A choice?")
print("=" * 76)
same = sum(1 for c in both if c["A_selected"] == c["B_selected"])
n = len(both)
# expected under 'independent redraw uniform over the 3 survivors' = 1/3
exp = n / 3.0
x2 = (same - exp) ** 2 / exp + ((n - same) - (n - exp)) ** 2 / (n - exp)
print(f"   B_selected == A_selected in {same}/{n} = {same/n:.4f} of BOTH-wrong cells "
      f"(chance if independent redraw over 3 survivors = 0.3333)")
print(f"   Pearson chi-square GOF vs 1/3: X2={x2:.1f} df=1 p={chi2sf(x2,1):.3e}")
# exact binomial as a second method
def binom_p_ge(k, n, p):
    return sum(math.comb(n, i) * p**i * (1-p)**(n-i) for i in range(k, n+1))
print(f"   exact one-sided binomial p(X>={same}|n={n},p=1/3) = {binom_p_ge(same,n,1/3):.3e}  [exact binomial test]")
print(f"   => {same} of the 335 pooled B errors ({same/335:.1%}) are literally the same letter")
print(f"      the model already picked in condition A. The pooled B letter profile is")
print(f"      partly a copy of the A profile, so the 2x4 'flat null' is not independent evidence.")

# --------------------------------------------------------------------------
print("\n" + "=" * 76)
print("P2. Destination profile of the NEWLY CREATED errors (DROP cells) vs A errors")
print("=" * 76)
def prof_letter(rows, key):
    o = collections.Counter(); e = collections.Counter()
    for c in rows:
        o[c[key]] += 1
        for x in surv(c):
            e[x] += 1.0/3.0
    return [o[x] for x in L], [e[x] for x in L]

def prof_rank(rows, key):
    r = collections.Counter()
    for c in rows:
        r[surv(c).index(c[key])] += 1
    return [r[i] for i in range(3)]

for name, rows, key in [("A errors      ", Aerr, "A_selected"),
                        ("B all errors  ", Berr, "B_selected"),
                        ("B DROP only   ", drop, "B_selected"),
                        ("B BOTH-wrong  ", both, "B_selected")]:
    o, e = prof_letter(rows, key)
    x2, df = gof(o, e)
    rk = prof_rank(rows, key)
    nn = sum(rk)
    x2r, _ = gof(rk, [nn/3.0]*3)
    print(f"   {name} n={nn:4d}  letters obs={o} obs/exp={['%.2f'%(a/b) for a,b in zip(o,e)]}"
          f"  X2={x2:5.2f} p={chi2sf(x2,3):.4f}")
    print(f"   {' '*14}          rank={rk} frac={['%.3f'%(x/nn) for x in rk]}"
          f"  X2={x2r:5.2f} p={chi2sf(x2r,2):.4f}")

def indep(r0, r1):
    k = len(r0); t = sum(r0)+sum(r1)
    ct = [r0[j]+r1[j] for j in range(k)]; rt = [sum(r0), sum(r1)]
    s = 0.0
    for i, r in enumerate([r0, r1]):
        for j in range(k):
            e = rt[i]*ct[j]/t
            if e > 0: s += (r[j]-e)**2/e
    return s, k-1

oA,_ = prof_letter(Aerr,"A_selected"); oD,_ = prof_letter(drop,"B_selected")
oBo,_ = prof_letter(both,"B_selected")
x,df = indep(oA, oD); print(f"\n   2x4 letters  A-errors vs B-DROP-only : X2={x:.2f} df={df} p={chi2sf(x,df):.4f}  [Pearson chi-square independence]")
x,df = indep(oA, oBo); print(f"   2x4 letters  A-errors vs B-BOTH     : X2={x:.2f} df={df} p={chi2sf(x,df):.4f}")
x,df = indep(oD, oBo); print(f"   2x4 letters  B-DROP vs B-BOTH       : X2={x:.2f} df={df} p={chi2sf(x,df):.4f}")

rA = prof_rank(Aerr,"A_selected"); rD = prof_rank(drop,"B_selected"); rB = prof_rank(Berr,"B_selected")
rBo = prof_rank(both,"B_selected")
x,df = indep(rA, rB);  print(f"\n   2x3 RANK     A-errors vs B-all      : X2={x:.2f} df={df} p={chi2sf(x,df):.4f}  [Pearson chi-square independence]")
x,df = indep(rA, rD);  print(f"   2x3 RANK     A-errors vs B-DROP-only: X2={x:.2f} df={df} p={chi2sf(x,df):.4f}")
x,df = indep(rD, rBo); print(f"   2x3 RANK     B-DROP vs B-BOTH       : X2={x:.2f} df={df} p={chi2sf(x,df):.4f}")

# --------------------------------------------------------------------------
print("\n" + "=" * 76)
print("P3. Cluster-robust versions of the two 'significant' positional tests")
print("=" * 76)
def cluster_wald_letter(rows, key):
    """Design-based Wald that the per-item availability-conditional letter choice is uniform.
    Statistic: 3-vector of rank proportions is done elsewhere; here we test the LETTER
    profile by comparing observed letter counts to per-cell availability, clustered by item."""
    n = len(rows)
    ph = [0.0]*4;
    for c in rows:
        i = L.index(c[key]); ph[i] += 1.0/n
    p0 = [0.0]*4
    for c in rows:
        for x in surv(c):
            p0[L.index(x)] += (1.0/3.0)/n
    g = collections.defaultdict(lambda: [0.0]*4)
    for c in rows:
        v = [0.0]*4; v[L.index(c[key])] = 1.0
        av = [0.0]*4
        for x in surv(c): av[L.index(x)] = 1.0/3.0
        for j in range(4):
            g[c["question_id"]][j] += (v[j]-av[j]) - (ph[j]-p0[j])
    G = len(g)
    V = [[0.0]*4 for _ in range(4)]
    for s in g.values():
        for i in range(4):
            for j in range(4):
                V[i][j] += s[i]*s[j]
    f = G/(G-1.0)/(n*n)
    V = [[V[i][j]*f for j in range(4)] for i in range(4)]
    d = [ph[j]-p0[j] for j in range(3)]     # drop letter 'd'
    M = [[V[i][j] for j in range(3)] for i in range(3)]
    # 3x3 inverse via Gauss-Jordan
    A = [row[:] + [1.0 if i==j else 0.0 for j in range(3)] for i,row in enumerate(M)]
    for i in range(3):
        p = max(range(i,3), key=lambda r: abs(A[r][i])); A[i],A[p]=A[p],A[i]
        pv = A[i][i]
        A[i] = [x/pv for x in A[i]]
        for r in range(3):
            if r!=i:
                f2 = A[r][i]
                A[r] = [a-f2*b for a,b in zip(A[r],A[i])]
    Mi = [row[3:] for row in A]
    W = sum(d[i]*Mi[i][j]*d[j] for i in range(3) for j in range(3))
    naive = sum((ph[j]*n - p0[j]*n)**2/(p0[j]*n) for j in range(4))
    return W, naive, G

W, naive, G = cluster_wald_letter(Berr, "B_selected")
print(f"   LETTER GOF (B errors): naive Pearson X2={naive:.2f} df=3 p={chi2sf(naive,3):.4f}")
print(f"                          cluster-robust Wald W={W:.2f} df=3 p={chi2sf(W,3):.4f}  "
      f"[design-based Wald, item-clustered sandwich, {G} item clusters]")
ph, Wr, x2n, Gr = cluster_wald(Berr, "B_selected")
print(f"   RANK  GOF (B errors):  naive Pearson X2={x2n:.2f} df=2 p={chi2sf(x2n,2):.4f}")
print(f"                          cluster-robust Wald W={Wr:.2f} df=2 p={chi2sf(Wr,2):.4f}")

# and a within-model (independent) check: each model separately, then Fisher-combine
print("\n   Per-model rank GOF (cells independent within a model), Fisher combination:")
models = sorted(set(c["model"] for c in cells))
ps = []
for m in models:
    rows = [c for c in Berr if c["model"]==m]
    rk = prof_rank(rows,"B_selected"); nn = sum(rk)
    x2,_ = gof(rk,[nn/3.0]*3); p = chi2sf(x2,2); ps.append(p)
    print(f"     {m:26s} n={nn:3d} rank={rk} X2={x2:5.2f} p={p:.4f}")
fisher = -2*sum(math.log(p) for p in ps)
print(f"     Fisher X2={fisher:.2f} df={2*len(ps)} p={chi2sf(fisher,2*len(ps)):.4f}  [Fisher's method]")
ps4 = []
for m in models:
    rows = [c for c in Berr if c["model"]==m]
    o,e = prof_letter(rows,"B_selected"); x2,_=gof(o,e); p=chi2sf(x2,3); ps4.append(p)
    print(f"     {m:26s} letters obs={o} X2={x2:5.2f} p={p:.4f}")
fisher4 = -2*sum(math.log(p) for p in ps4)
print(f"     Fisher X2={fisher4:.2f} df={2*len(ps4)} p={chi2sf(fisher4,2*len(ps4)):.4f}  [Fisher's method]")

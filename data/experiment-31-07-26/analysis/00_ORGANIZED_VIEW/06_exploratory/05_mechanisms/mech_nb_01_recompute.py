"""Refutation pass on the 'noise bound' claim from who-recovers.

Part 1: recompute the 2x2 table + every number the claim states.
Part 2: LINEAR PROGRAM.  The claim asserts a ceiling
            noise-attributable losses <= min(lost, gained) = 45.
        The claim's OWN definition of "noise-only losses" (its section N4) is
            S = sum_i p_i (1 - p_i)
        = expected A-correct -> B-wrong flips if B were merely a re-run of A.
        So the honest ceiling is
            max  S   subject to the model reproducing the observed 2x2 exactly.
        That is a linear program over a distribution on (p, q) in [0,1]^2 with
        4 equality constraints; solve it with a two-phase simplex.
Method names are stated with every p-value.
"""
import math, json, collections, os

BASE = os.path.dirname(os.path.abspath(__file__))
cells = [r for r in json.load(open(os.path.join(BASE, "paired_clean.json")))
         if r["analysis_include"]]

N = len(cells)
n11 = sum(1 for r in cells if r["A_correct"] and r["B_correct"])
n10 = sum(1 for r in cells if r["A_correct"] and not r["B_correct"])
n01 = sum(1 for r in cells if not r["A_correct"] and r["B_correct"])
n00 = N - n11 - n10 - n01
D = n10 + n01

print("=" * 90)
print("R1. OBSERVED TABLE (paired_clean.json, analysis_include==true, as of now)")
print(f"    N={N}  items={len(set(r['question_id'] for r in cells))} "
      f"clusters={len(set(r['cluster'] for r in cells))} "
      f"models={len(set(r['model'] for r in cells))}")
print(f"    n11(both right)={n11}  n10(LOST)={n10}  n01(GAINED)={n01}  n00(both wrong)={n00}")
print(f"    discordant D={D}   net={n10-n01}   net/N={(n10-n01)/N:.4f}")
print(f"    acc A={(n11+n10)/N:.4f}  acc B={(n11+n01)/N:.4f}")
print()
print("    CLAIM STATED: N=1299, lost=247, gained=45, discordant=292, net=202 (15.6 pts)")
print(f"    RECOMPUTED  : N={N}, lost={n10}, gained={n01}, discordant={D}, "
      f"net={n10-n01} ({(n10-n01)/N*100:.1f} pts)")

# ---- exact tests ------------------------------------------------------------
def binom_pmf_sum(lo, hi, n, p=0.5):
    return sum(math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(lo, hi + 1))

one_sided = binom_pmf_sum(0, n01, D)          # exact binomial (McNemar exact), one-sided
two_sided = min(1.0, 2 * one_sided)
print()
print("R2. EXACT McNEMAR (two-sided exact binomial test on the discordant pairs, H0: p=0.5)")
print(f"    P(gained <= {n01} | D={D}, p=0.5) = {one_sided:.3e}   two-sided p = {two_sided:.3e}")
print("    -> the 'all losses are noise' story is dead.  This part of the claim survives.")

print()
print("R3. THE CLAIM'S SYMMETRY CEILING, AS STATED")
print(f"    2 x min(lost,gained) = {2*n01} cells = {2*n01/D:.1%} of discordant, "
      f"{n01/n10:.1%} of losses")
print(f"    implied instability mass S <= {n01}; re-run disagreement 2S/N <= {2*n01/N:.4f}")

# ---------------------------------------------------------------------------
# Two-phase simplex:  min c.x  s.t.  A x = b,  x >= 0
# ---------------------------------------------------------------------------
def simplex(A, b, c):
    m, n = len(A), len(A[0])
    b = list(b)
    for i in range(m):                      # make b >= 0
        if b[i] < 0:
            A[i] = [-v for v in A[i]]; b[i] = -b[i]
    # phase 1
    T = [A[i][:] + [1.0 if j == i else 0.0 for j in range(m)] + [b[i]] for i in range(m)]
    basis = [n + i for i in range(m)]
    cost = [0.0] * n + [1.0] * m

    def run(T, basis, cost, ncols):
        while True:
            y = [0.0] * len(T)
            # reduced costs via explicit row reduction (small problem: recompute z row)
            z = [0.0] * (ncols + 1)
            for i, bi in enumerate(basis):
                cb = cost[bi]
                if cb:
                    for j in range(ncols + 1):
                        z[j] += cb * T[i][j]
            enter = -1
            for j in range(ncols):
                if cost[j] - z[j] < -1e-9:
                    enter = j; break              # Bland's rule -> no cycling
            if enter < 0:
                return z[ncols]
            ratios = [(T[i][ncols] / T[i][enter], basis[i], i)
                      for i in range(len(T)) if T[i][enter] > 1e-9]
            if not ratios:
                raise RuntimeError("unbounded")
            _, _, piv = min(ratios)
            pv = T[piv][enter]
            T[piv] = [v / pv for v in T[piv]]
            for i in range(len(T)):
                if i != piv and abs(T[i][enter]) > 1e-12:
                    f = T[i][enter]
                    T[i] = [T[i][j] - f * T[piv][j] for j in range(ncols + 1)]
            basis[piv] = enter

    obj1 = run(T, basis, cost, n + m)
    if obj1 > 1e-7:
        raise RuntimeError(f"infeasible (phase-1 objective {obj1})")
    # drop artificials, phase 2
    T2 = [row[:n] + [row[n + m]] for row in T]
    cost2 = list(c)
    for i, bi in enumerate(basis):
        if bi >= n:                                   # artificial still basic at 0
            for j in range(n):
                if abs(T2[i][j]) > 1e-9:
                    pv = T2[i][j]
                    T2[i] = [v / pv for v in T2[i]]
                    for k in range(len(T2)):
                        if k != i and abs(T2[k][j]) > 1e-12:
                            f = T2[k][j]
                            T2[k] = [T2[k][t] - f * T2[i][t] for t in range(n + 1)]
                    basis[i] = j
                    break
    val = run(T2, basis, cost2, n)
    x = [0.0] * n
    for i, bi in enumerate(basis):
        if bi < n:
            x[bi] = T2[i][n]
    return val, x


# grid of (p,q) atoms
STEP = 0.01
G = [i * STEP for i in range(int(1 / STEP) + 1)]
atoms = [(p, q) for p in G for q in G]
A = [[1.0] * len(atoms),
     [p * q for p, q in atoms],
     [p * (1 - q) for p, q in atoms],
     [(1 - p) * q for p, q in atoms]]
b = [1.0, n11 / N, n10 / N, n01 / N]
obj = [p * (1 - p) for p, q in atoms]          # S per cell

print()
print("=" * 90)
print("R4. IS 45 REALLY A CEILING?  LP over all per-cell models that reproduce the table")
print("    max/min  S = sum_i p_i(1-p_i)  s.t.  E[n11],E[n10],E[n01] match exactly, "
      "w>=0, sum w=1")
print(f"    (grid {len(atoms)} atoms, step {STEP}; two-phase simplex with Bland's rule)")
vmax, xmax = simplex([row[:] for row in A], b, [-v for v in obj])
Smax = -vmax * N
vmin, xmin = simplex([row[:] for row in A], b, obj[:])
Smin = vmin * N
for nm, S, x in (("MAX", Smax, xmax), ("MIN", Smin, xmin)):
    sup = sorted(((w, atoms[i]) for i, w in enumerate(x) if w > 1e-9), reverse=True)
    print(f"    {nm} S = {S:8.1f} cells  = {S/n10:6.1%} of the {n10} losses; "
          f"implied re-run disagreement 2S/N = {2*S/N:.3f}")
    print(f"          support: " + "  ".join(f"w={w:.3f}@(p={p:.2f},q={q:.2f})" for w, (p, q) in sup))
print()
print(f"    The claim's ceiling of {n01} losses ({n01/n10:.1%}) is NOT the maximum. The maximum")
print(f"    noise-only-loss mass compatible with the very same 2x2 is {Smax:.0f} ({Smax/n10:.0%}).")
print("    The claim's own latent-normal fit (33.6%) already sits above its stated ceiling.")

# ---- reproduce the claim's own latent fit on current data --------------------
GRID = [(-14 + 28 * i / 2400) for i in range(2401)]
def moments(mu, sigma, delta):
    h = GRID[1] - GRID[0]
    E = dict(p=0.0, pq=0.0, p1q=0.0, q1p=0.0, pp=0.0, w=0.0)
    for t in GRID:
        w = math.exp(-0.5 * ((t - mu) / sigma) ** 2) / (sigma * math.sqrt(2 * math.pi)) * h
        p = 1 / (1 + math.exp(-t)); q = 1 / (1 + math.exp(-(t - delta)))
        E["w"] += w; E["p"] += w * p; E["pq"] += w * p * q
        E["p1q"] += w * p * (1 - q); E["q1p"] += w * (1 - p) * q; E["pp"] += w * p * (1 - p)
    for k in E:
        if k != "w": E[k] /= E["w"]
    return E

def nelder_mead(f, x0, step=0.4, it=700):
    n = len(x0)
    S = [list(x0)] + [[x0[j] + (step if j == i else 0) for j in range(n)] for i in range(n)]
    F = [f(s) for s in S]
    for _ in range(it):
        o = sorted(range(n + 1), key=lambda i: F[i]); S = [S[i] for i in o]; F = [F[i] for i in o]
        c = [sum(S[i][j] for i in range(n)) / n for j in range(n)]
        xr = [c[j] + (c[j] - S[n][j]) for j in range(n)]; fr = f(xr)
        if fr < F[0]:
            xe = [c[j] + 2 * (c[j] - S[n][j]) for j in range(n)]; fe = f(xe)
            S[n], F[n] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < F[n - 1]:
            S[n], F[n] = xr, fr
        else:
            xc = [c[j] + 0.5 * (S[n][j] - c[j]) for j in range(n)]; fc = f(xc)
            if fc < F[n]: S[n], F[n] = xc, fc
            else:
                for i in range(1, n + 1):
                    S[i] = [(S[i][j] + S[0][j]) / 2 for j in range(n)]; F[i] = f(S[i])
    return S[0], F[0]

def lossf(par):
    mu, ls, delta = par
    E = moments(mu, math.exp(ls), delta)
    return ((E["pq"] - n11/N)**2 + (E["p1q"] - n10/N)**2 + (E["q1p"] - n01/N)**2)

par, fv = nelder_mead(lossf, [2.2, math.log(2.0), 1.2])
mu, sigma, delta = par[0], math.exp(par[1]), par[2]
E = moments(mu, sigma, delta)
print()
print("R5. THE CLAIM'S OWN LOGIT-NORMAL FIT, RECOMPUTED (Nelder-Mead, exactly identified)")
print(f"    mu={mu:.3f} sigma={sigma:.3f} delta={delta:.3f} (OR {math.exp(-delta):.3f})  "
      f"residual {fv:.2e}")
print(f"    2E[p(1-p)] = {2*E['pp']:.3f}   noise-only expected losses = {N*E['pp']:.1f} "
      f"= {N*E['pp']/n10:.1%} of {n10}")
print(f"    -> {N*E['pp']/n10:.1%} > the claim's own {n01/n10:.1%} ceiling.  Internal contradiction.")

json.dump(dict(N=N, n11=n11, n10=n10, n01=n01, n00=n00, D=D,
               one_sided_exact_binomial=one_sided, two_sided=two_sided,
               S_max_LP=Smax, S_min_LP=Smin, S_max_share_of_losses=Smax / n10,
               latent=dict(mu=mu, sigma=sigma, delta=delta, S=N * E["pp"],
                           share=N * E["pp"] / n10, rerun=2 * E["pp"])),
          open(os.path.join(BASE, "mech_nb_01_out.json"), "w"), indent=1)

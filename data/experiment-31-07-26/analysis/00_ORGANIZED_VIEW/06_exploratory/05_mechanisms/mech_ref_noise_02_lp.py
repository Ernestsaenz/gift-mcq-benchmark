"""Assumption-light MAXIMUM of the instability mass S = sum_i p_i(1-p_i), subject to the
model reproducing the observed 2x2 in expectation.

Model class (identical to the one the claim uses): cell i has P(correct)=p_i in A and q_i in B,
responses independent Bernoulli.  Any joint distribution F over (p,q) in [0,1]^2 is allowed --
this is strictly MORE general than the claim's logit-normal family and strictly more general
than the claim's noise/systematic partition.

Constraints (exact match of the three free cells):
  E[pq] = n11/N,  E[p(1-q)] = n10/N,  E[(1-p)q] = n01/N,  E[1] = 1
Objective: maximise (and minimise) E[p(1-p)]  -> S = N*E[p(1-p)], re-run disagreement = 2S/N.

Solved as a linear program in the (discretised) measure F by a from-scratch dense simplex
(Phase-1 artificial basis + Phase-2, Bland's rule to avoid cycling).  Stdlib only.
"""
import json, math, collections

# ------------------------------------------------------------------ simplex
def simplex(A, b, c):
    """max c'x  s.t.  Ax = b (b>=0), x >= 0.  Returns (value, x). Dense, Bland's rule."""
    m, n = len(A), len(A[0])
    # Phase 1
    T = [row[:] + [1.0 if i == j else 0.0 for j in range(m)] + [b[i]] for i, row in enumerate(A)]
    basis = [n + i for i in range(m)]
    def pivot(T, basis, cost, ncols):
        while True:
            # reduced costs z_j - c_j  (minimisation of cost' x)
            y = [cost[basis[i]] for i in range(m)]
            enter = -1
            for j in range(ncols):
                if j in basis: continue
                rc = sum(y[i] * T[i][j] for i in range(m)) - cost[j]
                if rc > 1e-9:
                    enter = j; break                      # Bland: first improving
            if enter < 0: return
            ratios = [(T[i][-1] / T[i][enter], basis[i], i) for i in range(m) if T[i][enter] > 1e-9]
            if not ratios: return                          # unbounded
            _, _, r = min(ratios)
            pv = T[r][enter]
            T[r] = [v / pv for v in T[r]]
            for i in range(m):
                if i != r and abs(T[i][enter]) > 1e-14:
                    f = T[i][enter]
                    T[i] = [T[i][k] - f * T[r][k] for k in range(len(T[i]))]
            basis[r] = enter
    cost1 = [0.0] * n + [1.0] * m                          # minimise sum of artificials
    pivot(T, basis, [-v for v in cost1], n + m)            # maximise -sum artificials
    infeas = sum(T[i][-1] for i in range(m) if basis[i] >= n)
    if infeas > 1e-7:
        return None, None
    # drop artificial columns
    T2 = [row[:n] + [row[-1]] for row in T]
    for i in range(m):
        if basis[i] >= n:                                  # degenerate artificial in basis
            for j in range(n):
                if abs(T2[i][j]) > 1e-9:
                    pv = T2[i][j]
                    T2[i] = [v / pv for v in T2[i]]
                    for k in range(m):
                        if k != i and abs(T2[k][j]) > 1e-14:
                            f = T2[k][j]
                            T2[k] = [T2[k][t] - f * T2[i][t] for t in range(n + 1)]
                    basis[i] = j; break
    pivot(T2, basis, c, n)
    x = [0.0] * n
    for i in range(m):
        if basis[i] < n: x[basis[i]] = T2[i][-1]
    return sum(c[j] * x[j] for j in range(n)), x


def bounds_for_table(n11, n10, n01, N, G=81, label=""):
    grid = [max(1e-7, min(1 - 1e-7, k / (G - 1))) for k in range(G)]
    cols, obj = [], []
    for p in grid:
        for q in grid:
            cols.append((p * q, p * (1 - q), (1 - p) * q, 1.0))
            obj.append(p * (1 - p))
    A = [[c[k] for c in cols] for k in range(4)]
    b = [n11 / N, n10 / N, n01 / N, 1.0]
    hi, xh = simplex(A, b, obj)
    lo, xl = simplex(A, b, [-v for v in obj])
    lo = -lo if lo is not None else None
    return hi, lo, cols, obj, xh, grid


P = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
rows = [r for r in json.load(open(P)) if r["analysis_include"]]

def table(rs):
    n11 = sum(1 for r in rs if r["A_correct"] and r["B_correct"])
    n10 = sum(1 for r in rs if r["A_correct"] and not r["B_correct"])
    n01 = sum(1 for r in rs if not r["A_correct"] and r["B_correct"])
    return n11, n10, n01, len(rs)

n11, n10, n01, N = table(rows)
print(f"POOLED  n11={n11} lost={n10} gained={n01} N={N}")
hi, lo, cols, obj, xh, grid = bounds_for_table(n11, n10, n01, N, G=81)
print(f"  LP max E[p(1-p)] = {hi:.5f}  -> S_max = {hi*N:.1f} cells, re-run disagreement 2S/N = {2*hi:.4f}")
print(f"  LP min E[p(1-p)] = {lo:.5f}  -> S_min = {lo*N:.1f} cells, re-run disagreement 2S/N = {2*lo:.4f}")
print(f"  CLAIM asserts S <= 45 and 2S/N <= 0.069.")
print(f"  => share of the {n10} losses attributable to re-run noise ranges "
      f"{lo*N/n10:.1%} .. {hi*N/n10:.1%}  (claim: '<= 18.2%')")
print(f"  Jensen ceiling (ignoring joint constraints): E[p](1-E[p]) = "
      f"{((n11+n10)/N)*(1-(n11+n10)/N):.5f} -> S <= {((n11+n10)/N)*(1-(n11+n10)/N)*N:.1f}")

# show the optimal support
sup = sorted([(w, cols[i], obj[i], i) for i, w in enumerate(xh) if w > 1e-8], reverse=True)
print("  optimal F support (mass, p, q):")
for w, cc, o, i in sup:
    pq, p1q, q1p, _ = cc
    # recover p,q from index
    p = grid[i // len(grid)]; q = grid[i % len(grid)]
    print(f"     mass={w:.4f}  p={p:.4f}  q={q:.4f}   p(1-p)={o:.4f}")

print()
print("PER-MODEL (sum of per-model LP maxima = tighter, still assumption-light)")
tot_hi = tot_lo = tot_lost = 0
for m in sorted({r["model"] for r in rows}):
    rs = [r for r in rows if r["model"] == m]
    a, l, g, n = table(rs)
    h2, l2, _, _, _, _ = bounds_for_table(a, l, g, n, G=81)
    tot_hi += h2 * n; tot_lo += l2 * n; tot_lost += l
    print(f"  {m:<28} lost={l:>3} gain={g:>3}  S_max={h2*n:>6.1f} (2S/n={2*h2:.3f})  "
          f"S_min={l2*n:>5.1f}  noise share of losses <= {h2*n/l:>6.1%}")
print(f"  TOTAL over models: S_max={tot_hi:.1f} of {tot_lost} losses = {tot_hi/tot_lost:.1%}   "
      f"S_min={tot_lo:.1f} = {tot_lo/tot_lost:.1%}")

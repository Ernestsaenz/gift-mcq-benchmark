"""Step 6: mixed-effects logistic models by Gauss-Hermite quadrature, maximised
with a hand-rolled Nelder-Mead. Pure stdlib.

Models (fixed effects throughout: intercept, condition B, 3 model contrasts):
  M0  no random effects (pooled logistic)
  M1  + random intercept for ITEM
  M2  + random intercepts for CLUSTER and ITEM (nested)
  M3  + random intercepts for CLUSTER, ITEM and CELL (= item x model)

Items are strictly nested in clusters and 197/208 clusters hold exactly one item,
so for singleton clusters u_cluster + v_item collapses to a single N(0, sc^2+si^2)
draw. That is both a speed-up and the central identifiability fact reported below.

Speed: the cell-level integral is precomputed on the grid of distinct outer
offsets t (Q for singleton clusters, Q^2 for multi-item clusters) x 4 models x 4
response patterns, so a likelihood evaluation is table lookups plus sums.

Gauss-Hermite nodes computed from scratch (Newton iteration on the physicists'
Hermite polynomial, Numerical Recipes 'gauher').
"""
import sys, math, time
from collections import defaultdict
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from stats_lib import *

def gauher(n, eps=1e-14, maxit=100):
    x = [0.0] * n; w = [0.0] * n
    m = (n + 1) // 2
    pim4 = math.pi ** -0.25
    z = 0.0
    for i in range(m):
        if i == 0:
            z = math.sqrt(2.0 * n + 1.0) - 1.85575 * (2.0 * n + 1.0) ** (-1.0 / 6.0)
        elif i == 1:
            z -= 1.14 * (n ** 0.426) / z
        elif i == 2:
            z = 1.86 * z - 0.86 * x[0]
        elif i == 3:
            z = 1.91 * z - 0.91 * x[1]
        else:
            z = 2.0 * z - x[i - 2]
        pp = 1.0
        for _ in range(maxit):
            p1, p2 = pim4, 0.0
            for j in range(1, n + 1):
                p3 = p2; p2 = p1
                p1 = z * math.sqrt(2.0 / j) * p2 - math.sqrt((j - 1.0) / j) * p3
            pp = math.sqrt(2.0 * n) * p2
            z1 = z; z = z1 - p1 / pp
            if abs(z - z1) <= eps:
                break
        x[i] = z; x[n - 1 - i] = -z
        w[i] = 2.0 / (pp * pp); w[n - 1 - i] = w[i]
    return x, w

NORM = 1.0 / math.sqrt(math.pi)
SQ2 = math.sqrt(2.0)

def logp(y, eta):
    if y == 1:
        return -math.log1p(math.exp(-eta)) if eta > -700 else eta
    return -math.log1p(math.exp(eta)) if eta < 700 else -eta

def lse(terms):
    mx = max(t[0] for t in terms)
    return mx + math.log(sum(w * math.exp(l - mx) for l, w in terms) * NORM)

# ------------------------------------------------------------------ data prep
rows = load()
models = sorted({r["model"] for r in rows})
MI = {m: i for i, m in enumerate(models)}
MSHORT = {m: m.split("/")[-1] for m in models}
cl_items = defaultdict(lambda: defaultdict(list))
for r in rows:
    cl_items[r["cluster"]][r["question_id"]].append(r)
# item -> list of (model_index, pattern_index); pattern = 2*A + B
SINGLE, MULTI = [], []
for c, items in cl_items.items():
    enc = [[(MI[r["model"]], 2 * r["A_correct"] + r["B_correct"]) for r in cells]
           for q, cells in items.items()]
    (SINGLE if len(enc) == 1 else MULTI).append(enc)
print("clusters: %d singleton-item, %d multi-item (%d items in multi-item clusters)"
      % (len(SINGLE), len(MULTI), sum(len(c) for c in MULTI)))
PAT = [(0, 0), (0, 1), (1, 0), (1, 1)]  # (A_correct, B_correct)

def build(Q):
    HX, HW = gauher(Q)
    return HX, HW

def make_negll(Q, use_cluster, use_item, use_cell):
    HX, HW = build(Q)
    def negll(p):
        b0, b1, g1, g2, g3 = p[0], p[1], p[2], p[3], p[4]
        i = 5
        sc = math.exp(p[i]) if use_cluster else 0.0; i += 1 if use_cluster else 0
        si = math.exp(p[i]) if use_item else 0.0;    i += 1 if use_item else 0
        sw = math.exp(p[i]) if use_cell else 0.0
        G = [0.0, g1, g2, g3]
        base = [(b0 + G[m], b0 + b1 + G[m]) for m in range(4)]

        def cell_tab(t):
            """[model][pattern] -> log P(cell responses | offset t), cell RE integrated."""
            out = []
            for m in range(4):
                ea, eb = base[m][0] + t, base[m][1] + t
                if sw == 0.0:
                    out.append([logp(ya, ea) + logp(yb, eb) for (ya, yb) in PAT])
                else:
                    row = []
                    zs = [SQ2 * sw * xx for xx in HX]
                    for (ya, yb) in PAT:
                        row.append(lse([(logp(ya, ea + z) + logp(yb, eb + z), ww)
                                        for z, ww in zip(zs, HW)]))
                    out.append(row)
            return out

        total = 0.0
        # --- singleton clusters: one N(0, sc^2+si^2) effect
        st = math.sqrt(sc * sc + si * si)
        if SINGLE:
            if st == 0.0:
                tab = cell_tab(0.0)
                for cl in SINGLE:
                    total += sum(tab[m][pt] for (m, pt) in cl[0])
            else:
                tabs = [(cell_tab(SQ2 * st * xx), ww) for xx, ww in zip(HX, HW)]
                for cl in SINGLE:
                    item = cl[0]
                    total += lse([(sum(tab[m][pt] for (m, pt) in item), ww)
                                  for tab, ww in tabs])
        # --- multi-item clusters
        if MULTI:
            if sc == 0.0:
                if si == 0.0:
                    tab = cell_tab(0.0)
                    for cl in MULTI:
                        for item in cl:
                            total += sum(tab[m][pt] for (m, pt) in item)
                else:
                    tabs = [(cell_tab(SQ2 * si * xx), ww) for xx, ww in zip(HX, HW)]
                    for cl in MULTI:
                        for item in cl:
                            total += lse([(sum(tab[m][pt] for (m, pt) in item), ww)
                                          for tab, ww in tabs])
            else:
                # grid over (u, v)
                grid = []
                for xu, wu in zip(HX, HW):
                    u = SQ2 * sc * xu
                    if si == 0.0:
                        grid.append((wu, [(cell_tab(u), 1.0 / NORM)]))
                    else:
                        grid.append((wu, [(cell_tab(u + SQ2 * si * xv), wv)
                                          for xv, wv in zip(HX, HW)]))
                for cl in MULTI:
                    outer = []
                    for wu, inner in grid:
                        s2 = 0.0
                        for item in cl:
                            s2 += lse([(sum(tab[m][pt] for (m, pt) in item), wv)
                                       for tab, wv in inner])
                        outer.append((s2, wu))
                    total += lse(outer)
        return -total
    return negll

def nelder_mead(f, x0, step=0.4, tol=1e-11, maxit=6000):
    n = len(x0)
    pts = [list(x0)]
    for i in range(n):
        q = list(x0); q[i] += step
        pts.append(q)
    vals = [f(q) for q in pts]
    for it in range(maxit):
        o = sorted(range(n + 1), key=lambda k: vals[k])
        pts = [pts[k] for k in o]; vals = [vals[k] for k in o]
        if abs(vals[-1] - vals[0]) < tol * (abs(vals[0]) + tol):
            break
        cen = [sum(pts[k][j] for k in range(n)) / n for j in range(n)]
        xr = [cen[j] + (cen[j] - pts[-1][j]) for j in range(n)]
        fr = f(xr)
        if fr < vals[0]:
            xe = [cen[j] + 2.0 * (cen[j] - pts[-1][j]) for j in range(n)]
            fe = f(xe)
            pts[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = xr, fr
        else:
            xc = [cen[j] + 0.5 * (pts[-1][j] - cen[j]) for j in range(n)]
            fc = f(xc)
            if fc < vals[-1]:
                pts[-1], vals[-1] = xc, fc
            else:
                for k in range(1, n + 1):
                    pts[k] = [pts[0][j] + 0.5 * (pts[k][j] - pts[0][j]) for j in range(n)]
                    vals[k] = f(pts[k])
    k = min(range(n + 1), key=lambda j: vals[j])
    return pts[k], vals[k]

Q = 15
print("GH nodes Q =", Q)
specs = [
    ("M0 fixed only",            False, False, False, [1.0, -1.0, 0.0, 0.0, 0.0]),
    ("M1 +item RI",              False, True,  False, [1.5, -1.2, 0.0, 0.0, 0.0, 0.0]),
    ("M2 +cluster+item RI",      True,  True,  False, [1.5, -1.2, 0.0, 0.0, 0.0, -0.7, 0.0]),
    ("M3 +cluster+item+cell RI", True,  True,  True,  [2.0, -1.5, 0.0, 0.0, 0.0, -0.7, 0.0, -0.4]),
]
res = {}
print("\n%-26s %11s %5s %10s %9s   %s" % ("model", "loglik", "npar", "b1(cond B)", "OR", "variance components"))
for name, uc, ui, uw, x0 in specs:
    f = make_negll(Q, uc, ui, uw)
    t0 = time.time()
    best, bv = nelder_mead(f, x0, 0.5)
    best, bv = nelder_mead(f, best, 0.15)
    best, bv = nelder_mead(f, best, 0.04)
    best, bv = nelder_mead(f, best, 0.01)
    res[name] = (best, bv, f, (uc, ui, uw))
    lab, i = [], 5
    if uc: lab.append("sd_cluster=%.4f" % math.exp(best[i])); i += 1
    if ui: lab.append("sd_item=%.4f" % math.exp(best[i])); i += 1
    if uw: lab.append("sd_cell=%.4f" % math.exp(best[i]))
    print("%-26s %11.4f %5d %10.4f %9.4f   %s   [%.0fs]"
          % (name, -bv, len(best), best[1], math.exp(best[1]), ", ".join(lab) or "-", time.time() - t0))

print("\nfixed model contrasts (M3), reference = %s:" % MSHORT[models[0]])
b3 = res["M3 +cluster+item+cell RI"][0]
for j, m in enumerate(models[1:]):
    print("   %-24s %+0.4f" % (MSHORT[m], b3[2 + j]))

print("\n=== LRTs. Variance components sit on the boundary, so the reference is the")
print("    0.5*chi2_0 + 0.5*chi2_1 mixture: p = 0.5 * P(chi2_1 > LR). ===")
for a, b, lab in [("M0 fixed only", "M1 +item RI", "item RI"),
                  ("M1 +item RI", "M2 +cluster+item RI", "cluster RI | item"),
                  ("M2 +cluster+item RI", "M3 +cluster+item+cell RI", "cell RI | cluster+item")]:
    LR = 2 * (res[a][1] - res[b][1])
    print("   add %-24s LR = %8.4f   p(chi2_1) = %.4e   p(mixture) = %.4e"
          % (lab, LR, chi2_sf(max(LR, 0), 1), 0.5 * chi2_sf(max(LR, 0), 1)))

print("\n=== profile log-likelihood in sd_cluster under M2 (is it identified?) ===")
best2, bv2, f2, _ = res["M2 +cluster+item RI"]
print("   %12s %14s %10s" % ("sd_cluster", "-loglik", "delta"))
prof = []
for sc in [0.001, 0.05, 0.10, 0.20, 0.30, 0.40, 0.60, 0.90]:
    def g(q):
        return f2(list(q[:5]) + [math.log(sc)] + [q[5]])
    q0 = list(best2[:5]) + [best2[6]]
    qb, gv = nelder_mead(g, q0, 0.1)
    qb, gv = nelder_mead(g, qb, 0.02)
    prof.append((sc, gv))
    print("   %12.3f %14.4f %10.4f" % (sc, gv, gv - bv2))
print("   -> a drop of 1.92 log-lik units is the 95%% profile-likelihood cutoff (boundary-corrected)")

print("\n=== quadrature sensitivity: refit M3 at several Q ===")
for Qx in (9, 11, 21):
    f = make_negll(Qx, True, True, True)
    best, bv = nelder_mead(f, res["M3 +cluster+item+cell RI"][0], 0.05)
    best, bv = nelder_mead(f, best, 0.01)
    print("   Q=%2d  loglik=%11.4f  b1=%+.5f  sd_cluster=%.4f sd_item=%.4f sd_cell=%.4f"
          % (Qx, -bv, best[1], math.exp(best[5]), math.exp(best[6]), math.exp(best[7])))

print("\n=== the CONDITION effect is a different number under every specification ===")
print("   %-40s %10s %9s" % ("target / model", "log-OR", "OR"))
for name in ["M0 fixed only", "M1 +item RI", "M2 +cluster+item RI", "M3 +cluster+item+cell RI"]:
    print("   %-40s %+10.4f %9.4f" % (name, res[name][0][1], math.exp(res[name][0][1])))
_b = sum(1 for r in rows if r["A_correct"] == 1 and r["B_correct"] == 0)
_c = sum(1 for r in rows if r["A_correct"] == 0 and r["B_correct"] == 1)
_cond = -math.log(_b / _c)
print("   %-40s %+10.4f %9.4f" % ("conditional logistic == McNemar", _cond, math.exp(_cond)))
print("   (marginal GEE independence wc: see stats_04 output)")

# dump the fitted M3 parameters for the calibration study in stats_08
import json
_b3, _, _, _ = res["M3 +cluster+item+cell RI"]
json.dump(dict(b0=_b3[0], b1=_b3[1], gm=[0.0, _b3[2], _b3[3], _b3[4]],
               sd_cluster=math.exp(_b3[5]), sd_item=math.exp(_b3[6]),
               sd_cell=math.exp(_b3[7]), models=models),
          open("stats_m3_fit.json", "w"), indent=1)
print("\nwrote stats_m3_fit.json for the calibration study")

"""Conditional (McFadden) logit over the 3-alternative choice set, fit by
Newton-Raphson. Horse-races length / position / similarity / A-attractor /
other-models'-B-choice as predictors of WHICH distractor a B error lands on.
Also: is condition A's error pattern equally convergent?"""
import sys, collections, math, random
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_lib import *

random.seed(3)
Q = load_questions()
cells = load_cells()
models = sorted(set(c["model"] for c in cells))
errsB = [c for c in cells if c["B_correct"] == 0]
errsA = [c for c in cells if c["A_correct"] == 0]
A_pick = collections.defaultdict(dict)
for c in errsA:
    A_pick[c["question_id"]][c["model"]] = c["A_selected"]
B_pick = collections.defaultdict(dict)
for c in errsB:
    B_pick[c["question_id"]][c["model"]] = c["B_selected"]


def surv(qid):
    return [L for L in LETTERS if L != Q[qid]["B"]["correct_letter"]]


# ---------------- linear algebra ----------------
def solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M[r][i]))
        if abs(M[p][i]) < 1e-12:
            M[i][i] += 1e-8
            p = i
        M[i], M[p] = M[p], M[i]
        pv = M[i][i]
        M[i] = [x / pv for x in M[i]]
        for r in range(n):
            if r != i and M[r][i] != 0:
                f = M[r][i]
                M[r] = [x - f * y for x, y in zip(M[r], M[i])]
    return [M[i][n] for i in range(n)]


def inv(A):
    n = len(A)
    cols = []
    for j in range(n):
        e = [1.0 if i == j else 0.0 for i in range(n)]
        cols.append(solve(A, e))
    return [[cols[j][i] for j in range(n)] for i in range(n)]


def clogit(sets, names, iters=60):
    """sets: list of (chosen_index, [featvec, ...]). Returns beta, se, ll, ll0."""
    k = len(names)
    beta = [0.0] * k
    for _ in range(iters):
        g = [0.0] * k
        H = [[0.0] * k for _ in range(k)]
        for ch, X in sets:
            u = [sum(b * x for b, x in zip(beta, xv)) for xv in X]
            mx = max(u)
            ex = [math.exp(v - mx) for v in u]
            s = sum(ex)
            p = [e / s for e in ex]
            xbar = [sum(p[i] * X[i][j] for i in range(len(X))) for j in range(k)]
            for j in range(k):
                g[j] += X[ch][j] - xbar[j]
            for j in range(k):
                for l in range(k):
                    H[j][l] -= sum(p[i] * (X[i][j] - xbar[j]) * (X[i][l] - xbar[l])
                                   for i in range(len(X)))
        step = solve([[-h for h in row] for row in H], g)
        beta = [b + s for b, s in zip(beta, step)]
        if max(abs(s) for s in step) < 1e-9:
            break
    V = inv([[-h for h in row] for row in H])
    se = [math.sqrt(max(V[i][i], 0.0)) for i in range(k)]
    ll = 0.0
    for ch, X in sets:
        u = [sum(b * x for b, x in zip(beta, xv)) for xv in X]
        mx = max(u); ex = [math.exp(v - mx) for v in u]
        ll += u[ch] - mx - math.log(sum(ex))
    ll0 = sum(-math.log(len(X)) for _, X in sets)
    return beta, se, ll, ll0


def normal_sf2(z):
    return math.erfc(abs(z) / math.sqrt(2.0))


def zfeat(vals):
    m = sum(vals) / len(vals)
    sd = (sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5
    return [(v - m) / sd if sd > 1e-9 else 0.0 for v in vals]


def build(errs, use_loo_b=False):
    sets = []
    for c in errs:
        q = c["question_id"]; S = surv(q)
        removed = Q[q]["A"]["correct_text"]
        lens = [len(Q[q]["B"]["opts"][L]) for L in S]
        jac = [jaccard(Q[q]["B"]["opts"][L], removed) for L in S]
        zl, zj = zfeat(lens), zfeat(jac)
        othersA = set(L for m, L in A_pick[q].items() if m != c["model"])
        othersB = set(L for m, L in B_pick[q].items() if m != c["model"])
        X = []
        for i, L in enumerate(S):
            row = [zl[i], zj[i],
                   1.0 if i == 1 else 0.0, 1.0 if i == 2 else 0.0,
                   1.0 if L in othersA else 0.0]
            if use_loo_b:
                row.append(1.0 if L in othersB else 0.0)
            X.append(row)
        sets.append((S.index(c["B_selected"]), X))
    return sets


NAMES = ["len (z, within set)", "sim to deleted answer (z)", "slot=2nd survivor",
         "slot=3rd survivor", "another model's A-error letter"]

for use in (False, True):
    nm = NAMES + (["another model's B-error letter"] if use else [])
    sets = build(errsB, use)
    beta, se, ll, ll0 = clogit(sets, nm)
    print("=" * 78)
    print(f"CONDITIONAL LOGIT on {len(sets)} B errors, 3 alternatives each"
          + (" (+ leave-one-out other-model B choice)" if use else ""))
    print("=" * 78)
    print(f"{'term':34s} {'beta':>8s} {'se':>7s} {'z':>7s} {'p':>10s} {'OR':>7s}")
    for n, b, s in zip(nm, beta, se):
        print(f"{n:34s} {b:8.3f} {s:7.3f} {b/s:7.2f} {normal_sf2(b/s):10.2e} {math.exp(b):7.2f}")
    print(f"  logL={ll:.2f}  null logL={ll0:.2f}  McFadden pseudo-R2={1-ll/ll0:.4f}  "
          f"LR chi2={2*(ll-ll0):.1f} df={len(nm)} p={chisq_sf(2*(ll-ll0), len(nm)):.3e}")
    print()

print("=" * 78)
print("CONDITION A: IS THE ERROR PATTERN EQUALLY CONVERGENT?")
print("=" * 78)


def agree(errs, key):
    by_q = collections.defaultdict(list)
    for c in errs:
        by_q[c["question_id"]].append(c[key])
    s = t = 0
    dist = collections.Counter()
    for v in by_q.values():
        dist[len(v)] += 1
        cnt = collections.Counter(v)
        s += sum(x * (x - 1) // 2 for x in cnt.values()); t += len(v) * (len(v) - 1) // 2
    return s, t, len(by_q), dist


sA, tA, iA, dA = agree(errsA, "A_selected")
sB, tB, iB, dB = agree(errsB, "B_selected")
print(f"  condition A: {len(errsA)} errors on {iA} items, agreement {sA}/{tA} = "
      f"{sA/tA:.3f}   #erring models per item {dict(sorted(dA.items()))}")
print(f"  condition B: {len(errsB)} errors on {iB} items, agreement {sB}/{tB} = "
      f"{sB/tB:.3f}   #erring models per item {dict(sorted(dB.items()))}")
NP = 20000; ge = 0
for _ in range(NP):
    fake = [{"question_id": c["question_id"], "A_selected": random.choice(surv(c["question_id"]))}
            for c in errsA]
    s, t, _, _ = agree(fake, "A_selected")
    if s / t >= sA / tA:
        ge += 1
print(f"  condition-A agreement permutation p (uniform over survivors) = {(ge+1)/(NP+1):.5f}")

print()
print("=" * 78)
print("ITEM-LEVEL: DOES A-ERROR COUNT PREDICT B-ERROR COUNT? (Spearman + perm)")
print("=" * 78)
items = sorted(set(c["question_id"] for c in cells))
ac = {q: 0 for q in items}; bc = {q: 0 for q in items}
for c in cells:
    ac[c["question_id"]] += 1 - c["A_correct"]
    bc[c["question_id"]] += 1 - c["B_correct"]
x = [ac[q] for q in items]; y = [bc[q] for q in items]


def rankit(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v); i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def pearson(a, b):
    n = len(a); ma = sum(a) / n; mb = sum(b) / n
    num = sum((p - ma) * (q - mb) for p, q in zip(a, b))
    da = math.sqrt(sum((p - ma) ** 2 for p in a)); db = math.sqrt(sum((q - mb) ** 2 for q in b))
    return num / (da * db)


rho = pearson(rankit(x), rankit(y))
NP = 20000; ge = 0
yy = list(y)
for _ in range(NP):
    random.shuffle(yy)
    if abs(pearson(rankit(x), rankit(yy))) >= abs(rho) - 1e-12:
        ge += 1
print(f"  Spearman rho(A errors/item, B errors/item) = {rho:.3f} over {len(items)} items, "
      f"permutation p={(ge+1)/(NP+1):.5f}")
print(f"  items with 0 A errors: {sum(1 for q in items if ac[q]==0)}; of those, "
      f"{sum(1 for q in items if ac[q]==0 and bc[q]>0)} pick up >=1 B error")
print(f"  items with >=1 A error: {sum(1 for q in items if ac[q]>0)}; of those, "
      f"{sum(1 for q in items if ac[q]>0 and bc[q]>0)} have >=1 B error")

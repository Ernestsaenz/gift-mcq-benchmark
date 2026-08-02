"""(iii) Is the A->B drop larger for harder items?

Difficulty is built from condition-A performance, which creates a CEILING
ARTIFACT: an item all 4 models got right in A can only stay level or fall, an
item all 4 got wrong can only stay level or rise.  So the naive contrast is
guaranteed to show "bigger drops on easy items" even under pure independence.
Both versions are computed:

  NAIVE   diff_A(i) = number of models correct in A (0..4), correlated with
          the same model's own A outcome  -> reported WITH a parametric null
          simulation that quantifies how much of the slope is artifact.

  LOMO    leave-one-model-out: for model m on item i, difficulty is the number
          of the OTHER models correct in A (0..3).  This is independent of
          model m's own A outcome, so the ceiling artifact is removed.
          Primary analysis.

  EFFORT  a difficulty score that never touches accuracy: the mean, over the
          OTHER reasoning models, of the z-scored log2 reasoning tokens spent
          in condition A.

Tests:
  * per-level rates with Clopper-Pearson exact binomial CIs
  * cluster bootstrap (208 clusters, percentile) on the slope of the drop
    against the difficulty level, and on the retention gradient
  * logistic regression MLE (own Newton-Raphson) B_correct ~ A_correct + diff
"""
import math, random
from collections import defaultdict
from mech_merge import load_merged
from mech_lib_effort import (MODELS, SHORT, mean, sd, median, pearson,
                             logistic_fit, cluster_bootstrap, boot_p_two_sided)
from mech_lib_effort import cp_ci as binom_exact_ci

rows = load_merged()

# ---------------------------------------------------------------- difficulty
byitem = defaultdict(list)
for r in rows:
    byitem[r["question_id"]].append(r)

for r in rows:
    peers = [x for x in byitem[r["question_id"]] if x["model"] != r["model"]]
    r["diff_all"] = sum(x["A_correct"] for x in byitem[r["question_id"]])
    r["n_all"] = len(byitem[r["question_id"]])
    r["lomo"] = sum(x["A_correct"] for x in peers)
    r["n_peers"] = len(peers)

# effort-based difficulty from the three reasoning models
REAS = [m for m in MODELS if m != "google/gemma-4-26b-a4b-it"]
zA = {}
for m in REAS:
    v = [math.log2(r["A_reason"] + 1) for r in rows if r["model"] == m]
    mu, s = mean(v), sd(v)
    for r in rows:
        if r["model"] == m:
            zA[(r["question_id"], m)] = (math.log2(r["A_reason"] + 1) - mu) / s
for r in rows:
    peers = [zA[(r["question_id"], m)] for m in REAS
             if m != r["model"] and (r["question_id"], m) in zA]
    r["effort_diff"] = mean(peers) if peers else float("nan")

print("=" * 104)
print("(iii) ITEM DIFFICULTY AND THE A->B DROP")
print("=" * 104)
print("Item difficulty distribution (models correct in A, out of 4):")
d = defaultdict(int)
for qid, rs in byitem.items():
    d[sum(x["A_correct"] for x in rs)] += 1
for k in sorted(d):
    print(f"   {k}/4 models correct in A : {d[k]:>4} items")

# -------------------------------------------------------------- NAIVE version
print()
print("-" * 104)
print("[NAIVE, artifact-prone]  item-level mean drop by number of models correct in A")
print("-" * 104)
print(f"{'diff_A':>7} {'items':>6} {'mean acc A':>11} {'mean acc B':>11} "
      f"{'mean drop':>10}")
lvl = defaultdict(list)
for qid, rs in byitem.items():
    k = sum(x["A_correct"] for x in rs)
    lvl[k].append((mean([x["A_correct"] for x in rs]),
                   mean([x["B_correct"] for x in rs])))
for k in sorted(lvl):
    v = lvl[k]
    a, b = mean([x[0] for x in v]), mean([x[1] for x in v])
    print(f"{k:>7} {len(v):>6} {a:>11.3f} {b:>11.3f} {a-b:>+10.3f}")


def naive_slope(rs):
    """OLS slope of item-level drop on diff_A, computed from cell rows."""
    bi = defaultdict(list)
    for r in rs:
        bi[(r["question_id"], id(r) // 10 ** 12 if False else r["question_id"])].append(r)
    xs, ys = [], []
    seen = defaultdict(list)
    for r in rs:
        seen[r["question_id"]].append(r)
    for qid, g in seen.items():
        k = sum(x["A_correct"] for x in g)
        xs.append(k)
        ys.append(mean([x["A_correct"] for x in g]) - mean([x["B_correct"] for x in g]))
    mx, my = mean(xs), mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else float("nan")


pt, lo, hi, reps = cluster_bootstrap(rows, naive_slope, B=3000, seed=61)
print(f"   OLS slope of item drop on diff_A = {pt:+.4f} per model-correct  "
      f"95% CI [{lo:+.4f},{hi:+.4f}] (cluster bootstrap)")

# parametric null: independent Bernoulli, NO item effects at all
rng = random.Random(7)
accA = {m: mean([r["A_correct"] for r in rows if r["model"] == m]) for m in MODELS}
accB = {m: mean([r["B_correct"] for r in rows if r["model"] == m]) for m in MODELS}
sims = []
for _ in range(2000):
    fake = []
    for r in rows:
        fake.append({"question_id": r["question_id"],
                     "A_correct": 1 if rng.random() < accA[r["model"]] else 0,
                     "B_correct": 1 if rng.random() < accB[r["model"]] else 0})
    sims.append(naive_slope(fake))
sims.sort()
print(f"   PARAMETRIC NULL simulation (2000 draws; every cell an independent")
print(f"   Bernoulli at its model's marginal rate, i.e. items are all equally")
print(f"   hard and A/B are unlinked):  expected slope = {mean(sims):+.4f} "
      f"[{sims[int(.025*len(sims))]:+.4f},{sims[int(.975*len(sims))]:+.4f}]")
print(f"   -> the naive gradient is essentially entirely a ceiling artifact.")

# --------------------------------------------------------------- LOMO version
print()
print("-" * 104)
print("[LOMO, clean]  model m's own A and B rates by how many of the OTHER 3")
print("models got the item right in A.  Exact Clopper-Pearson 95% CIs.")
print("-" * 104)
print(f"{'peers correct':>13} {'cells':>6} {'acc A':>7} {'acc A 95% CI':>18} "
      f"{'acc B':>7} {'acc B 95% CI':>18} {'drop':>8} {'retention':>10} "
      f"{'retention 95% CI':>20}")
g = defaultdict(list)
for r in rows:
    if r["n_peers"] == 3:
        g[r["lomo"]].append(r)
for k in sorted(g):
    rs = g[k]
    ka, kb, n = sum(r["A_correct"] for r in rs), sum(r["B_correct"] for r in rs), len(rs)
    ca, cb = binom_exact_ci(ka, n), binom_exact_ci(kb, n)
    keep = [r for r in rs if r["A_correct"] == 1]
    kk = sum(r["B_correct"] for r in keep)
    ck = binom_exact_ci(kk, len(keep)) if keep else (float("nan"),) * 2
    print(f"{k:>13} {n:>6} {ka/n:>7.3f} [{ca[0]:.3f},{ca[1]:.3f}]{'':>5} "
          f"{kb/n:>7.3f} [{cb[0]:.3f},{cb[1]:.3f}]{'':>5} {ka/n-kb/n:>+8.3f} "
          f"{(kk/len(keep) if keep else float('nan')):>10.3f} "
          f"[{ck[0]:.3f},{ck[1]:.3f}]{'':>5}")


def lomo_drop_slope(rs):
    rs = [r for r in rs if r["n_peers"] == 3]
    by = defaultdict(lambda: [0, 0, 0])
    for r in rs:
        s = by[r["lomo"]]
        s[0] += r["A_correct"]
        s[1] += r["B_correct"]
        s[2] += 1
    xs, ys, w = [], [], []
    for k, (a, b, n) in by.items():
        xs.append(k)
        ys.append((a - b) / n)
        w.append(n)
    if len(xs) < 2:
        return None
    mx = sum(x * ww for x, ww in zip(xs, w)) / sum(w)
    my = sum(y * ww for y, ww in zip(ys, w)) / sum(w)
    den = sum(ww * (x - mx) ** 2 for x, ww in zip(xs, w))
    if den == 0:
        return None
    return sum(ww * (x - mx) * (y - my) for x, y, ww in zip(xs, ys, w)) / den


def lomo_retention_slope(rs):
    rs = [r for r in rs if r["n_peers"] == 3 and r["A_correct"] == 1]
    by = defaultdict(lambda: [0, 0])
    for r in rs:
        s = by[r["lomo"]]
        s[0] += r["B_correct"]
        s[1] += 1
    xs, ys, w = [], [], []
    for k, (b, n) in by.items():
        xs.append(k)
        ys.append(b / n)
        w.append(n)
    if len(xs) < 2:
        return None
    mx = sum(x * ww for x, ww in zip(xs, w)) / sum(w)
    my = sum(y * ww for y, ww in zip(ys, w)) / sum(w)
    den = sum(ww * (x - mx) ** 2 for x, ww in zip(xs, w))
    if den == 0:
        return None
    return sum(ww * (x - mx) * (y - my) for x, y, ww in zip(xs, ys, w)) / den


pt, lo, hi, reps = cluster_bootstrap(rows, lomo_drop_slope, B=4000, seed=62)
print(f"\n   weighted OLS slope of DROP on peer-difficulty = {pt:+.4f} per peer-correct")
print(f"      95% CI [{lo:+.4f},{hi:+.4f}]  p_boot={boot_p_two_sided(reps,0.0):.4g} "
      f"(cluster bootstrap, 208 clusters, 4000 reps)")
pt2, lo2, hi2, reps2 = cluster_bootstrap(rows, lomo_retention_slope, B=4000, seed=63)
print(f"   weighted OLS slope of RETENTION (P(B ok | A ok)) on peer-difficulty = "
      f"{pt2:+.4f}")
print(f"      95% CI [{lo2:+.4f},{hi2:+.4f}]  p_boot={boot_p_two_sided(reps2,0.0):.4g}")
print("   RETENTION is the artifact-free statistic: it conditions on A_correct==1")
print("   and its predictor uses only the other three models.")

# per model
print()
print(f"{'model':<18} {'peers':>6} {'n(A=1)':>7} {'retention':>10} {'95% CI':>18}")
for m in MODELS:
    for k in range(4):
        rs = [r for r in rows if r["model"] == m and r["n_peers"] == 3
              and r["lomo"] == k and r["A_correct"] == 1]
        if not rs:
            continue
        kk = sum(r["B_correct"] for r in rs)
        ci = binom_exact_ci(kk, len(rs))
        print(f"{SHORT[m]:<18} {k:>6} {len(rs):>7} {kk/len(rs):>10.3f} "
              f"[{ci[0]:.3f},{ci[1]:.3f}]")

# ------------------------------------------------------------ logistic models
print()
print("-" * 104)
print("Logistic MLE (own Newton-Raphson), pooled over models with model dummies:")
print("  B_correct ~ 1 + A_correct + lomo_peers_correct + model dummies")
print("  Wald p from the inverse observed information; cluster-bootstrap CI too.")
print("-" * 104)
sub = [r for r in rows if r["n_peers"] == 3]
mods = MODELS[1:]


def design(rs):
    X, y = [], []
    for r in rs:
        row = [float(r["A_correct"]), float(r["lomo"])]
        row += [1.0 if r["model"] == mm else 0.0 for mm in mods]
        X.append(row)
        y.append(float(r["B_correct"]))
    return X, y


X, y = design(sub)
b, se = logistic_fit(X, y)
names = ["intercept", "A_correct", "lomo_peers"] + [SHORT[mm] for mm in mods]
for i, nm in enumerate(names):
    z = b[i] / se[i]
    print(f"   {nm:<20} b={b[i]:>+8.4f}  se={se[i]:.4f}  "
          f"OR={math.exp(b[i]):>6.3f}  p_wald={math.erfc(abs(z)/math.sqrt(2)):.4g}")


def coef_lomo(rs):
    XX, yy = design(rs)
    if len(set(yy)) < 2:
        return None
    bb, _ = logistic_fit(XX, yy)
    return None if bb is None else bb[2]


_, clo, chi, creps = cluster_bootstrap(sub, coef_lomo, B=2000, seed=64)
print(f"   lomo_peers cluster-bootstrap 95% CI [{clo:+.4f},{chi:+.4f}]  "
      f"p_boot={boot_p_two_sided(creps,0.0):.4g}")

# ------------------------------------------------------- effort difficulty
print()
print("-" * 104)
print("[EFFORT difficulty]  difficulty measured by how much the OTHER reasoning")
print("models thought in condition A (mean z of log2 reasoning tokens).")
print("Retention P(B ok | A ok) by tercile of that score.")
print("-" * 104)
sub2 = [r for r in rows if r["A_correct"] == 1 and r["effort_diff"] == r["effort_diff"]]
vals = sorted(r["effort_diff"] for r in sub2)
t1, t2 = vals[len(vals) // 3], vals[2 * len(vals) // 3]
print(f"{'tercile of peer effort':>24} {'n':>6} {'retention':>10} {'95% CI':>18}")
for lab, sel in (("low (least thinking)", lambda v: v <= t1),
                 ("mid", lambda v: t1 < v <= t2),
                 ("high (most thinking)", lambda v: v > t2)):
    rs = [r for r in sub2 if sel(r["effort_diff"])]
    kk = sum(r["B_correct"] for r in rs)
    ci = binom_exact_ci(kk, len(rs))
    print(f"{lab:>24} {len(rs):>6} {kk/len(rs):>10.3f} [{ci[0]:.3f},{ci[1]:.3f}]")


def eff_coef(rs):
    rs = [r for r in rs if r["A_correct"] == 1 and r["effort_diff"] == r["effort_diff"]]
    XX = [[r["effort_diff"]] + [1.0 if r["model"] == mm else 0.0 for mm in mods]
          for r in rs]
    yy = [float(r["B_correct"]) for r in rs]
    if len(set(yy)) < 2:
        return None
    bb, _ = logistic_fit(XX, yy)
    return None if bb is None else bb[1]


rs0 = [r for r in rows if r["A_correct"] == 1 and r["effort_diff"] == r["effort_diff"]]
XX = [[r["effort_diff"]] + [1.0 if r["model"] == mm else 0.0 for mm in mods] for r in rs0]
yy = [float(r["B_correct"]) for r in rs0]
bb, sse = logistic_fit(XX, yy)
zz = bb[1] / sse[1]
_, elo, ehi, ereps = cluster_bootstrap(rows, eff_coef, B=2000, seed=65)
print(f"   logistic B_correct ~ peer_effort + model dummies (A_correct==1 only):")
print(f"      b(peer effort, per 1 SD) = {bb[1]:+.4f}  OR={math.exp(bb[1]):.3f}  "
      f"p_wald={math.erfc(abs(zz)/math.sqrt(2)):.4g}  "
      f"cluster-boot 95% CI [{elo:+.4f},{ehi:+.4f}]  p_boot={boot_p_two_sided(ereps,0.0):.4g}")

# ---------------------------------------------- gains on items model got wrong
print()
print("-" * 104)
print("The other half of the picture: items the model got WRONG in A")
print("-" * 104)
print(f"{'model':<18} {'n(A=0)':>7} {'P(B correct | A wrong)':>23} {'95% CI':>18} "
      f"{'P(B ok | A ok)':>15}")
for m in MODELS:
    rs = [r for r in rows if r["model"] == m and r["A_correct"] == 0]
    kk = sum(r["B_correct"] for r in rs)
    ci = binom_exact_ci(kk, len(rs))
    rk = [r for r in rows if r["model"] == m and r["A_correct"] == 1]
    print(f"{SHORT[m]:<18} {len(rs):>7} {kk/len(rs):>23.3f} "
          f"[{ci[0]:.3f},{ci[1]:.3f}]{'':>5} "
          f"{mean([r['B_correct'] for r in rk]):>15.3f}")

"""Final combined model for the effort/difficulty topic.

Outcome: retention, B_correct among cells with A_correct == 1 (artifact-free).
Predictors, all measurable BEFORE the swap:
   own_effort_A   z(log2 reasoning tokens the model itself spent in A)
   peer_effort_A  mean z(log2 reasoning tokens the OTHER reasoning models spent in A)
   peer_acc_A     number of the other 3 models correct in A (0..3)
   model dummies

Question: does item difficulty still predict the drop once the model's own
condition-A effort is controlled, and which difficulty signal is stronger?

Logistic MLE, own Newton-Raphson; Wald p from the inverse observed
information; cluster bootstrap (208 clusters, 2000 reps, percentile) 95% CIs.
gemma-4-26b is excluded from own_effort models (it emits no reasoning tokens).
"""
import math
from collections import defaultdict
from mech_merge import load_merged
from mech_lib_effort import (MODELS, SHORT, mean, sd, logistic_fit,
                             cluster_bootstrap, boot_p_two_sided, cp_ci)

rows = load_merged()
REAS = [m for m in MODELS if m != "google/gemma-4-26b-a4b-it"]

byitem = defaultdict(list)
for r in rows:
    byitem[r["question_id"]].append(r)

zA = {}
for m in REAS:
    v = [math.log2(r["A_reason"] + 1) for r in rows if r["model"] == m]
    mu, s = mean(v), sd(v)
    for r in rows:
        if r["model"] == m:
            zA[(r["question_id"], m)] = (math.log2(r["A_reason"] + 1) - mu) / s

for r in rows:
    peers = [x for x in byitem[r["question_id"]] if x["model"] != r["model"]]
    r["peer_acc"] = sum(x["A_correct"] for x in peers)
    r["n_peers"] = len(peers)
    pz = [zA[(r["question_id"], m)] for m in REAS
          if m != r["model"] and (r["question_id"], m) in zA]
    r["peer_eff"] = mean(pz) if pz else float("nan")
    r["own_eff"] = zA.get((r["question_id"], r["model"]), float("nan"))

sub = [r for r in rows if r["A_correct"] == 1 and r["n_peers"] == 3
       and r["peer_eff"] == r["peer_eff"] and r["own_eff"] == r["own_eff"]]
mods = [m for m in REAS[1:]]

print("=" * 100)
print("COMBINED RETENTION MODEL  (reasoning models only, A_correct == 1)")
print(f"n = {len(sub)} cells")
print("=" * 100)

SPECS = [
    ("peer_acc only",            ["peer_acc"]),
    ("peer_effort only",         ["peer_eff"]),
    ("own_effort only",          ["own_eff"]),
    ("peer_acc + peer_effort",   ["peer_acc", "peer_eff"]),
    ("own + peer effort",        ["own_eff", "peer_eff"]),
    ("all three",                ["peer_acc", "peer_eff", "own_eff"]),
]


def design(rs, cols):
    X = [[float(r[c]) for c in cols]
         + [1.0 if r["model"] == mm else 0.0 for mm in mods] for r in rs]
    y = [float(r["B_correct"]) for r in rs]
    return X, y


for label, cols in SPECS:
    X, y = design(sub, cols)
    b, se = logistic_fit(X, y)
    print(f"\n  [{label}]")
    for i, c in enumerate(cols):
        z = b[i + 1] / se[i + 1]

        def coef(rs, cc=cols, ii=i + 1):
            rs = [r for r in rs if r["A_correct"] == 1 and r["n_peers"] == 3
                  and r["peer_eff"] == r["peer_eff"] and r["own_eff"] == r["own_eff"]]
            XX, yy = design(rs, cc)
            if len(set(yy)) < 2:
                return None
            bb, _ = logistic_fit(XX, yy)
            return None if bb is None else bb[ii]

        _, lo, hi, reps = cluster_bootstrap(rows, coef, B=1500, seed=80 + i)
        print(f"     {c:<12} b={b[i+1]:>+7.4f}  OR={math.exp(b[i+1]):>5.3f}  "
              f"p_wald={math.erfc(abs(z)/math.sqrt(2)):>9.4g}  "
              f"cluster-boot 95% CI [{lo:>+7.4f},{hi:>+7.4f}]  "
              f"p_boot={boot_p_two_sided(reps,0.0):.4g}")

print()
print("=" * 100)
print("2x2 cross-tab of retention: peer accuracy x peer effort (median splits)")
print("=" * 100)
med_eff = sorted(r["peer_eff"] for r in sub)[len(sub) // 2]
print(f"{'peer_acc':<12} {'peer effort':<16} {'n':>5} {'retention':>10} {'95% CI':>18}")
for pa in ("<=2 (harder)", "=3 (easier)"):
    for pe in ("low", "high"):
        rs = [r for r in sub
              if ((r["peer_acc"] <= 2) if pa.startswith("<=") else (r["peer_acc"] == 3))
              and ((r["peer_eff"] <= med_eff) if pe == "low" else (r["peer_eff"] > med_eff))]
        if not rs:
            continue
        k = sum(r["B_correct"] for r in rs)
        ci = cp_ci(k, len(rs))
        print(f"{pa:<12} {pe:<16} {len(rs):>5} {k/len(rs):>10.3f} "
              f"[{ci[0]:.3f},{ci[1]:.3f}]")

print()
print("=" * 100)
print("Effort spent in A on the cells the model LOST vs KEPT (reasoning models)")
print("=" * 100)
from mech_lib_effort import median, quantile
print(f"{'model':<18} {'kept: med A_reason':>19} {'lost: med A_reason':>19} "
      f"{'ratio':>7} {'kept: med B_reason':>19} {'lost: med B_reason':>19}")
for m in REAS:
    rs = [r for r in rows if r["model"] == m and r["A_correct"] == 1]
    kept = [r for r in rs if r["B_correct"] == 1]
    lost = [r for r in rs if r["B_correct"] == 0]
    print(f"{SHORT[m]:<18} {median([r['A_reason'] for r in kept]):>19.0f} "
          f"{median([r['A_reason'] for r in lost]):>19.0f} "
          f"{median([r['A_reason'] for r in lost])/median([r['A_reason'] for r in kept]):>7.2f} "
          f"{median([r['B_reason'] for r in kept]):>19.0f} "
          f"{median([r['B_reason'] for r in lost]):>19.0f}")

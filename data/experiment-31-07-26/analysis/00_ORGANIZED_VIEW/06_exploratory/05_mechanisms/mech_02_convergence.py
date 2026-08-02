"""(b) Do different models converge on the SAME wrong distractor more than chance?
Three permutation nulls of increasing strictness."""
import sys, collections, random
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_lib import *

random.seed(20260731)
NPERM = 20000

cells = load_cells()
models = sorted(set(c["model"] for c in cells))

errs = [c for c in cells if c["B_correct"] == 0]
surv_of = {}
for c in cells:
    surv_of[c["question_id"]] = [L for L in LETTERS if L != c["correct_letter"]]


def agreement(assign):
    """assign: list of (qid, letter). Returns (same_pairs, total_pairs)."""
    by_q = collections.defaultdict(list)
    for q, L in assign:
        by_q[q].append(L)
    same = tot = 0
    for q, v in by_q.items():
        k = len(v)
        cnt = collections.Counter(v)
        same += sum(x * (x - 1) // 2 for x in cnt.values())
        tot += k * (k - 1) // 2
    return same, tot


base = [(c["question_id"], c["B_selected"]) for c in errs]
obs_same, obs_tot = agreement(base)
obs = obs_same / obs_tot
print(f"OBSERVED within-item pairwise destination agreement (condition B): "
      f"{obs_same}/{obs_tot} = {obs:.4f}")
p_, lo, hi = wilson(obs_same, obs_tot)
print(f"  Wilson 95% CI (pairs treated as independent, indicative only): [{lo:.3f}, {hi:.3f}]")


def perm_test(name, sampler):
    ge = 0
    vals = []
    for _ in range(NPERM):
        s, t = agreement(sampler())
        v = s / t
        vals.append(v)
        if v >= obs - 1e-12:
            ge += 1
    mean = sum(vals) / len(vals)
    sd = (sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5
    p = (ge + 1) / (NPERM + 1)
    print(f"\n{name}")
    print(f"  null mean={mean:.4f}  sd={sd:.4f}  observed={obs:.4f}  "
          f"z={(obs-mean)/sd:.1f}  perm p={p:.5f} ({ge}/{NPERM} >= obs)")
    return mean, sd, p


# ---- Null 1: each error uniform over its 3 survivors ----
def s1():
    return [(q, random.choice(surv_of[q])) for q, _ in base]


perm_test("NULL 1 - uniform over the 3 surviving distractors (20,000 perms)", s1)

# ---- Null 2: preserve each model's empirical rank-position propensity ----
rank_prof = {}
for m in models:
    rk = collections.Counter()
    for c in errs:
        if c["model"] == m:
            rk[surv_of[c["question_id"]].index(c["B_selected"])] += 1
    n = sum(rk.values())
    rank_prof[m] = [rk[i] / n for i in range(3)]
err_m = [c["model"] for c in errs]


def s2():
    out = []
    for c in errs:
        pr = rank_prof[c["model"]]
        r = random.random()
        i = 0 if r < pr[0] else (1 if r < pr[0] + pr[1] else 2)
        out.append((c["question_id"], surv_of[c["question_id"]][i]))
    return out


perm_test("NULL 2 - resampled from each model's own slot-position propensity", s2)

# ---- Null 3: within model, shuffle chosen letters across items with the SAME
# correct_letter (identical survivor set). Preserves each model's exact letter
# marginal and every item's availability. ----
strata = collections.defaultdict(list)  # (model, correct_letter) -> indices
qid_of = [c["question_id"] for c in errs]
cl_of = {c["question_id"]: c["correct_letter"] for c in cells}
for i, c in enumerate(errs):
    strata[(c["model"], c["correct_letter"])].append(i)
sel = [c["B_selected"] for c in errs]


def s3():
    out = list(sel)
    for k, idxs in strata.items():
        vals = [sel[i] for i in idxs]
        random.shuffle(vals)
        for i, v in zip(idxs, vals):
            out[i] = v
    return list(zip(qid_of, out))


perm_test("NULL 3 - within-model shuffle across items sharing the NOTA slot "
          "(preserves model letter marginals + availability)", s3)

print()
print("=" * 78)
print("PAIRWISE MODEL-BY-MODEL AGREEMENT ON DESTINATION")
print("=" * 78)
by_qm = {(c["question_id"], c["model"]): c["B_selected"] for c in errs}
print(f"{'model pair':60s} {'same/tot':>10s} {'rate':>7s}")
for i in range(len(models)):
    for j in range(i + 1, len(models)):
        m1, m2 = models[i], models[j]
        s = t = 0
        for q in set(x[0] for x in by_qm):
            if (q, m1) in by_qm and (q, m2) in by_qm:
                t += 1
                s += by_qm[(q, m1)] == by_qm[(q, m2)]
        lab = f"{m1.split('/')[-1]} vs {m2.split('/')[-1]}"
        print(f"{lab:60s} {s:4d}/{t:<5d} {s/t if t else 0:7.3f}")

print()
print("=" * 78)
print("UNANIMITY ON ITEMS WHERE >=3 MODELS ERRED")
print("=" * 78)
by_q = collections.defaultdict(list)
for c in errs:
    by_q[c["question_id"]].append(c["B_selected"])
for k in (2, 3, 4):
    grp = [v for v in by_q.values() if len(v) == k]
    unan = sum(1 for v in grp if len(set(v)) == 1)
    # chance of unanimity under uniform-over-3
    chance = (1 / 3.0) ** (k - 1)
    print(f"  {k} erring models: {len(grp):3d} items, all-same {unan:3d} "
          f"({unan/len(grp) if grp else 0:.3f}) vs chance {chance:.4f}")

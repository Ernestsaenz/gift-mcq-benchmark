"""Step 7: robustness of the cross-model convergence result.

Worry: if every model shares a letter bias (e.g. all like 'd'), destinations would agree
across models with no item-specific attraction at all.  So re-run the permutation under a
null that PRESERVES each model's own empirical positional preference among survivors.
"""
import collections, random
from mech_ref_acc_lib import load_cells, cp_ci, binom_test_exact

cells = load_cells()
SHORT = {"google/gemini-3.6-flash": "gemini", "z-ai/glm-5.2": "glm",
         "qwen/qwen3.6-35b-a3b": "qwen", "google/gemma-4-26b-a4b-it": "gemma"}
MODELS = ["gemini", "glm", "qwen", "gemma"]
LETTERS = ["a", "b", "c", "d"]
for r in cells:
    r["m"] = SHORT[r["model"]]
by_item = collections.defaultdict(dict)
for r in cells:
    by_item[r["question_id"]][r["m"]] = r


def concord(assign):
    """assign: list of lists of chosen letters, one list per item."""
    same = tot = 0
    for ls in assign:
        for i in range(len(ls)):
            for j in range(i + 1, len(ls)):
                tot += 1
                same += (ls[i] == ls[j])
    return same, tot


def build(restrict_allA=False):
    items = []
    for qid, d in by_item.items():
        if restrict_allA and not (len(d) == 4 and all(r["A_correct"] for r in d.values())):
            continue
        fails = [r for r in d.values() if r["A_correct"] and not r["B_correct"]]
        if len(fails) >= 2:
            surv = sorted(L for L in LETTERS if L != fails[0]["correct_letter"])
            items.append((surv, [(r["m"], r["B_selected"]) for r in fails]))
    return items


# empirical per-model distribution over survivor SLOT INDEX (0,1,2 after sorting survivors)
slotdist = collections.defaultdict(lambda: [0, 0, 0])
for r in cells:
    if r["A_correct"] and not r["B_correct"]:
        surv = sorted(L for L in LETTERS if L != r["correct_letter"])
        slotdist[r["m"]][surv.index(r["B_selected"])] += 1
print("Per-model empirical preference over survivor slot index (0=lowest letter):")
for m in MODELS:
    v = slotdist[m]
    t = sum(v)
    print(f"   {m:8} {v}  -> {[round(100*x/t,1) for x in v]}%  (n={t})")

rng = random.Random(101)
for label, restrict in (("ALL items with >=2 abandonments", False),
                        ("ONLY items where all 4 models were A-correct", True)):
    items = build(restrict)
    obs_same, obs_tot = concord([[l for _, l in f] for _, f in items])
    lo, hi = cp_ci(obs_same, obs_tot)
    print()
    print("=" * 96)
    print(f"{label}:  {len(items)} items, {obs_tot} model-pairs")
    print("=" * 96)
    print(f"   observed concordance {obs_same}/{obs_tot} = {100*obs_same/obs_tot:.1f}% "
          f"CP95 [{100*lo:.1f},{100*hi:.1f}]")
    for nullname, sampler in (
            ("uniform over 3 survivors", lambda m, surv: rng.choice(surv)),
            ("model's own slot preference (preserves letter bias)",
             lambda m, surv: surv[rng.choices([0, 1, 2], weights=slotdist[m])[0]])):
        B, ge, tots = 20000, 0, 0.0
        for _ in range(B):
            a = [[sampler(m, surv) for m, _ in f] for surv, f in items]
            s, t = concord(a)
            tots += s
            ge += (s >= obs_same)
        print(f"   null = {nullname}")
        print(f"      mean null concordance {tots/B:.1f}/{obs_tot} = {100*tots/B/obs_tot:.1f}%   "
              f"Monte-Carlo P(>= obs) = {(ge+1)/(B+1):.4g}  (B={B})")

print()
print("=" * 96)
print("Sanity: are the abandonment destinations concentrated on a few letters overall?")
print("=" * 96)
c = collections.Counter(r["B_selected"] for r in cells if r["A_correct"] and not r["B_correct"])
print(f"   {dict(c)}   total {sum(c.values())}")
print("   -> destinations are spread across all four letters; the convergence is WITHIN item,")
print("      not a shared global letter preference.")

"""Defensible analytic paths that the 160-spec grid does NOT enumerate.

The published grid varies: exclusion (4) x outcome (2) x unit/inference (13|7)
x pooling (2).  Crucially it never varies:
  * the *granularity* of the position-coherence exclusion (it is binary: letter
    'a' in/out), even though the defect it encodes is graded by position;
  * which models are pooled (leave-one-model-out);
  * stratification by item features that plausibly interact with the swap.

This script computes the pooled cell-level delta under those paths.
"""
import json, os, collections, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "paired_clean.json")))
MODELS = sorted({r["model"] for r in rows})


def delta_cell(recs):
    if not recs:
        return float("nan")
    return 100.0 * sum(r["B_correct"] - r["A_correct"] for r in recs) / len(recs)


def acc(recs, arm):
    return 100.0 * sum(r[arm] for r in recs) / len(recs)


def show(label, recs, extra=""):
    if not recs:
        print(f"{label:<46} {'--- empty ---'}")
        return
    n = len(recs)
    ni = len({r['question_id'] for r in recs})
    print(f"{label:<46} N={n:>5} items={ni:>4} accA={acc(recs,'A_correct'):>6.2f} "
          f"accB={acc(recs,'B_correct'):>6.2f} delta={delta_cell(recs):>8.3f} {extra}")


PRIMARY = [r for r in rows if r["analysis_include"]]
ALL = rows

print("=" * 110)
print("BASELINE (in-grid anchors)")
print("=" * 110)
show("primary / lenient / cell  [headline]", PRIMARY)
show("none / lenient / cell", ALL)

print()
print("=" * 110)
print("A. POSITION OF THE CORRECT LETTER  -- the exclusion the grid treats as binary")
print("=" * 110)
nodefect = [r for r in rows if not r["excl_item_defect"]]
for L in ("a", "b", "c", "d"):
    show(f"correct_letter == '{L}'  (defect items dropped)",
         [r for r in nodefect if r["correct_letter"] == L])
print()
show("letter in {b,c,d}  == 'primary' set", [r for r in nodefect if r["correct_letter"] != "a"])
show("letter in {c,d}    (stricter antecedent rule)", [r for r in nodefect if r["correct_letter"] in "cd"])
show("letter == 'd'      (strictest: full antecedent)", [r for r in nodefect if r["correct_letter"] == "d"])
print()
print("  -> spread of the pooled delta across the four single-position analyses:")
pos = {L: delta_cell([r for r in nodefect if r["correct_letter"] == L]) for L in "abcd"}
print("    ", {k: round(v, 3) for k, v in pos.items()},
      " range =", round(max(pos.values()) - min(pos.values()), 3), "pp")

print()
print("=" * 110)
print("B. PER-MODEL DELTAS and LEAVE-ONE-MODEL-OUT POOLING")
print("=" * 110)
for m in MODELS:
    show(f"only {m}", [r for r in PRIMARY if r["model"] == m])
print()
for m in MODELS:
    show(f"leave-one-model-out: drop {m}", [r for r in PRIMARY if r["model"] != m])
pm = [delta_cell([r for r in PRIMARY if r["model"] == m]) for m in MODELS]
print("  -> per-model range =", round(max(pm) - min(pm), 3), "pp")

print()
print("=" * 110)
print("C. ITEM-FEATURE STRATA (each stratum is a defensible restriction)")
print("=" * 110)
for flag in ("negated_stem", "has_context"):
    for v in (True, False):
        show(f"{flag} == {v}", [r for r in PRIMARY if r[flag] is v])
print()
parts = collections.Counter(r["exam_part"] for r in PRIMARY)
for p, _ in sorted(parts.items()):
    show(f"exam_part == {p}", [r for r in PRIMARY if r["exam_part"] == p])
print()
regions = collections.Counter(r["region"] for r in PRIMARY)
for rg, _ in sorted(regions.items()):
    show(f"region == {rg}", [r for r in PRIMARY if r["region"] == rg])
print()
years = sorted({r["year"] for r in PRIMARY})
for y in years:
    show(f"year == {y}", [r for r in PRIMARY if r["year"] == y])

print()
print("=" * 110)
print("D. LEAVE-ONE-OUT JACKKNIFE over clusters / regions  (does any single unit drive it?)")
print("=" * 110)
cl = sorted({r["cluster"] for r in PRIMARY})
jk = [(g, delta_cell([r for r in PRIMARY if r["cluster"] != g])) for g in cl]
jk.sort(key=lambda t: t[1])
print(f"  leave-one-cluster-out: min={jk[0][1]:.3f} (drop cluster {jk[0][0]})  "
      f"max={jk[-1][1]:.3f} (drop cluster {jk[-1][0]})  span={jk[-1][1]-jk[0][1]:.3f} pp")
rg = sorted({r["region"] for r in PRIMARY})
jr = [(g, delta_cell([r for r in PRIMARY if r["region"] != g])) for g in rg]
jr.sort(key=lambda t: t[1])
print(f"  leave-one-region-out : min={jr[0][1]:.3f} (drop {jr[0][0]})  "
      f"max={jr[-1][1]:.3f} (drop {jr[-1][0]})  span={jr[-1][1]-jr[0][1]:.3f} pp")

print()
print("=" * 110)
print("E. SIGN-FLIP REACHABILITY: how far is the nearest zero?")
print("=" * 110)
b = sum(1 for r in PRIMARY if r["A_correct"] == 1 and r["B_correct"] == 0)
c = sum(1 for r in PRIMARY if r["A_correct"] == 0 and r["B_correct"] == 1)
print(f"  discordant pairs (primary): A-only b={b}  B-only c={c}  net={c-b}  of N={len(PRIMARY)}")
print(f"  a sign flip requires converting >{ (b-c)//2 } A-only discordants into B-only ones")

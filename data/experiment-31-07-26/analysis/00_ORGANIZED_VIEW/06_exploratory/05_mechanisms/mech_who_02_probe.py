"""Mechanism probes: where the lost answers go, stickiness, lure concentration, tokens."""
import collections, math
from mech_who_00_build import cells

L4 = "abcd"

def mean(v): return sum(v) / len(v) if v else float("nan")
def sd(v):
    m = mean(v); return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1)) if len(v) > 1 else float("nan")
def welch(x, y):
    mx, my, nx, ny = mean(x), mean(y), len(x), len(y)
    vx, vy = sd(x) ** 2, sd(y) ** 2
    se = math.sqrt(vx / nx + vy / ny)
    t = (mx - my) / se
    df = (vx / nx + vy / ny) ** 2 / ((vx / nx) ** 2 / (nx - 1) + (vy / ny) ** 2 / (ny - 1))
    # two-sided p via normal approx on t with df (df is large here); use incomplete beta by series
    return mx, my, t, df, 2 * (1 - _tcdf(abs(t), df))
def _tcdf(t, df):
    x = df / (df + t * t)
    return 1 - 0.5 * _ibeta(df / 2, 0.5, x)
def _ibeta(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    f, c, d = 1.0, 1.0, 0.0
    for i in range(0, 300):
        m = i // 2
        if i == 0: num = 1.0
        elif i % 2 == 0: num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else: num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1 + num * d
        d = 1 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1 + num / (c if abs(c) > 1e-30 else 1e-30)
        f *= c * d
        if abs(1 - c * d) < 1e-12: break
    if x < (a + 1) / (a + b + 2):
        return front * (f - 1)
    return 1 - _ibeta(b, a, 1 - x)

print("=" * 78)
print("P1. POSITION OF THE CHOSEN OPTION (is there a slot bias in B?)")
Adist = collections.Counter(r["A_selected"] for r in cells)
Bdist = collections.Counter(r["B_selected"] for r in cells)
print("   A_selected:", {k: Adist[k] for k in L4}, " (correct_letter never 'a')")
print("   B_selected:", {k: Bdist[k] for k in L4})
# restrict to the distractor slots only (i.e. exclude the NOTA/correct slot)
Awd = collections.Counter(r["A_selected"] for r in cells if not r["A_correct"])
Bwd = collections.Counter(r["B_selected"] for r in cells if not r["B_correct"])
print("   among A-WRONG cells (n=%d) the chosen distractor:" % sum(Awd.values()),
      {k: Awd[k] for k in L4})
print("   among B-WRONG cells (n=%d) the chosen distractor:" % sum(Bwd.values()),
      {k: Bwd[k] for k in L4})
# availability-corrected: 'a' is a distractor in 100% of items, b/c/d only when != correct_letter
avail_A = collections.Counter()
for r in cells:
    for L in L4:
        if L != r["correct_letter"]: avail_A[L] += 1
print("   slot availability as a distractor (per condition, n cells):", dict(avail_A))
print("   pick-rate per available distractor slot:")
for L in L4:
    print(f"     {L}:  A-wrong {Awd[L]}/{avail_A[L]}={Awd[L]/avail_A[L]:.4f}   "
          f"B-wrong {Bwd[L]}/{avail_A[L]}={Bwd[L]/avail_A[L]:.4f}   "
          f"ratio {Bwd[L]/max(Awd[L],1e-9)/1.0:.2f}x")

print()
print("=" * 78)
print("P2. STICKINESS: among A-WRONG cells, does B keep the same wrong letter?")
aw = [r for r in cells if not r["A_correct"]]
same = sum(1 for r in aw if r["B_selected"] == r["A_selected"])
tonota = sum(1 for r in aw if r["B_correct"])
other = len(aw) - same - tonota
print(f"   n={len(aw)}:  kept same distractor {same} ({same/len(aw):.3f}), "
      f"switched to NOTA {tonota} ({tonota/len(aw):.3f}), "
      f"switched to a different distractor {other} ({other/len(aw):.3f})")
print("   -> among the A-wrong cells that stayed wrong (n=%d), %d/%d kept the identical letter"
      % (len(aw) - tonota, same, len(aw) - tonota))

print()
print("=" * 78)
print("P3. LURE CONCENTRATION: when models are wrong, do they converge on ONE distractor?")
def conc(field, cond):
    """per item, over the models wrong in that condition, prob two random wrong models agree"""
    byitem = collections.defaultdict(list)
    for r in cells:
        if not r[cond]:
            byitem[r["question_id"]].append(r[field])
    num = den = 0
    for q, v in byitem.items():
        if len(v) < 2: continue
        c = collections.Counter(v)
        pairs = len(v) * (len(v) - 1) / 2
        agree = sum(x * (x - 1) / 2 for x in c.values())
        num += agree; den += pairs
    return num, den, num / den if den else float("nan")
for field, cond, lab in (("A_selected", "A_correct", "condition A"),
                         ("B_selected", "B_correct", "condition B")):
    n, d, p = conc(field, cond)
    print(f"   {lab}: P(two wrong models pick the SAME distractor) = {n:.0f}/{d:.0f} = {p:.3f} "
          f"(chance with 3 distractors = 0.333)")

print()
print("=" * 78)
print("P4. LOST cells: is the B-choice the item's dominant lure? (leave-one-out)")
# lure = for item q and condition B, which distractor did the OTHER models pick when wrong
hit = tot = 0
for r in cells:
    if not r["lost"]: continue
    peers = collections.Counter(x["B_selected"] for x in cells
                                if x["question_id"] == r["question_id"] and x["model"] != r["model"]
                                and not x["B_correct"])
    if not peers: continue
    top = peers.most_common(1)[0][0]
    tot += 1; hit += int(r["B_selected"] == top)
print(f"   lost cells with >=1 peer also wrong in B: {tot}; B-choice == peers' modal lure: "
      f"{hit} = {hit/tot:.3f}  (chance ~0.333-0.5)")

print()
print("=" * 78)
print("P5. TOKENS / LATENCY by outcome cell")
groups = {"A+B+ (kept)": [r for r in cells if r["A_correct"] and r["B_correct"]],
          "A+B- (lost)": [r for r in cells if r["lost"]],
          "A-B+ (gained)": [r for r in cells if r["gained"]],
          "A-B- (both wrong)": [r for r in cells if not r["A_correct"] and not r["B_correct"]]}
print(f"   {'group':<20}{'n':>5}{'A_tok':>9}{'B_tok':>9}{'B-A':>9}{'B/A':>7}")
for g, rows in groups.items():
    at = [r["A_tokens"] for r in rows]; bt = [r["B_tokens"] for r in rows]
    print(f"   {g:<20}{len(rows):>5}{mean(at):>9.0f}{mean(bt):>9.0f}"
          f"{mean(bt)-mean(at):>9.0f}{mean(bt)/mean(at):>7.2f}")
print("   Welch t-test, A_tokens: lost vs kept (per model, and pooled):")
x = [r["A_tokens"] for r in groups["A+B- (lost)"]]; y = [r["A_tokens"] for r in groups["A+B+ (kept)"]]
mx, my, t, df, p = welch(x, y)
print(f"     pooled  lost {mx:.0f} vs kept {my:.0f}  t={t:.2f} df={df:.0f} p={p:.4f}")
for m in sorted(set(r["model"] for r in cells)):
    x = [r["A_tokens"] for r in groups["A+B- (lost)"] if r["model"] == m]
    y = [r["A_tokens"] for r in groups["A+B+ (kept)"] if r["model"] == m]
    mx, my, t, df, p = welch(x, y)
    print(f"     {m:<28} lost {mx:.0f} (n={len(x)}) vs kept {my:.0f} (n={len(y)})  t={t:.2f} p={p:.4f}")
print("   Welch t-test, B_tokens: lost vs kept (pooled):")
x = [r["B_tokens"] for r in groups["A+B- (lost)"]]; y = [r["B_tokens"] for r in groups["A+B+ (kept)"]]
mx, my, t, df, p = welch(x, y)
print(f"     lost {mx:.0f} vs kept {my:.0f}  t={t:.2f} df={df:.0f} p={p:.4f}")
print("   Welch t-test, B_tokens among A-WRONG cells: gained vs stayed-wrong:")
x = [r["B_tokens"] for r in groups["A-B+ (gained)"]]; y = [r["B_tokens"] for r in groups["A-B- (both wrong)"]]
mx, my, t, df, p = welch(x, y)
print(f"     gained {mx:.0f} vs stayed {my:.0f}  t={t:.2f} df={df:.0f} p={p:.4f}")

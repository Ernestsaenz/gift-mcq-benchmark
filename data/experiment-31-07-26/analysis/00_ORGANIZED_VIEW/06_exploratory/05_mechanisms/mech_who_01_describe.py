"""Descriptive characterisation of the lost / gained discordant sets."""
import collections, math, json
from mech_who_00_build import cells, items

def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"),) * 3
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, c - h, c + h

print("=" * 78)
print("1. 2x2 PAIRED TABLE (all 1299 cells)")
n11 = sum(1 for r in cells if r["A_correct"] and r["B_correct"])
n10 = sum(1 for r in cells if r["A_correct"] and not r["B_correct"])
n01 = sum(1 for r in cells if not r["A_correct"] and r["B_correct"])
n00 = sum(1 for r in cells if not r["A_correct"] and not r["B_correct"])
print(f"  A+B+ {n11}   A+B- (LOST) {n10}   A-B+ (GAINED) {n01}   A-B- {n00}")
print(f"  A acc {(n11+n10)/len(cells):.4f}  B acc {(n11+n01)/len(cells):.4f}  "
      f"delta {(n01-n10)/len(cells):+.4f}")
print(f"  P(lost | A correct)  = {n10}/{n10+n11} = {n10/(n10+n11):.4f}")
print(f"  P(gained | A wrong)  = {n01}/{n01+n00} = {n01/(n01+n00):.4f}")
# exact McNemar (binomial, two-sided)
n = n10 + n01
p2 = 2 * sum(math.comb(n, k) * 0.5 ** n for k in range(min(n10, n01) + 1))
print(f"  exact McNemar (two-sided binomial on {n} discordant): p = {min(1.0,p2):.3e}")

print()
print("=" * 78)
print("2. WHERE DOES THE LOST SET GO?  (B_selected among lost cells)")
lost = [r for r in cells if r["lost"]]
gained = [r for r in cells if r["gained"]]
both_wrong = [r for r in cells if not r["A_correct"] and not r["B_correct"]]
print(f"  lost n={len(lost)}  gained n={len(gained)}  both-wrong n={len(both_wrong)}")
# offset of chosen letter relative to the NOTA slot
def off(r, f):
    return "abcd".index(r[f]) - "abcd".index(r["correct_letter"])
print("  lost: B_selected letter dist:", dict(collections.Counter(r["B_selected"] for r in lost)))
print("  lost: B_selected offset from NOTA slot:",
      dict(sorted(collections.Counter(off(r, "B_selected") for r in lost).items())))
# in A the lost cells were correct -> A_selected == correct_letter. what fraction of
# lost cells picked, in B, the option the model would rank 2nd? proxy: the distractor
# most often chosen in A by OTHER models on the same item
peer_wrong = collections.Counter()
for r in cells:
    if not r["A_correct"]:
        peer_wrong[(r["question_id"], r["A_selected"])] += 1
hit = tot = 0
for r in lost:
    cand = [(peer_wrong.get((r["question_id"], L), 0), L) for L in "abcd" if L != r["correct_letter"]]
    cand.sort(reverse=True)
    if cand[0][0] > 0:
        tot += 1
        hit += int(r["B_selected"] == cand[0][1])
print(f"  lost cells whose B choice == the distractor other models fell for in A: "
      f"{hit}/{tot} = {hit/tot:.3f} (chance ~1/3)")

print()
print("=" * 78)
print("3. WHAT DID THE GAINED SET DO IN A?")
print("  gained: A_selected offset from correct slot:",
      dict(sorted(collections.Counter(off(r, "A_selected") for r in gained).items())))
print("  gained by model:", dict(collections.Counter(r["model"] for r in gained)))

print()
print("=" * 78)
print("4. MARGINAL RATES BY FEATURE")

def show(name, keyfn, rows_num, rows_den_label):
    print(f"\n  -- {name} --   ({rows_den_label})")
    g = collections.defaultdict(lambda: [0, 0])
    for r in rows_num:
        k = keyfn(r)
        g[k][0] += r[OUT]; g[k][1] += 1
    for k in sorted(g, key=lambda x: (str(type(x)), x)):
        kk, nn = g[k]
        p, lo, hi = wilson(kk, nn)
        print(f"     {str(k):<28} {kk:4d}/{nn:4d} = {p:.3f}  [{lo:.3f},{hi:.3f}]")

qs = sorted(r["qlen"] for r in cells)
cs = sorted(r["correct_len"] for r in cells)
def _q(v, arr):
    n = len(arr)
    cuts = [arr[n // 4], arr[n // 2], arr[3 * n // 4]]
    return sum(v > c for c in cuts)
QQ = lambda v: f"Q{_q(v, qs)+1}"
CQ = lambda v: f"Q{_q(v, cs)+1}"

for OUT, base, lab in (("lost", [r for r in cells if r["A_correct"]], "denominator = A-correct cells"),
                       ("gained", [r for r in cells if not r["A_correct"]], "denominator = A-wrong cells")):
    print("\n" + "#" * 70)
    print(f"### OUTCOME = {OUT.upper()}   n_denominator = {len(base)}")
    show("model", lambda r: r["model"], base, lab)
    show("NOTA slot letter (=correct_letter)", lambda r: r["correct_letter"], base, lab)
    show("negated_stem", lambda r: r["negated_stem"], base, lab)
    show("has_context", lambda r: r["has_context"], base, lab)
    show("qlen quartile", lambda r: QQ(r["qlen"]), base, lab)
    show("LOO item difficulty (peer A acc)", lambda r: r["loo_A_acc"], base, lab)
    show("correct option was longest", lambda r: r["is_longest"], base, lab)
    show("correct option length quartile", lambda r: CQ(r["correct_len"]), base, lab)
    show("distractor_has_combo", lambda r: r["distractor_has_combo"], base, lab)

qs = sorted(r["qlen"] for r in cells)
cs = sorted(r["correct_len"] for r in cells)
def _q(v, arr):
    n = len(arr)
    cuts = [arr[n // 4], arr[n // 2], arr[3 * n // 4]]
    return sum(v > c for c in cuts)
QQ = lambda v: f"Q{_q(v, qs)+1}"
CQ = lambda v: f"Q{_q(v, cs)+1}"

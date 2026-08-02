"""Step 2: DISCRIMINATING TEST.

"Willingness to endorse NOTA, given the model demonstrably knew the medicine" is a
model-level disposition toward a string.  It should therefore be roughly INVARIANT to
how well-established the item's answer is, once we have conditioned on A_correct.

Rival accounts named in the open question -- lost recognition shortcut / added
difficulty -- predict the opposite: among A_correct cells, the ones that were lucky,
shallow or string-matched should fail B far more than the ones the model robustly knew.

Instrument for "robustly known": how many of the OTHER 3 models also answered A
correctly on the same item (0..3).  This is independent of the focal model's B behaviour.
"""
import collections
from mech_ref_acc_lib import cp_ci, cochran_armitage, load_cells, chisq_sf

cells = load_cells()
SHORT = {"google/gemini-3.6-flash": "gemini", "z-ai/glm-5.2": "glm",
         "qwen/qwen3.6-35b-a3b": "qwen", "google/gemma-4-26b-a4b-it": "gemma"}
MODELS = ["gemini", "glm", "qwen", "gemma"]
for r in cells:
    r["m"] = SHORT[r["model"]]

by_item = collections.defaultdict(dict)
for r in cells:
    by_item[r["question_id"]][r["m"]] = r

# consensus = # of OTHER models correct in A on this item
for qid, d in by_item.items():
    for m, r in d.items():
        r["peer_ok"] = sum(o["A_correct"] for om, o in d.items() if om != m)
        r["peer_n"] = len(d) - 1

print("=" * 100)
print("TEST 1  P(B correct | A correct), stratified by PEER A-consensus (0..3 other models right in A)")
print("        Claim predicts a flat line (disposition toward a string).")
print("=" * 100)
hdr = f"{'model':8} " + " ".join(f"{'peer=' + str(s):>16}" for s in range(4)) + f" {'CA-trend z':>11} {'p':>9}"
print(hdr)
rows_all = collections.defaultdict(lambda: [0, 0])
for m in MODELS:
    sub = [r for r in cells if r["m"] == m and r["A_correct"] and r["peer_n"] == 3]
    line = f"{m:8} "
    ca = []
    for s in range(4):
        g = [r for r in sub if r["peer_ok"] == s]
        k, n = sum(r["B_correct"] for r in g), len(g)
        rows_all[s][0] += k
        rows_all[s][1] += n
        ca.append((s, k, n))
        line += f"{(str(k) + '/' + str(n)):>7}{'':1}{(f'{100*k/n:.0f}%' if n else '  -'):>8}"
    z, p = cochran_armitage(ca)
    print(line + f" {z:11.2f} {p:9.2g}")
ca = [(s, rows_all[s][0], rows_all[s][1]) for s in range(4)]
z, p = cochran_armitage(ca)
line = f"{'POOLED':8} "
for s in range(4):
    k, n = rows_all[s]
    line += f"{(str(k) + '/' + str(n)):>7}{'':1}{(f'{100*k/n:.0f}%' if n else '  -'):>8}"
print(line + f" {z:11.2f} {p:9.2g}")
print("  method: Cochran-Armitage trend test (normal approx), two-sided.")

print()
print("  Pooled strata with exact Clopper-Pearson 95% CIs:")
for s in range(4):
    k, n = rows_all[s]
    lo, hi = cp_ci(k, n)
    print(f"    peer_ok={s}: P(B|Aok) = {k:4}/{n:<4} = {100*k/n:5.1f}%  CP95 [{100*lo:.1f},{100*hi:.1f}]"
          f"   'refusal' = {100-100*k/n:.1f}%")

# 2x2 extremes, Fisher
from mech_ref_acc_lib import fisher_2x2
k0, n0 = rows_all[0]
k3, n3 = rows_all[3]
print(f"\n  peer_ok=0 vs peer_ok=3, Fisher exact 2x2 p = "
      f"{fisher_2x2(k3, n3 - k3, k0, n0 - k0):.3g}")

print()
print("=" * 100)
print("TEST 2  Same instrument, but is the gradient just 'A_correct is noisy'?")
print("        Compare the SAME gradient in the A arm's own residual difficulty:")
print("        P(A correct) by peer consensus, to show the instrument is a difficulty scale.")
print("=" * 100)
for m in MODELS:
    sub = [r for r in cells if r["m"] == m and r["peer_n"] == 3]
    line = f"{m:8} "
    for s in range(4):
        g = [r for r in sub if r["peer_ok"] == s]
        k, n = sum(r["A_correct"] for r in g), len(g)
        line += f"{(str(k) + '/' + str(n)):>7}{'':1}{(f'{100*k/n:.0f}%' if n else '  -'):>8}"
    print(line)

print()
print("=" * 100)
print("TEST 3  Is 'refusal' an item property or a model disposition?")
print("        Among the 325 items, how do the 4 models' B-failures co-occur?")
print("        Disposition -> near-independent across models. Item difficulty -> clustered.")
print("=" * 100)
full = [d for d in by_item.values() if len(d) == 4]
# restrict to items where ALL FOUR models got A right (all 'demonstrably knew it')
allA = [d for d in full if all(r["A_correct"] for r in d.values())]
dist = collections.Counter(sum(1 for r in d.values() if not r["B_correct"]) for d in allA)
n_items = len(allA)
p_hat = sum(k * v for k, v in dist.items()) / (4 * n_items)
print(f"  items where all 4 models were A-correct: {n_items}")
print(f"  mean per-model B-failure rate on these items: {100*p_hat:.1f}%")
obs = [dist.get(i, 0) for i in range(5)]
from math import comb
exp = [n_items * comb(4, i) * p_hat ** i * (1 - p_hat) ** (4 - i) for i in range(5)]
print(f"  {'#models failing B':>18} : " + " ".join(f"{i:>7}" for i in range(5)))
print(f"  {'observed items':>18} : " + " ".join(f"{o:>7}" for o in obs))
print(f"  {'binomial-null exp':>18} : " + " ".join(f"{e:>7.1f}" for e in exp))
# collapse to keep exp>=5
o2 = [obs[0], obs[1], obs[2] + obs[3] + obs[4]]
e2 = [exp[0], exp[1], exp[2] + exp[3] + exp[4]]
x2 = sum((o - e) ** 2 / e for o, e in zip(o2, e2))
print(f"  collapsed obs {o2} vs exp {[round(e,1) for e in e2]}")
print(f"  Pearson chi-square GOF vs independent-Bernoulli null (df=1, one param estimated): "
      f"X2={x2:.2f}, p={chisq_sf(x2, 1):.3g}")
print("  -> overdispersion means B failure is carried by particular ITEMS, not by an")
print("     independent per-cell willingness coin.")

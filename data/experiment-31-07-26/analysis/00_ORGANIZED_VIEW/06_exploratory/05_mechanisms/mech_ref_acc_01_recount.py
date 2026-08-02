"""Step 1: recount every number in the nota-acceptance claim, independently."""
import collections, json
from mech_ref_acc_lib import cp_ci, mcnemar_exact, load_cells

cells = load_cells()
SHORT = {"google/gemini-3.6-flash": "gemini", "z-ai/glm-5.2": "glm",
         "qwen/qwen3.6-35b-a3b": "qwen", "google/gemma-4-26b-a4b-it": "gemma"}
by = collections.defaultdict(list)
for r in cells:
    by[SHORT[r["model"]]].append(r)

print("=" * 92)
print("A) CLAIM'S HEADLINE: P(B correct | A correct)  [claimed: gemini 90.3 287/318, glm 77.8 235/302,")
print("   qwen 76.7 221/288, gemma 68.2 176/258; pooled 78.8 919/1166]")
print("=" * 92)
print(f"{'model':8} {'k/n':>10} {'P(B|Aok)':>9} {'CP95':>18} | {'b=Aok->Bx':>9} {'c=Ax->Bok':>9} "
      f"{'netpp':>7} {'McNemar p':>10}")
tot_k = tot_n = 0
agg = {}
for m, rs in sorted(by.items(), key=lambda kv: -sum(r["A_correct"] for kv2 in [kv] for r in kv[1])):
    aok = [r for r in rs if r["A_correct"]]
    k = sum(r["B_correct"] for r in aok)
    n = len(aok)
    tot_k += k
    tot_n += n
    b = sum(1 for r in rs if r["A_correct"] and not r["B_correct"])
    c = sum(1 for r in rs if not r["A_correct"] and r["B_correct"])
    lo, hi = cp_ci(k, n)
    net = 100.0 * (c - b) / len(rs)
    agg[m] = dict(k=k, n=n, b=b, c=c, N=len(rs),
                  Aacc=sum(r["A_correct"] for r in rs) / len(rs),
                  Bacc=sum(r["B_correct"] for r in rs) / len(rs))
    print(f"{m:8} {k:4}/{n:<5} {100*k/n:8.1f}% [{100*lo:5.1f},{100*hi:5.1f}] | {b:9} {c:9} "
          f"{net:7.1f} {mcnemar_exact(b, c):10.2e}")
lo, hi = cp_ci(tot_k, tot_n)
print(f"{'POOLED':8} {tot_k:4}/{tot_n:<5} {100*tot_k/tot_n:8.1f}% [{100*lo:5.1f},{100*hi:5.1f}]"
      f"   refusal rate {100-100*tot_k/tot_n:.1f}% [{100-100*hi:.1f},{100-100*lo:.1f}]")

print()
print("=" * 92)
print("B) 'those refusal cells are X% of each model's ENTIRE B error mass'")
print("   [claimed: gemini 91.2, gemma 62.6, qwen 75.3, glm 82.7]")
print("=" * 92)
print(f"{'model':8} {'B errors':>9} {'b (Aok->Bx)':>12} {'share':>8} | {'Bx & Ax':>8} {'share':>8}")
for m in ("gemini", "gemma", "qwen", "glm"):
    rs = by[m]
    berr = sum(1 for r in rs if not r["B_correct"])
    b = agg[m]["b"]
    both = berr - b
    print(f"{m:8} {berr:9} {b:12} {100*b/berr:7.1f}% | {both:8} {100*both/berr:7.1f}%")

print()
print("=" * 92)
print("C) Marginal accuracies and the actual drop")
print("=" * 92)
print(f"{'model':8} {'N':>5} {'A acc':>7} {'B acc':>7} {'drop pp':>8}")
for m in ("gemini", "gemma", "qwen", "glm"):
    a = agg[m]
    print(f"{m:8} {a['N']:5} {100*a['Aacc']:6.1f}% {100*a['Bacc']:6.1f}% {100*(a['Aacc']-a['Bacc']):8.1f}")
A = sum(r["A_correct"] for r in cells) / len(cells)
B = sum(r["B_correct"] for r in cells) / len(cells)
print(f"{'ALL':8} {len(cells):5} {100*A:6.1f}% {100*B:6.1f}% {100*(A-B):8.1f}")

print()
print("=" * 92)
print("D) The OTHER conditional the claim never reports: P(A correct | B correct),")
print("   and P(B correct | A wrong).  If the drop were pure one-way 'NOTA refusal',")
print("   P(B|A wrong) should be near the 1/3-guess floor, not high.")
print("=" * 92)
print(f"{'model':8} {'P(B|Aok)':>9} {'P(B|Awrong)':>12} {'P(A|Bok)':>9} {'P(A|Bwrong)':>12}")
for m in ("gemini", "gemma", "qwen", "glm"):
    rs = by[m]
    aok = [r for r in rs if r["A_correct"]]
    ax = [r for r in rs if not r["A_correct"]]
    bok = [r for r in rs if r["B_correct"]]
    bx = [r for r in rs if not r["B_correct"]]
    f = lambda s, key: 100 * sum(r[key] for r in s) / len(s) if s else float("nan")
    print(f"{m:8} {f(aok,'B_correct'):8.1f}% {f(ax,'B_correct'):11.1f}% "
          f"{f(bok,'A_correct'):8.1f}% {f(bx,'A_correct'):11.1f}%")

json.dump({m: agg[m] for m in agg}, open("mech_ref_acc_01_out.json", "w"), indent=1)

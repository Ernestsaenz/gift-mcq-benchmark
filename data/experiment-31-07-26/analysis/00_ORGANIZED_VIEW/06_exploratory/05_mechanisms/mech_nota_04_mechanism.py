"""nota-acceptance part 3: what drives the refusal?

(a) Deliberation markers: token/latency deltas B-A, split by whether the model
    ended up accepting NOTA. Does refusing look like 'never noticed' or 'noticed
    and declined'?
(b) Item-level clumping: among items ALL FOUR models got right in A, is the number
    of models that accept NOTA in B distributed as independent coin flips
    (idiosyncratic aversion) or over-dispersed (item-driven: one specific rival
    claim pulls everyone)?  Poisson-binomial expectation by exact convolution,
    dispersion tested by Monte-Carlo on the chi-square statistic.
"""
import json
import math
import random
from collections import Counter, defaultdict

import stats_lib as S

random.seed(20260731)
ROWS = [r for r in json.load(open(
    "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
    "experiment-31-07-26/analysis/paired_clean.json")) if r["analysis_include"]]
MODELS = sorted(set(r["model"] for r in ROWS))
SHORT = {m: m.split("/")[-1] for m in MODELS}


def med(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return float("nan")
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def mannwhitney_p(x, y):
    """Two-sided Mann-Whitney U, normal approximation with tie correction."""
    nx, ny = len(x), len(y)
    if nx == 0 or ny == 0:
        return float("nan"), float("nan")
    allv = sorted([(v, 0) for v in x] + [(v, 1) for v in y])
    ranks = [0.0] * len(allv)
    i = 0
    ties = []
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1][0] == allv[i][0]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for t in range(i, j + 1):
            ranks[t] = r
        ties.append(j - i + 1)
        i = j + 1
    Rx = sum(rk for rk, (v, g) in zip(ranks, allv) if g == 0)
    U = Rx - nx * (nx + 1) / 2.0
    mu = nx * ny / 2.0
    n = nx + ny
    var = nx * ny / 12.0 * ((n + 1) - sum(t ** 3 - t for t in ties) / (n * (n - 1)))
    if var <= 0:
        return U, 1.0
    return U, S.two_sided_z_p(abs((U - mu) / math.sqrt(var)))


print("=" * 104)
print("9. DELIBERATION MARKERS. Restricted to cells the model got RIGHT in A (it knew the key),")
print("   so the only question is what it does once that key text becomes 'Ninguna...'.")
print("   Delta = B minus A on the same item, same model.")
print("=" * 104)
print(f"{'model':<22}{'median dTokens | accepted':>30}{'median dTokens | refused':>28}{'Mann-Whitney p':>18}")
for m in MODELS:
    rs = [r for r in ROWS if r["model"] == m and r["A_correct"] == 1]
    acc = [r["B_tokens"] - r["A_tokens"] for r in rs if r["B_correct"] == 1]
    ref = [r["B_tokens"] - r["A_tokens"] for r in rs if r["B_correct"] == 0]
    U, p = mannwhitney_p(acc, ref)
    print(f"{SHORT[m]:<22}{med(acc):>21.0f} (n={len(acc):<4}){med(ref):>19.0f} (n={len(ref):<4}){p:>18.3g}")

print()
print(f"{'model':<22}{'median dLatency ms | accept':>30}{'median dLatency | refused':>28}{'Mann-Whitney p':>18}")
for m in MODELS:
    rs = [r for r in ROWS if r["model"] == m and r["A_correct"] == 1]
    acc = [r["B_latency_ms"] - r["A_latency_ms"] for r in rs if r["B_correct"] == 1]
    ref = [r["B_latency_ms"] - r["A_latency_ms"] for r in rs if r["B_correct"] == 0]
    U, p = mannwhitney_p(acc, ref)
    print(f"{SHORT[m]:<22}{med(acc):>21.0f} (n={len(acc):<4}){med(ref):>19.0f} (n={len(ref):<4}){p:>18.3g}")

print()
print("   median tokens per arm (all cells)")
for m in MODELS:
    rs = [r for r in ROWS if r["model"] == m]
    a, b = med([r["A_tokens"] for r in rs]), med([r["B_tokens"] for r in rs])
    print(f"     {SHORT[m]:<22} A={a:>6.0f}  B={b:>6.0f}  ratio={b/a:.2f}")

# ------------------------------------------------------------------ clumping
print()
print("=" * 104)
print("10. IS REFUSAL IDIOSYNCRATIC OR ITEM-DRIVEN?")
print("    Items where ALL FOUR models answered A correctly (every model demonstrably knew the key).")
print("    k = how many of the 4 then accepted NOTA in B.")
print("    Expected under independence = Poisson-binomial with each model's own P(B ok | A ok)")
print("    on this item set, by exact convolution; fit tested by Monte-Carlo chi-square.")
print("=" * 104)
by_item = defaultdict(dict)
for r in ROWS:
    by_item[r["question_id"]][r["model"]] = r
full = sorted(q for q, d in by_item.items() if len(d) == 4 and all(d[m]["A_correct"] == 1 for m in MODELS))
print(f"    items where all 4 got A right: {len(full)}")

ps = []
for m in MODELS:
    k = sum(by_item[q][m]["B_correct"] for q in full)
    ps.append(k / len(full))
    print(f"      {SHORT[m]:<22} accepts NOTA on {k}/{len(full)} = {100*k/len(full):.1f}%")

dist = [1.0]
for p in ps:
    nd = [0.0] * (len(dist) + 1)
    for i, v in enumerate(dist):
        nd[i] += v * (1 - p)
        nd[i + 1] += v * p
    dist = nd
obs = Counter(sum(by_item[q][m]["B_correct"] for m in MODELS) for q in full)
N = len(full)
print(f"\n    {'k of 4 accept NOTA':<24}{'observed':>12}{'expected (indep.)':>22}")
for k in range(5):
    print(f"    {k:<24}{obs.get(k,0):>12}{dist[k]*N:>22.1f}")
x2 = sum((obs.get(k, 0) - dist[k] * N) ** 2 / (dist[k] * N) for k in range(5) if dist[k] * N > 0)
NMC = 20000
ge = 0
for _ in range(NMC):
    c = Counter()
    for _ in range(N):
        c[sum(1 for p in ps if random.random() < p)] += 1
    s = sum((c.get(k, 0) - dist[k] * N) ** 2 / (dist[k] * N) for k in range(5) if dist[k] * N > 0)
    if s >= x2 - 1e-12:
        ge += 1
print(f"\n    chi-square statistic = {x2:.2f};  Monte-Carlo p (20000 draws from the fitted")
print(f"    Poisson-binomial; no df correction needed) = {(ge+1)/(NMC+1):.4g}")
print(f"    items where 0 of 4 accept NOTA: observed {obs.get(0,0)}  vs {dist[0]*N:.1f} expected")
print(f"    items where 4 of 4 accept NOTA: observed {obs.get(4,0)}  vs {dist[4]*N:.1f} expected")

unan = [q for q in full if sum(by_item[q][m]["B_correct"] for m in MODELS) == 0]
same = [q for q in unan if len(set(by_item[q][m]["B_selected"] for m in MODELS)) == 1]
print(f"    of the {len(unan)} unanimous-refusal items, {len(same)} had all four models converge on the")
print(f"    SAME distractor letter (expected under independent choice among 3 distractors ~ {len(unan)/9:.1f})")
print("    unanimous-refusal item ids: " + ", ".join(unan))
json.dump(unan, open("/private/tmp/claude-501/-Users-ernestsaenz-Programming-GIFT-abstract-dossier/"
                     "a0613478-db50-4bbd-ba89-911fee14cc09/scratchpad/unanimous_refusal.json", "w"))

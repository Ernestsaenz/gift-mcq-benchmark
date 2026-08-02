"""Mechanism discriminators: NOTA-aversion baseline, deliberation cost,
attractor-inheritance split by whether A was correct."""
import sys, collections, random, re
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_lib import *

random.seed(11)
Q = load_questions()
cells = load_cells()
models = sorted(set(c["model"] for c in cells))
errsB = [c for c in cells if c["B_correct"] == 0]
errsA = [c for c in cells if c["A_correct"] == 0]
A_pick = collections.defaultdict(dict)
for c in errsA:
    A_pick[c["question_id"]][c["model"]] = c["A_selected"]

print("=" * 78)
print("M1. IS THERE A NATIVE 'NINGUNA' DISTRACTOR IN CONDITION A? (aversion baseline)")
print("=" * 78)
pat = re.compile(r"ningun", re.I)
nat = []
for qid in set(c["question_id"] for c in cells):
    a = Q[qid]["A"]
    for L in LETTERS:
        if pat.search(strip_acc(a["opts"][L])):
            nat.append((qid, L, L == a["correct_letter"], a["opts"][L]))
print(f"  condition-A options containing 'ningun*': {len(nat)} across "
      f"{len(set(x[0] for x in nat))} items")
wrongnota = [(q, L) for q, L, isc, t in nat if not isc]
rightnota = [(q, L) for q, L, isc, t in nat if isc]
print(f"    as a WRONG option: {len(wrongnota)}   as the CORRECT option: {len(rightnota)}")
for q, L, isc, t in nat[:8]:
    print(f"      {q} [{L}] correct={isc}: {t[:90]}")
if wrongnota:
    s = set(wrongnota)
    n = sel = 0
    for c in cells:
        for q, L in s:
            if c["question_id"] == q:
                n += 1
                sel += c["A_selected"] == L
    print(f"  model-cells facing a WRONG 'ninguna' option in A: {n}; selected it {sel} "
          f"({sel/n if n else 0:.3f})  [random baseline 0.250]")
if rightnota:
    s = set(rightnota)
    n = sel = 0
    for c in cells:
        for q, L in s:
            if c["question_id"] == q:
                n += 1
                sel += c["A_selected"] == L
    print(f"  model-cells facing a CORRECT 'ninguna' option in A: {n}; selected it {sel} "
          f"({sel/n if n else 0:.3f})")

print()
print("=" * 78)
print("M2. ATTRACTOR INHERITANCE, SPLIT BY WHETHER THE MODEL HAD 'A' CORRECT")
print("=" * 78)
for label, sub in (("A correct -> B wrong (the drop)", [c for c in errsB if c["A_correct"] == 1]),
                   ("A wrong  -> B wrong",             [c for c in errsB if c["A_correct"] == 0])):
    hit = tot = 0; nulls = []
    for c in sub:
        q = c["question_id"]
        others = {m: L for m, L in A_pick[q].items() if m != c["model"]}
        if not others:
            continue
        tot += 1
        picks = set(others.values())
        hit += c["B_selected"] in picks
        nulls.append(len(picks) / 3.0)
    if tot:
        exp = sum(nulls)
        NP = 20000; ge = 0
        for _ in range(NP):
            if sum(1 for p in nulls if random.random() < p) >= hit:
                ge += 1
        print(f"  {label:34s} n={len(sub):3d}  testable={tot:3d}  "
              f"matches another model's A-error letter: {hit} ({hit/tot:.3f}) "
              f"vs {exp/tot:.3f} chance, perm p={(ge+1)/(NP+1):.5f}")

# convergence within each subgroup
print()
for label, sub in (("A correct -> B wrong", [c for c in errsB if c["A_correct"] == 1]),
                   ("A wrong  -> B wrong",  [c for c in errsB if c["A_correct"] == 0])):
    by_q = collections.defaultdict(list)
    for c in sub:
        by_q[c["question_id"]].append(c["B_selected"])
    s = t = 0
    for v in by_q.values():
        cnt = collections.Counter(v)
        s += sum(x * (x - 1) // 2 for x in cnt.values()); t += len(v) * (len(v) - 1) // 2
    print(f"  {label:34s} within-item pairwise agreement {s}/{t} = "
          f"{s/t if t else float('nan'):.3f}  (chance .333)")

print()
print("=" * 78)
print("M3. DELIBERATION: TOKENS AND LATENCY BY OUTCOME")
print("=" * 78)


def mstats(v):
    v = sorted(v)
    n = len(v)
    return sum(v) / n, v[n // 2]


def mannwhitney_p(x, y, NP=20000):
    """Permutation test on the difference of means (label shuffle)."""
    obs = sum(x) / len(x) - sum(y) / len(y)
    pool = list(x) + list(y); nx = len(x)
    ge = 0
    for _ in range(NP):
        random.shuffle(pool)
        d = sum(pool[:nx]) / nx - sum(pool[nx:]) / (len(pool) - nx)
        if abs(d) >= abs(obs) - 1e-12:
            ge += 1
    return obs, (ge + 1) / (NP + 1)


print(f"{'model':28s} {'B-correct tok':>14s} {'B-error tok':>13s} {'diff':>8s} {'perm p':>9s}")
for m in models + ["ALL"]:
    sub = cells if m == "ALL" else [c for c in cells if c["model"] == m]
    ok = [c["B_tokens"] for c in sub if c["B_correct"]]
    bad = [c["B_tokens"] for c in sub if not c["B_correct"]]
    d, p = mannwhitney_p(ok, bad, 8000)
    print(f"{m:28s} {sum(ok)/len(ok):14.1f} {sum(bad)/len(bad):13.1f} {d:+8.1f} {p:9.5f}")

print("\n  A->B token inflation on cells where B was CORRECT vs where B was WRONG:")
for m in models + ["ALL"]:
    sub = cells if m == "ALL" else [c for c in cells if c["model"] == m]
    ok = [c["B_tokens"] - c["A_tokens"] for c in sub if c["B_correct"]]
    bad = [c["B_tokens"] - c["A_tokens"] for c in sub if not c["B_correct"]]
    d, p = mannwhitney_p(ok, bad, 8000)
    print(f"  {m:28s} correct {sum(ok)/len(ok):+8.1f}   error {sum(bad)/len(bad):+8.1f}  "
          f"diff {d:+7.1f}  perm p={p:.5f}")

print()
print("=" * 78)
print("M4. NOTA-SLOT LETTER: DOES THE DROP DEPEND ON WHERE 'NINGUNA' SITS?")
print("=" * 78)
for L in ("b", "c", "d"):
    sub = [c for c in cells if c["correct_letter"] == L]
    a = sum(c["A_correct"] for c in sub) / len(sub)
    b = sum(c["B_correct"] for c in sub) / len(sub)
    print(f"  NOTA at [{L}] n={len(sub):4d}  A acc={a:.3f}  B acc={b:.3f}  drop={a-b:.3f}")

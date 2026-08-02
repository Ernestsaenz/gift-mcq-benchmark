"""(a) audit the parse-failure accounting behind the 'strict' outcome axis,
(b) recompute inference independently (own McNemar, own bootstrap, own permutation,
    fresh seeds), and
(c) run inference paths the grid deliberately excludes -- notably treating the
    4 MODELS as the resampling unit.
"""
import sqlite3, json, os, math, random, collections
from math import comb

HERE = os.path.dirname(os.path.abspath(__file__))
DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"
con = sqlite3.connect(DB, uri=True)
con.row_factory = sqlite3.Row
EXPA, EXPB = "expA_or_310726", "expB_or_310726"

rows = json.load(open(os.path.join(HERE, "paired_clean.json")))
MODELS = sorted({r["model"] for r in rows})
PRIMARY = [r for r in rows if r["analysis_include"]]

# ---------------------------------------------------------------------------
# (a) parse-failure accounting
# ---------------------------------------------------------------------------
q = """
SELECT e.name AS expname, qu.question_id AS qid, lc.model AS model,
       lc.run_index AS run, pa.parse_status AS pstatus
FROM logical_calls lc
JOIN experiments e  ON e.id = lc.experiment_id
JOIN questions   qu ON qu.id = lc.question_id
LEFT JOIN parsed_answers pa ON pa.logical_call_id = lc.id
WHERE e.name IN (?, ?)
"""
raw = [dict(r) for r in con.execute(q, (EXPA, EXPB))]
print("=" * 100)
print("(a) PARSE-FAILURE ACCOUNTING  (what the 'strict' outcome axis is supposed to cover)")
print("=" * 100)
print("run_index values:", collections.Counter(r["run"] for r in raw))
qa = {r["qid"] for r in raw if r["expname"] == EXPA}
qb = {r["qid"] for r in raw if r["expname"] == EXPB}
print(f"items in A={len(qa)}  items in B={len(qb)}  intersection={len(qa & qb)}")
inter = qa & qb

cell = {}
for r in raw:
    if r["qid"] not in inter:
        continue
    arm = "A" if r["expname"] == EXPA else "B"
    cell.setdefault((r["qid"], r["model"]), {}).setdefault(arm, []).append(r["pstatus"])

both = {k: v for k, v in cell.items() if "A" in v and "B" in v}
print(f"(item,model) cells with both arms present, items in A∩B: {len(both)}")


def ok(sts):
    return any(s == "ok" for s in sts)


bothok = [k for k, v in both.items() if ok(v["A"]) and ok(v["B"])]
onlyA = [k for k, v in both.items() if ok(v["A"]) and not ok(v["B"])]
onlyB = [k for k, v in both.items() if not ok(v["A"]) and ok(v["B"])]
neither = [k for k, v in both.items() if not ok(v["A"]) and not ok(v["B"])]
print(f"   both arms parsed      : {len(bothok)}   <- paired_clean.json has {len(rows)}")
print(f"   A parsed, B FAILED    : {len(onlyA)}   {sorted(onlyA)}")
print(f"   A FAILED, B parsed    : {len(onlyB)}   {sorted(onlyB)}")
print(f"   both arms FAILED      : {len(neither)} {sorted(neither)}")
print("   -> the published 'strict' arm adds", len(onlyA) + len(onlyB) + len(neither),
      "cell(s) worth of information; it hardcodes exactly 1.")

# ---------------------------------------------------------------------------
# (b) independent inference on the primary set
# ---------------------------------------------------------------------------
print()
print("=" * 100)
print("(b) INDEPENDENT INFERENCE on primary/lenient (own code, fresh seeds)")
print("=" * 100)


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(comb(n, i) for i in range(k + 1)) / 2.0 ** n)


b = sum(1 for r in PRIMARY if r["A_correct"] == 1 and r["B_correct"] == 0)
c = sum(1 for r in PRIMARY if r["A_correct"] == 0 and r["B_correct"] == 1)
print(f"  pooled discordants b(A only)={b} c(B only)={c}   exact McNemar p={mcnemar_exact(b,c):.3e}")

bycl = collections.defaultdict(list)
for r in PRIMARY:
    bycl[r["cluster"]].append(r)
CL = sorted(bycl)
agg = [(sum(x["A_correct"] for x in bycl[g]), sum(x["B_correct"] for x in bycl[g]), len(bycl[g]))
       for g in CL]
K = len(CL)


def cell_delta(idx, flips=None):
    sA = sB = n = 0
    for j, i in enumerate(idx):
        a, bb, nn = agg[i]
        if flips is not None and flips[j]:
            a, bb = bb, a
        sA += a; sB += bb; n += nn
    return 100.0 * (sB - sA) / n


obs = cell_delta(list(range(K)))
print(f"  observed pooled cell delta = {obs:.4f} pp   (K={K} clusters)")

for seed in (1, 2, 12345):
    rng = random.Random(seed)
    B = 20000
    dist = [cell_delta([rng.randrange(K) for _ in range(K)]) for _ in range(B)]
    dist.sort()
    lo, hi = dist[int(0.025 * B)], dist[int(0.975 * B)]
    npos = sum(1 for x in dist if x >= 0)
    print(f"    cluster bootstrap seed={seed:>5}: 95% CI [{lo:.3f}, {hi:.3f}]  "
          f"#(boot delta >= 0) = {npos}/{B}")

for seed in (7, 8):
    rng = random.Random(seed)
    B = 20000
    ge = 0
    for _ in range(B):
        fl = [rng.getrandbits(1) for _ in range(K)]
        if abs(cell_delta(list(range(K)), fl)) >= abs(obs) - 1e-12:
            ge += 1
    print(f"    cluster sign-flip permutation seed={seed}: p=({ge}+1)/({B}+1) = {(ge+1)/(B+1):.3e}")

# ---------------------------------------------------------------------------
# (c) inference paths the grid excludes: MODELS as the resampling unit
# ---------------------------------------------------------------------------
print()
print("=" * 100)
print("(c) OFF-GRID INFERENCE: the 4 models as the unit of generalisation")
print("=" * 100)
pm = []
for m in MODELS:
    mr = [r for r in PRIMARY if r["model"] == m]
    d = 100.0 * sum(x["B_correct"] - x["A_correct"] for x in mr) / len(mr)
    bb = sum(1 for r in mr if r["A_correct"] == 1 and r["B_correct"] == 0)
    cc = sum(1 for r in mr if r["A_correct"] == 0 and r["B_correct"] == 1)
    pm.append(d)
    print(f"  {m:<28} delta={d:>8.3f}  b={bb:>3} c={cc:>3}  McNemar p={mcnemar_exact(bb,cc):.3e}")

n = len(pm)
neg = sum(1 for d in pm if d < 0)
# exact two-sided sign test over models
p_sign = 2.0 * sum(comb(n, i) for i in range(min(neg, n - neg) + 1)) / 2.0 ** n
p_sign = min(1.0, p_sign)
print(f"\n  exact two-sided SIGN test over the {n} model-level deltas: {neg}/{n} negative -> p = {p_sign:.4f}")
# exact permutation (sign-flip) over models, on the mean
mean = sum(pm) / n
cnt = 0
for mask in range(2 ** n):
    v = sum(pm[i] * (1 if (mask >> i) & 1 else -1) for i in range(n)) / n
    if abs(v) >= abs(mean) - 1e-12:
        cnt += 1
print(f"  exact sign-flip permutation over models (mean={mean:.3f}): p = {cnt}/{2**n} = {cnt/2**n:.4f}")
print(f"  -> with only {n} models, the SMALLEST attainable p from a model-level exact test is "
      f"{2.0/2**n:.4f}; nothing in this family can reach 0.05.")

# grid's own weakest spec, for comparison
stored = json.load(open(os.path.join(HERE, "sens_speccurve_results.json")))
w = max(stored["results"], key=lambda r: r["p"])
print(f"  grid's weakest spec: p={w['p']:.4f}  ({w['exclusion']}/{w['outcome']} "
      f"{w['unit']}/{w['inference']}/{w['pooling']}) -- uses a t(3) approximation on the same 4 numbers.")

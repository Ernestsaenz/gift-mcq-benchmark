#!/usr/bin/env python3
"""Independent recomputation of the OBSERVED block on the clean subset.

Method: direct enumeration over analysis_include==true rows in paired_clean.json.
Standard library only (json, collections). No p-values computed here -- this is
a pure descriptive recount plus structural checks (N, distinct items, clusters,
duplicate keys, per-model balance).
"""
import json
from collections import Counter, defaultdict

P = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"

rows = json.load(open(P))
print("rows in file:", len(rows))

# --- inspect the include flag itself ---
flagvals = Counter(repr(r.get("analysis_include")) for r in rows)
print("analysis_include value counts:", dict(flagvals))

clean = [r for r in rows if r.get("analysis_include") is True]
print("clean cells (analysis_include is True):", len(clean))

# exclusion reasons among dropped rows
dropped = [r for r in rows if r.get("analysis_include") is not True]
print("dropped cells:", len(dropped))
print("  excl_item_defect true:", sum(1 for r in dropped if r.get("excl_item_defect")))
print("  excl_nota_position_a true:", sum(1 for r in dropped if r.get("excl_nota_position_a")))
print("  neither flag:", sum(1 for r in dropped
                            if not r.get("excl_item_defect") and not r.get("excl_nota_position_a")))

# --- structural checks ---
qids = set(r["question_id"] for r in clean)
clusters = set(r["cluster"] for r in clean)
models = sorted(set(r["model"] for r in clean))
print("distinct question_id:", len(qids))
print("distinct cluster:", len(clusters))
print("distinct model:", len(models), models)

keys = Counter((r["question_id"], r["model"]) for r in clean)
dupes = {k: v for k, v in keys.items() if v > 1}
print("duplicate (question_id, model) keys:", len(dupes))
if dupes:
    for k, v in list(dupes.items())[:10]:
        print("   DUP", k, v)

# --- outcome coding sanity: are A_correct/B_correct strictly 0/1, no missing? ---
acv = Counter(repr(r.get("A_correct")) for r in clean)
bcv = Counter(repr(r.get("B_correct")) for r in clean)
print("A_correct values:", dict(acv))
print("B_correct values:", dict(bcv))

# --- per-model table ---
by_model = defaultdict(list)
for r in clean:
    by_model[r["model"]].append(r)

def pct(num, den):
    return 100.0 * num / den if den else float("nan")

print()
print(f"{'model':28s} {'n':>5s} {'distinct_q':>10s} {'A%':>8s} {'B%':>8s} {'delta_pp':>9s}")
order = sorted(by_model, key=lambda m: -pct(sum(x['A_correct'] for x in by_model[m]), len(by_model[m])))
tot_n = tot_a = tot_b = 0
per_model = {}
for m in order:
    rs = by_model[m]
    n = len(rs)
    a = sum(r["A_correct"] for r in rs)
    b = sum(r["B_correct"] for r in rs)
    dq = len(set(r["question_id"] for r in rs))
    ap, bp = pct(a, n), pct(b, n)
    per_model[m] = (n, a, b, ap, bp, ap - bp, dq)
    print(f"{m:28s} {n:5d} {dq:10d} {ap:8.4f} {bp:8.4f} {ap-bp:9.4f}")
    tot_n += n; tot_a += a; tot_b += b

ap, bp = pct(tot_a, tot_n), pct(tot_b, tot_n)
print(f"{'POOLED':28s} {tot_n:5d} {len(qids):10d} {ap:8.4f} {bp:8.4f} {ap-bp:9.4f}")
print(f"POOLED raw counts: A {tot_a}/{tot_n}  B {tot_b}/{tot_n}")

# --- which model(s) are missing items, and which item(s) ---
print()
for m in order:
    have = set(r["question_id"] for r in by_model[m])
    missing = qids - have
    extra = have - qids
    print(f"{m:28s} cells={len(by_model[m])} missing_qids={sorted(missing)} n_missing={len(missing)}")

# is the missing item present in the FULL file for that model (i.e. excluded), or absent entirely?
allkeys = set((r["question_id"], r["model"]) for r in rows)
print()
for m in order:
    have = set(r["question_id"] for r in by_model[m])
    for q in sorted(qids - have):
        present_raw = (q, m) in allkeys
        info = [r for r in rows if r["question_id"] == q and r["model"] == m]
        print(f"  model={m} qid={q} present_in_raw_file={present_raw}",
              {k: info[0][k] for k in ("analysis_include", "excl_item_defect", "excl_nota_position_a")}
              if info else "ROW ABSENT ENTIRELY")

# --- rounding check against the claimed numbers ---
print()
claimed = {
    "google/gemini-3.6-flash": (325, 97.85, 89.54, -8.31),
    "z-ai/glm-5.2": (324, 93.21, 75.00, -18.21),
    "qwen/qwen3.6-35b-a3b": (325, 88.62, 72.62, -16.00),
    "google/gemma-4-26b-a4b-it": (325, 79.38, 59.69, -19.69),
}
# match claimed keys to actual model strings by substring
def find(sub):
    hits = [m for m in per_model if sub in m]
    return hits[0] if len(hits) == 1 else None

for cm, (cn, ca, cb, cd) in claimed.items():
    short = cm.split("/")[-1]
    m = find(short)
    if m is None:
        print(f"CLAIM {short}: NO MATCHING MODEL STRING")
        continue
    n, a, b, apct, bpct, dpp, dq = per_model[m]
    ok = (n == cn and abs(round(apct, 2) - ca) < 0.005 and abs(round(bpct, 2) - cb) < 0.005
          and abs(round(dpp, 2) - cd) < 0.005)
    print(f"CLAIM {short:22s} n {n}=={cn}? {n==cn} | A {round(apct,2)} vs {ca} | "
          f"B {round(bpct,2)} vs {cb} | d {round(dpp,2)} vs {cd} -> {'MATCH' if ok else 'MISMATCH'}")

print(f"CLAIM POOLED n {tot_n}==1299? {tot_n==1299} | A {round(ap,2)} vs 89.76 | "
      f"B {round(bp,2)} vs 74.21 | d {round(ap-bp,2)} vs -15.55")

# --- OBSERVED block (1-dp) reproduction ---
print()
obs = {"gemini-3.6-flash": (97.8, 89.5, -8.3), "glm-5.2": (93.2, 75.0, -18.2),
       "qwen3.6-35b-a3b": (88.6, 72.6, -16.0), "gemma-4-26b-a4b-it": (79.4, 59.7, -19.7)}
for short, (oa, ob, od) in obs.items():
    m = find(short)
    n, a, b, apct, bpct, dpp, dq = per_model[m]
    print(f"OBSERVED {short:20s} A {round(apct,1)} vs {oa} | B {round(bpct,1)} vs {ob} | "
          f"d {round(dpp,1)} vs {od} -> "
          f"{'MATCH' if (round(apct,1)==oa and round(bpct,1)==ob and round(dpp,1)==od) else 'MISMATCH'}")

# --- McNemar discordant cells per model (context for the 'mcnemar-exact' agent) ---
print()
print(f"{'model':28s} {'b(A1B0)':>8s} {'c(A0B1)':>8s} {'both1':>7s} {'both0':>7s}")
for m in order:
    rs = by_model[m]
    b_ = sum(1 for r in rs if r["A_correct"] == 1 and r["B_correct"] == 0)
    c_ = sum(1 for r in rs if r["A_correct"] == 0 and r["B_correct"] == 1)
    n11 = sum(1 for r in rs if r["A_correct"] == 1 and r["B_correct"] == 1)
    n00 = sum(1 for r in rs if r["A_correct"] == 0 and r["B_correct"] == 0)
    print(f"{m:28s} {b_:8d} {c_:8d} {n11:7d} {n00:7d}")

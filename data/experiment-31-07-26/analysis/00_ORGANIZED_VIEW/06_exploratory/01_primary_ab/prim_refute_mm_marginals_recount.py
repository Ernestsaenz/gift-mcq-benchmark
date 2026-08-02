#!/usr/bin/env python3
"""Independent recount of the claimed marginals from paired_clean.json.
Stdlib only. No modelling -- pure counting, exactly as the claim asserts."""
import json
from collections import defaultdict, Counter

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"

rows = json.load(open(PATH))
print("total records in file:", len(rows))

inc = [r for r in rows if r.get("analysis_include") is True]
print("analysis_include==True cells:", len(inc))

flagcnt = Counter((r.get("excl_item_defect"), r.get("excl_nota_position_a"), r.get("analysis_include")) for r in rows)
print("(excl_item_defect, excl_nota_position_a, analysis_include) ->", dict(flagcnt))

models = sorted({r["model"] for r in inc})
items = {r["question_id"] for r in inc}
clusters = {r["cluster"] for r in inc}
print("distinct models:", len(models), models)
print("distinct question_id (items):", len(items))
print("distinct clusters:", len(clusters))
print("long-form rows (2 conditions x cells):", 2 * len(inc))


def pct(n, d):
    return 100.0 * n / d if d else float("nan")


per_model = defaultdict(lambda: {"n": 0, "A": 0, "B": 0, "items": []})
for r in inc:
    m = per_model[r["model"]]
    m["n"] += 1
    m["A"] += int(r["A_correct"])
    m["B"] += int(r["B_correct"])
    m["items"].append(r["question_id"])

print("\n%-28s %5s %6s %9s %6s %9s %10s" % ("model", "n", "A_ok", "A%", "B_ok", "B%", "delta_pp"))
tA = tB = tN = 0
for mod in models:
    m = per_model[mod]
    a, b, n = m["A"], m["B"], m["n"]
    tA += a; tB += b; tN += n
    print("%-28s %5d %6d %9.4f %6d %9.4f %10.4f" % (mod, n, a, pct(a, n), b, pct(b, n), pct(b, n) - pct(a, n)))
    dupes = [k for k, v in Counter(m["items"]).items() if v > 1]
    if dupes:
        print("   !! duplicate item rows for this model:", dupes)
print("%-28s %5d %6d %9.4f %6d %9.4f %10.4f" % ("POOLED", tN, tA, pct(tA, tN), tB, pct(tB, tN), pct(tB, tN) - pct(tA, tN)))

for mod in models:
    miss = items - set(per_model[mod]["items"])
    if miss:
        print("model %s missing items (vs union): %s" % (mod, sorted(miss)))

present_raw = defaultdict(set)
for r in rows:
    present_raw[r["model"]].add(r["question_id"])
raw_items = {r["question_id"] for r in rows}
print("\nraw file: distinct items =", len(raw_items), " distinct models =", len(present_raw))
for mod in sorted(present_raw):
    print("  raw cells for %-28s = %d" % (mod, len(present_raw[mod])))
for mod in models:
    gone = items - present_raw[mod]
    if gone:
        print("  %s: item(s) ABSENT FROM FILE: %s" % (mod, sorted(gone)))
    excl = (items & present_raw[mod]) - set(per_model[mod]["items"])
    if excl:
        print("  %s: item(s) present but analysis_include=False: %s" % (mod, sorted(excl)))

claims = {
    "gemini-3.6-flash": (318, 325, 291, 325),
    "glm-5.2": (302, 324, 243, 324),
    "qwen3.6-35b-a3b": (288, 325, 236, 325),
    "gemma-4-26b-a4b-it": (258, 325, 194, 325),
}
print("\n--- claimed vs recomputed ---")
allok = True
for mod in models:
    key = None
    for k in claims:
        if k in mod:
            key = k
    m = per_model[mod]
    if key is None:
        print("%-28s NO CLAIM MATCH (got A=%d/%d B=%d/%d)" % (mod, m["A"], m["n"], m["B"], m["n"]))
        allok = False
        continue
    ca, cn, cb, cn2 = claims[key]
    ok = (ca == m["A"] and cn == m["n"] and cb == m["B"] and cn2 == m["n"])
    allok = allok and ok
    print("%-28s claim A=%d/%d B=%d/%d | got A=%d/%d B=%d/%d | %s"
          % (mod, ca, cn, cb, cn2, m["A"], m["n"], m["B"], m["n"], "MATCH" if ok else "MISMATCH"))
print("all per-model claims match:", allok)

print("\npooled claim: A 89.76% -> B 74.21% (-15.55pp)")
print("pooled  got : A %.4f%% -> B %.4f%% (%.4fpp)" % (pct(tA, tN), pct(tB, tN), pct(tB, tN) - pct(tA, tN)))
print("pooled 2dp  : A %.2f -> B %.2f (delta %.2f)" % (pct(tA, tN), pct(tB, tN), pct(tB, tN) - pct(tA, tN)))
print("pooled counts: A %d/%d  B %d/%d" % (tA, tN, tB, tN))

print("\nper-model delta rounding check:")
for mod in models:
    m = per_model[mod]
    a, b, n = m["A"], m["B"], m["n"]
    exact = pct(b, n) - pct(a, n)
    print("  %-28s exact %.4f | diff-then-round %.2f | round-then-diff %.2f"
          % (mod, exact, round(exact, 2), round(pct(b, n), 2) - round(pct(a, n), 2)))

print("\ndiscordant A->B pairs per model (b=A1B0 | c=A0B1):")
for mod in models:
    n10 = sum(1 for r in inc if r["model"] == mod and r["A_correct"] == 1 and r["B_correct"] == 0)
    n01 = sum(1 for r in inc if r["model"] == mod and r["A_correct"] == 0 and r["B_correct"] == 1)
    n11 = sum(1 for r in inc if r["model"] == mod and r["A_correct"] == 1 and r["B_correct"] == 1)
    n00 = sum(1 for r in inc if r["model"] == mod and r["A_correct"] == 0 and r["B_correct"] == 0)
    print("  %-28s a=%d b=%d c=%d d=%d  net=%d  (b-c)/n=%.4fpp"
          % (mod, n11, n10, n01, n00, n10 - n01, 100.0 * (n01 - n10) / (n11 + n10 + n01 + n00)))

print("\nclusters in included subset:", len(clusters), " in raw file:", len({r['cluster'] for r in rows}))
cl_items = defaultdict(set)
for r in inc:
    cl_items[r["cluster"]].add(r["question_id"])
sizes = Counter(len(v) for v in cl_items.values())
print("cluster size (items per cluster) distribution:", dict(sorted(sizes.items())))
print("sum of cluster item counts =", sum(len(v) for v in cl_items.values()))

# value-domain checks
print("\nA_correct/B_correct value domains:",
      sorted({r["A_correct"] for r in inc}), sorted({r["B_correct"] for r in inc}))
print("analysis_include value domain in raw file:", sorted({str(r.get('analysis_include')) for r in rows}))

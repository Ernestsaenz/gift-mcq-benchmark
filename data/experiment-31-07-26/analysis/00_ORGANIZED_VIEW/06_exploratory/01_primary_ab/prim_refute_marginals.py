#!/usr/bin/env python3
"""Independent recount of the clean-subset marginals / grid shape.

Stdlib only. No numpy/scipy/pandas.
Refutation target: claim from "per-model-contrasts" section 1.
"""
import json
from collections import Counter, defaultdict

PATH = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")

rows = json.load(open(PATH))
print("total rows in file:", len(rows))

clean = [r for r in rows if r.get("analysis_include") is True]
print("analysis_include==true rows (cells):", len(clean))

# --- exclusion flag accounting -------------------------------------------
excl = [r for r in rows if r.get("analysis_include") is not True]
print("excluded rows:", len(excl))
print("  excl_item_defect true:", sum(1 for r in excl if r.get("excl_item_defect")))
print("  excl_nota_position_a true:", sum(1 for r in excl if r.get("excl_nota_position_a")))

# --- grid shape ------------------------------------------------------------
items = sorted({r["question_id"] for r in clean})
models = sorted({r["model"] for r in clean})
clusters = sorted({r["cluster"] for r in clean})
print("distinct items:", len(items))
print("distinct models:", len(models), models)
print("distinct clusters:", len(clusters))

# duplicate cells? (item, model) should be unique
cell_counts = Counter((r["question_id"], r["model"]) for r in clean)
dups = {k: v for k, v in cell_counts.items() if v > 1}
print("duplicated (item,model) cells:", len(dups), list(dups.items())[:5])

# holes in the item x model grid
present = defaultdict(set)
for r in clean:
    present[r["model"]].add(r["question_id"])
allitems = set(items)
print("\n-- per model item coverage --")
holes = {}
for m in models:
    missing = sorted(allitems - present[m])
    holes[m] = missing
    print(f"  {m}: n={len(present[m])}  missing={missing}")

# item -> cluster uniqueness
item2clusters = defaultdict(set)
for r in clean:
    item2clusters[r["question_id"]].add(r["cluster"])
multi = {i: sorted(c) for i, c in item2clusters.items() if len(c) > 1}
print("\nitems mapped to >1 cluster:", len(multi), list(multi.items())[:5])

# same check on the FULL file (including excluded rows)
i2c_full = defaultdict(set)
for r in rows:
    i2c_full[r["question_id"]].add(r["cluster"])
multi_full = {i: sorted(c) for i, c in i2c_full.items() if len(c) > 1}
print("items mapped to >1 cluster (full file):", len(multi_full))

# --- marginals -------------------------------------------------------------
print("\n-- per-model marginals (clean subset) --")
stat = {}
for m in models:
    sub = [r for r in clean if r["model"] == m]
    n = len(sub)
    a = sum(r["A_correct"] for r in sub)
    b = sum(r["B_correct"] for r in sub)
    pa = a / n
    pb = b / n
    stat[m] = (n, a, b, pa, pb, (pb - pa) * 100.0)
    print(f"  {m}: n={n}  A={a} ({pa*100:.4f}%)  B={b} ({pb*100:.4f}%)  "
          f"delta={(pb-pa)*100:+.4f} pp  (rounded {(pb-pa)*100:+.2f} pp)")

# --- claimed numbers, checked one at a time --------------------------------
CLAIM = {
    # model-substring: (n, A_correct, B_correct, A_pct, B_pct, delta_pp)
    "gemini": (325, 318, 291, 97.8, 89.5, -8.31),
    "glm":    (324, 302, 243, 93.2, 75.0, -18.21),
    "qwen":   (325, 288, 236, 88.6, 72.6, -16.00),
    "gemma":  (325, 258, 194, 79.4, 59.7, -19.69),
}
print("\n-- claim check --")
ok_all = True
for key, (cn, ca, cb, cpa, cpb, cd) in CLAIM.items():
    m = [x for x in models if key in x]
    if len(m) != 1:
        print(f"  {key}: MODEL NAME AMBIGUOUS/MISSING -> {m}")
        ok_all = False
        continue
    m = m[0]
    n, a, b, pa, pb, d = stat[m]
    checks = [
        ("n", n == cn, f"{n} vs claimed {cn}"),
        ("A_correct", a == ca, f"{a} vs claimed {ca}"),
        ("B_correct", b == cb, f"{b} vs claimed {cb}"),
        ("A_pct", abs(pa * 100 - cpa) < 0.05, f"{pa*100:.4f} vs claimed {cpa}"),
        ("B_pct", abs(pb * 100 - cpb) < 0.05, f"{pb*100:.4f} vs claimed {cpb}"),
        ("delta_pp", abs(d - cd) < 0.005, f"{d:.4f} vs claimed {cd}"),
    ]
    bad = [c for c in checks if not c[1]]
    print(f"  {m}: {'OK' if not bad else 'MISMATCH'}")
    for name, good, msg in checks:
        print(f"      {name}: {'ok ' if good else 'BAD'} {msg}")
    if bad:
        ok_all = False

# --- b320 specifically -----------------------------------------------------
print("\n-- b320 rows in FULL file --")
for r in rows:
    if r["question_id"] == "b320":
        print("   ", r["model"], "include=", r.get("analysis_include"),
              "defect=", r.get("excl_item_defect"),
              "nota_a=", r.get("excl_nota_position_a"),
              "A=", r["A_correct"], "B=", r["B_correct"])
present_full_b320 = [r["model"] for r in rows if r["question_id"] == "b320"]
print("    models with a b320 row at all:", sorted(present_full_b320))

# --- arithmetic identity: 4*325 - 1 = 1299 ---------------------------------
print("\ncells check: 4*%d - holes(%d) = %d ; observed %d"
      % (len(items), sum(len(v) for v in holes.values()),
         4 * len(items) - sum(len(v) for v in holes.values()), len(clean)))
print("\nALL CLAIMED NUMBERS MATCH:", ok_all)

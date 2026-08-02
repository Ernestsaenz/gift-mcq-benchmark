"""ca_cov_01: confirm the observed cross-arm numbers, and characterise the
covered vs uncovered split of dataset A. Stdlib only.
"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ca_lib as L

BASE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
SHORT = {"google/gemini-3.6-flash": "gemini-3.6-flash",
         "google/gemma-4-26b-a4b-it": "gemma-4-26b-a4b-it",
         "qwen/qwen3.6-35b-a3b": "qwen3.6-35b-a3b",
         "z-ai/glm-5.2": "glm-5.2"}

rows = L.load(include_only=True)
allrows = L.load(include_only=False)
print("cells all / include:", len(allrows), len(rows))
print("items include:", len(set(r['question_id'] for r in rows)),
      " clusters:", len(set(r['cluster'] for r in rows)),
      " models:", len(set(r['model'] for r in rows)))

print("\n=== OBSERVED CONFIRMATION (analysis_include cells) ===")
print(f"{'model':22s} {'n':>4s} {'GIFT':>7s} {'OR':>7s} {'delta_pp':>9s} "
      f"{'b(G+O-)':>8s} {'c(G-O+)':>8s} {'chi2':>6s} {'p_exact':>9s}")
tot_b = tot_c = 0
for m in MODELS + ["POOLED"]:
    sub = rows if m == "POOLED" else [r for r in rows if r['model'] == m]
    n = len(sub)
    g = sum(r['gift_correct'] for r in sub)
    o = sum(r['or_correct'] for r in sub)
    b = sum(1 for r in sub if r['gift_correct'] and not r['or_correct'])
    c = sum(1 for r in sub if r['or_correct'] and not r['gift_correct'])
    x2, _ = L.mcnemar_chi2(b, c)
    pe = L.mcnemar_exact(b, c)
    print(f"{SHORT.get(m,m):22s} {n:4d} {100*g/n:6.1f}% {100*o/n:6.1f}% "
          f"{100*(g-o)/n:+8.2f} {b:8d} {c:8d} {x2:6.2f} {pe:9.4f}")

# ---------------------------------------------------------------- coverage
items, cells = json.load(open(os.path.join(BASE, "ca_cov_or_full.json"))).values()
cov = set(json.load(open(os.path.join(BASE, "gift_coverage.json")))["complete_all_models"])
meta = json.load(open(os.path.join(BASE, "dataset_meta.json")))["exclusions"]
defect = set(meta["administrative_legal_out_of_domain"]) | set(meta["adjudicated_key_defect"])

orc = {}   # (model,qid) -> 0/1
for c_ in cells:
    if c_["exp"] == "expA_or_310726":
        orc[(c_["model"], c_["qid"])] = c_["letter_correct"]
giftc = {}
for c_ in cells:
    if c_["exp"] == "expA_gift_310726":
        giftc[(c_["model"], c_["qid"])] = c_["letter_correct"]

allq = list(items.keys())
print("\n=== COVERAGE SPLIT (dataset A, 474 items) ===")
print("covered (all 4 GIFT models):", len(cov),
      " uncovered:", len(allq) - len(cov))
covd = cov - defect
uncd = set(allq) - cov - defect
print("after dropping the 14 defective items -> covered:", len(covd),
      " uncovered:", len(uncd), " defective:", len(defect))


def or_acc(qids):
    k = n = 0
    for q in qids:
        for m in MODELS:
            v = orc.get((m, q))
            if v is None:
                continue
            n += 1
            k += v
    return k, n


for name, S in [("covered 319 (RUN_STATUS basis)", cov),
                ("uncovered 155 (RUN_STATUS basis)", set(allq) - cov),
                ("covered 311 (clean)", covd),
                ("uncovered 149 (clean)", uncd),
                ("all 474", set(allq)), ("all 460 clean", set(allq) - defect)]:
    k, n = or_acc(S)
    lo, hi = L.wilson(k, n)
    print(f"OR-A accuracy, {name:34s} items={len(S):3d} cells={n:4d} "
          f"{100*k/n:6.2f}%  [{100*lo:.2f},{100*hi:.2f}]")

# item-level difficulty (# of 4 OR models correct); b320/glm missing -> denom 3
diff = {}
for q in allq:
    vs = [orc[(m, q)] for m in MODELS if (m, q) in orc]
    diff[q] = (sum(vs), len(vs))
json.dump({"or_correct": {f"{m}|{q}": v for (m, q), v in orc.items()},
           "gift_correct": {f"{m}|{q}": v for (m, q), v in giftc.items()},
           "difficulty": {q: diff[q] for q in allq},
           "covered": sorted(cov), "defect": sorted(defect)},
          open(os.path.join(BASE, "ca_cov_grid.json"), "w"))

print("\n=== ITEM DIFFICULTY DISTRIBUTION (OR-A models-correct out of 4) ===")
print(f"{'k_correct':>9s} {'covered311':>11s} {'uncovered149':>13s}")
for k in range(5):
    a = sum(1 for q in covd if diff[q][0] == k and diff[q][1] == 4)
    b = sum(1 for q in uncd if diff[q][0] == k and diff[q][1] == 4)
    print(f"{k:9d} {a:11d} {b:13d}")
odd = [q for q in (covd | uncd) if diff[q][1] != 4]
print("items with <4 OR cells:", odd, [diff[q] for q in odd])

# order / prefix structure
print("\n=== ORDER STRUCTURE ===")
cov_ord = sorted(items[q]["order"] for q in cov)
unc_ord = sorted(items[q]["order"] for q in set(allq) - cov)
print("covered order  min/median/max:", cov_ord[0], cov_ord[len(cov_ord)//2], cov_ord[-1])
print("uncovered order min/median/max:", unc_ord[0], unc_ord[len(unc_ord)//2], unc_ord[-1])
print("covered share in first 250 dataset positions:",
      sum(1 for o in cov_ord if o < 250), "/250")
print("covered share in positions 250-473:",
      sum(1 for o in cov_ord if o >= 250), "/224")

print("\n=== REGION MIX ===")
regs = sorted(set(items[q]["region"] for q in allq))
print(f"{'region':22s} {'cov':>5s} {'unc':>5s} {'ORacc_cov':>10s} {'ORacc_unc':>10s}")
for rg in regs:
    a = [q for q in covd if items[q]["region"] == rg]
    b = [q for q in uncd if items[q]["region"] == rg]
    ka, na = or_acc(a); kb, nb = or_acc(b)
    sa = f"{100*ka/na:9.1f}%" if na else "        --"
    sb = f"{100*kb/nb:9.1f}%" if nb else "        --"
    print(f"{rg:22s} {len(a):5d} {len(b):5d} {sa} {sb}")

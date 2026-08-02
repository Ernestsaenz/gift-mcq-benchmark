"""ca_wb_06: the cleanest ability test available in these data.

'Retrieval helps weaker models more' predicts that on the SAME item, a weaker
model should be rescued more often than a stronger one. Restrict to items where
BOTH models of a pair were wrong on OpenRouter, so item difficulty is held
exactly fixed, then compare who GIFT rescued. Exact McNemar (sign) test on the
discordant items.

Same design for breakage: items both models got RIGHT on OpenRouter.
"""
import json, os
from ca_wb_lib import (load, table, MODELS, SHORT, wilson, mcnemar_exact,
                       cluster_boot, ci, boot_p, pct, BASE)

rows = load()
cell = {(r["model"], r["question_id"]): r for r in rows}
items = sorted({r["question_id"] for r in rows})

order = ["google/gemma-4-26b-a4b-it", "qwen/qwen3.6-35b-a3b",
         "z-ai/glm-5.2", "google/gemini-3.6-flash"]   # weakest -> strongest on OR

print("MATCHED RECOVERY: items where BOTH models were wrong on OpenRouter.")
print("b = only model X rescued, c = only model Y rescued, exact McNemar.")
print("%-14s %-14s %6s %8s %8s %5s %5s %10s" % (
    "X (weaker)", "Y (stronger)", "n both", "X recov", "Y recov", "b", "c", "McN exact"))
print("-" * 100)
out = {"recovery": {}, "breakage": {}}
for i in range(len(order)):
    for j in range(i + 1, len(order)):
        X, Y = order[i], order[j]
        both = [q for q in items
                if cell[(X, q)]["or_correct"] == 0 and cell[(Y, q)]["or_correct"] == 0]
        if not both:
            print("%-14s %-14s %6d   (no items both models missed)" % (SHORT[X], SHORT[Y], 0))
            continue
        gx = sum(cell[(X, q)]["gift_correct"] for q in both)
        gy = sum(cell[(Y, q)]["gift_correct"] for q in both)
        b = sum(1 for q in both if cell[(X, q)]["gift_correct"] and not cell[(Y, q)]["gift_correct"])
        c = sum(1 for q in both if cell[(Y, q)]["gift_correct"] and not cell[(X, q)]["gift_correct"])
        p = mcnemar_exact(b, c)
        print("%-14s %-14s %6d %8s %8s %5d %5d %10.4f" % (
            SHORT[X], SHORT[Y], len(both), pct(gx / len(both)), pct(gy / len(both)),
            b, c, p))
        out["recovery"]["%s|%s" % (X, Y)] = dict(n=len(both), gx=gx, gy=gy, b=b, c=c, p=p)

print()
print("MATCHED BREAKAGE: items where BOTH models were right on OpenRouter.")
print("b = only X broken by GIFT, c = only Y broken.")
print("%-14s %-14s %6s %8s %8s %5s %5s %10s" % (
    "X (weaker)", "Y (stronger)", "n both", "X break", "Y break", "b", "c", "McN exact"))
print("-" * 100)
for i in range(len(order)):
    for j in range(i + 1, len(order)):
        X, Y = order[i], order[j]
        both = [q for q in items
                if cell[(X, q)]["or_correct"] == 1 and cell[(Y, q)]["or_correct"] == 1]
        bx = sum(1 - cell[(X, q)]["gift_correct"] for q in both)
        by = sum(1 - cell[(Y, q)]["gift_correct"] for q in both)
        b = sum(1 for q in both if not cell[(X, q)]["gift_correct"] and cell[(Y, q)]["gift_correct"])
        c = sum(1 for q in both if cell[(X, q)]["gift_correct"] and not cell[(Y, q)]["gift_correct"])
        p = mcnemar_exact(b, c)
        print("%-14s %-14s %6d %8s %8s %5d %5d %10.4f" % (
            SHORT[X], SHORT[Y], len(both), pct(bx / len(both)), pct(by / len(both)),
            b, c, p))
        out["breakage"]["%s|%s" % (X, Y)] = dict(n=len(both), bx=bx, by=by, b=b, c=c, p=p)

# ---- the single most informative matched contrast: weakest vs the rest pooled
print()
print("POOLED MATCHED CONTRAST: gemma (weakest, OR 83.0%) vs each stronger model,")
print("on the items where both were wrong on OpenRouter.")
X = "google/gemma-4-26b-a4b-it"
tb = tc = tn = 0
for Y in order[1:]:
    both = [q for q in items
            if cell[(X, q)]["or_correct"] == 0 and cell[(Y, q)]["or_correct"] == 0]
    tn += len(both)
    tb += sum(1 for q in both if cell[(X, q)]["gift_correct"] and not cell[(Y, q)]["gift_correct"])
    tc += sum(1 for q in both if cell[(Y, q)]["gift_correct"] and not cell[(X, q)]["gift_correct"])
print("  %d matched item-pairs; gemma-only rescued %d, stronger-only rescued %d;"
      % (tn, tb, tc))
print("  exact McNemar p = %.4f  (pairs are not independent across the three"
      % mcnemar_exact(tb, tc))
print("  comparisons -- this is descriptive, not a valid single test)")
out["gemma_vs_rest"] = dict(n=tn, b=tb, c=tc, p=mcnemar_exact(tb, tc))

json.dump(out, open(os.path.join(BASE, "ca_wb_06_matched.json"), "w"), indent=1)
print("\nwritten ca_wb_06_matched.json")

"""ca_cov_03: the 108 GIFT cells that fall OUTSIDE the 319 fully-covered items.

GIFT finished 1384 cells but only 319 items x 4 models = 1276 of them form the
paired set. The other 108 cells sit on items that GIFT never completed on all
four models -- i.e. they are drawn from exactly the region the cross-arm
analysis throws away. They are the only *direct* observation of GIFT behaviour
in the uncovered stratum, so they are an out-of-sample check on any transfer
assumption.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ca_lib as L

BASE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
SHORT = {"google/gemini-3.6-flash": "gemini", "google/gemma-4-26b-a4b-it": "gemma",
         "qwen/qwen3.6-35b-a3b": "qwen", "z-ai/glm-5.2": "glm"}

G = json.load(open(os.path.join(BASE, "ca_cov_grid.json")))
orc = {tuple(k.split("|")): v for k, v in G["or_correct"].items()}
gic = {tuple(k.split("|")): v for k, v in G["gift_correct"].items()}
covered = set(G["covered"]); defect = set(G["defect"])
items = json.load(open(os.path.join(BASE, "ca_cov_or_full.json")))["items"]


def loo_k(qid, model):
    vs = [orc[(m, qid)] for m in MODELS if m != model and (m, qid) in orc]
    return sum(vs) if len(vs) == 3 else None


extra = []
for (m, q), gv in gic.items():
    if q in covered:
        continue
    if q in defect:
        continue
    if (m, q) not in orc:
        continue
    extra.append({"question_id": q, "model": m, "gift_correct": gv,
                  "or_correct": orc[(m, q)], "loo_k": loo_k(q, m),
                  "region": items[q]["region"], "order": items[q]["order"]})

print("GIFT cells on NOT-fully-covered, non-defective items:", len(extra))
print("distinct items:", len(set(r["question_id"] for r in extra)))
print("by model:", {SHORT[m]: sum(1 for r in extra if r["model"] == m) for m in MODELS})

n = len(extra)
g = sum(r["gift_correct"] for r in extra); o = sum(r["or_correct"] for r in extra)
b = sum(1 for r in extra if r["gift_correct"] and not r["or_correct"])
c = sum(1 for r in extra if r["or_correct"] and not r["gift_correct"])
print(f"\n=== OUT-OF-SAMPLE (uncovered-region) GIFT vs OR, n={n} cells ===")
print(f"GIFT {100*g/n:.2f}%   OR {100*o/n:.2f}%   delta {100*(g-o)/n:+.2f} pp   "
      f"b={b} c={c}  exact p={L.mcnemar_exact(b,c):.4f}")
lo, hi = L.wilson(g, n); print(f"  GIFT Wilson 95% [{100*lo:.1f},{100*hi:.1f}]")
lo, hi = L.wilson(o, n); print(f"  OR   Wilson 95% [{100*lo:.1f},{100*hi:.1f}]")


def dfn(rs):
    return (sum(r["gift_correct"] - r["or_correct"] for r in rs) / len(rs)) if rs else None


bs = L.cluster_bootstrap(extra, dfn, keyf=lambda r: r["question_id"], B=20000, seed=771)
l2, h2 = L.ci(bs)
print(f"  delta 95% CI (item-level bootstrap, {len(set(r['question_id'] for r in extra))} items): "
      f"[{100*l2:+.2f}, {100*h2:+.2f}] pp")

print(f"\n{'model':8s} {'n':>4s} {'GIFT':>7s} {'OR':>7s} {'delta_pp':>9s} {'b':>3s} {'c':>3s}")
for m in MODELS:
    sub = [r for r in extra if r["model"] == m]
    if not sub:
        continue
    nn = len(sub)
    gg = sum(r["gift_correct"] for r in sub); oo = sum(r["or_correct"] for r in sub)
    bb = sum(1 for r in sub if r["gift_correct"] and not r["or_correct"])
    cc = sum(1 for r in sub if r["or_correct"] and not r["gift_correct"])
    print(f"{SHORT[m]:8s} {nn:4d} {100*gg/nn:6.1f}% {100*oo/nn:6.1f}% "
          f"{100*(gg-oo)/nn:+8.2f} {bb:3d} {cc:3d}")

print(f"\n{'loo_k':>5s} {'n':>4s} {'GIFT':>7s} {'OR':>7s} {'delta_pp':>9s}")
for k in range(4):
    sub = [r for r in extra if r["loo_k"] == k]
    if not sub:
        continue
    nn = len(sub)
    gg = sum(r["gift_correct"] for r in sub); oo = sum(r["or_correct"] for r in sub)
    print(f"{k:5d} {nn:4d} {100*gg/nn:6.1f}% {100*oo/nn:6.1f}% {100*(gg-oo)/nn:+8.2f}")

# how representative of the truly-uncovered mass are these 108 cells?
uncov_items = [q for q in items if q not in covered and q not in defect]
print("\nuncovered clean items:", len(uncov_items),
      " of which touched by >=1 GIFT cell:",
      len(set(r["question_id"] for r in extra)))
oo = sum(orc[(m, q)] for q in uncov_items for m in MODELS if (m, q) in orc)
nn = sum(1 for q in uncov_items for m in MODELS if (m, q) in orc)
print(f"OR accuracy over ALL uncovered clean cells: {100*oo/nn:.2f}% (n={nn})")
print(f"OR accuracy over the 108 GIFT-touched uncovered cells: {100*o/n:.2f}% (n={n})")

json.dump({"n": n, "gift": g, "orr": o, "b": b, "c": c,
           "delta": (g - o) / n, "ci": [l2, h2],
           "or_all_uncovered": oo / nn, "n_all_uncovered": nn,
           "cells": extra},
          open(os.path.join(BASE, "ca_cov_03_out.json"), "w"), indent=1)

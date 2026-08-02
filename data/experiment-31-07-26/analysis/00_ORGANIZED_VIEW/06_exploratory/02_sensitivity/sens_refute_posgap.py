#!/usr/bin/env python3
"""
Independent recomputation of the 'position-artifact' robustness claim.

CLAIM under test:
  full delta = -17.3270 pp ; published delta = -15.5504 pp ; gap = 1.7766 pp
  gap decomposes as 1.58 pp (position-(a) exclusion) + 0.20 pp (item-defect + reweighting)
  => exclusions shrank the degradation by ~1/10, not qualitatively.

Method: per-cell paired difference d = B_correct - A_correct over (item x model) cells.
Pooled delta = mean(d) * 100. Direct arithmetic; no model.
"""
import json, os, random, math
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(BASE, "paired_clean.json")
rows = json.load(open(P))

def pct(x):
    return 100.0 * x

def summarize(sub, name):
    n = len(sub)
    a = sum(r["A_correct"] for r in sub)
    b = sum(r["B_correct"] for r in sub)
    d = [r["B_correct"] - r["A_correct"] for r in sub]
    delta = 100.0 * sum(d) / n if n else float("nan")
    items = len({r["question_id"] for r in sub})
    clus = len({r["cluster"] for r in sub})
    return dict(name=name, n=n, items=items, clusters=clus,
                A=100.0*a/n, B=100.0*b/n, delta=delta)

def line(s):
    print(f"{s['name']:<34} n={s['n']:>5} items={s['items']:>4} clus={s['clusters']:>4} "
          f"A={s['A']:8.4f} B={s['B']:8.4f} delta={s['delta']:9.4f}")

print("=" * 110)
print("SECTION 0 -- integrity of the exclusion flags")
print("=" * 110)
bad = [r for r in rows if r["analysis_include"] != (not r["excl_item_defect"] and not r["excl_nota_position_a"])]
print(f"rows where analysis_include != NOT(defect) AND NOT(pos_a): {len(bad)}")
missing = [r for r in rows if r.get("A_correct") is None or r.get("B_correct") is None]
print(f"rows with missing A_correct/B_correct: {len(missing)}")
vals = {(r["A_correct"], r["B_correct"]) for r in rows}
print(f"distinct (A_correct,B_correct) value pairs: {sorted(vals)}")

# does the pos-a flag really equal correct_letter=='a'?
mism = [r for r in rows if (r["correct_letter"] == "a") != r["excl_nota_position_a"]]
print(f"rows where excl_nota_position_a != (correct_letter=='a'): {len(mism)}")
posa_items = {r["question_id"] for r in rows if r["excl_nota_position_a"]}
def_items = {r["question_id"] for r in rows if r["excl_item_defect"]}
print(f"n items flagged pos_a: {len(posa_items)}  n items flagged defect: {len(def_items)}  "
      f"overlap: {len(posa_items & def_items)}")

meta = json.load(open(os.path.join(BASE, "dataset_meta.json")))
named = set(meta["exclusions"]["administrative_legal_out_of_domain"]) | set(meta["exclusions"]["adjudicated_key_defect"])
print(f"meta-named defect items: {len(named)}  match flag set: {named == def_items}")
print(f"cells per item distribution (all): ", end="")
cnt = defaultdict(int)
per = defaultdict(int)
for r in rows:
    per[r["question_id"]] += 1
for v in per.values():
    cnt[v] += 1
print(dict(sorted(cnt.items())))

print()
print("=" * 110)
print("SECTION 1 -- the four headline sets (claim's own NUMBERS block)")
print("=" * 110)
FULL = rows
NO_DEF = [r for r in rows if not r["excl_item_defect"]]
NO_POSA = [r for r in rows if not r["excl_nota_position_a"]]
PUB = [r for r in rows if r["analysis_include"]]

sF = summarize(FULL, "FULL (unfiltered)")
sD = summarize(NO_DEF, "drop item-defects only")
sP = summarize(NO_POSA, "drop position-(a) only")
sB = summarize(PUB, "PUBLISHED (both dropped)")
for s in (sF, sD, sP, sB):
    line(s)

claimed = {
    "FULL n": 1691, "FULL A": 89.36, "FULL B": 72.03, "FULL delta": -17.3270,
    "PUB n": 1299, "PUB delta": -15.5504,
    "NODEF n": 1647, "NODEF delta": -17.06,
    "NOPOSA n": 1327, "NOPOSA delta": -15.7498,
}
print()
print("check vs claimed:")
checks = [
    ("FULL n", sF["n"], 1691, 0), ("FULL A%", sF["A"], 89.36, 0.005),
    ("FULL B%", sF["B"], 72.03, 0.005), ("FULL delta", sF["delta"], -17.3270, 0.0001),
    ("PUB n", sB["n"], 1299, 0), ("PUB delta", sB["delta"], -15.5504, 0.0001),
    ("NODEF n", sD["n"], 1647, 0), ("NODEF delta", sD["delta"], -17.06, 0.005),
    ("NOPOSA n", sP["n"], 1327, 0), ("NOPOSA delta", sP["delta"], -15.7498, 0.0001),
]
for nm, got, want, tol in checks:
    ok = abs(got - want) <= tol
    print(f"  {nm:<14} recomputed={got:12.4f}  claimed={want:10.4f}  |diff|={abs(got-want):.6f}  {'OK' if ok else '*** MISMATCH ***'}")

gap = sB["delta"] - sF["delta"]
print(f"\n  gap (published - full) = {gap:.4f} pp  (claim: 1.7766)  diff={abs(gap-1.7766):.6f}")

print()
print("=" * 110)
print("SECTION 2 -- path decomposition of the gap (order matters)")
print("=" * 110)
path1_a = sP["delta"] - sF["delta"]          # full -> drop posa
path1_b = sB["delta"] - sP["delta"]          # -> also drop defects
path2_a = sD["delta"] - sF["delta"]          # full -> drop defects
path2_b = sB["delta"] - sD["delta"]          # -> also drop posa
print(f"PATH 1 (posa first, the claim's path):")
print(f"   step posa    : {path1_a:+.4f} pp   (claim 1.58)")
print(f"   step defect  : {path1_b:+.4f} pp   (claim 0.20)")
print(f"   sum          : {path1_a+path1_b:+.4f} pp")
print(f"PATH 2 (defect first):")
print(f"   step defect  : {path2_a:+.4f} pp")
print(f"   step posa    : {path2_b:+.4f} pp")
print(f"   sum          : {path2_a+path2_b:+.4f} pp")
sh_posa = 0.5 * (path1_a + path2_b)
sh_def = 0.5 * (path2_a + path1_b)
print(f"SHAPLEY (order-averaged):  posa={sh_posa:+.4f}  defect={sh_def:+.4f}  sum={sh_posa+sh_def:+.4f}")
print(f"interaction term |path1_a - path2_b| = {abs(path1_a-path2_b):.4f} pp")

print()
print("=" * 110)
print("SECTION 3 -- what the excluded strata actually look like")
print("=" * 110)
POSA_ONLY = [r for r in rows if r["excl_nota_position_a"]]
DEF_ONLY = [r for r in rows if r["excl_item_defect"]]
POSA_NODEF = [r for r in rows if r["excl_nota_position_a"] and not r["excl_item_defect"]]
DEF_NOPOSA = [r for r in rows if r["excl_item_defect"] and not r["excl_nota_position_a"]]
BOTH = [r for r in rows if r["excl_item_defect"] and r["excl_nota_position_a"]]
DROPPED = [r for r in rows if not r["analysis_include"]]
for sub, nm in ((POSA_ONLY, "EXCLUDED: pos-(a) (any)"), (POSA_NODEF, "EXCLUDED: pos-(a) & not defect"),
                (DEF_ONLY, "EXCLUDED: item-defect (any)"), (DEF_NOPOSA, "EXCLUDED: defect & not pos-(a)"),
                (BOTH, "EXCLUDED: both flags"), (DROPPED, "EXCLUDED: all dropped cells")):
    if sub:
        line(summarize(sub, nm))

print()
print("=" * 110)
print("SECTION 4 -- algebraic sanity: gap as weighted contrast")
print("=" * 110)
nF, nB = sF["n"], sB["n"]
nDrop = nF - nB
dDrop = summarize(DROPPED, "drop")["delta"]
# delta_full = w*delta_pub + (1-w)*delta_drop
w = nB / nF
recon = w * sB["delta"] + (1 - w) * dDrop
print(f"  n_full={nF} n_pub={nB} n_dropped={nDrop}  w=n_pub/n_full={w:.6f}")
print(f"  reconstruction w*delta_pub+(1-w)*delta_drop = {recon:.4f}  vs delta_full={sF['delta']:.4f}")
print(f"  gap identity (1-w)*(delta_pub - delta_drop) = {(1-w)*(sB['delta']-dDrop):.4f}  vs gap={gap:.4f}")

print()
print("=" * 110)
print("SECTION 5 -- is the shrinkage 'about a tenth'? relative framings")
print("=" * 110)
print(f"  gap / |delta_full|             = {gap/abs(sF['delta'])*100:.2f} %")
print(f"  gap / |delta_pub|              = {gap/abs(sB['delta'])*100:.2f} %")
print(f"  ratio delta_pub / delta_full   = {sB['delta']/sF['delta']:.4f}")

#!/usr/bin/env python3
"""
sens_exclusion_strata.py -- is each exclusion rule REMOVING a genuinely different
stratum, or is it removing noise?

For each rule, compare the A->B delta INSIDE the excluded stratum against the
delta in its complement, as a paired contrast on the SAME bootstrap resample of
clinical-context clusters (clusters straddle both strata, so pairing is required).

  interaction = delta(excluded stratum) - delta(retained stratum)
  negative  => the excluded items degrade MORE than the ones kept
              => the exclusion is doing real work, not just trimming n

95% percentile CI from 20000 cluster-bootstrap replicates; two-sided bootstrap p.
Also reports the letter-position profile of B answers to characterise the defect.
stdlib only.
"""
import json, os, random, math
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "paired_clean.json")))
MODELS = sorted(set(r["model"] for r in rows))
KEYS = ["*"] + MODELS
R, SEED = 20000, 20260731

STRATA = {
    "posA":   ("excl_nota_position_a", "correct letter == 'a' (91 items)"),
    "defect": ("excl_item_defect",     "adjudicated defective (11 items present)"),
}

for sname, (field, desc) in STRATA.items():
    tab = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0, 0, 0])))
    for r in rows:
        arm = "IN" if r[field] else "OUT"
        for k in (r["model"], "*"):
            t = tab[r["cluster"]][arm][k]
            t[0] += 1; t[1] += r["A_correct"]; t[2] += r["B_correct"]
    clusters = sorted(tab)
    C = len(clusters)
    flat = [[(arm, k, v[0], v[1], v[2]) for arm in tab[c] for k, v in tab[c][arm].items()] for c in clusters]

    def agg(idxs):
        acc = {a: {k: [0, 0, 0] for k in KEYS} for a in ("IN", "OUT")}
        for i in idxs:
            for (arm, k, n, sa, sb) in flat[i]:
                t = acc[arm][k]; t[0] += n; t[1] += sa; t[2] += sb
        return acc

    obs = agg(range(C))
    rng = random.Random(SEED)
    reps = [agg([rng.randrange(C) for _ in range(C)]) for _ in range(R)]

    def dlt(acc, arm, k):
        n, sa, sb = acc[arm][k]
        return (sb - sa) / n if n else None

    def pct(v, q):
        v = sorted(v); i = q * (len(v) - 1)
        lo, hi = int(math.floor(i)), int(math.ceil(i))
        return v[lo] if lo == hi else v[lo] + (v[hi] - v[lo]) * (i - lo)

    print("=" * 100)
    print(f"STRATUM '{sname}'  --  {desc}")
    print("=" * 100)
    print(f"{'model':<26} {'d_excluded':>12} {'d_retained':>12} {'interaction':>13} {'95% CI':>22} {'p_boot':>9}")
    for k in KEYS:
        di, do = dlt(obs, "IN", k), dlt(obs, "OUT", k)
        if di is None or do is None:
            continue
        vals = [dlt(rp, "IN", k) - dlt(rp, "OUT", k) for rp in reps
                if dlt(rp, "IN", k) is not None and dlt(rp, "OUT", k) is not None]
        lo, hi = pct(vals, 0.025), pct(vals, 0.975)
        nle = sum(1 for x in vals if x <= 0); nge = sum(1 for x in vals if x >= 0)
        p = min(1.0, 2 * min(nle, nge) / len(vals))
        nm = "POOLED" if k == "*" else k.split("/")[-1]
        star = " *" if (lo > 0 or hi < 0) else ""
        print(f"{nm:<26} {di:>+12.4f} {do:>+12.4f} {di-do:>+13.4f} "
              f"{'['+format(lo,'+.4f')+','+format(hi,'+.4f')+']':>22} {p:>9.4f}{star}")
    print()

# ---- letter-position profile of B answers -------------------------------------
print("=" * 100)
print("WHERE DO MODELS GO IN ARM B?  distribution of B_selected relative to the NOTA slot")
print("=" * 100)
print(f"{'stratum':<12} {'model':<26} {'n':>5} {'picks NOTA slot':>16} {'picks (a)':>11} {'picks other':>12}")
for label, sel in (("posA", lambda r: r["excl_nota_position_a"]), ("rest", lambda r: not r["excl_nota_position_a"])):
    for m in MODELS + ["*"]:
        sub = [r for r in rows if sel(r) and (m == "*" or r["model"] == m)]
        n = len(sub)
        nota = sum(1 for r in sub if r["B_selected"] == r["correct_letter"])
        pa = sum(1 for r in sub if r["B_selected"] == "a")
        print(f"{label:<12} {('POOLED' if m=='*' else m.split('/')[-1]):<26} {n:>5} "
              f"{nota/n:>16.4f} {pa/n:>11.4f} {(n-nota)/n:>12.4f}")
    print()

# ---- how many of the 14 named defective items are actually in the file ---------
meta = json.load(open(os.path.join(HERE, "dataset_meta.json")))
named = meta["exclusions"]["administrative_legal_out_of_domain"] + meta["exclusions"]["adjudicated_key_defect"]
present = set(r["question_id"] for r in rows)
flagged = set(r["question_id"] for r in rows if r["excl_item_defect"])
print("=" * 100)
print("PROVENANCE CHECK ON THE '14 DEFECTIVE ITEMS'")
print("=" * 100)
print(f"  named in dataset_meta.json : {len(named)}")
print(f"  present in paired_clean    : {len([q for q in named if q in present])}  -> {sorted(q for q in named if q in present)}")
print(f"  ABSENT from paired_clean   : {len([q for q in named if q not in present])} -> {sorted(q for q in named if q not in present)}")
print(f"  flagged excl_item_defect   : {len(flagged)}")
print(f"  items in file              : {len(present)}   cells: {len(rows)}   (423*4 = 1692, so 1 cell unparsed)")
missing = [(q, 4 - c) for q, c in Counter(r['question_id'] for r in rows).items() if c != 4]
print(f"  incomplete items           : {missing}")

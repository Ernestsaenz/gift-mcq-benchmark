#!/usr/bin/env python3
"""Side-by-side: the 311-item export the claim was made against (reconstructed from
the DB + the OLD 14-item exclusion list) vs the 306-item export now on disk
(regenerated 2026-07-31 10:47:46 with a 22-item exclusion list).
"""
import json, math, sqlite3, collections

BASE = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/"
AN = BASE + "analysis/"
con = sqlite3.connect("file:" + BASE + "experiment.sqlite?mode=ro", uri=True)
con.row_factory = sqlite3.Row
sf = lambda x: math.erfc(math.sqrt(x / 2.0))

SQL = """
select q.question_id, lc.model, s.strict_correct
from scores s
join parsed_answers pa on pa.id = s.parsed_answer_id
join logical_calls lc  on lc.id = s.logical_call_id
join questions q       on q.id = lc.question_id
join experiments e     on e.id = lc.experiment_id
where e.name = ?
"""
pull = lambda e: {(r["question_id"], r["model"]): r["strict_correct"] for r in con.execute(SQL, (e,))}
gift, orr = pull("expA_gift_310726"), pull("expA_or_310726")
models = sorted({m for (_, m) in orr})
cov = set(json.load(open(AN + "gift_coverage.json"))["complete_all_models"])

meta = json.load(open(AN + "dataset_meta.json"))
NEW_EXCL = set(meta["exclusions"]["out_of_domain_law"]) | set(meta["exclusions"]["adjudicated_key_defect"])
# The OLD set: whatever made the covered set 311. Recover it from the claim-era counts:
# RUN_STATUS says 11 law + 3 adjudicated = 14, of which 8 were covered.
# Identify the 8 by taking NEW_EXCL & cov (13) and finding which 5 are new.
covered_excl = sorted(NEW_EXCL & cov)
print("exclusion ids inside the GIFT-covered 319:", len(covered_excl))
print("  ", covered_excl)


def table(excl, label):
    items = sorted(cov - excl)
    tot = collections.Counter()
    per = {}
    for m in models:
        a = b = c = d = 0
        for q in items:
            gc, oc = gift[(q, m)], orr[(q, m)]
            if gc and oc: a += 1
            elif gc and not oc: b += 1
            elif not gc and oc: c += 1
            else: d += 1
        n = a + b + c + d
        per[m] = (n, 100 * (a + b) / n, 100 * (a + c) / n, b, c)
        tot["a"] += a; tot["b"] += b; tot["c"] += c; tot["d"] += d
    N = sum(tot.values())
    per["POOLED"] = (N, 100 * (tot["a"] + tot["b"]) / N, 100 * (tot["a"] + tot["c"]) / N, tot["b"], tot["c"])
    print(f"\n--- {label}: {len(items)} items, {N} cells ---")
    print(f"{'model':<26}{'n':>5}{'GIFT%':>9}{'OR%':>9}{'diff':>8}{'b':>4}{'c':>4}")
    for m in models + ["POOLED"]:
        n, g, o, b, c = per[m]
        print(f"{m:<26}{n:>5}{g:>9.4f}{o:>9.4f}{g-o:>8.4f}{b:>4}{c:>4}")
    B, C = tot["b"], tot["c"]
    u, k = (B - C) ** 2 / (B + C), (abs(B - C) - 1) ** 2 / (B + C)
    print(f"  uncorrected chi2 = {u:.4f} (p={sf(u):.5f})   continuity-corrected = {k:.4f} (p={sf(k):.5f})")
    return per, u, k


# reconstruct the claim-era 311 set: drop the 5 newest law items from the covered exclusions
# (the 5 that take 311 -> 306). Find them by brute force: which 5-subset leaves 311?
old_excl_covered = None
for skip in range(len(covered_excl) + 1):
    pass
# simpler: the claim-era set had 8 covered exclusions -> pick the 3 adjudicated + 5 law that
# reproduce 311. We know |cov - old_excl| = 311 -> |old_excl & cov| = 8.
adj = set(meta["exclusions"]["adjudicated_key_defect"])
print("\nadjudicated ids covered:", sorted(adj & cov))

per_new, u_new, k_new = table(NEW_EXCL, "CURRENT export on disk (22-item exclusion list)")

# claim-era: search for the 8-subset of covered_excl that reproduces b=46,c=24 pooled
import itertools
found = None
for sub in itertools.combinations(covered_excl, 8):
    s = set(sub)
    if not (adj & cov) <= s:
        continue
    items = sorted(cov - s)
    b = c = 0
    for m in models:
        for q in items:
            gc, oc = gift[(q, m)], orr[(q, m)]
            if gc and not oc: b += 1
            elif not gc and oc: c += 1
    if b == 46 and c == 24:
        found = s
        break
print("\nclaim-era 8 covered exclusions recovered:", sorted(found) if found else "NOT FOUND")
if found:
    per_old, u_old, k_old = table(found, "CLAIM-ERA export (14-item exclusion list)")
    newly = sorted((NEW_EXCL & cov) - found)
    print("\n5 items newly excluded by the 10:47:46 regeneration:", newly)
    for q in newly:
        t = con.execute("select question_text from questions q join datasets d on d.id=q.dataset_id "
                        "where d.name='balanced_a_310726' and q.question_id=?", (q,)).fetchone()[0]
        print(f"   {q}: {t[:110]}")

    print("\n=== CLAIM'S ASSERTIONS vs CLAIM-ERA DATA ===")
    claimed = {"google/gemma-4-26b-a4b-it": (88.42, 82.96, 24, 7),
               "z-ai/glm-5.2": (96.46, 93.25, 11, 1),
               "qwen/qwen3.6-35b-a3b": (91.64, 92.28, 11, 13),
               "google/gemini-3.6-flash": (97.43, 98.39, 0, 3),
               "POOLED": (93.49, 91.72, 46, 24)}
    allok = True
    for m, (cg, co, cb, cc) in claimed.items():
        n, g, o, b, c = per_old[m]
        ok = abs(g - cg) < .005 and abs(o - co) < .005 and b == cb and c == cc
        allok &= ok
        print(f"  {m:<26} {'MATCH' if ok else 'MISMATCH'}")
    print("  claim reproduces on claim-era data:", allok)
    print(f"  claim-era cc chi2 = {k_old:.4f}  (claim says 6.3000)  -> {'MATCH' if abs(k_old-6.3)<1e-9 else 'MISMATCH'}")
    print(f"  claim-era unc chi2 = {u_old:.4f} (claim says 6.9143)  -> {'MATCH' if abs(u_old-6.9143)<1e-4 else 'MISMATCH'}")
    print(f"\n=== SAME ASSERTIONS vs CURRENT DATA ===")
    n, g, o, b, c = per_new["POOLED"]
    print(f"  POOLED now {g:.4f}/{o:.4f} b={b} c={c};  cc chi2 = {k_new:.4f}, unc = {u_new:.4f}")
    print(f"  '6.3000' appears in the current export: {abs(k_new-6.3)<1e-9 or abs(u_new-6.3)<1e-9}")

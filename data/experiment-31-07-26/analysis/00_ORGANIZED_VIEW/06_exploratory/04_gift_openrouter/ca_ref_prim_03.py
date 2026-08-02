#!/usr/bin/env python3
"""Rebuild the cross-arm 2x2s FROM THE DATABASE, ignoring cross_arm_A.json entirely.
Then diff against the export. This is the real independence test of the claim.
"""
import json, math, sqlite3, collections

BASE = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/"
AN = BASE + "analysis/"
con = sqlite3.connect("file:" + BASE + "experiment.sqlite?mode=ro", uri=True)
con.row_factory = sqlite3.Row

print("=== experiments in DB ===")
for r in con.execute("select e.id,e.name,d.name ds,e.prompt_version from experiments e join datasets d on d.id=e.dataset_id order by e.id"):
    print(f"  id={r['id']:<3} {r['name']:<22} dataset={r['ds']:<22} prompt={r['prompt_version']}")

# Explicit experiment names ONLY (RUN_STATUS hazard #2), and the scored attempt path
# scores -> parsed_answers.provider_attempt_id -> provider_attempts.
SQL = """
select q.question_id, lc.model, s.strict_correct, pa.selected_letter, q.correct_letter
from scores s
join parsed_answers pa on pa.id = s.parsed_answer_id
join logical_calls lc  on lc.id = s.logical_call_id
join questions q       on q.id = lc.question_id
join experiments e     on e.id = lc.experiment_id
where e.name = ?
"""


def pull(expname):
    d = {}
    dupes = 0
    for r in con.execute(SQL, (expname,)):
        k = (r["question_id"], r["model"])
        if k in d:
            dupes += 1
        d[k] = (r["strict_correct"], r["selected_letter"], r["correct_letter"])
    return d, dupes


gift, dg = pull("expA_gift_310726")
orr, do = pull("expA_or_310726")
print()
print(f"GIFT arm scored cells in DB : {len(gift)}   (dup keys: {dg})")
print(f"OR   arm scored cells in DB : {len(orr)}   (dup keys: {do})")

# GIFT coverage: questions complete on all four models
models = sorted({m for (_, m) in orr})
print("models:", models)
gcov = collections.defaultdict(set)
for (q, m) in gift:
    gcov[q].add(m)
complete = {q for q, s in gcov.items() if len(s) == len(models) and s == set(models)}
print(f"questions GIFT completed on ALL {len(models)} models: {len(complete)}   (RUN_STATUS says 319)")

covfile = json.load(open(AN + "gift_coverage.json"))
covids = set(covfile if isinstance(covfile, list) else covfile.get("question_ids", covfile))
print(f"gift_coverage.json ids: {len(covids)}  identical to DB-derived set: {complete == covids}")

# exclusions
meta = json.load(open(AN + "dataset_meta.json"))
print("dataset_meta.json keys:", list(meta.keys())[:12])
defects = None
for k, v in meta.items():
    if isinstance(v, list) and v and isinstance(v[0], str) and all(x.startswith("b") for x in v[:5]):
        print(f"  meta['{k}'] -> {len(v)} ids, sample {v[:6]}")
        if defects is None or len(v) > len(defects):
            defects = set(v)
print("defect id set size used:", len(defects) if defects else None)

analysed = sorted(complete - (defects or set()))
print(f"\nDB-derived analysis items: {len(analysed)}   (claim/RUN_STATUS say 311)")

# Build 2x2 straight from DB
print()
print("=== DB-DERIVED 2x2 (independent of cross_arm_A.json) ===")
print(f"{'model':<26}{'n':>5}{'GIFT%':>9}{'OR%':>9}{'diff_pp':>9}{'b':>4}{'c':>4}")
tot = collections.Counter()
db_rows = []
for m in models:
    a = b = c = d = 0
    for q in analysed:
        gk, ok = gift.get((q, m)), orr.get((q, m))
        if gk is None or ok is None:
            continue
        gc, oc = gk[0], ok[0]
        db_rows.append((q, m, gc, oc))
        if gc and oc: a += 1
        elif gc and not oc: b += 1
        elif not gc and oc: c += 1
        else: d += 1
    n = a + b + c + d
    tot["a"] += a; tot["b"] += b; tot["c"] += c; tot["d"] += d
    print(f"{m:<26}{n:>5}{100*(a+b)/n:>9.4f}{100*(a+c)/n:>9.4f}{100*(b-c)/n:>9.4f}{b:>4}{c:>4}")
N = sum(tot.values())
print(f"{'POOLED':<26}{N:>5}{100*(tot['a']+tot['b'])/N:>9.4f}{100*(tot['a']+tot['c'])/N:>9.4f}"
      f"{100*(tot['b']-tot['c'])/N:>9.4f}{tot['b']:>4}{tot['c']:>4}")

B, C = tot["b"], tot["c"]
unc = (B - C) ** 2 / (B + C)
cc = (abs(B - C) - 1) ** 2 / (B + C)
sf = lambda x: math.erfc(math.sqrt(x / 2.0))
print(f"\nDB uncorrected chi2 = {unc:.4f} (p={sf(unc):.5f})   DB continuity-corrected = {cc:.4f} (p={sf(cc):.5f})")

# === diff DB vs export, cell by cell ===
print()
print("=== CELL-BY-CELL DIFF: DB vs cross_arm_A.json ===")
exp = {(r["question_id"], r["model"]): (r["gift_correct"], r["or_correct"])
       for r in json.load(open(AN + "cross_arm_A.json")) if r["analysis_include"]}
dbm = {(q, m): (gc, oc) for (q, m, gc, oc) in db_rows}
print("export cells:", len(exp), " db cells:", len(dbm))
only_exp = set(exp) - set(dbm)
only_db = set(dbm) - set(exp)
disagree = [k for k in set(exp) & set(dbm) if exp[k] != dbm[k]]
print("in export not DB:", len(only_exp), sorted(only_exp)[:5])
print("in DB not export:", len(only_db), sorted(only_db)[:5])
print("value disagreements:", len(disagree), disagree[:5])
print("EXPORT FAITHFULLY REPRODUCES THE DB:", not only_exp and not only_db and not disagree)

# === coverage bias, recomputed from DB ===
print()
print("=== COVERAGE BIAS (recomputed from DB) ===")
allq = {q for (q, m) in orr}
uncovered = allq - complete
def or_acc(qs):
    v = [orr[(q, m)][0] for q in qs for m in models if (q, m) in orr]
    return 100 * sum(v) / len(v), len(v)
ac, nc = or_acc(complete)
au, nu = or_acc(uncovered)
print(f"OR accuracy on {len(complete)} GIFT-covered items   : {ac:.2f}%  (n={nc} cells)")
print(f"OR accuracy on {len(uncovered)} never-covered items : {au:.2f}%  (n={nu} cells)")
print(f"covered items are {ac-au:.2f}pp easier  -> RUN_STATUS claims 91.1 vs 82.9 (8.2pp)")

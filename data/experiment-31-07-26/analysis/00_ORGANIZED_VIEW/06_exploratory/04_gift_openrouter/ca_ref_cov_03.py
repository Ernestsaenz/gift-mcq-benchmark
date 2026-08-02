"""ca_ref_cov_03: does the sequential-prefix coverage bias undermine the pooled GIFT advantage?
Independent pull from experiment.sqlite (scores -> parsed_answers -> provider_attempts join,
explicit experiment names per RUN_STATUS hazard #2). Stdlib only.
"""
import json, math, os, random, sqlite3
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.path.dirname(BASE), "experiment.sqlite")
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

MODELS = ["google/gemma-4-26b-a4b-it", "z-ai/glm-5.2",
          "qwen/qwen3.6-35b-a3b", "google/gemini-3.6-flash"]
SHORT = {"google/gemini-3.6-flash": "gemini", "google/gemma-4-26b-a4b-it": "gemma",
         "qwen/qwen3.6-35b-a3b": "qwen", "z-ai/glm-5.2": "glm"}

Q = """
select q.question_id, q.region, q.question_number, l.model, s.letter_correct
from scores s
join parsed_answers p on p.id = s.parsed_answer_id
join logical_calls  l on l.id = s.logical_call_id
join experiments    e on e.id = l.experiment_id
join questions      q on q.id = l.question_id
join datasets       d on d.id = q.dataset_id
where e.name = ? and d.name = 'balanced_a_310726' and p.parse_status = 'ok'
"""
orc, gic, region, qnum = {}, {}, {}, {}
for qid, rg, num, m, lc in con.execute(Q, ("expA_or_310726",)):
    orc[(m, qid)] = lc
    region[qid] = rg
    qnum[qid] = num
for qid, rg, num, m, lc in con.execute(Q, ("expA_gift_310726",)):
    gic[(m, qid)] = lc
allq = sorted(region, key=lambda x: int(x[1:]))
print("dataset A items:", len(allq), " OR scored cells:", len(orc), " GIFT scored cells:", len(gic))

covered = sorted(q for q in allq if all((m, q) in gic and (m, q) in orc for m in MODELS))
print("items complete on all 4 GIFT models AND all 4 OR models:", len(covered))
cov_run = set(json.load(open(os.path.join(BASE, "gift_coverage.json")))["complete_all_models"])
print("agrees with shipped gift_coverage.json:", set(covered) == cov_run, len(cov_run))

meta = json.load(open(os.path.join(BASE, "dataset_meta.json")))["exclusions"]
DEFECT = set(meta["out_of_domain_law"]) | set(meta["adjudicated_key_defect"])
covd = [q for q in covered if q not in DEFECT]
uncd = [q for q in allq if q not in cov_run and q not in DEFECT]
print(f"clean covered={len(covd)}  clean uncovered={len(uncd)}  defect={len(DEFECT)}")


def acc(qs, table):
    k = n = 0
    for q in qs:
        for m in MODELS:
            v = table.get((m, q))
            if v is None:
                continue
            n += 1
            k += v
    return k, n


print("\n=== 1. IS THE COVERED SUBSET EASIER? (OpenRouter, the arm with full coverage) ===")
for nm, qs in [("covered 319 (raw)", sorted(cov_run)),
               ("uncovered 155 (raw)", [q for q in allq if q not in cov_run]),
               ("covered clean", covd), ("uncovered clean", uncd)]:
    k, n = acc(qs, orc)
    print(f"  OR-A {nm:22s} items={len(qs):3d} cells={n:4d} acc={100*k/n:6.2f}%")
k1, n1 = acc(sorted(cov_run), orc)
k2, n2 = acc([q for q in allq if q not in cov_run], orc)
print(f"  gap = {100*(k1/n1 - k2/n2):.2f}pp   (RUN_STATUS claims 91.1 vs 82.9 = 8.2pp)")

print("\n=== 2. POSITION STRUCTURE (coverage is a prefix, so position is a proxy for coverage) ===")
pos = {q: i for i, q in enumerate(allq)}
cs = sorted(pos[q] for q in cov_run)
print(f"  covered positions: min={cs[0]} median={cs[len(cs)//2]} max={cs[-1]}")
for lo, hi in [(0, 118), (118, 237), (237, 355), (355, 474)]:
    blk = [q for q in allq if lo <= pos[q] < hi]
    nc = sum(1 for q in blk if q in cov_run)
    k, n = acc(blk, orc)
    print(f"  positions {lo:3d}-{hi:3d}: covered {nc:3d}/{len(blk):3d} ({100*nc/len(blk):5.1f}%)  "
          f"OR acc {100*k/n:6.2f}%")

# ------------------------------------------------------------------ 3. difficulty strata
# LOO difficulty: for cell (m,q) use how many of the OTHER 3 OR models got q right.
# Using all 4 would mechanically force the paired delta (if all 4 OR right, GIFT can only lose).
def loo(m, q):
    vs = [orc[(mm, q)] for mm in MODELS if mm != m and (mm, q) in orc]
    return sum(vs), len(vs)


print("\n=== 3. THE STRATIFIER IS ITSELF THE OUTCOME -- mechanical coupling check ===")
print("  paired delta by FULL OR difficulty k (all 4 OR models), covered clean items:")
print(f"  {'k':>2s} {'cells':>6s} {'b':>4s} {'c':>4s} {'delta_pp':>9s}")
for k in range(5):
    sub = [(m, q) for q in covd for m in MODELS
           if sum(orc[(mm, q)] for mm in MODELS) == k]
    if not sub:
        continue
    b = sum(1 for m, q in sub if gic[(m, q)] and not orc[(m, q)])
    c = sum(1 for m, q in sub if orc[(m, q)] and not gic[(m, q)])
    print(f"  {k:2d} {len(sub):6d} {b:4d} {c:4d} {100*(b-c)/len(sub):+9.2f}")
print("  -> at k=4 b is forced to 0, at k=0 c is forced to 0: this stratifier cannot be reweighted.")

print("\n=== 4. LEAVE-ONE-MODEL-OUT difficulty strata (stratifier independent of the focal cell) ===")
strata_cov = defaultdict(list)   # d -> list of (m,q) covered clean
for q in covd:
    for m in MODELS:
        strata_cov[loo(m, q)[0]].append((m, q))
strata_unc = defaultdict(int)    # d -> cell count among clean uncovered
for q in uncd:
    for m in MODELS:
        if (m, q) in orc:
            strata_unc[loo(m, q)[0]] += 1
Ncov = sum(len(v) for v in strata_cov.values())
Nunc = sum(strata_unc.values())
print(f"  {'d_LOO':>5s} {'cov_cells':>9s} {'cov_share':>9s} {'unc_cells':>9s} {'unc_share':>9s} "
      f"{'b':>4s} {'c':>4s} {'delta_pp':>9s}")
deltas, wcov, wunc = {}, {}, {}
for d in range(4):
    S = strata_cov[d]
    b = sum(1 for m, q in S if gic[(m, q)] and not orc[(m, q)])
    c = sum(1 for m, q in S if orc[(m, q)] and not gic[(m, q)])
    deltas[d] = 100 * (b - c) / len(S) if S else 0.0
    wcov[d] = len(S) / Ncov
    wunc[d] = strata_unc[d] / Nunc
    print(f"  {d:5d} {len(S):9d} {wcov[d]:9.4f} {strata_unc[d]:9d} {wunc[d]:9.4f} "
          f"{b:4d} {c:4d} {deltas[d]:+9.2f}")

obs = sum(wcov[d] * deltas[d] for d in range(4))
ext_unc = sum(wunc[d] * deltas[d] for d in range(4))
wfull = {d: (wcov[d] * Ncov + wunc[d] * Nunc) / (Ncov + Nunc) for d in range(4)}
ext_full = sum(wfull[d] * deltas[d] for d in range(4))
print(f"\n  observed delta on covered mix      = {obs:+.3f} pp")
print(f"  same strata reweighted to UNCOVERED = {ext_unc:+.3f} pp")
print(f"  same strata reweighted to FULL 474  = {ext_full:+.3f} pp")

# ------------------------------------------------------------------ 5. region reweighting
print("\n=== 5. REGION REWEIGHTING (post-stratify covered onto the full-dataset region mix) ===")
regs = sorted(set(region.values()))
print(f"  {'region':24s} {'cov_it':>6s} {'unc_it':>6s} {'cells':>6s} {'delta_pp':>9s}")
rd, rw_cov, rw_full = {}, {}, {}
tot_cov_cells = 0
for rg in regs:
    S = [(m, q) for q in covd if region[q] == rg for m in MODELS]
    tot_cov_cells += len(S)
for rg in regs:
    S = [(m, q) for q in covd if region[q] == rg for m in MODELS]
    ni = len([q for q in covd if region[q] == rg])
    nu = len([q for q in uncd if region[q] == rg])
    if S:
        b = sum(1 for m, q in S if gic[(m, q)] and not orc[(m, q)])
        c = sum(1 for m, q in S if orc[(m, q)] and not gic[(m, q)])
        rd[rg] = 100 * (b - c) / len(S)
        rw_cov[rg] = len(S) / tot_cov_cells
    else:
        rd[rg] = None
        rw_cov[rg] = 0.0
    rw_full[rg] = (ni + nu)
    print(f"  {rg:24s} {ni:6d} {nu:6d} {len(S):6d} "
          f"{('%+9.2f' % rd[rg]) if rd[rg] is not None else '       --'}")
tf = sum(rw_full.values())
num = sum((rw_full[rg] / tf) * rd[rg] for rg in regs if rd[rg] is not None)
den = sum(rw_full[rg] / tf for rg in regs if rd[rg] is not None)
print(f"\n  observed (covered mix)                 = {sum(rw_cov[rg]*rd[rg] for rg in regs if rd[rg] is not None):+.3f} pp")
print(f"  region-post-stratified to full dataset = {num/den:+.3f} pp "
      f"(covers {100*den:.1f}% of full-dataset item mass)")

# ------------------------------------------------------------------ 6. worst / best case bounds
print("\n=== 6. MANSKI-STYLE BOUNDS on the full-dataset pooled delta ===")
cov_cells = sum(1 for q in covd for m in MODELS)
unc_cells = sum(1 for q in uncd for m in MODELS if (m, q) in orc)
net = sum((gic[(m, q)] - orc[(m, q)]) for q in covd for m in MODELS)
print(f"  observed net (GIFT-OR) on {cov_cells} covered clean cells = {net:+d}")
print(f"  unobserved GIFT on {unc_cells} uncovered clean cells.")
or_unc_k, _ = acc(uncd, orc)
lo_net = net + (0 - or_unc_k)          # GIFT gets every uncovered item wrong
hi_net = net + (unc_cells - or_unc_k)  # GIFT gets every uncovered item right
T = cov_cells + unc_cells
print(f"  OR correct on uncovered = {or_unc_k}/{unc_cells}")
print(f"  full-dataset delta bounds = [{100*lo_net/T:+.2f}, {100*hi_net/T:+.2f}] pp  (uninformative by design)")
print(f"  width {100*(hi_net-lo_net)/T:.1f}pp vs point estimate {100*net/cov_cells:+.2f}pp "
      f"-- the design cannot bound the target quantity.")

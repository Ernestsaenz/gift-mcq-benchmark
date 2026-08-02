"""Re-do the coverage reweighting with the de-confounded (leave-one-model-out)
difficulty stratifier, since ca_prim_04 showed the same-arm stratifier
manufactures most of the difficulty gradient.

For cell (item i, model m): stratum = number of the OTHER three models that
OpenRouter answered correctly on item i (0..3). Computable for all 474 items
from the complete OpenRouter arm, so the target distribution covers the items
GIFT never reached.
"""
import json, os, sys, math, collections, sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_prim_lib import LCG, percentile, mcnemar_exact

BASE = os.path.dirname(os.path.abspath(__file__))
con = sqlite3.connect(f"file:{os.path.join(os.path.dirname(BASE), 'experiment.sqlite')}?mode=ro", uri=True)
rows = [r for r in json.load(open(os.path.join(BASE, 'cross_arm_A.json')))
        if r.get('analysis_include')]
MODELS = sorted({r['model'] for r in rows})
cov = set(json.load(open(os.path.join(BASE, 'gift_coverage.json')))['complete_all_models'])
meta = json.load(open(os.path.join(BASE, 'dataset_meta.json')))
defect = set(meta['exclusions']['administrative_legal_out_of_domain']) | \
         set(meta['exclusions']['adjudicated_key_defect'])
SEED, B = 20260731, 20000
out = {}

q = """select lc.model, q.question_id, s.letter_correct
       from logical_calls lc join questions q on q.id = lc.question_id
       join parsed_answers pa on pa.logical_call_id = lc.id
       join scores s on s.logical_call_id = lc.id
       where lc.experiment_id = 6 and pa.parse_status = 'ok'"""
orm = collections.defaultdict(dict)
for m, qid, lc in con.execute(q):
    orm[qid][m] = lc

elig = [i for i in orm if i not in defect]
print(f"eligible items = {len(elig)}  (covered {len([i for i in elig if i in cov])}, "
      f"missing {len([i for i in elig if i not in cov])})")


def stratum(qid, model):
    """# of the other three models OpenRouter got right on this item."""
    d = orm[qid]
    if model not in d:
        return None
    return sum(v for m2, v in d.items() if m2 != model)


# target: cell-level stratum counts over ALL eligible items x 4 models
target = collections.Counter()
target_by_model = collections.defaultdict(collections.Counter)
for i in elig:
    for m in MODELS:
        s = stratum(i, m)
        if s is not None:
            target[s] += 1
            target_by_model[m][s] += 1
print("target cell counts by LOO stratum (460 eligible items):", dict(sorted(target.items())))
covered_counts = collections.Counter(stratum(r['question_id'], r['model']) for r in rows)
print("analysed cell counts by LOO stratum (311 covered):    ", dict(sorted(covered_counts.items())))
out['stratum_counts'] = {"target_all_eligible": dict(target),
                         "analysed_covered": dict(covered_counts)}


def poststrat(sample, tgt, model=None):
    agg = collections.defaultdict(lambda: [0, 0, 0])
    for r in sample:
        if model and r['model'] != model:
            continue
        a = agg[stratum(r['question_id'], r['model'])]
        a[0] += r['gift_correct']; a[1] += r['or_correct']; a[2] += 1
    num = den = 0.0
    for k, w in tgt.items():
        if w and k in agg and agg[k][2]:
            num += w * (agg[k][0] - agg[k][1]) / agg[k][2]
            den += w
    return num / den if den else None


def raw(sample, model=None):
    s = [r for r in sample if (model is None or r['model'] == model)]
    return ((sum(r['gift_correct'] for r in s) - sum(r['or_correct'] for r in s)) / len(s)
            if s else None)


by_cluster = collections.defaultdict(list)
for r in rows:
    by_cluster[r['cluster']].append(r)
clus = [by_cluster[c] for c in sorted(by_cluster)]
K = len(clus)
rng = LCG(SEED)
keys = ['POOLED'] + MODELS
pt_boot = {k: [] for k in keys}
rw_boot = {k: [] for k in keys}
for _ in range(B):
    samp = []
    for _ in range(K):
        samp.extend(clus[rng.randrange(K)])
    for k in keys:
        mm = None if k == 'POOLED' else k
        tg = target if k == 'POOLED' else target_by_model[k]
        v = raw(samp, mm)
        if v is not None:
            pt_boot[k].append(v)
        v2 = poststrat(samp, tg, mm)
        if v2 is not None:
            rw_boot[k].append(v2)
for k in keys:
    pt_boot[k].sort(); rw_boot[k].sort()

print("\n                              unweighted RD            LOO-difficulty reweighted RD")
res = {}
for k in keys:
    mm = None if k == 'POOLED' else k
    tg = target if k == 'POOLED' else target_by_model[k]
    r0 = raw(rows, mm)
    r1 = poststrat(rows, tg, mm)
    lo0, hi0 = percentile(pt_boot[k], .025), percentile(pt_boot[k], .975)
    lo1, hi1 = percentile(rw_boot[k], .025), percentile(rw_boot[k], .975)
    nl = sum(1 for v in rw_boot[k] if v <= 0); ng = sum(1 for v in rw_boot[k] if v >= 0)
    res[k] = {"unweighted_rd_pp": 100 * r0, "unweighted_ci_pp": (100 * lo0, 100 * hi0),
              "reweighted_rd_pp": 100 * r1, "reweighted_ci_pp": (100 * lo1, 100 * hi1),
              "reweighted_p_boot": min(1.0, 2 * min(nl, ng) / len(rw_boot[k])),
              "shift_pp": 100 * (r1 - r0)}
    print(f"{k:28s} {100*r0:+6.2f} ({100*lo0:+6.2f},{100*hi0:+6.2f})   "
          f"{100*r1:+6.2f} ({100*lo1:+6.2f},{100*hi1:+6.2f})   shift={100*(r1-r0):+5.2f}pp")
out['reweighted_loo'] = res

# how different is the covered vs missing stratum mix, in one number
tot_t = sum(target.values()); tot_c = sum(covered_counts.values())
tvd = 0.5 * sum(abs(target.get(s, 0) / tot_t - covered_counts.get(s, 0) / tot_c)
                for s in set(target) | set(covered_counts))
out['stratum_mix_total_variation_distance'] = tvd
print(f"\ntotal-variation distance between analysed and full-eligible stratum mix = {tvd:.4f}")

# and the same-arm (confounded) comparison, for the record
def stratum_same(qid, model):
    return sum(orm[qid].values())
out['note'] = ("The same-arm stratifier used in ca_prim_03 gave +2.64pp; the "
               "leave-one-model-out stratifier here is the de-confounded version "
               "because a model's own OpenRouter outcome never enters its own "
               "stratum assignment.")

json.dump(out, open(os.path.join(BASE, 'ca_prim_05_reweight_loo.json'), 'w'), indent=1, default=str)
print("wrote ca_prim_05_reweight_loo.json")

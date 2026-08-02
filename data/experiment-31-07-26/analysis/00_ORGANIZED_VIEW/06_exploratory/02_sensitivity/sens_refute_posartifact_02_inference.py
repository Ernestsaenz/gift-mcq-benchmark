#!/usr/bin/env python
"""Reproduce the three inference routes for the position artifact, then stress them.

Routes as specified in the claim:
 (i)   nonparametric cluster bootstrap, 20000 resamples of the 281 clusters,
       percentile CI; two-sided p = 2*min(share>0, share<0)
 (ii)  item-level randomisation: permute the 'key is a' label over the 423 items,
       each item's model cells kept intact; statistic |artifact|; 20000 draws
 (iii) same, but labels permuted only within the 9 mixed clusters

Stdlib only. Deterministic seeds.
"""
import json, os, random, collections, math

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, 'paired_clean.json')))

for r in D:
    r['d'] = r['B_correct'] - r['A_correct']

# ---------- item / cluster containers ----------
def build(rows):
    items = collections.OrderedDict()
    for r in rows:
        items.setdefault(r['question_id'], []).append(r)
    itemlist = list(items.keys())
    isA  = {q: items[q][0]['correct_letter'] == 'a' for q in itemlist}
    clu  = {q: items[q][0]['cluster'] for q in itemlist}
    dsum = {q: sum(x['d'] for x in items[q]) for q in itemlist}
    dn   = {q: len(items[q]) for q in itemlist}
    clusters = collections.OrderedDict()
    for q in itemlist:
        clusters.setdefault(clu[q], []).append(q)
    return itemlist, isA, clu, dsum, dn, clusters

def artifact_from(itemlist, isA, dsum, dn):
    sa = na = sn = nn = 0
    for q in itemlist:
        if isA[q]: sa += dsum[q]; na += dn[q]
        else:      sn += dsum[q]; nn += dn[q]
    if na == 0 or nn == 0:
        return None
    return 100.0*(sa/na - sn/nn)

def run(rows, label, B=20000, seed=20260731):
    itemlist, isA, clu, dsum, dn, clusters = build(rows)
    obs = artifact_from(itemlist, isA, dsum, dn)
    ncl = len(clusters)
    print('\n########## %s ##########' % label)
    print('cells=%d items=%d clusters=%d  OBS ARTIFACT = %+.4f pp' % (len(rows), len(itemlist), ncl, obs))

    # ---- (i) cluster bootstrap ----
    rnd = random.Random(seed)
    ckeys = list(clusters.keys())
    reps = []
    degenerate = 0
    for _ in range(B):
        sa = na = sn = nn = 0
        for _ in range(ncl):
            c = ckeys[rnd.randrange(ncl)]
            for q in clusters[c]:
                if isA[q]: sa += dsum[q]; na += dn[q]
                else:      sn += dsum[q]; nn += dn[q]
        if na == 0 or nn == 0:
            degenerate += 1
            continue
        reps.append(100.0*(sa/na - sn/nn))
    reps.sort()
    n = len(reps)
    lo = reps[int(math.floor(0.025*n))]
    hi = reps[min(n-1, int(math.ceil(0.975*n))-1)]
    above = sum(1 for x in reps if x > 0)
    below = sum(1 for x in reps if x < 0)
    p_boot = 2.0*min(above, below)/n
    mean = sum(reps)/n
    sd = math.sqrt(sum((x-mean)**2 for x in reps)/(n-1))
    print(' (i)   cluster bootstrap  B=%d (degenerate %d)' % (n, degenerate))
    print('       95%% percentile CI = [%+.4f, %+.4f]   bootSE=%.4f  bootmean=%+.4f' % (lo, hi, sd, mean))
    print('       two-sided p = 2*min(share) = %.4f    (share>0 = %.5f)' % (p_boot, above/n))
    # normal-approx and t(ncl-1) versions using the same bootstrap SE
    z = abs(obs)/sd
    p_norm = 2*(1-0.5*(1+math.erf(z/math.sqrt(2))))
    print('       Wald z=%.3f  p_norm=%.4f   CI_wald=[%+.4f,%+.4f]' % (z, p_norm, obs-1.96*sd, obs+1.96*sd))

    # ---- (ii) item-level randomisation ----
    rnd = random.Random(seed+1)
    labels = [isA[q] for q in itemlist]
    ge = 0
    for _ in range(B):
        rnd.shuffle(labels)
        perm = dict(zip(itemlist, labels))
        v = artifact_from(itemlist, perm, dsum, dn)
        if abs(v) >= abs(obs) - 1e-12:
            ge += 1
    p_item = (ge+1)/(B+1)
    print(' (ii)  item-level randomisation p = %.4f  (%d/%d)' % (p_item, ge, B))

    # ---- (iii) within-mixed-cluster randomisation ----
    mixed = [c for c, qs in clusters.items() if len(set(isA[q] for q in qs)) > 1]
    nmixitems = sum(len(clusters[c]) for c in mixed)
    rnd = random.Random(seed+2)
    base = dict(isA)
    ge = 0
    for _ in range(B):
        perm = dict(base)
        for c in mixed:
            qs = clusters[c]
            labs = [base[q] for q in qs]
            rnd.shuffle(labs)
            for q, l in zip(qs, labs):
                perm[q] = l
        v = artifact_from(itemlist, perm, dsum, dn)
        if abs(v) >= abs(obs) - 1e-12:
            ge += 1
    p_clu = (ge+1)/(B+1)
    print(' (iii) cluster-stratified randomisation p = %.4f  (%d/%d) [mixed clusters=%d, items=%d]'
          % (p_clu, ge, B, len(mixed), nmixitems))
    return dict(obs=obs, ci=(lo, hi), se=sd, p_boot=p_boot, p_item=p_item, p_clu=p_clu)

res = {}
res['full']   = run(D, 'FULL unfiltered (claim baseline)')
res['nodef']  = run([r for r in D if not r['excl_item_defect']], 'defect items excluded (excl_item_defect==False)')

# leave-one-model-out
print('\n\n===== LEAVE ONE MODEL OUT (full set) =====')
for m in sorted(set(r['model'] for r in D)):
    res['drop_'+m] = run([r for r in D if r['model'] != m], 'drop %s' % m, B=8000)

json.dump({k: {kk: vv for kk, vv in v.items()} for k, v in res.items()},
          open(os.path.join(HERE, 'sens_refute_posartifact_02_out.json'), 'w'), indent=1)

#!/usr/bin/env python
"""
sens_position_artifact2.py -- follow-ups to sens_position_artifact.py

(1) all pairwise letter contrasts with cluster-bootstrap CIs + omnibus letter
    heterogeneity randomisation test
(2) alternative counterfactuals (a behaves like b; like d; like b&d only; like c)
(3) ceiling-corrected interaction: flip rate P(B wrong | A correct) by letter x model,
    which removes the per-model differences in A-arm headroom
(4) baseline-accuracy vs artifact association across the 4 models
Stdlib only. Cluster bootstrap = resample the 281 clinical-context clusters.
"""
import json, random, math, collections

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
B = 20000
P = 20000
SEED = 20260731

rows = json.load(open(PATH))
MODELS = sorted(set(r["model"] for r in rows))
LETTERS = ["a", "b", "c", "d"]
for r in rows:
    r["d"] = r["B_correct"] - r["A_correct"]
    r["is_a"] = r["correct_letter"] == "a"

def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")
def quantile(s, q):
    if not s: return float("nan")
    p = q * (len(s) - 1); lo, hi = int(math.floor(p)), int(math.ceil(p))
    return s[lo] if lo == hi else s[lo] + (s[hi] - s[lo]) * (p - lo)
def ci(v):
    s = sorted(x for x in v if x == x)
    return quantile(s, .025), quantile(s, .975)
def line(t):
    print("\n" + "=" * 78); print(t); print("=" * 78)

by_cluster = collections.defaultdict(list)
for r in rows: by_cluster[r["cluster"]].append(r)
clusters = list(by_cluster.values()); K = len(clusters)

# ---------------- estimands -----------------------------------------------
def stats_of(rs):
    o = {}
    dl = {L: [r["d"] for r in rs if r["correct_letter"] == L] for L in LETTERS}
    for L in LETTERS:
        o["d_" + L] = 100 * mean(dl[L]) if dl[L] else float("nan")
    for x, y in [("a","b"),("a","c"),("a","d"),("b","c"),("b","d"),("c","d")]:
        o[f"{x}-{y}"] = o["d_"+x] - o["d_"+y]
    nb = [r["d"] for r in rs if not r["is_a"]]
    o["d_bcd"] = 100 * mean(nb) if nb else float("nan")
    o["artifact"] = o["d_a"] - o["d_bcd"]
    o["ratio_a_bcd"] = o["d_a"] / o["d_bcd"] if o["d_bcd"] else float("nan")
    o["raw"] = 100 * mean(r["d"] for r in rs)
    # alternative counterfactuals: substitute (a) cells with the model-specific delta
    # computed on a chosen donor letter set
    for name, donors in [("cf_bcd", ("b","c","d")), ("cf_b", ("b",)),
                         ("cf_d", ("d",)), ("cf_bd", ("b","d")), ("cf_c", ("c",))]:
        don = {}
        ok = True
        for m in MODELS:
            v = [r["d"] for r in rs if r["model"] == m and r["correct_letter"] in donors]
            if not v: ok = False; break
            don[m] = mean(v)
        if not ok:
            o[name] = float("nan"); o[name + "_attrib"] = float("nan"); continue
        tot = sum(don[r["model"]] if r["is_a"] else r["d"] for r in rs)
        o[name] = 100 * tot / len(rs)
        o[name + "_attrib"] = o["raw"] - o[name]
    # ceiling-corrected: flip rate P(B wrong | A correct)
    for m in MODELS + ["ALL"]:
        for grp, f in [("a", lambda r: r["is_a"]), ("bcd", lambda r: not r["is_a"])]:
            sub = [r for r in rs if (m == "ALL" or r["model"] == m)
                   and f(r) and r["A_correct"] == 1]
            o[f"flip_{m}_{grp}"] = 100 * mean(1 - r["B_correct"] for r in sub) if sub else float("nan")
        o[f"flipart_{m}"] = o[f"flip_{m}_a"] - o[f"flip_{m}_bcd"]
    fa = [o[f"flipart_{m}"] for m in MODELS]
    o["flipart_spread"] = max(fa) - min(fa) if all(x == x for x in fa) else float("nan")
    for m in MODELS:
        ma = [r["d"] for r in rs if r["model"] == m and r["is_a"]]
        mb = [r["d"] for r in rs if r["model"] == m and not r["is_a"]]
        o["art_" + m] = 100*mean(ma) - 100*mean(mb) if ma and mb else float("nan")
    # association between baseline A accuracy and artifact across the 4 models
    xs, ys = [], []
    for m in MODELS:
        sm = [r for r in rs if r["model"] == m]
        if not sm or o["art_" + m] != o["art_" + m]: xs = []; break
        xs.append(100 * mean(r["A_correct"] for r in sm)); ys.append(o["art_" + m])
    if xs:
        mx, my = mean(xs), mean(ys)
        sx = math.sqrt(sum((x-mx)**2 for x in xs)); sy = math.sqrt(sum((y-my)**2 for y in ys))
        o["corr_base_artifact"] = (sum((x-mx)*(y-my) for x, y in zip(xs, ys))/(sx*sy)
                                   if sx and sy else float("nan"))
    else:
        o["corr_base_artifact"] = float("nan")
    return o

point = stats_of(rows)
rng = random.Random(SEED)
boot = collections.defaultdict(list)
for _ in range(B):
    samp = []
    for _ in range(K): samp.extend(clusters[rng.randrange(K)])
    for k, v in stats_of(samp).items(): boot[k].append(v)

def rep(k, lab, f="{:+.2f}"):
    lo, hi = ci(boot[k])
    print(f"{lab:<46}{f.format(point[k]):>9}   95% CI [{f.format(lo)}, {f.format(hi)}]")

line("1. DELTA BY LETTER AND ALL PAIRWISE CONTRASTS (full data, cluster bootstrap)")
for L in LETTERS: rep("d_" + L, f"delta | correct letter = {L}")
rep("d_bcd", "delta | b,c,d pooled")
print()
for c in ["a-b","a-c","a-d","b-c","b-d","c-d"]:
    rep(c, f"contrast delta({c[0]}) - delta({c[2]})")
print()
rep("artifact", "ARTIFACT  delta(a) - delta(bcd)")
rep("ratio_a_bcd", "ratio delta(a)/delta(bcd)", "{:.3f}")

# omnibus letter heterogeneity randomisation test (reassign letters across items)
by_item = collections.defaultdict(list)
for r in rows: by_item[r["question_id"]].append(r)
item_ids = list(by_item)
item_letter = {q: by_item[q][0]["correct_letter"] for q in item_ids}
letters_pool = [item_letter[q] for q in item_ids]

def letter_stat(lab):
    s = collections.defaultdict(float); n = collections.defaultdict(int)
    for q, rs in by_item.items():
        L = lab[q]
        for r in rs: s[L] += r["d"]; n[L] += 1
    d = {L: 100*s[L]/n[L] for L in LETTERS}
    grand = 100 * mean(r["d"] for r in rows)
    return sum(n[L]*(d[L]-grand)**2 for L in LETTERS), d

obs_stat, obs_d = letter_stat(item_letter)
rng2 = random.Random(SEED + 7)
cnt = 0
for _ in range(P):
    pool = letters_pool[:]; rng2.shuffle(pool)
    lab = dict(zip(item_ids, pool))
    if letter_stat(lab)[0] >= obs_stat: cnt += 1
print(f"\nomnibus letter heterogeneity (n-weighted between-letter SS of delta)")
print(f"  observed statistic {obs_stat:.1f}; randomisation p = {(cnt+1)/(P+1):.5g}"
      f"  [{P} reassignments of the 4 correct-letter labels across the 423 items]")

line("2. ALTERNATIVE COUNTERFACTUALS FOR THE 364 POSITION-(a) CELLS")
print(f"{'donor set for the (a) cells':<46}{'delta':>9}   95% CI                attributable")
for k, lab in [("cf_bcd","b,c,d average (primary)"), ("cf_b","letter b only (adjacent slot)"),
               ("cf_bd","letters b and d only"), ("cf_d","letter d only"),
               ("cf_c","letter c only")]:
    lo, hi = ci(boot[k]); alo, ahi = ci(boot[k + "_attrib"])
    print(f"{lab:<46}{point[k]:>+9.2f}   [{lo:+.2f}, {hi:+.2f}]     "
          f"{point[k+'_attrib']:+.2f} [{alo:+.2f}, {ahi:+.2f}]")
print(f"\nraw pooled delta (full, n=1691)             {point['raw']:+.2f}")

line("3. CEILING-CORRECTED INTERACTION: flip rate P(B incorrect | A correct)")
print(f"{'model':<28}{'A acc%':>8}{'flip% (a)':>11}{'flip% (bcd)':>13}{'flip artifact pp':>18}")
for m in MODELS:
    sm = [r for r in rows if r["model"] == m]
    print(f"{m:<28}{100*mean(r['A_correct'] for r in sm):>8.1f}"
          f"{point[f'flip_{m}_a']:>11.1f}{point[f'flip_{m}_bcd']:>13.1f}"
          f"{point[f'flipart_{m}']:>18.2f}")
print(f"{'ALL':<28}{100*mean(r['A_correct'] for r in rows):>8.1f}"
      f"{point['flip_ALL_a']:>11.1f}{point['flip_ALL_bcd']:>13.1f}{point['flipart_ALL']:>18.2f}")
print()
rep("flipart_ALL", "flip-rate artifact, pooled")
for m in MODELS: rep("flipart_" + m, "flip-rate artifact | " + m.split("/")[-1])
rep("flipart_spread", "flip-rate artifact spread (max-min)")
rep("corr_base_artifact", "Pearson r(A-arm acc, artifact) across 4 models", "{:+.3f}")

# interaction: pairwise model contrasts of the artifact
line("4. MODEL x LETTER-GROUP INTERACTION CONTRASTS (delta-scale artifact)")
for i in range(len(MODELS)):
    for j in range(i+1, len(MODELS)):
        m1, m2 = MODELS[i], MODELS[j]
        key = f"int_{i}_{j}"
        boot[key] = [b1 - b2 for b1, b2 in zip(boot["art_"+m1], boot["art_"+m2])]
        point[key] = point["art_"+m1] - point["art_"+m2]
        rep(key, f"artifact({m1.split('/')[-1]}) - artifact({m2.split('/')[-1]})")

# randomisation p for interaction, ceiling-corrected statistic
item_is_a = {q: by_item[q][0]["is_a"] for q in item_ids}
n_a = sum(item_is_a.values())
def flip_art_from_labels(lab):
    per = {}
    for m in MODELS:
        num = {True: [0, 0], False: [0, 0]}
        for q, rs in by_item.items():
            g = lab[q]
            for r in rs:
                if r["model"] == m and r["A_correct"] == 1:
                    num[g][0] += 1 - r["B_correct"]; num[g][1] += 1
        per[m] = (100*num[True][0]/num[True][1] - 100*num[False][0]/num[False][1]
                  if num[True][1] and num[False][1] else float("nan"))
    return per
obs_per = flip_art_from_labels(item_is_a)
obs_sp = max(obs_per.values()) - min(obs_per.values())
rng3 = random.Random(SEED + 9)
cs = 0
NP = 5000
for _ in range(NP):
    sh = item_ids[:]; rng3.shuffle(sh)
    lab = {q: (i < n_a) for i, q in enumerate(sh)}
    per = flip_art_from_labels(lab)
    if max(per.values()) - min(per.values()) >= obs_sp: cs += 1
print(f"\nrandomisation test for interaction on the ceiling-corrected (flip-rate) scale:")
print(f"  observed spread {obs_sp:.2f} pp; p = {(cs+1)/(NP+1):.5g}"
      f"  [{NP} reassignments of the (a) label across items, model marginals preserved]")

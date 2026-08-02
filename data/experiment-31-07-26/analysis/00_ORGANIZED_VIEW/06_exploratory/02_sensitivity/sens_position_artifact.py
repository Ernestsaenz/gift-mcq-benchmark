#!/usr/bin/env python
"""
sens_position_artifact.py -- quantify the position-(a) construction defect.

Design: paired binary. Each record = (item, model) cell with A_correct / B_correct.
Per-cell paired difference d = B_correct - A_correct in {-1,0,+1}.
Pooled delta = mean(d) over cells (equivalently mean(B) - mean(A) when the panel
is balanced within cell, which it is: A and B are observed for the same cell).

Inference:
  * CIs: nonparametric CLUSTER bootstrap -- resample the 281 clinical-context
    clusters with replacement, carrying every item x model cell in the cluster.
    This respects both item nesting and the model-crossed structure.
  * p-values: item-level randomisation (permutation) test -- reassign the
    "correct letter is (a)" label across items, keeping each item's 4 model cells
    together. Preserves item effects and each model's marginal d distribution;
    destroys any association between the letter label and d.
    A cluster-stratified variant (permute only within clusters that contain both
    (a) and non-(a) items) is reported as a clustering-robust check.

Stdlib only.
"""
import json, random, math, collections, sys

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
B = 20000          # bootstrap resamples
P = 20000          # permutations
SEED = 20260731

rows = json.load(open(PATH))
MODELS = sorted(set(r["model"] for r in rows))
LETTERS = ["a", "b", "c", "d"]

for r in rows:
    r["d"] = r["B_correct"] - r["A_correct"]
    r["is_a"] = (r["correct_letter"] == "a")

# ---------- helpers -------------------------------------------------------
def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")

def pct(x):
    return 100.0 * x

def quantile(sorted_xs, q):
    if not sorted_xs:
        return float("nan")
    pos = q * (len(sorted_xs) - 1)
    lo = int(math.floor(pos)); hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_xs[lo]
    return sorted_xs[lo] + (sorted_xs[hi] - sorted_xs[lo]) * (pos - lo)

def ci(vals, lo=0.025, hi=0.975):
    s = sorted(v for v in vals if v == v)
    return quantile(s, lo), quantile(s, hi)

def line(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)

# ---------- 0. sanity / counts -------------------------------------------
line("0. COUNTS")
print(f"cells total                     : {len(rows)}")
print(f"items total                     : {len(set(r['question_id'] for r in rows))}")
print(f"clusters total                  : {len(set(r['cluster'] for r in rows))}")
print(f"cells analysis_include==True     : {sum(1 for r in rows if r['analysis_include'])}")
print(f"cells excl_nota_position_a==True : {sum(1 for r in rows if r['excl_nota_position_a'])}")
print(f"cells excl_item_defect==True     : {sum(1 for r in rows if r['excl_item_defect'])}")
print("cells by letter                 : " +
      str({L: sum(1 for r in rows if r["correct_letter"] == L) for L in LETTERS}))
items_by_letter = {}
seen = {}
for r in rows:
    seen.setdefault(r["question_id"], r["correct_letter"])
print("items by letter                 : " + str(collections.Counter(seen.values())))

# ---------- 1. pooled deltas on the several exclusion sets ---------------
line("1. POOLED DELTA (B minus A), pp, ON EACH EXCLUSION SET")
sets = {
    "FULL / unfiltered (n=1691)":        lambda r: True,
    "drop item-defects only":            lambda r: not r["excl_item_defect"],
    "drop position-(a) only":            lambda r: not r["excl_nota_position_a"],
    "published analysis set":            lambda r: r["analysis_include"],
    "position-(a) cells only":           lambda r: r["excl_nota_position_a"],
}
print(f"{'set':<34}{'n':>6}{'A acc%':>9}{'B acc%':>9}{'delta pp':>10}")
pooled = {}
for name, f in sets.items():
    sub = [r for r in rows if f(r)]
    a, b = mean(r["A_correct"] for r in sub), mean(r["B_correct"] for r in sub)
    pooled[name] = (len(sub), pct(a), pct(b), pct(b - a))
    print(f"{name:<34}{len(sub):>6}{pct(a):>9.2f}{pct(b):>9.2f}{pct(b-a):>10.2f}")

RAW = pooled["FULL / unfiltered (n=1691)"][3]
PUB = pooled["published analysis set"][3]

# ---------- 2. delta by correct_letter, pooled and per model -------------
line("2. DELTA BY CORRECT LETTER  (full data, all 1691 cells)")
print(f"{'model':<28}" + "".join(f"{L:>18}" for L in LETTERS) + f"{'bcd pooled':>14}")
print(f"{'':<28}" + "".join(f"{'n  A%  B%  d':>18}" for L in LETTERS))
def cell_stats(sub):
    return len(sub), pct(mean(r["A_correct"] for r in sub)), pct(mean(r["B_correct"] for r in sub)), pct(mean(r["d"] for r in sub))

per_model_letter = {}
for m in MODELS + ["POOLED"]:
    sub_m = rows if m == "POOLED" else [r for r in rows if r["model"] == m]
    out = []
    for L in LETTERS:
        s = cell_stats([r for r in sub_m if r["correct_letter"] == L])
        per_model_letter[(m, L)] = s
        out.append(f"{s[0]:>4}{s[1]:>5.0f}{s[2]:>5.0f}{s[3]:>6.1f}")
    sb = cell_stats([r for r in sub_m if not r["is_a"]])
    per_model_letter[(m, "bcd")] = sb
    sa = per_model_letter[(m, "a")]
    per_model_letter[(m, "artifact")] = sa[3] - sb[3]
    print(f"{m:<28}" + "".join(f"{o:>18}" for o in out) +
          f"{sb[0]:>5}{sb[3]:>9.1f}")

line("2b. ARTIFACT CONTRAST  delta(a) - delta(b,c,d), pp, per model")
print(f"{'model':<28}{'A-arm acc% (all)':>18}{'d(a) pp':>10}{'d(bcd) pp':>12}{'artifact pp':>13}")
model_rank = []
for m in MODELS:
    sub_m = [r for r in rows if r["model"] == m]
    aacc = pct(mean(r["A_correct"] for r in sub_m))
    da = per_model_letter[(m, "a")][3]; db = per_model_letter[(m, "bcd")][3]
    model_rank.append((aacc, m, per_model_letter[(m, "artifact")]))
    print(f"{m:<28}{aacc:>18.2f}{da:>10.2f}{db:>12.2f}{per_model_letter[(m,'artifact')]:>13.2f}")
pa = per_model_letter[("POOLED", "a")][3]; pb = per_model_letter[("POOLED", "bcd")][3]
print(f"{'POOLED':<28}{pct(mean(r['A_correct'] for r in rows)):>18.2f}{pa:>10.2f}{pb:>12.2f}{pa-pb:>13.2f}")
ARTIFACT_POINT = pa - pb

# ---------- 3. counterfactual --------------------------------------------
line("3. COUNTERFACTUAL: position-(a) items behave like the b/c/d average")
# per-model substitution: every (a) cell's d is replaced by that model's d(bcd)
def counterfactual_delta(rs):
    dbcd = {}
    for m in set(r["model"] for r in rs):
        sm = [r["d"] for r in rs if r["model"] == m and not r["is_a"]]
        dbcd[m] = mean(sm)
    tot = 0.0
    for r in rs:
        tot += dbcd[r["model"]] if r["is_a"] else r["d"]
    return tot / len(rs)

CF = pct(counterfactual_delta(rows))
w_a = sum(1 for r in rows if r["is_a"]) / len(rows)
print(f"raw pooled delta (full data)        : {RAW:+.2f} pp")
print(f"counterfactual pooled delta         : {CF:+.2f} pp")
print(f"attributable to position-(a) defect : {RAW - CF:+.2f} pp"
      f"   ({100*(RAW-CF)/RAW:.1f}% of the raw delta)")
print(f"decomposition check w_a*(d_a-d_bcd) : {w_a*ARTIFACT_POINT:+.4f} pp"
      f"   (w_a = {w_a:.4f} = {sum(1 for r in rows if r['is_a'])}/{len(rows)})")
print(f"published analysis-set delta        : {PUB:+.2f} pp"
      f"   (differs from counterfactual by {PUB-CF:+.2f} pp: item-defect drops + reweighting)")

# ---------- 4. cluster bootstrap ------------------------------------------
line("4. CLUSTER BOOTSTRAP (%d resamples of the %d clusters, seed=%d)"
     % (B, len(set(r['cluster'] for r in rows)), SEED))
by_cluster = collections.defaultdict(list)
for r in rows:
    by_cluster[r["cluster"]].append(r)
clusters = list(by_cluster.values())

def stats_of(rs):
    """all estimands from one (re)sample"""
    out = {}
    n = len(rs)
    out["raw"] = pct(mean(r["d"] for r in rs))
    a_rows = [r for r in rs if r["is_a"]]
    b_rows = [r for r in rs if not r["is_a"]]
    out["d_a"] = pct(mean(r["d"] for r in a_rows)) if a_rows else float("nan")
    out["d_bcd"] = pct(mean(r["d"] for r in b_rows)) if b_rows else float("nan")
    out["artifact"] = out["d_a"] - out["d_bcd"]
    out["cf"] = pct(counterfactual_delta(rs))
    out["attrib"] = out["raw"] - out["cf"]
    out["share"] = out["attrib"] / out["raw"] if out["raw"] else float("nan")
    for L in LETTERS:
        s = [r["d"] for r in rs if r["correct_letter"] == L]
        out["d_" + L] = pct(mean(s)) if s else float("nan")
    for m in MODELS:
        ma = [r["d"] for r in rs if r["model"] == m and r["is_a"]]
        mb = [r["d"] for r in rs if r["model"] == m and not r["is_a"]]
        out["art_" + m] = (pct(mean(ma)) - pct(mean(mb))) if ma and mb else float("nan")
    arts = [out["art_" + m] for m in MODELS]
    out["art_spread"] = max(arts) - min(arts) if all(x == x for x in arts) else float("nan")
    return out

point = stats_of(rows)
rng = random.Random(SEED)
K = len(clusters)
boot = collections.defaultdict(list)
for _ in range(B):
    samp = []
    for _ in range(K):
        samp.extend(clusters[rng.randrange(K)])
    s = stats_of(samp)
    for k, v in s.items():
        boot[k].append(v)

def report(key, label, fmt="{:+.2f}"):
    lo, hi = ci(boot[key])
    p = point[key]
    print(f"{label:<44}{fmt.format(p):>10}   95% CI [{fmt.format(lo)}, {fmt.format(hi)}]")

report("raw", "raw pooled delta (full)")
report("d_a", "delta | correct letter = a")
report("d_b", "delta | correct letter = b")
report("d_c", "delta | correct letter = c")
report("d_d", "delta | correct letter = d")
report("d_bcd", "delta | b,c,d pooled")
report("artifact", "ARTIFACT = d(a) - d(bcd)   [pp]")
report("cf", "counterfactual pooled delta")
report("attrib", "attributable to artifact   [pp]")
report("share", "attributable share of raw delta", "{:.3f}")
print()
for m in MODELS:
    report("art_" + m, "artifact | " + m)
report("art_spread", "artifact spread (max - min across models)")

# bootstrap two-sided p for artifact != 0 (proportion of resamples on the far side, doubled)
def boot_p(key, null=0.0):
    v = [x for x in boot[key] if x == x]
    frac = sum(1 for x in v if x >= null) / len(v)
    return 2 * min(frac, 1 - frac)
print(f"\nbootstrap two-sided p (artifact = 0)      : {boot_p('artifact'):.4g}"
      f"   [2*min(share above, share below 0) over {B} cluster resamples]")

# ---------- 5. permutation test on the (a) label --------------------------
line("5. RANDOMISATION TEST -- reassign the 'letter == a' label across items")
by_item = collections.defaultdict(list)
for r in rows:
    by_item[r["question_id"]].append(r)
item_ids = list(by_item)
item_is_a = {q: by_item[q][0]["is_a"] for q in item_ids}
n_a_items = sum(item_is_a.values())

def artifact_from_labels(labels):
    """labels: dict item -> bool. returns pooled artifact and per-model artifacts."""
    sa = collections.defaultdict(float); na = collections.defaultdict(int)
    sb = collections.defaultdict(float); nb = collections.defaultdict(int)
    for q, rs in by_item.items():
        if labels[q]:
            for r in rs:
                sa[r["model"]] += r["d"]; na[r["model"]] += 1
        else:
            for r in rs:
                sb[r["model"]] += r["d"]; nb[r["model"]] += 1
    tota, totan = sum(sa.values()), sum(na.values())
    totb, totbn = sum(sb.values()), sum(nb.values())
    pooled_art = pct(tota / totan) - pct(totb / totbn)
    per = {}
    for m in MODELS:
        per[m] = pct(sa[m] / na[m]) - pct(sb[m] / nb[m]) if na[m] and nb[m] else float("nan")
    return pooled_art, per

obs_art, obs_per = artifact_from_labels(item_is_a)
obs_spread = max(obs_per.values()) - min(obs_per.values())
obs_var = mean([(v - mean(obs_per.values()))**2 for v in obs_per.values()])

rng2 = random.Random(SEED + 1)
cnt_art = 0; cnt_spread = 0; cnt_var = 0
perm_arts = []
for _ in range(P):
    shuffled = item_ids[:]
    rng2.shuffle(shuffled)
    lab = {q: (i < n_a_items) for i, q in enumerate(shuffled)}
    a_, per_ = artifact_from_labels(lab)
    perm_arts.append(a_)
    if abs(a_) >= abs(obs_art):
        cnt_art += 1
    sp = max(per_.values()) - min(per_.values())
    if sp >= obs_spread:
        cnt_spread += 1
    v_ = mean([(x - mean(per_.values()))**2 for x in per_.values()])
    if v_ >= obs_var:
        cnt_var += 1
print(f"observed pooled artifact                 : {obs_art:+.2f} pp")
print(f"permutation p (two-sided, |artifact|)    : {(cnt_art+1)/(P+1):.5g}"
      f"   [{P} label reassignments, items kept intact]")
lo, hi = ci(perm_arts)
print(f"null distribution of artifact: mean {mean(perm_arts):+.3f} pp, 95% range [{lo:+.2f}, {hi:+.2f}]")
print(f"\nINTERACTION (does the artifact differ by model?)")
print("per-model artifact: " + ", ".join(f"{m.split('/')[-1]}={obs_per[m]:+.2f}" for m in MODELS))
print(f"observed spread (max-min)                : {obs_spread:.2f} pp")
print(f"permutation p (spread statistic)         : {(cnt_spread+1)/(P+1):.5g}")
print(f"permutation p (variance statistic)       : {(cnt_var+1)/(P+1):.5g}")
print("  NOTE: this null preserves each model's marginal d distribution and each")
print("  item's 4 cells, so it tests letter-group x model INTERACTION, not main effects.")

# cluster-stratified variant (clustering-robust; only mixed clusters informative)
mixed = [c for c, rs in by_cluster.items()
         if len(set(r["question_id"] for r in rs)) > 1
         and len(set(by_item[q][0]["is_a"] for q in set(r["question_id"] for r in rs))) > 1]
mixed_items = [q for q in item_ids if by_item[q][0]["cluster"] in mixed]
print(f"\ncluster-stratified permutation (labels shuffled only WITHIN clusters that")
print(f"contain both (a) and non-(a) items): {len(mixed)} such clusters, {len(mixed_items)} items")
rng3 = random.Random(SEED + 2)
by_c_items = collections.defaultdict(list)
for q in item_ids:
    by_c_items[by_item[q][0]["cluster"]].append(q)
cnt_s = 0
for _ in range(P):
    lab = dict(item_is_a)
    for c in mixed:
        qs = by_c_items[c]
        vals = [item_is_a[q] for q in qs]
        rng3.shuffle(vals)
        for q, v in zip(qs, vals):
            lab[q] = v
    a_, _ = artifact_from_labels(lab)
    if abs(a_) >= abs(obs_art):
        cnt_s += 1
print(f"cluster-stratified permutation p         : {(cnt_s+1)/(P+1):.5g}")

# ---------- 6. mechanism: where does the B answer go? --------------------
line("6. MECHANISM -- B-arm answer distribution by correct letter (full data)")
print(f"{'letter':<8}{'n':>6}{'B picks key%':>14}{'B picks (a)%':>14}{'B picks other%':>16}{'A picks key%':>14}")
for L in LETTERS:
    sub = [r for r in rows if r["correct_letter"] == L]
    n = len(sub)
    key = pct(mean(1 if r["B_selected"] == r["correct_letter"] else 0 for r in sub))
    pa_ = pct(mean(1 if r["B_selected"] == "a" else 0 for r in sub))
    other = 100 - key
    akey = pct(mean(1 if r["A_selected"] == r["correct_letter"] else 0 for r in sub))
    print(f"{L:<8}{n:>6}{key:>14.1f}{pa_:>14.1f}{other:>16.1f}{akey:>14.1f}")

line("6b. Is the (a) subset intrinsically different? (A-arm baseline, item covariates)")
ai = [r for q, r in seen.items()]
items_full = {q: by_item[q][0] for q in item_ids}
for lab, f in [("letter a", lambda r: r["is_a"]), ("letter b/c/d", lambda r: not r["is_a"])]:
    sub = [r for r in rows if f(r)]
    it = [r for q, r in items_full.items() if f(r)]
    print(f"{lab:<14} cells={len(sub):>5}  A-arm acc={pct(mean(r['A_correct'] for r in sub)):.2f}%"
          f"  items={len(it):>4}  has_context={pct(mean(1 if r['has_context'] else 0 for r in it)):.1f}%"
          f"  negated_stem={pct(mean(1 if r['negated_stem'] else 0 for r in it)):.1f}%"
          f"  mean qlen={mean(r['qlen'] for r in it):.0f}")

# ---------- 7. robustness: artifact on the item-defect-cleaned set -------
line("7. ROBUSTNESS -- artifact estimate after also dropping the 11 item defects")
clean = [r for r in rows if not r["excl_item_defect"]]
pcl = stats_of(clean)
by_cluster_c = collections.defaultdict(list)
for r in clean:
    by_cluster_c[r["cluster"]].append(r)
cl_c = list(by_cluster_c.values())
rng4 = random.Random(SEED + 3)
bc = collections.defaultdict(list)
for _ in range(5000):
    samp = []
    for _ in range(len(cl_c)):
        samp.extend(cl_c[rng4.randrange(len(cl_c))])
    s = stats_of(samp)
    for k, v in s.items():
        bc[k].append(v)
for k, lab in [("raw", "raw pooled delta"), ("artifact", "ARTIFACT d(a)-d(bcd)"),
               ("cf", "counterfactual delta"), ("attrib", "attributable pp")]:
    lo, hi = ci(bc[k])
    print(f"{lab:<32}{pcl[k]:>+9.2f}   95% CI [{lo:+.2f}, {hi:+.2f}]   (5000 cluster resamples)")

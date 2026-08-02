#!/usr/bin/env python
"""
sens_position_artifact3.py -- is the (a)-vs-(bcd) gap a POSITION artifact or an
ITEM-COMPOSITION artifact?  The 91 (a) items are shorter and less often carry a
clinical context stem, so the raw contrast is confounded.

Direct standardisation: stratify items on has_context x qlen tercile
(terciles computed on all 423 items), compute the artifact inside each stratum,
then pool with weights = the overall item distribution across strata.
Strata with no (a) items or no (b/c/d) items are dropped and the weights
renormalised (reported).  Cluster bootstrap for CIs.

Also: exam_part / negated_stem balance, and the A-arm-only position check
(is there a baseline position bias before the swap at all?).
Stdlib only.
"""
import json, random, math, collections

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
B = 10000
SEED = 20260731
rows = json.load(open(PATH))
MODELS = sorted(set(r["model"] for r in rows))
for r in rows:
    r["d"] = r["B_correct"] - r["A_correct"]
    r["is_a"] = r["correct_letter"] == "a"

def mean(xs):
    xs = list(xs); return sum(xs)/len(xs) if xs else float("nan")
def quantile(s,q):
    if not s: return float("nan")
    p=q*(len(s)-1); lo,hi=int(math.floor(p)),int(math.ceil(p))
    return s[lo] if lo==hi else s[lo]+(s[hi]-s[lo])*(p-lo)
def ci(v):
    s=sorted(x for x in v if x==x); return quantile(s,.025),quantile(s,.975)
def line(t): print("\n"+"="*78); print(t); print("="*78)

# item table + qlen terciles
items = {}
for r in rows: items.setdefault(r["question_id"], r)
qs = sorted(r["qlen"] for r in items.values())
t1, t2 = quantile(qs, 1/3), quantile(qs, 2/3)
def tercile(q): return 0 if q <= t1 else (1 if q <= t2 else 2)
for r in rows:
    r["stratum"] = (r["has_context"], tercile(r["qlen"]))

line("0. WHY ADJUST -- composition of the (a) subset vs the (b,c,d) subset")
print(f"qlen terciles cut at {t1:.0f} / {t2:.0f} characters (423 items)")
print(f"{'stratum (has_context, qlen tercile)':<40}{'items a':>9}{'items bcd':>11}{'a share%':>10}")
sa = collections.Counter(); sb = collections.Counter()
for r in items.values():
    st = (r["has_context"], tercile(r["qlen"]))
    (sa if r["correct_letter"]=="a" else sb)[st] += 1
strata = sorted(set(list(sa)+list(sb)))
for st in strata:
    tot = sa[st]+sb[st]
    print(f"{str(st):<40}{sa[st]:>9}{sb[st]:>11}{100*sa[st]/tot:>10.1f}")
print(f"{'TOTAL':<40}{sum(sa.values()):>9}{sum(sb.values()):>11}")
print("\nother covariates (item level):")
for lab, f in [("a", lambda r: r["correct_letter"]=="a"), ("bcd", lambda r: r["correct_letter"]!="a")]:
    it=[r for r in items.values() if f(r)]
    ep=collections.Counter(r["exam_part"] for r in it)
    print(f"  {lab:<4} n={len(it):>4} negated_stem={100*mean(1 if r['negated_stem'] else 0 for r in it):5.1f}%"
          f" has_context={100*mean(1 if r['has_context'] else 0 for r in it):5.1f}%"
          f" qlen med={quantile(sorted(r['qlen'] for r in it),.5):.0f}"
          f" exam_part top3={ep.most_common(3)}")

# ---- standardised artifact ------------------------------------------------
def strat_artifact(rs, weights):
    """direct standardisation to the supplied stratum weights (item-count based)."""
    num = collections.defaultdict(lambda: [0.0,0,0.0,0])
    for r in rs:
        i = 0 if r["is_a"] else 2
        num[r["stratum"]][i] += r["d"]; num[r["stratum"]][i+1] += 1
    tot_w = 0.0; acc = 0.0; used = []
    for st, w in weights.items():
        v = num.get(st)
        if not v or v[1]==0 or v[3]==0: continue
        acc += w * (100*v[0]/v[1] - 100*v[2]/v[3]); tot_w += w; used.append(st)
    return (acc/tot_w if tot_w else float("nan")), tot_w, used

W = {st: sa[st]+sb[st] for st in strata}          # weights = all-item distribution
def crude(rs):
    a=[r["d"] for r in rs if r["is_a"]]; b=[r["d"] for r in rs if not r["is_a"]]
    return 100*mean(a)-100*mean(b) if a and b else float("nan")

pt_adj, wused, used = strat_artifact(rows, W)
pt_crude = crude(rows)
line("1. CRUDE vs STRATUM-STANDARDISED ARTIFACT")
print(f"strata used: {len(used)} of {len(strata)}; they carry "
      f"{100*wused/sum(W.values()):.1f}% of the item weight")
print(f"  dropped strata (no (a) or no (bcd) items): "
      f"{[st for st in strata if st not in used]}")

by_cluster = collections.defaultdict(list)
for r in rows: by_cluster[r["cluster"]].append(r)
cl = list(by_cluster.values()); K = len(cl)
rng = random.Random(SEED)
bc, bcr = [], []
for _ in range(B):
    s=[]
    for _ in range(K): s.extend(cl[rng.randrange(K)])
    bc.append(strat_artifact(s, W)[0]); bcr.append(crude(s))
lo,hi = ci(bcr); print(f"crude artifact          {pt_crude:+7.2f} pp   95% CI [{lo:+.2f}, {hi:+.2f}]")
lo,hi = ci(bc);  print(f"standardised artifact   {pt_adj:+7.2f} pp   95% CI [{lo:+.2f}, {hi:+.2f}]"
                       f"   ({B} cluster resamples)")

# per-stratum detail
line("2. ARTIFACT WITHIN EACH STRATUM (no smoothing; small cells shown as-is)")
print(f"{'stratum':<26}{'cells a':>9}{'cells bcd':>11}{'d(a)':>9}{'d(bcd)':>9}{'artifact':>10}")
num = collections.defaultdict(lambda: [0.0,0,0.0,0])
for r in rows:
    i = 0 if r["is_a"] else 2
    num[r["stratum"]][i]+=r["d"]; num[r["stratum"]][i+1]+=1
for st in strata:
    v=num[st]
    da = 100*v[0]/v[1] if v[1] else float("nan")
    db = 100*v[2]/v[3] if v[3] else float("nan")
    print(f"{str(st):<26}{v[1]:>9}{v[3]:>11}{da:>9.1f}{db:>9.1f}{da-db:>10.1f}")

# ---- A-arm baseline position check ---------------------------------------
line("3. A-ARM ONLY: baseline letter effects BEFORE the swap (no NOTA present)")
print(f"{'letter':<8}{'cells':>7}{'A acc%':>9}{'A picks (a)%':>14}")
for L in "abcd":
    sub=[r for r in rows if r["correct_letter"]==L]
    print(f"{L:<8}{len(sub):>7}{100*mean(r['A_correct'] for r in sub):>9.2f}"
          f"{100*mean(1 if r['A_selected']=='a' else 0 for r in sub):>14.2f}")
print("\nA-arm selection distribution overall:",
      dict(collections.Counter(r["A_selected"] for r in rows)))
print("B-arm selection distribution overall:",
      dict(collections.Counter(r["B_selected"] for r in rows)))

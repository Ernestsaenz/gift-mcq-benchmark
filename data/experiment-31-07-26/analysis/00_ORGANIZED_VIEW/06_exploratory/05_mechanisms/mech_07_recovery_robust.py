#!/usr/bin/env python3
"""mech_07: robustness + effect accounting for the negation shortcut.

1. Clopper-Pearson done properly (stats_lib.binom_exact_ci has an inverted
   bisection on the LOWER bound -- it returns 1.0; re-implemented here).
2. Cluster-bootstrap CI/p for the recovery contrast (Fisher exact treats the
   133 A-wrong cells as independent; they are not -- one item can contribute 4).
3. Label sensitivity: shipped flag / adjudicated / lexicon-without-manual-
   overrides / conservative markers only.
4. Attributable accounting: how many points of the headline drop does the
   shortcut buy back?
"""
import json, math, collections, random, sys
sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
from mech_stats import fisher_exact_2x2, wilson

ANA = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis"
rows = [r for r in json.load(open(f"{ANA}/paired_clean.json")) if r["analysis_include"]]
lab = json.load(open(f"{ANA}/mech_labels.json"))
STRONG = ("FALSO", "INCORRECTO", "ERRONEO", "INCIERTO", "EXCEPTO", "MENOS-UNA", "SALVO", "EXCEPCION")
for r in rows:
    L = lab[r["question_id"]]
    r["neg_adj"] = L["neg"]
    r["neg_flag"] = r["negated_stem"]
    r["neg_raw"] = len(L["hits"]) > 0          # lexicon, no manual overrides
    r["neg_strong"] = any(t in L["hits"] for t in STRONG)   # explicit polarity words only
MODELS = sorted({r["model"] for r in rows})


def cp(k, n, alpha=0.05):
    """Clopper-Pearson exact interval, bisection on the exact binomial tails."""
    def upper_tail(p):   # P(X >= k)
        return sum(math.comb(n, i) * p**i * (1-p)**(n-i) for i in range(k, n+1))

    def lower_tail(p):   # P(X <= k)
        return sum(math.comb(n, i) * p**i * (1-p)**(n-i) for i in range(0, k+1))
    if n == 0:
        return (float('nan'), float('nan'))
    if k == 0:
        lo = 0.0
    else:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = (a+b)/2
            if upper_tail(m) < alpha/2: a = m
            else: b = m
        lo = (a+b)/2
    if k == n:
        hi = 1.0
    else:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = (a+b)/2
            if lower_tail(m) > alpha/2: a = m
            else: b = m
        hi = (a+b)/2
    return lo, hi


BAR = "=" * 92
print(BAR); print("PART A -- logic-sufficient failure rate with a correct Clopper-Pearson CI"); print(BAR)
sub = {}
for r in rows:
    L = lab[r["question_id"]]
    sub[id(r)] = ("POS" if not L["neg"] else
                  "TRUTH-NEG" if any(t in L["hits"] for t in ("FALSO", "INCORRECTO", "ERRONEO", "INCIERTO"))
                  else "SET-NEG")
for tag in ("TRUTH-NEG", "SET-NEG", "POS"):
    rs = [r for r in rows if sub[id(r)] == tag and r["A_correct"] == 1]
    f = sum(1 for r in rs if not r["B_correct"])
    lo, hi = cp(f, len(rs))
    print(f"  {tag:10s} A-correct cells {len(rs):4d}   B failures {f:3d}"
          f"   rate {f/len(rs):.4f}  95% CP [{lo:.4f},{hi:.4f}]")
rs = [r for r in rows if sub[id(r)] == "TRUTH-NEG" and r["A_correct"] == 1]
for m in MODELS:
    s = [r for r in rs if r["model"] == m]
    f = sum(1 for r in s if not r["B_correct"])
    lo, hi = cp(f, len(s))
    print(f"    {m:28s} {f:3d}/{len(s):3d} = {f/len(s):.4f}  [{lo:.4f},{hi:.4f}]")

print("\n" + BAR); print("PART B -- recovery contrast under four labelings"); print(BAR)
for key, name in (("neg_flag", "shipped negated_stem flag"),
                  ("neg_adj", "adjudicated (primary)"),
                  ("neg_raw", "lexicon, no manual overrides"),
                  ("neg_strong", "explicit polarity words only (FALSO/INCORRECTO/EXCEPTO/menos una)")):
    neg = [r for r in rows if r[key]]; pos = [r for r in rows if not r[key]]
    an = [r for r in neg if not r["A_correct"]]; ap = [r for r in pos if not r["A_correct"]]
    kn = sum(r["B_correct"] for r in an); kp = sum(r["B_correct"] for r in ap)
    o, p = fisher_exact_2x2(kn, len(an)-kn, kp, len(ap)-kp)
    dn = sum(r["A_correct"]-r["B_correct"] for r in neg)/len(neg)
    dp = sum(r["A_correct"]-r["B_correct"] for r in pos)/len(pos)
    nit = len({r['question_id'] for r in neg})
    print(f"  {name:62s}\n     items marked {nit:3d} | recovery neg {kn}/{len(an)}={kn/len(an):.3f}"
          f"  non-neg {kp}/{len(ap)}={kp/len(ap):.3f}  OR={o:.3f} Fisher exact p={p:.4g}"
          f" | delta neg {dn:+.3f} non-neg {dp:+.3f}")

print("\n" + BAR); print("PART C -- cluster bootstrap for the recovery contrast (accounts for the"
                         "\n          fact that one item contributes up to 4 correlated cells)"); print(BAR)
neg = [r for r in rows if r["neg_adj"]]; pos = [r for r in rows if not r["neg_adj"]]
awn = [r for r in neg if not r["A_correct"]]; awp = [r for r in pos if not r["A_correct"]]
print(f"  A-wrong cells: negated {len(awn)} from {len({r['question_id'] for r in awn})} items"
      f" / {len({r['cluster'] for r in awn})} clusters;"
      f" non-negated {len(awp)} from {len({r['question_id'] for r in awp})} items"
      f" / {len({r['cluster'] for r in awp})} clusters")
byc = collections.defaultdict(list)
for r in rows:
    byc[r["cluster"]].append(r)
keys = list(byc); rng = random.Random(31072026)
bs = []
for _ in range(8000):
    samp = []
    for _ in range(len(keys)):
        samp.extend(byc[keys[rng.randrange(len(keys))]])
    a = [r for r in samp if r["neg_adj"] and not r["A_correct"]]
    b = [r for r in samp if not r["neg_adj"] and not r["A_correct"]]
    if len(a) < 5 or len(b) < 5:
        continue
    bs.append(sum(r["B_correct"] for r in a)/len(a) - sum(r["B_correct"] for r in b)/len(b))
bs.sort()
obs = sum(r["B_correct"] for r in awn)/len(awn) - sum(r["B_correct"] for r in awp)/len(awp)
frac = sum(1 for v in bs if v <= 0)/len(bs)
print(f"  observed recovery difference {obs:+.4f}"
      f"  cluster-bootstrap 95% CI [{bs[int(.025*len(bs))]:+.4f},{bs[int(.975*len(bs))]:+.4f}]"
      f"  two-sided bootstrap p ~ {2*min(frac,1-frac):.4g}  ({len(bs)} usable resamples)")

# item-level permutation of the polarity label, recovery statistic
items = collections.defaultdict(list)
for r in rows:
    items[r["question_id"]].append(r)
qs = list(items); labs = [items[q][0]["neg_adj"] for q in qs]
rng2 = random.Random(5); NP = 20000; cnt = 0
for _ in range(NP):
    rng2.shuffle(labs)
    a1 = a0 = b1 = b0 = 0
    for q, l in zip(qs, labs):
        for r in items[q]:
            if r["A_correct"]:
                continue
            if l:
                a1 += r["B_correct"]; a0 += 1
            else:
                b1 += r["B_correct"]; b0 += 1
    if a0 and b0 and abs(a1/a0 - b1/b0) >= abs(obs) - 1e-12:
        cnt += 1
print(f"  item-level permutation of the polarity label ({NP} perms, all model rows of an item"
      f" moved together): two-sided p={(cnt+1)/(NP+1):.4g}")

print("\n" + BAR); print("PART D -- how many points of the drop does the shortcut buy back?"); print(BAR)
n = len(rows)
A = sum(r["A_correct"] for r in rows)/n
Bacc = sum(r["B_correct"] for r in rows)/n
recp = sum(r["B_correct"] for r in awp)/len(awp)
recn = sum(r["B_correct"] for r in awn)/len(awn)
excess = len(awn) * (recn - recp)
print(f"  headline: A={A:.4f} B={Bacc:.4f} delta={A-Bacc:+.4f}")
print(f"  negated A-wrong cells {len(awn)}; excess B-correct attributable to the shortcut"
      f" = {len(awn)}*({recn:.4f}-{recp:.4f}) = {excess:.1f} cells")
print(f"  counterfactual B accuracy without the shortcut = {(Bacc*n-excess)/n:.4f}")
print(f"  counterfactual delta = {A-(Bacc*n-excess)/n:+.4f}   (vs {A-Bacc:+.4f} observed;"
      f" +{100*(A-(Bacc*n-excess)/n-(A-Bacc)):.2f} points, "
      f"{100*excess/(n*(A-Bacc)):.1f}% of the drop)")
print(f"  simply DROPPING all {len({r['question_id'] for r in neg})} negated items instead:")
d_drop = sum(r["A_correct"]-r["B_correct"] for r in pos)/len(pos)
print(f"    delta = {d_drop:+.4f} (+{100*(d_drop-(A-Bacc)):.2f} points, "
      f"{100*(d_drop-(A-Bacc))/(A-Bacc):+.1f}% relative)")

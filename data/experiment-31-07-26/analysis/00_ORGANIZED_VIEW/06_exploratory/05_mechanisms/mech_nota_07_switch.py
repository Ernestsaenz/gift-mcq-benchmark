"""nota-acceptance part 6: the switch test + drop accounting + cluster-robust CIs.

Key asymmetry the design creates: for a cell the model got WRONG in A, the option it
actually chose is byte-identical in B (mech_01 verified the three non-key options are
unchanged). A model with stable beliefs should therefore re-select it. Every departure
from that choice is caused by the one edit - the key text becoming 'Ninguna...'.
So: conditional on switching at all, how often is NOTA the destination?
Uniform-switch null = 1/3 (NOTA + two untouched distractors).
"""
import json
import random
from collections import defaultdict

from mech_nota_lib import binom_test_exact, cp_ci

random.seed(20260731)
ROWS = [r for r in json.load(open(
    "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
    "experiment-31-07-26/analysis/paired_clean.json")) if r["analysis_include"]]
MODELS = sorted(set(r["model"] for r in ROWS))
SHORT = {m: m.split("/")[-1] for m in MODELS}


def pct(k, n):
    return 100.0 * k / n if n else float("nan")


print("=" * 104)
print("15. THE SWITCH TEST (cells the model got WRONG in A; its chosen option is unchanged in B)")
print("=" * 104)
print(f"{'model':<22}{'A-wrong':>9}{'stays put':>12}{'-> NOTA':>10}{'-> other distr.':>17}"
      f"{'P(NOTA | switched)':>22}{'p vs 1/3':>11}")
tS = tN = tO = 0
for m in MODELS:
    rs = [r for r in ROWS if r["model"] == m and r["A_correct"] == 0]
    stay = sum(1 for r in rs if r["B_selected"] == r["A_selected"])
    nota = sum(1 for r in rs if r["B_correct"] == 1)
    oth = len(rs) - stay - nota
    tS += stay; tN += nota; tO += oth
    sw = nota + oth
    p = binom_test_exact(nota, sw, 1 / 3) if sw else float("nan")
    print(f"{SHORT[m]:<22}{len(rs):>9}{stay:>12}{nota:>10}{oth:>17}"
          f"{pct(nota,sw):>19.1f}% {p:>10.3g}   ({nota}/{sw})")
sw = tN + tO
lo, hi = cp_ci(tN, sw)
print(f"{'POOLED':<22}{tS+tN+tO:>9}{tS:>12}{tN:>10}{tO:>17}{pct(tN,sw):>19.1f}% "
      f"{binom_test_exact(tN, sw, 1/3):>10.3g}   ({tN}/{sw})  CP95 [{100*lo:.1f},{100*hi:.1f}]")
print("   [exact two-sided binomial test against the uniform-switch null of 1/3]")

print()
print("=" * 104)
print("16. ACCOUNTING FOR THE WHOLE A->B DROP")
print("=" * 104)
print(f"{'model':<22}{'n':>6}{'A ok->B wrong':>16}{'A wrong->B ok':>16}{'net drop':>12}"
      f"{'share of B errors that are A-ok cells':>40}")
for m in MODELS:
    rs = [r for r in ROWS if r["model"] == m]
    lost = sum(1 for r in rs if r["A_correct"] == 1 and r["B_correct"] == 0)
    gain = sum(1 for r in rs if r["A_correct"] == 0 and r["B_correct"] == 1)
    berr = sum(1 for r in rs if r["B_correct"] == 0)
    print(f"{SHORT[m]:<22}{len(rs):>6}{lost:>10} ({pct(lost,len(rs)):4.1f}%){gain:>10} "
          f"({pct(gain,len(rs)):4.1f}%){pct(lost-gain,len(rs)):>11.1f}pp"
          f"{pct(lost,berr):>34.1f}%  ({lost}/{berr})")

# ------------------------------------------------- cluster-robust bootstrap CIs
print()
print("=" * 104)
print("17. CLUSTER BOOTSTRAP (resample the 208 clusters with replacement, 20000 reps)")
print("    -- CIs that respect the fact that near-duplicate items are nested in clusters.")
print("=" * 104)
by_cluster = defaultdict(list)
for r in ROWS:
    by_cluster[r["cluster"]].append(r)
CL = list(by_cluster.values())
B = 20000


def boot(fn, label):
    obs = fn(ROWS)
    reps = []
    for _ in range(B):
        samp = []
        for _ in range(len(CL)):
            samp.extend(CL[random.randrange(len(CL))])
        v = fn(samp)
        if v == v:
            reps.append(v)
    reps.sort()
    lo = reps[int(0.025 * len(reps))]
    hi = reps[int(0.975 * len(reps))]
    print(f"    {label:<52} {100*obs:6.1f}%   cluster-bootstrap 95% CI [{100*lo:.1f}, {100*hi:.1f}]")


def mk(model, cond):
    def f(rows):
        s = [r for r in rows if (model is None or r["model"] == model)
             and r["A_correct"] == cond]
        return sum(r["B_correct"] for r in s) / len(s) if s else float("nan")
    return f


boot(mk(None, 1), "P(B ok | A ok), pooled")
boot(mk(None, 0), "P(B ok | A wrong), pooled  <-- headline")
for m in MODELS:
    boot(mk(m, 0), f"P(B ok | A wrong), {SHORT[m]}")

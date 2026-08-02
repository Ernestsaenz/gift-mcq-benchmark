"""nota-acceptance part 2: isolate a none-of-the-above RESPONSE TENDENCY.

Design fact: the NOTA string is inserted at the key letter, so in the analysis set
  select(key letter) in B  ==  B correct        (by construction)
  select(key letter) in A  ==  A correct        (by construction)
The contrast is still meaningful because it is the SAME slot, at the SAME position,
with the SAME three distractor texts (verified byte-identical in mech_01) - the only
thing that changed is the text sitting in that slot.

Extra isolations that are NOT tautological:
  (a) letter 'a' is never the key in the analysis set (correct_letter in {b,c,d}),
      so P(select 'a') is a pure distractor-attraction rate, comparable A vs B.
  (b) where the answer GOES when the model abandons the NOTA slot.
  (c) the excluded correct_letter=='a' stratum, where the same NOTA string sits in
      the FIRST slot and is therefore incoherent ("respuestas anteriores" with no
      antecedent) - a positional floor on NOTA acceptance.
"""
import json
from collections import Counter, defaultdict

from mech_nota_lib import cp_ci, fisher_2x2, mcnemar_exact

ALL = json.load(open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
                     "data/experiment-31-07-26/analysis/paired_clean.json"))
ROWS = [r for r in ALL if r["analysis_include"]]
MODELS = sorted(set(r["model"] for r in ROWS))
SHORT = {m: m.split("/")[-1] for m in MODELS}


def pct(k, n):
    return 100.0 * k / n if n else float("nan")


def cistr(k, n):
    lo, hi = cp_ci(k, n)
    return f"[{100*lo:4.1f},{100*hi:5.1f}]"


print("=" * 106)
print("4. NOTA-SLOT SELECTION RATE:  same slot, same position, same 3 distractors, different text")
print("=" * 106)
print(f"{'model':<22}{'picks key slot in A':<24}{'picks key slot in B (=NOTA)':<30}{'shift':>9}   McNemar (exact, paired items)")
for m in MODELS:
    rs = [r for r in ROWS if r["model"] == m]
    n = len(rs)
    ka = sum(1 for r in rs if r["A_selected"] == r["correct_letter"])
    kb = sum(1 for r in rs if r["B_selected"] == r["correct_letter"])
    b = sum(1 for r in rs if r["A_selected"] == r["correct_letter"] and r["B_selected"] != r["correct_letter"])
    c = sum(1 for r in rs if r["A_selected"] != r["correct_letter"] and r["B_selected"] == r["correct_letter"])
    print(f"{SHORT[m]:<22}{pct(ka,n):>6.1f}% {cistr(ka,n)} {ka:>3}/{n:<4} "
          f"{pct(kb,n):>6.1f}% {cistr(kb,n)} {kb:>3}/{n:<4}   {pct(kb,n)-pct(ka,n):>+6.1f}pp   "
          f"lost={b:<3} gained={c:<3} p={mcnemar_exact(b, c):.3g}")

print()
print("=" * 106)
print("5. LETTER 'a' - a plain distractor in BOTH arms (never the key in the analysis set)")
print("   If the NOTA-drop were only 'lost recognition of a memorised string' the leftover")
print("   probability mass should scatter; instead watch where it actually lands.")
print("=" * 106)
print(f"{'model':<22}{'P(pick a) in A':<24}{'P(pick a) in B':<24}{'shift':>9}   McNemar exact")
for m in MODELS:
    rs = [r for r in ROWS if r["model"] == m]
    n = len(rs)
    ka = sum(1 for r in rs if r["A_selected"] == "a")
    kb = sum(1 for r in rs if r["B_selected"] == "a")
    b = sum(1 for r in rs if r["A_selected"] == "a" and r["B_selected"] != "a")
    c = sum(1 for r in rs if r["A_selected"] != "a" and r["B_selected"] == "a")
    print(f"{SHORT[m]:<22}{pct(ka,n):>6.1f}% {cistr(ka,n)} {ka:>3}/{n:<4} "
          f"{pct(kb,n):>6.1f}% {cistr(kb,n)} {kb:>3}/{n:<4}   {pct(kb,n)-pct(ka,n):>+6.1f}pp   "
          f"a-only-in-A={b:<3} a-only-in-B={c:<3} p={mcnemar_exact(b, c):.3g}")

print()
print("=" * 106)
print("6. WHERE THE ANSWER GOES  (choice flow, per model)")
print("=" * 106)
for m in MODELS:
    rs = [r for r in ROWS if r["model"] == m]
    print(f"\n  {SHORT[m]}")
    # A correct -> B wrong : the model HAD identified the true claim; with it gone it
    # re-endorses one of the three claims it had just rejected instead of saying 'ninguna'.
    grp = [r for r in rs if r["A_correct"] == 1 and r["B_correct"] == 0]
    n1 = sum(1 for r in rs if r["A_correct"] == 1)
    print(f"    A correct & B wrong (knew the key, then endorsed a claim it had rejected): "
          f"{len(grp)}/{n1} = {pct(len(grp),n1):.1f}%  {cistr(len(grp),n1)}")
    if grp:
        ca = Counter(r["B_selected"] for r in grp)
        print(f"       B choice among those: {dict(sorted(ca.items()))}   "
              f"-> letter a = {pct(ca.get('a',0),len(grp)):.1f}% of them")
    # A wrong -> what happens in B
    gw = [r for r in rs if r["A_correct"] == 0]
    if gw:
        nota = sum(1 for r in gw if r["B_correct"] == 1)
        same = sum(1 for r in gw if r["B_correct"] == 0 and r["B_selected"] == r["A_selected"])
        othr = sum(1 for r in gw if r["B_correct"] == 0 and r["B_selected"] != r["A_selected"])
        print(f"    A wrong (n={len(gw)}): -> NOTA {nota} ({pct(nota,len(gw)):.1f}%) | "
              f"repeats its own A distractor {same} ({pct(same,len(gw)):.1f}%) | "
              f"switches to another distractor {othr} ({pct(othr,len(gw)):.1f}%)")

print()
print("=" * 106)
print("7. NOTA ACCEPTANCE BY SLOT POSITION  (key letter b / c / d), pooled and per model")
print("=" * 106)
print(f"{'model':<22}" + "".join(f"{'key='+L:>22}" for L in "bcd"))
for m in MODELS + ["POOLED"]:
    rs = ROWS if m == "POOLED" else [r for r in ROWS if r["model"] == m]
    line = f"{('POOLED' if m=='POOLED' else SHORT[m]):<22}"
    for L in "bcd":
        sub = [r for r in rs if r["correct_letter"] == L]
        k = sum(r["B_correct"] for r in sub)
        line += f"{pct(k,len(sub)):>9.1f}% ({k:>3}/{len(sub):<3})"
    print(line)
# chi-square on pooled position effect
import stats_lib as S
succ = [sum(r["B_correct"] for r in ROWS if r["correct_letter"] == L) for L in "bcd"]
tot = [sum(1 for r in ROWS if r["correct_letter"] == L) for L in "bcd"]
N, Sm = sum(tot), sum(succ)
ps = Sm / N
x2 = sum((o - t * pp) ** 2 / (t * pp) for s, t in zip(succ, tot)
         for o, pp in ((s, ps), (t - s, 1 - ps)))
print(f"   pooled position effect on NOTA acceptance: Pearson chi2(2)={x2:.2f}  p={S.chi2_sf(x2,2):.3g}")
# same for A, as the reference
succA = [sum(r["A_correct"] for r in ROWS if r["correct_letter"] == L) for L in "bcd"]
psA = sum(succA) / N
x2A = sum((o - t * pp) ** 2 / (t * pp) for s, t in zip(succA, tot)
          for o, pp in ((s, psA), (t - s, 1 - psA)))
print(f"   same test on condition A (reference):       Pearson chi2(2)={x2A:.2f}  p={S.chi2_sf(x2A,2):.3g}   "
      f"rates " + " ".join(f"{L}={pct(s,t):.1f}%" for L, s, t in zip('bcd', succA, tot)))

print()
print("=" * 106)
print("8. THE EXCLUDED correct_letter=='a' STRATUM: identical NOTA string, but in the FIRST slot,")
print("   where 'Ninguna de las respuestas ANTERIORES' has no antecedent. Positional floor.")
print("=" * 106)
EXA = [r for r in ALL if r["excl_nota_position_a"] and not r["excl_item_defect"]]
print(f"   cells: {len(EXA)}  items: {len(set(r['question_id'] for r in EXA))}")
print(f"{'model':<22}{'A acc':>18}{'B acc (NOTA in slot a)':>28}{'drop':>10}")
for m in MODELS:
    rs = [r for r in EXA if r["model"] == m]
    if not rs:
        continue
    n = len(rs)
    ka, kb = sum(r["A_correct"] for r in rs), sum(r["B_correct"] for r in rs)
    print(f"{SHORT[m]:<22}{pct(ka,n):>10.1f}% {ka:>3}/{n:<4}{pct(kb,n):>16.1f}% {kb:>3}/{n:<4}{pct(kb,n)-pct(ka,n):>+9.1f}pp")
kaT = sum(r["A_correct"] for r in EXA); kbT = sum(r["B_correct"] for r in EXA)
print(f"{'POOLED slot-a':<22}{pct(kaT,len(EXA)):>10.1f}% {kaT:>3}/{len(EXA):<4}"
      f"{pct(kbT,len(EXA)):>16.1f}% {kbT:>3}/{len(EXA):<4}{pct(kbT,len(EXA))-pct(kaT,len(EXA)):>+9.1f}pp")
kaM = sum(r["A_correct"] for r in ROWS); kbM = sum(r["B_correct"] for r in ROWS)
print(f"{'POOLED slots b/c/d':<22}{pct(kaM,len(ROWS)):>10.1f}% {kaM:>3}/{len(ROWS):<4}"
      f"{pct(kbM,len(ROWS)):>16.1f}% {kbM:>3}/{len(ROWS):<4}{pct(kbM,len(ROWS))-pct(kaM,len(ROWS)):>+9.1f}pp")
p = fisher_2x2(kbT, len(EXA) - kbT, kbM, len(ROWS) - kbM)
print(f"   NOTA acceptance slot-a vs slots b/c/d: Fisher exact two-sided p={p:.3g}")

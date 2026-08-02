"""nota-acceptance part 5: quote what a refusing model actually says about the NOTA option,
plus the negated-stem interaction (a NOTA option under a 'senale la INCORRECTA' stem is
semantically odd, so acceptance there is a surface-form effect, not a knowledge effect).
"""
import json
import re
import unicodedata
from collections import defaultdict

import stats_lib as S
from mech_nota_lib import cp_ci, fisher_2x2

ROWS = [r for r in json.load(open(
    "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
    "experiment-31-07-26/analysis/paired_clean.json")) if r["analysis_include"]]
T = json.load(open("/private/tmp/claude-501/-Users-ernestsaenz-Programming-GIFT-abstract-dossier/"
                   "a0613478-db50-4bbd-ba89-911fee14cc09/scratchpad/b_traces3.json"))
OPTS = json.load(open("/private/tmp/claude-501/-Users-ernestsaenz-Programming-GIFT-abstract-dossier/"
                      "a0613478-db50-4bbd-ba89-911fee14cc09/scratchpad/opts.json"))
MODELS = sorted(set(r["model"] for r in ROWS))
SHORT = {m: m.split("/")[-1] for m in MODELS}


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def pct(k, n):
    return 100.0 * k / n if n else float("nan")


print("=" * 104)
print("13. WHAT A REFUSING MODEL SAYS ABOUT THE 'Ninguna...' OPTION")
print("    Cells with A correct (knew the key) and B wrong (declined NOTA), reasoning excerpt")
print("    around the first occurrence of 'ninguna'.")
print("=" * 104)
shown = defaultdict(int)
for m in ("qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2", "google/gemini-3.6-flash"):
    for r in ROWS:
        if r["model"] != m or r["A_correct"] != 1 or r["B_correct"] != 0:
            continue
        t = T.get(f"B|{m}|{r['question_id']}")
        if not t:
            continue
        rea = " ".join(t[1].split())
        i = norm(rea).find("ninguna")
        if i < 0 or shown[m] >= 3:
            continue
        shown[m] += 1
        a = OPTS["A"][r["question_id"]]
        print(f"\n  [{SHORT[m]}] item {r['question_id']}  key={r['correct_letter']}  "
              f"A->{r['A_selected']} (correct)  B->{r['B_selected']}")
        print(f"    stem: {' '.join(a['question_text'].split())[:170]}")
        print(f"    key text removed in B: \"{' '.join(a[r['correct_letter']].split())[:150]}\"")
        print(f"    B answer it chose instead: \"{' '.join(a[r['B_selected']].split())[:150]}\"")
        print(f"    reasoning: ...{rea[max(0,i-260):i+380]}...")

print()
print("=" * 104)
print("14. NEGATED STEMS: 'Ninguna de las respuestas anteriores es correcta' inside a")
print("    'senale la INCORRECTA' item is a semantic knot. Acceptance by stem polarity.")
print("=" * 104)
print(f"{'model':<22}{'B acc | plain stem':>28}{'B acc | negated stem':>28}{'Fisher p':>12}")
for m in MODELS + ["POOLED"]:
    rs = ROWS if m == "POOLED" else [r for r in ROWS if r["model"] == m]
    pos = [r for r in rs if not r["negated_stem"]]
    neg = [r for r in rs if r["negated_stem"]]
    kp, kn = sum(r["B_correct"] for r in pos), sum(r["B_correct"] for r in neg)
    p = fisher_2x2(kp, len(pos) - kp, kn, len(neg) - kn)
    lab = "POOLED" if m == "POOLED" else SHORT[m]
    print(f"{lab:<22}{pct(kp,len(pos)):>18.1f}% {kp:>4}/{len(pos):<4}"
          f"{pct(kn,len(neg)):>18.1f}% {kn:>4}/{len(neg):<4}{p:>12.3g}")
print()
print(f"{'  same split on A':<22}{'A acc | plain':>28}{'A acc | negated':>28}{'Fisher p':>12}")
for m in MODELS + ["POOLED"]:
    rs = ROWS if m == "POOLED" else [r for r in ROWS if r["model"] == m]
    pos = [r for r in rs if not r["negated_stem"]]
    neg = [r for r in rs if r["negated_stem"]]
    kp, kn = sum(r["A_correct"] for r in pos), sum(r["A_correct"] for r in neg)
    p = fisher_2x2(kp, len(pos) - kp, kn, len(neg) - kn)
    lab = "POOLED" if m == "POOLED" else SHORT[m]
    print(f"{lab:<22}{pct(kp,len(pos)):>18.1f}% {kp:>4}/{len(pos):<4}"
          f"{pct(kn,len(neg)):>18.1f}% {kn:>4}/{len(neg):<4}{p:>12.3g}")

# conditional version: P(B ok | A ok) by polarity, pooled
print()
print("    P(B ok | A ok) by stem polarity, pooled over models:")
pos = [r for r in ROWS if r["A_correct"] == 1 and not r["negated_stem"]]
neg = [r for r in ROWS if r["A_correct"] == 1 and r["negated_stem"]]
kp, kn = sum(r["B_correct"] for r in pos), sum(r["B_correct"] for r in neg)
lp, hp = cp_ci(kp, len(pos)); ln, hn = cp_ci(kn, len(neg))
print(f"      plain   {pct(kp,len(pos)):.1f}% [{100*lp:.1f},{100*hp:.1f}]  {kp}/{len(pos)}")
print(f"      negated {pct(kn,len(neg)):.1f}% [{100*ln:.1f},{100*hn:.1f}]  {kn}/{len(neg)}")
print(f"      Fisher exact two-sided p = {fisher_2x2(kp, len(pos)-kp, kn, len(neg)-kn):.3g}")

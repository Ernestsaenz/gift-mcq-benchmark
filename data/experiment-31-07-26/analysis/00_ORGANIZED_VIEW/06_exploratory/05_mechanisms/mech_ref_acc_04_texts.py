"""Step 4: read the option texts of the items that drive the 'refusal' mass.

Hypothesis raised by step 3: many source items contain a CATCH-ALL / COMPOUND option
("Todas las respuestas anteriores son correctas", "Las respuestas a) y b) son
correctas", "Ninguna de las anteriores"). When the correct option's TEXT is swapped for
NOTA, such an option can become a competing-or-broken referent, so the model's choice is
an item-construction artifact, not a disposition about the NOTA string.
"""
import collections, re, unicodedata
from mech_ref_acc_lib import load_cells, load_questions, cp_ci, fisher_2x2, binom_test_exact

cells = load_cells()
Q = load_questions()
SHORT = {"google/gemini-3.6-flash": "gemini", "z-ai/glm-5.2": "glm",
         "qwen/qwen3.6-35b-a3b": "qwen", "google/gemma-4-26b-a4b-it": "gemma"}
MODELS = ["gemini", "glm", "qwen", "gemma"]
LETTERS = ["a", "b", "c", "d"]
for r in cells:
    r["m"] = SHORT[r["model"]]
by_item = collections.defaultdict(dict)
for r in cells:
    by_item[r["question_id"]][r["m"]] = r


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


RE_ALL = re.compile(r"\btodas las (respuestas|anteriores|opciones)|\btodas son correctas"
                    r"|\btodas las afirmaciones")
RE_NONE = re.compile(r"\bninguna de (las|los)|\bninguna es correcta|\bninguna de las anteriores")
RE_COMBO = re.compile(r"\b(las respuestas|las opciones)\s*[a-d]\s*\)?\s*(y|,|e)\s*[a-d]\s*\)?"
                      r"|\b[a-d]\s*\)\s*y\s*[a-d]\s*\)\s*son correctas"
                      r"|\bson correctas las")
RE_SONCOR = re.compile(r"son (correctas|ciertas|verdaderas)\b")


def kind(txt):
    t = norm(txt)
    if RE_NONE.search(t):
        return "NONE"
    if RE_ALL.search(t):
        return "ALL"
    if RE_COMBO.search(t) or (RE_SONCOR.search(t) and re.search(r"\b[a-d]\s*\)", t)):
        return "COMBO"
    return "plain"


print("=" * 104)
print("A) How many analysis items contain a catch-all / compound option in the A arm?")
print("=" * 104)
item_kinds = {}
for qid in by_item:
    a = Q[qid]["A"]
    ks = {L: kind(a["opts"][L]) for L in LETTERS}
    item_kinds[qid] = ks
cnt = collections.Counter()
for qid, ks in item_kinds.items():
    tags = sorted({v for v in ks.values() if v != "plain"})
    cnt["+".join(tags) if tags else "none"] += 1
for k, v in cnt.most_common():
    print(f"   {k:20} {v:4} items")
has_catchall = {qid for qid, ks in item_kinds.items()
                if any(v != "plain" for L, v in ks.items())}
print(f"   -> {len(has_catchall)}/{len(by_item)} items ({100*len(has_catchall)/len(by_item):.0f}%) "
      f"carry at least one catch-all/compound option")

print()
print("=" * 104)
print("B) Does the 'refusal' rate depend on whether the item carries a catch-all option?")
print("   P(B correct | A correct), split by item type.")
print("=" * 104)
print(f"   {'model':8} {'catch-all item':>26}   {'plain item':>26}   {'Fisher p':>9}")
tk1 = tn1 = tk2 = tn2 = 0
for m in MODELS:
    sub = [r for r in cells if r["m"] == m and r["A_correct"]]
    g1 = [r for r in sub if r["question_id"] in has_catchall]
    g2 = [r for r in sub if r["question_id"] not in has_catchall]
    k1, n1 = sum(r["B_correct"] for r in g1), len(g1)
    k2, n2 = sum(r["B_correct"] for r in g2), len(g2)
    tk1 += k1; tn1 += n1; tk2 += k2; tn2 += n2
    p = fisher_2x2(k1, n1 - k1, k2, n2 - k2)
    print(f"   {m:8} {k1:5}/{n1:<5} {100*k1/n1:6.1f}%{'':6} {k2:5}/{n2:<5} {100*k2/n2:6.1f}%{'':6} {p:9.3g}")
p = fisher_2x2(tk1, tn1 - tk1, tk2, tn2 - tk2)
lo1, hi1 = cp_ci(tk1, tn1)
lo2, hi2 = cp_ci(tk2, tn2)
print(f"   {'POOLED':8} {tk1:5}/{tn1:<5} {100*tk1/tn1:6.1f}%{'':6} {tk2:5}/{tn2:<5} {100*tk2/tn2:6.1f}%"
      f"{'':6} {p:9.3g}")
print(f"      CP95 catch-all [{100*lo1:.1f},{100*hi1:.1f}]   plain [{100*lo2:.1f},{100*hi2:.1f}]")
print("   method: Fisher exact 2x2, two-sided.")

print()
print("=" * 104)
print("C) When a model abandons NOTA on a catch-all item, does it land ON the catch-all option?")
print("=" * 104)
hit = tot = 0
per = collections.Counter()
for qid, d in by_item.items():
    ks = item_kinds[qid]
    for m, r in d.items():
        if not (r["A_correct"] and not r["B_correct"]):
            continue
        surv = [L for L in LETTERS if L != r["correct_letter"]]
        cs = [L for L in surv if ks[L] != "plain"]
        if not cs:
            continue
        tot += 1
        if r["B_selected"] in cs:
            hit += 1
            per[ks[r["B_selected"]]] += 1
lo, hi = cp_ci(hit, tot)
print(f"   landed on a catch-all/compound survivor: {hit}/{tot} = {100*hit/tot:.1f}% "
      f"CP95 [{100*lo:.1f},{100*hi:.1f}]")
print(f"   (chance if uniform over the 3 survivors and 1 of them is catch-all: 33.3%)")
print(f"   exact binomial vs p0=1/3: p = {binom_test_exact(hit, tot, 1/3):.3g}   breakdown {dict(per)}")

print()
print("=" * 104)
print("D) The 6 items where ALL FOUR models abandoned NOTA -- full option texts (arm B)")
print("=" * 104)
worst = []
for qid, d in by_item.items():
    nf = sum(1 for r in d.values() if r["A_correct"] and not r["B_correct"])
    if nf >= 3 and len(d) == 4:
        worst.append((nf, qid))
worst.sort(reverse=True)
for nf, qid in worst[:9]:
    d = by_item[qid]
    b = Q[qid]["B"]
    cl = b["correct_letter"]
    dest = collections.Counter(r["B_selected"] for r in d.values()
                               if r["A_correct"] and not r["B_correct"])
    print(f"\n--- {qid}  nfail={nf}  correct_letter={cl}  destinations={dict(dest)}")
    print(f"    Q: {Q[qid]['B']['qtext'][:260]}")
    for L in LETTERS:
        mark = "<<NOTA" if L == cl else ("<<CHOSEN" if L in dest else "")
        print(f"     {L}) [{item_kinds[qid][L]:6}] {b['opts'][L][:150]}  {mark}")

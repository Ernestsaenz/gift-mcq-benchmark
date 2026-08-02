"""nota-acceptance part 4: read the model's own words in condition B.

Does a model that REFUSES the NOTA slot even register that the option is there?

CIRCULARITY GUARD: the answer payload is a JSON object that echoes
selected_option_text, so a model that ACCEPTS NOTA trivially prints the string
'Ninguna de las respuestas anteriores es correcta.'  We therefore search only the
REASONING channel (message.reasoning / reasoning_details), never the answer JSON,
and we drop any model that emits no reasoning at all.
"""
import json
import re
import sqlite3
import unicodedata
from collections import defaultdict

from mech_nota_lib import cp_ci, fisher_2x2

DB = ("file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
      "experiment-31-07-26/experiment.sqlite?mode=ro")
ROWS = [r for r in json.load(open(
    "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
    "experiment-31-07-26/analysis/paired_clean.json")) if r["analysis_include"]]
MODELS = sorted(set(r["model"] for r in ROWS))
SHORT = {m: m.split("/")[-1] for m in MODELS}
CACHE = ("/private/tmp/claude-501/-Users-ernestsaenz-Programming-GIFT-abstract-dossier/"
         "a0613478-db50-4bbd-ba89-911fee14cc09/scratchpad/b_traces3.json")
# The DB holds FIVE experiments (expA_or, expB_or, expA_gift, expB_gift, smoke).
# dataset_meta.json says the paired analysis is the OpenRouter arm only; matching on
# name.startswith('expA') silently mixes in the GIFT arm, so pin the exact names and
# reach the attempt that was actually SCORED via scores -> parsed_answers.
EXPS = {"expA_or_310726": "A", "expB_or_310726": "B"}


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def split_body(body):
    """Return (answer_channel, reasoning_channel)."""
    try:
        j = json.loads(body)
    except Exception:
        return (body or "", "")
    ans, rea = [], []
    for ch in j.get("choices", []) or []:
        msg = ch.get("message") or {}
        if isinstance(msg.get("content"), str):
            ans.append(msg["content"])
        if isinstance(msg.get("reasoning"), str):
            rea.append(msg["reasoning"])
        for d in msg.get("reasoning_details") or []:
            for k in ("text", "summary", "data"):
                if isinstance(d.get(k), str):
                    rea.append(d[k])
    return ("\n".join(ans), "\n".join(rea))


try:
    T = json.load(open(CACHE))
    SEL = json.load(open(CACHE + ".sel"))
except Exception:
    con = sqlite3.connect(DB, uri=True)
    c = con.cursor()
    T, SEL = {}, {}
    for exp, model, qid, letter, body in c.execute(
            "select e.name, lc.model, q.question_id, pans.selected_letter, pa.response_body "
            "from scores s "
            "join parsed_answers pans on pans.id = s.parsed_answer_id "
            "join provider_attempts pa on pa.id = pans.provider_attempt_id "
            "join logical_calls lc on lc.id = s.logical_call_id "
            "join experiments e on e.id = lc.experiment_id "
            "join questions q on q.id = lc.question_id "
            "where e.name in ('expA_or_310726','expB_or_310726')"):
        k = f"{EXPS[exp]}|{model}|{qid}"
        T[k] = split_body(body or "")
        SEL[k] = letter
    con.close()
    json.dump(T, open(CACHE, "w"), ensure_ascii=False)
    json.dump(SEL, open(CACHE + ".sel", "w"))
print(f"traces cached: {len(T)}")

# integrity check: the letter attached to the trace must equal the letter in paired_clean
bad = 0
for r in ROWS:
    for arm in "AB":
        s = SEL.get(f"{arm}|{r['model']}|{r['question_id']}")
        if s is not None and (s or "").lower() != r[f"{arm}_selected"]:
            bad += 1
print(f"trace<->paired_clean selected-letter mismatches: {bad} / {2*len(ROWS)}")

print()
print("   reasoning-channel availability in the B arm (analysis cells)")
for m in MODELS:
    rs = [r for r in ROWS if r["model"] == m]
    have = [T.get(f"B|{m}|{r['question_id']}") for r in rs]
    n_r = sum(1 for h in have if h and len(h[1].strip()) > 0)
    chars = [len(h[1]) for h in have if h]
    chars.sort()
    print(f"     {SHORT[m]:<22} cells with non-empty reasoning: {n_r}/{len(rs)}   "
          f"median reasoning chars: {chars[len(chars)//2] if chars else 0}")

MENTION = re.compile(r"ninguna|none of the (above|answers|options)|\bningun[ao]\b")

print()
print("=" * 104)
print("12. DOES THE MODEL'S REASONING EVEN MENTION THE 'Ninguna...' OPTION IN CONDITION B?")
print("    Restricted to cells the model got RIGHT in A (it knew the true claim), so a refusal")
print("    cannot be blamed on not knowing the medicine. Reasoning channel only - the answer")
print("    JSON is excluded because accepting NOTA would echo the string tautologically.")
print("=" * 104)
print(f"{'model':<22}{'reasoning names NOTA | accepted':>34}{'| refused':>26}{'Fisher exact p':>18}")
tot = [0, 0, 0, 0]
for m in MODELS:
    rs = [r for r in ROWS if r["model"] == m and r["A_correct"] == 1]
    got = [(r, T.get(f"B|{m}|{r['question_id']}")) for r in rs]
    got = [(r, t[1]) for r, t in got if t and t[1].strip()]
    if not got:
        print(f"{SHORT[m]:<22}{'-- emits no reasoning channel, cannot be assessed --':>78}")
        continue
    acc = [(r, t) for r, t in got if r["B_correct"] == 1]
    ref = [(r, t) for r, t in got if r["B_correct"] == 0]
    ka = sum(1 for r, t in acc if MENTION.search(norm(t)))
    kr = sum(1 for r, t in ref if MENTION.search(norm(t)))
    tot[0] += ka; tot[1] += len(acc); tot[2] += kr; tot[3] += len(ref)
    p = fisher_2x2(ka, len(acc) - ka, kr, len(ref) - kr)
    print(f"{SHORT[m]:<22}{100*ka/len(acc):>24.1f}% {ka:>3}/{len(acc):<4}"
          f"{100*kr/len(ref):>17.1f}% {kr:>3}/{len(ref):<4}{p:>18.3g}")
if tot[1] and tot[3]:
    lo, hi = cp_ci(tot[2], tot[3])
    print(f"{'POOLED (reasoners)':<22}{100*tot[0]/tot[1]:>24.1f}% {tot[0]:>3}/{tot[1]:<4}"
          f"{100*tot[2]/tot[3]:>17.1f}% {tot[2]:>3}/{tot[3]:<4}"
          f"{fisher_2x2(tot[0], tot[1]-tot[0], tot[2], tot[3]-tot[2]):>18.3g}")
    print(f"    refused-but-explicitly-considered-it: {tot[2]}/{tot[3]} = {100*tot[2]/tot[3]:.1f}%  "
          f"CP95 [{100*lo:.1f},{100*hi:.1f}]")

# baseline: how often does the A-arm reasoning contain 'ninguna' at all?
print()
print("    baseline - same regex on the A-arm reasoning (no NOTA option present):")
for m in MODELS:
    rs = [r for r in ROWS if r["model"] == m]
    got = [T.get(f"A|{m}|{r['question_id']}") for r in rs]
    got = [t[1] for t in got if t and t[1].strip()]
    if not got:
        continue
    k = sum(1 for t in got if MENTION.search(norm(t)))
    print(f"      {SHORT[m]:<22} {k}/{len(got)} = {100*k/len(got):.1f}%")

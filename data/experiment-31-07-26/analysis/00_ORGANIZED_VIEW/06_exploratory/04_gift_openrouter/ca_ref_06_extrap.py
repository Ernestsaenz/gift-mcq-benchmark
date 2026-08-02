#!/usr/bin/env python
"""Leave-one-out difficulty gradient (no conditioning-on-own-outcome artifact) +
OpenRouter backend-routing check across arms."""
import json, math, collections, sqlite3

AN = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/"
DB = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite"
J = json.load(open("/private/tmp/claude-501/-Users-ernestsaenz-Programming-GIFT-abstract-dossier/a0613478-db50-4bbd-ba89-911fee14cc09/scratchpad/cross_arm_A.NEW.json"))
cells = [c for c in J if c["analysis_include"]]

# leave-one-out OR difficulty: for cell (q,m) use the OTHER 3 models' OR correctness
byq = collections.defaultdict(list)
for c in cells: byq[c["question_id"]].append(c)
print("--- GIFT-vs-OR net discordance by LEAVE-ONE-OUT OR difficulty (other 3 models) ---")
strat = collections.defaultdict(lambda: [0, 0, 0])
for c in cells:
    loo = sum(o["or_correct"] for o in byq[c["question_id"]] if o["model"] != c["model"])
    strat[loo][2] += 1
    if c["gift_correct"] and not c["or_correct"]: strat[loo][0] += 1
    if not c["gift_correct"] and c["or_correct"]: strat[loo][1] += 1
for s in sorted(strat):
    b, cc, n = strat[s]
    print("  other-3 OR correct %d/3  cells=%4d  b=%2d c=%2d  net=%+3d  net per 100 cells=%+.2f"
          % (s, n, b, cc, b - cc, 100.0 * (b - cc) / n))

# same, restricted to gemma (the driver)
print("\n  -- gemma only --")
st2 = collections.defaultdict(lambda: [0, 0, 0])
for c in cells:
    if "gemma" not in c["model"]: continue
    loo = sum(o["or_correct"] for o in byq[c["question_id"]] if o["model"] != c["model"])
    st2[loo][2] += 1
    if c["gift_correct"] and not c["or_correct"]: st2[loo][0] += 1
    if not c["gift_correct"] and c["or_correct"]: st2[loo][1] += 1
for s in sorted(st2):
    b, cc, n = st2[s]
    print("  other-3 OR correct %d/3  cells=%4d  b=%2d c=%2d  net=%+3d  net per 100=%+.2f"
          % (s, n, b, cc, b - cc, 100.0 * (b - cc) / n))

# ---- backend routing: what provider actually served each OpenRouter / GIFT call? ----
con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
con.row_factory = sqlite3.Row
print("\n--- backend/provider recorded in the scored attempt, by arm and model ---")
for exp in ("expA_or_310726", "expA_gift_310726"):
    cnt = collections.defaultdict(collections.Counter)
    for r in con.execute("""SELECT lc.model model, att.response_json rj
                            FROM experiments e JOIN logical_calls lc ON lc.experiment_id=e.id
                            JOIN scores s ON s.logical_call_id=lc.id
                            JOIN parsed_answers pa ON pa.id=s.parsed_answer_id
                            JOIN provider_attempts att ON att.id=pa.provider_attempt_id
                            WHERE e.name=?""", (exp,)):
        prov = None
        if r["rj"]:
            try:
                d = json.loads(r["rj"])
                prov = d.get("provider") or d.get("provider_name") or (d.get("meta") or {}).get("provider")
            except Exception:
                prov = "<unparseable>"
        cnt[r["model"]][prov] += 1
    print(" ", exp)
    for m in sorted(cnt):
        print("    %-26s %s" % (m.split("/")[-1], dict(cnt[m])))

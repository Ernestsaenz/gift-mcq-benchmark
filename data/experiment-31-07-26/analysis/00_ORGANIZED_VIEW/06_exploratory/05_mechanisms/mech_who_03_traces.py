"""Mine the raw model reasoning traces for condition B: does the model consider and
reject 'Ninguna de las respuestas anteriores'?  Read-only on the DB."""
import sqlite3, json, os, re, collections, unicodedata
from mech_who_00_build import cells, items, DB

con = sqlite3.connect(DB, uri=True)
# experiment 6 = condition A (dataset 1), experiment 7 = condition B (dataset 2), openrouter
rows = con.execute("""
  select e.id, q.question_id, lc.model, pa.response_json
  from logical_calls lc
  join experiments e on e.id = lc.experiment_id
  join questions q on q.id = lc.question_id
  join provider_attempts pa on pa.logical_call_id = lc.id
  where e.id in (6,7) and pa.response_json is not null
""").fetchall()

txt = {}
for eid, qid, model, rj in rows:
    try:
        j = json.loads(rj)
        msg = j["choices"][0]["message"]
    except Exception:
        continue
    txt[("A" if eid == 6 else "B", qid, model)] = (msg.get("content") or "",
                                                   msg.get("reasoning") or "")

def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))

NONE_RE = re.compile(r"\bningun[ao]\b|\bnone of the (above|answers|options)\b|"
                     r"\bnone\b.{0,15}\bcorrect\b")
ELIM = re.compile(r"\b(incorrect|not correct|false|wrong|descartar|descarto|es falsa|"
                  r"no es correcta|eliminate|rule out)\b")

print("=" * 78)
print("T0. trace coverage")
have = collections.Counter()
for r in cells:
    for c in "AB":
        have[(c, r["model"], ("B" if c == "B" else "A"), bool(txt.get((c, r["question_id"], r["model"]))))] += 1
cov = collections.Counter()
for r in cells:
    for c in "AB":
        k = txt.get((c, r["question_id"], r["model"]))
        cov[(r["model"], c, "content" if k else "MISSING",
             "reasoning" if (k and k[1].strip()) else "no-reasoning")] += 1
for k in sorted(cov): print("   ", k, cov[k])

print()
print("=" * 78)
print("T1. In condition B, does the trace MENTION the none-of-the-above option?")
print("    (models that emit reasoning text only)")
groups = {"B correct (picked NOTA)": lambda r: r["B_correct"],
          "LOST (A+ -> B-)": lambda r: r["lost"],
          "both wrong (A- B-)": lambda r: (not r["A_correct"]) and (not r["B_correct"]),
          "GAINED (A- -> B+)": lambda r: r["gained"]}
for model in sorted(set(r["model"] for r in cells)):
    lines = []
    for g, f in groups.items():
        n = m = 0
        for r in cells:
            if r["model"] != model or not f(r): continue
            t = txt.get(("B", r["question_id"], model))
            if not t or not t[1].strip(): continue
            n += 1; m += int(bool(NONE_RE.search(norm(t[1]))))
        if n: lines.append(f"      {g:<26} {m:4d}/{n:4d} = {m/n:.3f}")
    if lines:
        print(f"   {model}")
        print("\n".join(lines))

print()
print("=" * 78)
print("T2. In condition A, did the trace already MENTION 'ninguna'? (should be ~0: no NOTA option)")
for model in sorted(set(r["model"] for r in cells)):
    n = m = 0
    for r in cells:
        t = txt.get(("A", r["question_id"], model))
        if r["model"] != model or not t or not t[1].strip(): continue
        n += 1; m += int(bool(NONE_RE.search(norm(t[1]))))
    if n: print(f"   {model:<28} {m}/{n} = {m/n:.3f}")

if __name__ == "__main__":
    import pickle
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "mech_who_traces.pkl"), "wb") as fh:
        pickle.dump(txt, fh)
    print("\n(traces cached)")

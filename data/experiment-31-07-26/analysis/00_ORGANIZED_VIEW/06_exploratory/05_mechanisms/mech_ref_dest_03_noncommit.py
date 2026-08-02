"""REFUTATION pass 3: the only channel through which non-commitment could be
recorded is an attempt that ends at the token cap without emitting the JSON.
Quantify it per condition on the analysed cells, test the A-vs-B asymmetry with
an exact paired (McNemar) test and a cluster-permutation test, and inspect what
the truncated generations actually contain. Stdlib only. READ-ONLY on the DB."""
import json, sqlite3, collections, math, random, re

BASE = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26"
DB = f"file:{BASE}/experiment.sqlite?mode=ro"
inc = [r for r in json.load(open(f"{BASE}/analysis/paired_clean.json"))
       if r["analysis_include"]]
cellkey = {(c["question_id"], c["model"]): c for c in inc}

con = sqlite3.connect(DB, uri=True)
con.row_factory = sqlite3.Row
cond = {"expA_or_310726": "A", "expB_or_310726": "B"}
q = """
select e.name exp, lc.model model, qq.question_id qid, lc.id lcid, pa.id paid,
       pa.attempt_index, pa.status_code, pa.finish_reason, pa.completion_tokens,
       pa.latency_ms, pa.request_sha256, ps.parse_status, ps.selected_letter
from provider_attempts pa
join logical_calls lc on lc.id = pa.logical_call_id
join experiments e on e.id = lc.experiment_id
join questions qq on qq.id = lc.question_id
left join parsed_answers ps on ps.provider_attempt_id = pa.id
where e.name in ('expA_or_310726','expB_or_310726')
order by 1,2,3,6
"""
att = collections.defaultdict(list)
for r in con.execute(q):
    att[(cond[r["exp"]], r["model"], r["qid"])].append(dict(r))

print("=" * 78)
print("1. NON-COMMITTING ATTEMPTS (finish_reason='length', no JSON emitted)")
print("=" * 78)
flag = {}
for C in "AB":
    for (qid, m) in cellkey:
        a = att.get((C, m, qid), [])
        flag[(C, m, qid)] = 1 if any(x["parse_status"] != "ok" for x in a) else 0
for C in "AB":
    n = sum(flag[(C, m, q_)] for (q_, m) in cellkey)
    print(f"  cond {C}: cells with >=1 non-answering attempt = {n}/{len(cellkey)} "
          f"= {n/len(cellkey):.3%}")
    per = collections.Counter(m for (q_, m) in cellkey if flag[(C, m, q_)])
    print(f"            by model: {dict(per)}")
    tot = collections.Counter()
    for (q_, m) in cellkey:
        for x in att.get((C, m, q_), []):
            if x["parse_status"] != "ok":
                tot[x["finish_reason"]] += 1
    print(f"            non-answering attempts by finish_reason: {dict(tot)}")

# paired exact McNemar (binomial on discordant pairs, p=0.5, two-sided)
b = sum(1 for (q_, m) in cellkey if flag[("B", m, q_)] and not flag[("A", m, q_)])
c = sum(1 for (q_, m) in cellkey if flag[("A", m, q_)] and not flag[("B", m, q_)])
both = sum(1 for (q_, m) in cellkey if flag[("A", m, q_)] and flag[("B", m, q_)])


def binom_two_sided(k, n, p=0.5):
    if n == 0:
        return 1.0
    pmf = lambda i: math.comb(n, i) * p ** i * (1 - p) ** (n - i)
    obs = pmf(k)
    return min(1.0, sum(pmf(i) for i in range(n + 1) if pmf(i) <= obs * (1 + 1e-9)))


print(f"\n  paired table: B-only={b}  A-only={c}  both={both}")
print(f"  exact McNemar (two-sided binomial on {b+c} discordant pairs, p=0.5): "
      f"p={binom_two_sided(b, b + c):.4f}")

# cluster-permutation: flip A/B labels within a whole cluster
clus = collections.defaultdict(list)
for c_ in inc:
    clus[c_["cluster"]].append((c_["question_id"], c_["model"]))
obs_diff = (sum(flag[("B", m, q_)] for (q_, m) in cellkey)
            - sum(flag[("A", m, q_)] for (q_, m) in cellkey))
rng = random.Random(20260731)
N = 20000
ge = 0
for _ in range(N):
    d = 0
    for cl, cells in clus.items():
        s = 1 if rng.random() < 0.5 else -1
        for (q_, m) in cells:
            d += s * (flag[("B", m, q_)] - flag[("A", m, q_)])
    if abs(d) >= abs(obs_diff):
        ge += 1
print(f"  cluster-sign-flip permutation (208 clusters, N={N}): "
      f"observed B-A = {obs_diff:+d}, two-sided p={(ge+1)/(N+1):.4f}")

print()
print("=" * 78)
print("2. DOES THE RETRY POLICY MATTER FOR THE SCORED OUTCOME?")
print("=" * 78)
for C in "AB":
    rt = [(q_, m) for (q_, m) in cellkey if flag[(C, m, q_)]]
    nr = [(q_, m) for (q_, m) in cellkey if not flag[(C, m, q_)]]
    er = sum(1 - cellkey[(q_, m)][f"{C}_correct"] for (q_, m) in rt)
    en = sum(1 - cellkey[(q_, m)][f"{C}_correct"] for (q_, m) in nr)
    print(f"  cond {C}: error rate | needed a retry  = {er}/{len(rt)} = "
          f"{er/max(1,len(rt)):.1%}")
    print(f"           error rate | first attempt ok = {en}/{len(nr)} = {en/len(nr):.1%}")

# glm-only, the model that carries essentially all of it
print("\n  glm-5.2 only (carries 40/45 of the retry cells):")
for C in "AB":
    rt = [(q_, m) for (q_, m) in cellkey if m == "z-ai/glm-5.2" and flag[(C, m, q_)]]
    nr = [(q_, m) for (q_, m) in cellkey if m == "z-ai/glm-5.2" and not flag[(C, m, q_)]]
    er = sum(1 - cellkey[(q_, m)][f"{C}_correct"] for (q_, m) in rt)
    en = sum(1 - cellkey[(q_, m)][f"{C}_correct"] for (q_, m) in nr)
    print(f"    {C}: retry-cells {er}/{len(rt)} err ({er/max(1,len(rt)):.0%}) | "
          f"clean {en}/{len(nr)} err ({en/len(nr):.1%})")

print()
print("=" * 78)
print("3. THE DROPPED CELL")
print("=" * 78)
allq = set(c["question_id"] for c in inc)
models = sorted(set(c["model"] for c in inc))
missing = [(q_, m) for q_ in allq for m in models if (q_, m) not in cellkey]
print("  (item,model) pairs in the 325x4 grid absent from the analysis set:", missing)
for (q_, m) in missing:
    for C in "AB":
        for x in att.get((C, m, q_), []):
            print(f"    {C} {m} {q_} attempt={x['attempt_index']} status={x['status_code']} "
                  f"finish={x['finish_reason']} tokens={x['completion_tokens']} "
                  f"parse={x['parse_status']}")

print()
print("=" * 78)
print("4. WHAT IS IN A TRUNCATED (NON-COMMITTING) B GENERATION?")
print("=" * 78)
ids = []
for (q_, m) in cellkey:
    for x in att.get(("B", m, q_), []):
        if x["parse_status"] != "ok":
            ids.append((q_, m, x["paid"], x["completion_tokens"]))
print("  non-answering B attempts on analysed cells:", len(ids))
shown = 0
for (q_, m, paid, tk) in ids:
    body = con.execute("select response_body from provider_attempts where id=?",
                       (paid,)).fetchone()[0]
    try:
        j = json.loads(body)
        txt = j["choices"][0]["message"].get("content") or ""
        rsn = j["choices"][0]["message"].get("reasoning") or ""
    except Exception:
        txt, rsn = body or "", ""
    blob = (rsn + "\n" + txt)
    low = blob.lower()
    hits = {k: low.count(k) for k in
            ["ninguna", "no es correcta", "ninguna de las respuestas", "pero", "sin embargo",
             "opcion c", "opción c", "correcta es"]}
    if shown < 4:
        shown += 1
        print(f"\n  --- {m} {q_} tokens={tk} content_len={len(txt)} reasoning_len={len(rsn)}")
        print("      keyword counts:", hits)
        tail = re.sub(r"\s+", " ", blob)[-700:]
        print("      TAIL:", tail)

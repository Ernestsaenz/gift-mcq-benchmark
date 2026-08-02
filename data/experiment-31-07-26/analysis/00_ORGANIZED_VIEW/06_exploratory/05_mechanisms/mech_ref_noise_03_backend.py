"""Backend provenance as a natural experiment on the noise floor.

The claim states: "No replicate runs exist in the DB and the 208 clusters are shared clinical
vignettes, not duplicate items, so no direct replicate estimate is available."

But OpenRouter records which physical inference backend served each call, in
provider_attempts.response_body -> JSON field "provider".  When condition A and condition B
of the same (item, model) cell were served by DIFFERENT backends, the A/B comparison confounds
the NOTA manipulation with a change of serving stack (quantisation, kernels, batching).
That is a between-condition perturbation that is NOT the manipulation, and it is observable.
"""
import sqlite3, json, collections, math

con = sqlite3.connect('file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/'
                      'data/experiment-31-07-26/experiment.sqlite?mode=ro', uri=True)
con.row_factory = sqlite3.Row

rows = list(con.execute("""
 select lc.id lc, lc.experiment_id eid, lc.question_id qid, lc.model model,
        s.letter_correct lcorr, pa.selected_letter sel, p.response_body rb, p.id aid
 from logical_calls lc
 join parsed_answers pa on pa.logical_call_id = lc.id and pa.parse_status='ok'
 join scores s on s.parsed_answer_id = pa.id
 join provider_attempts p on p.id = pa.provider_attempt_id
 where lc.experiment_id in (6,7,8,9)
"""))
print("scored rows pulled:", len(rows))

def prov(rb):
    if not rb: return None
    i = rb.find('"provider"')
    if i < 0: return None
    try:
        j = json.loads(rb[rb.index('{', max(0, i-2000)) if False else rb.find('{'):])
        return j.get('provider')
    except Exception:
        seg = rb[i:i+80]
        k = seg.find(':');
        return seg[k+1:].strip().strip('",').split('"')[1] if '"' in seg[k+1:] else None

# route: experiments 6/7 = openrouter A/B ; 8/9 = gift A/B
A_EXP = {6: 'or', 8: 'gift'}
B_EXP = {7: 'or', 9: 'gift'}
cellsA, cellsB = {}, {}
for r in rows:
    p = prov(r['rb'])
    key = (r['qid'], r['model'], A_EXP.get(r['eid']) or B_EXP.get(r['eid']))
    rec = dict(correct=r['lcorr'], sel=r['sel'], backend=p)
    if r['eid'] in A_EXP: cellsA[key] = rec
    else: cellsB[key] = rec
print("A cells:", len(cellsA), " B cells:", len(cellsB))
print("route split:", collections.Counter(k[2] for k in cellsA))
print("backends seen:", collections.Counter(v['backend'] for v in list(cellsA.values())+list(cellsB.values())).most_common())

# ------------------------------------------------------------------ pair up
paired = []
for k, a in cellsA.items():
    b = cellsB.get(k)
    if b is None: continue
    paired.append(dict(qid=k[0], model=k[1], route=k[2], A=a['correct'], B=b['correct'],
                       Abk=a['backend'], Bbk=b['backend']))
print("paired cells (DB, before analysis exclusions):", len(paired))

# align with the curated inclusion set
J = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
jj = json.load(open(J))
inc = {(str(r['question_id']), r['model']) for r in jj if r['analysis_include']}
print("curated included keys:", len(inc))
use = [c for c in paired if (str(c['qid']), c['model']) in inc]
print("DB pairs matching curated include set:", len(use))

def tab(rs):
    n11 = sum(1 for r in rs if r['A'] and r['B'])
    n10 = sum(1 for r in rs if r['A'] and not r['B'])
    n01 = sum(1 for r in rs if not r['A'] and r['B'])
    return n11, n10, n01, len(rs)

def binom_cdf(k, n, p):
    return sum(math.comb(n, i)*p**i*(1-p)**(n-i) for i in range(0, k+1))

print()
print("=" * 90)
print("BACKEND EXCHANGEABILITY BETWEEN CONDITIONS")
same = [c for c in use if c['Abk'] == c['Bbk'] and c['Abk']]
diff = [c for c in use if c['Abk'] != c['Bbk'] and c['Abk'] and c['Bbk']]
print(f"  same backend in A and B : {len(same)}")
print(f"  DIFFERENT backend       : {len(diff)}  ({len(diff)/(len(same)+len(diff)):.1%} of pairs)")

for nm, rs in (("ALL", use), ("SAME-backend", same), ("DIFF-backend", diff)):
    a, l, g, n = tab(rs)
    if not n: continue
    D = l + g
    acorr = a + l
    print(f"\n  [{nm}] n={n}  n11={a} lost={l} gained={g}")
    print(f"     A acc={acorr/n:.4f}  B acc={(a+g)/n:.4f}  net drop={(l-g)/n:.4f}")
    print(f"     discordance (l+g)/n            = {D/n:.4f}")
    print(f"     symmetric 'noise' block 2*g/n  = {2*g/n:.4f}   <-- the claim's own instability metric")
    print(f"     implied instability mass S=g   = {g}   (2S/n = {2*g/n:.4f})")
    print(f"     P(lost | A correct)            = {l/acorr:.4f}")

# formal test: is the symmetric-noise share equal across same/diff backend?
a1, l1, g1, n1 = tab(same); a2, l2, g2, n2 = tab(diff)
print()
print("  Test: gain rate (the claim's noise diagnostic) same vs diff backend")
print(f"    same: {g1}/{n1} = {g1/n1:.4f}    diff: {g2}/{n2} = {g2/n2:.4f}")
# Fisher exact, two-sided, on gains vs non-gains
def fisher(a, b, c, d):
    n = a+b+c+d
    def lp(x, y, z, w):
        return (math.lgamma(x+y+1)+math.lgamma(z+w+1)+math.lgamma(x+z+1)+math.lgamma(y+w+1)
                - math.lgamma(n+1)-math.lgamma(x+1)-math.lgamma(y+1)-math.lgamma(z+1)-math.lgamma(w+1))
    obs = lp(a, b, c, d); tot = 0.0
    rt = a+b
    for x in range(0, min(a+b, a+c)+1):
        y = rt-x; z = a+c-x; w = c+d-z
        if y < 0 or z < 0 or w < 0: continue
        v = lp(x, y, z, w)
        if v <= obs + 1e-9: tot += math.exp(v)
    return min(1.0, tot)
print(f"    Fisher exact two-sided p = {fisher(g1, n1-g1, g2, n2-g2):.4g}")
print("  Test: loss rate among A-correct, same vs diff backend")
print(f"    same: {l1}/{a1+l1} = {l1/(a1+l1):.4f}   diff: {l2}/{a2+l2} = {l2/(a2+l2):.4f}")
print(f"    Fisher exact two-sided p = {fisher(l1, a1, l2, a2):.4g}")

print()
print("  Per-model (backend pools differ by model -> check the effect is not a model artefact)")
for m in sorted({c['model'] for c in use}):
    s = [c for c in same if c['model'] == m]; d = [c for c in diff if c['model'] == m]
    if not s or not d:
        print(f"    {m:<28} same={len(s)} diff={len(d)}  (skipped)"); continue
    a1_, l1_, g1_, n1_ = tab(s); a2_, l2_, g2_, n2_ = tab(d)
    print(f"    {m:<28} same n={n1_:>4} 2g/n={2*g1_/n1_:.3f} lossrate={l1_/(a1_+l1_):.3f} | "
          f"diff n={n2_:>4} 2g/n={2*g2_/n2_:.3f} lossrate={l2_/(a2_+l2_):.3f}")

print()
print("  Is the backend MARGINAL distribution the same in A and B? (exchangeability premise)")
ca = collections.Counter(c['Abk'] for c in use); cb = collections.Counter(c['Bbk'] for c in use)
keys = sorted(set(ca) | set(cb), key=lambda k: -(ca[k]+cb[k]))
print(f"    {'backend':<20}{'A':>6}{'B':>6}")
for k in keys[:14]:
    print(f"    {str(k):<20}{ca[k]:>6}{cb[k]:>6}")
# chi-square on the A vs B backend distribution
tot = sum(ca.values()) + sum(cb.values())
chi = 0.0; dfree = 0
for k in keys:
    for obs, nn in ((ca[k], sum(ca.values())), (cb[k], sum(cb.values()))):
        exp = (ca[k]+cb[k]) * nn / tot
        if exp > 0: chi += (obs-exp)**2/exp
    dfree += 1
print(f"    Pearson chi-square = {chi:.1f} on {dfree-1} df  (A vs B backend mix)")

"""Step 3: DB verification of the B manipulation, positional control, power analysis."""
import sqlite3, math, random, re, unicodedata
from collections import defaultdict, Counter
import mech_ref_nota_lib as L

rows = L.cells()
MODELS = sorted({r["model"] for r in rows})
short = {m: m.split("/")[-1] for m in MODELS}
IDX = {"a": 1, "b": 2, "c": 3, "d": 4}

con = sqlite3.connect(L.DB, uri=True)
qs = {}
for ds, key in (("balanced_a_310726", "A"), ("balanced_b_310726", "B")):
    for r in con.execute(
            "select q.question_id,q.option_a,q.option_b,q.option_c,q.option_d,q.correct_letter "
            "from questions q join datasets d on d.id=q.dataset_id where d.name=?", (ds,)):
        qs.setdefault(r[0], {})[key] = r
con.close()


def norm(s):
    s = "".join(c for c in unicodedata.normalize("NFD", (s or "").lower())
                if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", " ", s).strip()


NOTA_RE = re.compile(r"ningun[ao]\s+de\s+(las|los)")
items = {r["question_id"] for r in rows}
print("=== verification of the B manipulation on the", len(items), "analysed items ===")
bad_slot, extra_nota_B, native_nota_A, changed_distr = 0, 0, 0, 0
for qid in items:
    A, B = qs[qid]["A"], qs[qid]["B"]
    cl = A[5]
    if cl != B[5]:
        print("  correct_letter differs!", qid)
    if not NOTA_RE.search(norm(B[IDX[cl]])):
        bad_slot += 1
    for Lt in "abcd":
        if Lt == cl:
            continue
        if norm(A[IDX[Lt]]) != norm(B[IDX[Lt]]):
            changed_distr += 1
        if NOTA_RE.search(norm(B[IDX[Lt]])):
            extra_nota_B += 1
        if NOTA_RE.search(norm(A[IDX[Lt]])):
            native_nota_A += 1
print(f"  B slot at correct_letter is NOT a NOTA string: {bad_slot}")
print(f"  non-target distractor text changed A->B      : {changed_distr}")
print(f"  a SECOND NOTA-like option exists in B        : {extra_nota_B}")
print(f"  native NOTA-like distractor already in A     : {native_nota_A}")
print("  distinct B NOTA strings:",
      Counter(qs[q]["B"][IDX[qs[q]["B"][5]]] for q in items).most_common(3))

# ---- native NOTA in A: does the model pick it when it is WRONG? (false-positive rate)
nat = []
for qid in items:
    A = qs[qid]["A"]
    cl = A[5]
    for Lt in "abcd":
        if Lt != cl and NOTA_RE.search(norm(A[IDX[Lt]])):
            nat.append((qid, Lt))
natmap = dict(nat)
if natmap:
    sel = [(r, natmap[r["question_id"]]) for r in rows if r["question_id"] in natmap]
    hit = sum(1 for r, Lt in sel if r["A_selected"] == Lt)
    print(f"\n  A-condition items carrying a WRONG native NOTA distractor: {len(natmap)} items,"
          f" {len(sel)} cells; model picked that wrong NOTA in {hit} ({hit/len(sel)*100:.1f}%)")

# ---------------- positional control ----------------
print("\n=== positional control: NOTA slot position = correct_letter ===")
aw = [r for r in rows if r["A_correct"] == 0]
print("  correct_letter distribution, all included cells:",
      dict(Counter(r["correct_letter"] for r in rows)))
print("  correct_letter distribution, A-wrong cells    :",
      dict(Counter(r["correct_letter"] for r in aw)))
print("  A_selected distribution among A-wrong cells   :",
      dict(Counter(r["A_selected"] for r in aw)))
print("\n  switch-share landing on NOTA, stratified by NOTA position:")
for pos in "abcd":
    sub = [r for r in aw if r["correct_letter"] == pos]
    sw = [r for r in sub if r["B_selected"] != r["A_selected"]]
    nota = sum(1 for r in sw if r["B_selected"] == r["correct_letter"])
    if sw:
        lo, hi = L.clopper_pearson(nota, len(sw))
        p = L.binom_exact_2sided(nota, len(sw), 1 / 3)
        print(f"    NOTA at '{pos}': A-wrong n={len(sub):3d}  switches={len(sw):3d}  "
              f"NOTA={nota:3d} ({nota/len(sw)*100:5.1f}%) CP95[{lo*100:.0f},{hi*100:.0f}] p={p:.1e}")

print("\n  sensitivity: drop cells flagged excl_nota_position_a / excl_item_defect (raw file)")
raw = L.cells(include_only=False)
for flag in ("excl_nota_position_a", "excl_item_defect"):
    sub = [r for r in raw if r["analysis_include"] and not r[flag] and r["A_correct"] == 0]
    sw = [r for r in sub if r["B_selected"] != r["A_selected"]]
    nota = sum(1 for r in sw if r["B_selected"] == r["correct_letter"])
    print(f"    excluding {flag}: A-wrong n={len(sub)} switches={len(sw)} NOTA={nota}"
          f" ({nota/len(sw)*100:.1f}%)" if sw else "")

# ---------------- cluster bootstrap on the switch-share ----------------
units = defaultdict(list)
for r in rows:
    units[r["cluster"]].append(r)


def sw_share(rs):
    sw = [r for r in rs if r["A_correct"] == 0 and r["B_selected"] != r["A_selected"]]
    if not sw:
        return None
    return sum(1 for r in sw if r["B_selected"] == r["correct_letter"]) / len(sw)


lo, hi, dist = L.cluster_bootstrap(units, sw_share, reps=20000, seed=771)
print(f"\ncluster bootstrap of the pooled NOTA-share-of-switches: 95% CI "
      f"[{lo*100:.1f}, {hi*100:.1f}]  frac reps <= 1/3: {sum(1 for v in dist if v<=1/3)/len(dist):.5f}")


def stay_rate(rs):
    s = [r for r in rs if r["A_correct"] == 0]
    return sum(1 for r in s if r["B_selected"] == r["A_selected"]) / len(s) if s else None


lo2, hi2, d2 = L.cluster_bootstrap(units, stay_rate, reps=20000, seed=772)
k = sum(1 for r in aw if r["B_selected"] == r["A_selected"])
print(f"stay rate (repeat the A distractor) {k}/{len(aw)} = {k/len(aw)*100:.1f}%  "
      f"CP95{[round(v*100,1) for v in L.clopper_pearson(k,len(aw))]}  "
      f"cluster-boot [{lo2*100:.1f},{hi2*100:.1f}]  "
      f"vs uniform-reguess 25%: exact p={L.binom_exact_2sided(k,len(aw),0.25):.2e}")

# ---------------- power of the across-model homogeneity test ----------------
print("\n=== power of the 4x2 chi-square that the claim reads as 'indistinguishable' ===")
ns = [7, 67, 37, 22]
rng = random.Random(999)


def power(rates, reps=20000, alpha=0.05):
    hit = 0
    for _ in range(reps):
        tbl = []
        for n, p in zip(ns, rates):
            k = sum(1 for _ in range(n) if rng.random() < p)
            tbl.append([k, n - k])
        if sum(t[0] for t in tbl) in (0, sum(ns)):
            continue
        if L.chisq_table(tbl)[2] < alpha:
            hit += 1
    return hit / reps


scen = {
    "all equal at .338 (null)": [.338] * 4,
    "observed rates .571/.269/.405/.364": [.571, .269, .405, .364],
    "two at .25 vs two at .55": [.55, .25, .55, .25],
    "two at .20 vs two at .60": [.60, .20, .60, .20],
    "one model .80, rest .25": [.80, .25, .25, .25],
    "gemma .25 vs other three .60": [.60, .25, .60, .60],
}
for lab, r in scen.items():
    print(f"  {lab:<38s} power = {power(r)*100:5.1f}%")

print("\n  CI on the largest observed pairwise difference (gemini 4/7 vs gemma 18/67):")


def newcombe(k1, n1, k2, n2):
    l1, u1 = L.clopper_pearson(k1, n1); l2, u2 = L.clopper_pearson(k2, n2)
    return (l1 - u2, u1 - l2)   # conservative CP-based interval for the difference


d = 4 / 7 - 18 / 67
lo3, hi3 = newcombe(4, 7, 18, 67)
print(f"    diff = {d*100:.1f} pp,  conservative 95% interval [{lo3*100:.0f}, {hi3*100:.0f}] pp"
      f"  -> data compatible with anything from a {abs(lo3)*100:.0f}pp deficit to a {hi3*100:.0f}pp surplus")

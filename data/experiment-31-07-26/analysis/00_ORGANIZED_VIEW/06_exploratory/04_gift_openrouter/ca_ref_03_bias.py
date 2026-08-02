#!/usr/bin/env python
"""Partial-coverage bias + robustness probes for the cross-arm A claim. Stdlib only."""
import json, math, random, collections, sqlite3

AN = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/"
DB = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite"
J = json.load(open(AN + "cross_arm_A.json"))
P = json.load(open(AN + "ca_ref_00_pull.json"))
cells = [c for c in J if c["analysis_include"]]
covered_items = set(c["question_id"] for c in cells)          # 311 analysed
cov319 = set(json.load(open(AN + "gift_coverage.json"))["complete_all_models"])
meta = json.load(open(AN + "dataset_meta.json"))
_ex = meta["exclusions"]
defect = set(_ex.get("administrative_legal_out_of_domain", _ex.get("out_of_domain_law", []))) | set(_ex["adjudicated_key_defect"])

con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
con.row_factory = sqlite3.Row
qmeta = {r["question_id"]: dict(r) for r in con.execute(
    "SELECT question_id, region, year, exam_part, correct_letter FROM questions q "
    "JOIN datasets d ON d.id=q.dataset_id WHERE d.name='balanced_a_310726'")}

orr = {}
for k, v in P["or"].items():
    qid, model = k.split("|")[:2]
    orr[(qid, model)] = v

print("dataset A items %d ; gift complete-on-all-4 %d ; analysed %d ; covered==319-defect: %s"
      % (len(qmeta), len(cov319), len(covered_items), covered_items == (cov319 - defect)))

# ---------- 1. is the covered subset easier? (OR full-arm evidence) ----------
def orstats(items):
    n = k = 0
    for (qid, m), v in orr.items():
        if qid in items:
            n += 1; k += v["letter_correct"]
    return k, n, (100.0 * k / n if n else float('nan'))

allitems = set(qmeta)
unc = allitems - cov319
print("\n--- OpenRouter accuracy, covered vs never-reached (raw, incl. defect items) ---")
k1, n1, p1 = orstats(cov319); k2, n2, p2 = orstats(unc)
print("covered   n_items=%3d cells=%4d OR acc=%.2f%% (%d/%d)" % (len(cov319), n1, p1, k1, n1))
print("uncovered n_items=%3d cells=%4d OR acc=%.2f%% (%d/%d)" % (len(unc), n2, p2, k2, n2))
print("gap = %+.2f pp" % (p1 - p2))
kd1, nd1, pd1 = orstats(cov319 - defect); kd2, nd2, pd2 = orstats(unc - defect)
print("after dropping the 14 defect items: covered %.2f%% (%d/%d) vs uncovered %.2f%% (%d/%d) gap %+.2fpp"
      % (pd1, kd1, nd1, pd2, kd2, nd2, pd1 - pd2))

# two-proportion z (independent items; approximate)
def two_prop_z(k1, n1, k2, n2):
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1.0 / n1 + 1.0 / n2))
    z = (k1 / n1 - k2 / n2) / se
    return z, math.erfc(abs(z) / math.sqrt(2))
z, pv = two_prop_z(k1, n1, k2, n2)
print("two-proportion z = %.3f  p = %.2e  (normal approx, cells treated independent -> anticonservative)" % (z, pv))

# ---------- 2. region mix ----------
print("\n--- region mix (items) ---")
rc = collections.Counter(qmeta[q]["region"] for q in cov319)
ru = collections.Counter(qmeta[q]["region"] for q in unc)
for r in sorted(set(rc) | set(ru)):
    print("  %-22s covered %3d  missing %3d" % (r, rc[r], ru[r]))

# ---------- 3. does GIFT's advantage depend on item difficulty? ----------
# stratify the 311 analysed items by OR difficulty (0-4 of the 4 models correct on OR)
ordiff = collections.defaultdict(int)
for c in cells: ordiff[c["question_id"]] += c["or_correct"]
print("\n--- GIFT-vs-OR discordance by OR item difficulty (analysed 311) ---")
strat = collections.defaultdict(lambda: [0, 0, 0])   # b, c, ncells
for c in cells:
    s = ordiff[c["question_id"]]
    strat[s][2] += 1
    if c["gift_correct"] and not c["or_correct"]: strat[s][0] += 1
    if not c["gift_correct"] and c["or_correct"]: strat[s][1] += 1
for s in sorted(strat):
    b, cc, n = strat[s]
    nit = sum(1 for q in ordiff if ordiff[q] == s)
    print("  OR-correct %d/4  items=%3d cells=%4d  b=%2d c=%2d  net=%+3d  net/cell=%+.4f"
          % (s, nit, n, b, cc, b - cc, (b - cc) / n))

# ---------- 4. leave-one-model-out ----------
print("\n--- leave-one-model-out pooled McNemar ---")
def mc(rows):
    b = sum(1 for r in rows if r["gift_correct"] and not r["or_correct"])
    c = sum(1 for r in rows if not r["gift_correct"] and r["or_correct"])
    n = len(rows)
    g = sum(r["gift_correct"] for r in rows); o = sum(r["or_correct"] for r in rows)
    chi = ((b - c) ** 2) / (b + c) if b + c else float('nan')
    return b, c, n, 100.0 * (g - o) / n, chi, math.erfc(math.sqrt(chi / 2)) if b + c else float('nan')
models = sorted(set(c["model"] for c in cells))
for drop in [None] + models:
    rows = [r for r in cells if r["model"] != drop]
    b, c, n, d, chi, pv = mc(rows)
    print("  drop %-26s n=%4d d=%+5.2fpp b=%2d c=%2d chi2u=%6.3f p=%.4f" % (str(drop), n, d, b, c, chi, pv))

# ---------- 5. heterogeneity across models ----------
# Under a common odds ratio, the 4 discordant splits should be homogeneous.
# Conditional (McNemar) heterogeneity: chi2_total(1df each, uncorrected) minus pooled 1df.
tot = 0.0
for m in models:
    rows = [r for r in cells if r["model"] == m]
    b, c, n, d, chi, pv = mc(rows)
    tot += chi
b, c, n, d, chi_p, pv = mc(cells)
het = tot - chi_p
print("\n--- model heterogeneity ---")
print("sum of 4 per-model uncorrected McNemar chi2 = %.3f ; pooled = %.3f ; heterogeneity chi2(3df) = %.3f p = %.4f"
      % (tot, chi_p, het, __import__("math").exp(0) and None or 0) if False else "")
# chi2 sf for df=3 via regularized upper incomplete gamma, series/CF implemented below
def gammainc_upper_reg(s, x):
    if x < 0: return 1.0
    if x == 0: return 1.0
    if x < s + 1:      # series for lower
        term = 1.0 / s; tot = term; n = 0
        while True:
            n += 1; term *= x / (s + n); tot += term
            if abs(term) < abs(tot) * 1e-16 or n > 10000: break
        low = tot * math.exp(-x + s * math.log(x) - math.lgamma(s))
        return 1.0 - low
    # continued fraction for upper
    tiny = 1e-300
    b0 = x + 1 - s; c0 = 1 / tiny; d0 = 1 / b0; h = d0
    for i in range(1, 10000):
        an = -i * (i - s)
        b0 += 2
        d0 = an * d0 + b0
        if abs(d0) < tiny: d0 = tiny
        c0 = b0 + an / c0
        if abs(c0) < tiny: c0 = tiny
        d0 = 1 / d0
        de = d0 * c0
        h *= de
        if abs(de - 1) < 1e-16: break
    return math.exp(-x + s * math.log(x) - math.lgamma(s)) * h
print("sum per-model chi2u = %.4f ; pooled chi2u = %.4f ; heterogeneity chi2 = %.4f on 3 df, p = %.4f"
      % (tot, chi_p, het, gammainc_upper_reg(1.5, het / 2)))

# ---------- 6. exact cluster sign-flip via DP ----------
byclus = collections.defaultdict(int)
for c in cells: byclus[c["cluster"]] += (c["gift_correct"] - c["or_correct"])
nz = [v for v in byclus.values() if v != 0]
T = sum(byclus.values())
off = sum(abs(v) for v in nz)
size = 2 * off + 1
dist = [0.0] * size; dist[off] = 1.0
for v in nz:
    nd = [0.0] * size
    for i, p in enumerate(dist):
        if p:
            nd[i + v] += p * 0.5
            nd[i - v] += p * 0.5
    dist = nd
pexact = sum(p for i, p in enumerate(dist) if abs(i - off) >= abs(T))
print("\n--- cluster arm-flip randomization, EXACT by DP over %d nonzero clusters ---" % len(nz))
print("T=%d  exact two-sided p = %.6f" % (T, pexact))

# ---------- 7. cluster bootstrap CI on the paired difference ----------
clus_rows = collections.defaultdict(list)
for c in cells: clus_rows[c["cluster"]].append(c)
keys = list(clus_rows)
rng = random.Random(20260731)
B = 20000; diffs = []
for _ in range(B):
    g = o = n = 0
    for _ in range(len(keys)):
        for r in clus_rows[keys[rng.randrange(len(keys))]]:
            n += 1; g += r["gift_correct"]; o += r["or_correct"]
    diffs.append(100.0 * (g - o) / n)
diffs.sort()
print("\ncluster bootstrap (B=%d, resample clusters) diff = %+.3fpp  95%% CI [%+.3f, %+.3f]  P(diff<=0)=%.4f"
      % (B, 100.0 * (sum(r['gift_correct'] for r in cells) - sum(r['or_correct'] for r in cells)) / len(cells),
         diffs[int(.025 * B)], diffs[int(.975 * B)], sum(1 for d in diffs if d <= 0) / B))

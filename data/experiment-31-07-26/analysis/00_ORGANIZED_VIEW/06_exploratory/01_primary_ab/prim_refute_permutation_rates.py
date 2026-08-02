#!/usr/bin/env python3
"""Independent recomputation of the observed A/B rates, deltas, discordant
pairs, and panel shape from paired_clean.json. Stdlib only.

Refutation target: the "permutation" agent's descriptive claim.
"""
import json, collections, os, sys

P = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"

raw = json.load(open(P))
print("RAW rows in file:", len(raw))

# --- what fields actually exist / what values does analysis_include take
keys = collections.Counter()
for r in raw:
    keys[tuple(sorted(r.keys()))] += 1
print("distinct key-signatures:", len(keys))
for k, v in keys.items():
    print("  n=%d  keys=%s" % (v, list(k)))

print("analysis_include value counts:", collections.Counter(repr(r.get("analysis_include")) for r in raw))

# --- exclusion flag crosstab on the FULL file
print("\nexclusion flags on full file:")
print("  excl_item_defect     :", collections.Counter(repr(r.get("excl_item_defect")) for r in raw))
print("  excl_nota_position_a :", collections.Counter(repr(r.get("excl_nota_position_a")) for r in raw))

flagged = collections.Counter()
for r in raw:
    flagged[(bool(r.get("excl_item_defect")), bool(r.get("excl_nota_position_a")), bool(r.get("analysis_include")))] += 1
print("  (defect, nota_a, include) ->", dict(flagged))

# ================= CLEAN SUBSET =================
D = [r for r in raw if r.get("analysis_include") is True]
print("\n=== analysis_include is True ===")
print("cells:", len(D))

items = sorted({r["question_id"] for r in D})
models = sorted({r["model"] for r in D})
clusters = sorted({r["cluster"] for r in D})
print("items:", len(items), "models:", len(models), "clusters:", len(clusters))
print("models:", models)

# --- (question_id, model) uniqueness
pair_ct = collections.Counter((r["question_id"], r["model"]) for r in D)
dups = {k: v for k, v in pair_ct.items() if v > 1}
print("duplicate (question_id, model) keys:", len(dups), (list(dups.items())[:5] if dups else ""))

# --- item -> cluster a function?
i2c = collections.defaultdict(set)
for r in D:
    i2c[r["question_id"]].add(r["cluster"])
multi = {k: v for k, v in i2c.items() if len(v) > 1}
print("items mapping to >1 cluster:", len(multi), (list(multi.items())[:5] if multi else ""))

# --- panel balance: which (item, model) cells are missing
present = set(pair_ct)
missing = [(i, m) for i in items for m in models if (i, m) not in present]
print("missing (item, model) cells vs full 325x4 grid:", len(missing), missing)

# --- are those missing cells present in the RAW file at all?
raw_pairs = collections.Counter((r["question_id"], r["model"]) for r in raw)
print("\nfate of each missing cell in the RAW (unfiltered) file:")
for (i, m) in missing:
    rows = [r for r in raw if r["question_id"] == i and r["model"] == m]
    if not rows:
        print("  %-6s %-26s ABSENT from file entirely (n_raw_rows=0)" % (i, m))
    for r in rows:
        print("  %-6s %-26s present in raw: include=%r defect=%r nota_a=%r "
              "A_correct=%r B_correct=%r A_selected=%r B_selected=%r A_tokens=%r B_tokens=%r"
              % (i, m, r.get("analysis_include"), r.get("excl_item_defect"),
                 r.get("excl_nota_position_a"), r.get("A_correct"), r.get("B_correct"),
                 r.get("A_selected"), r.get("B_selected"), r.get("A_tokens"), r.get("B_tokens")))

# --- how many raw rows per model (unfiltered)
print("\nraw rows per model (unfiltered):", dict(collections.Counter(r["model"] for r in raw)))
print("clean cells per model:", dict(collections.Counter(r["model"] for r in D)))
print("raw distinct items:", len({r["question_id"] for r in raw}))

# --- sanity: are A_correct/B_correct strictly 0/1?
print("A_correct values:", collections.Counter(repr(r["A_correct"]) for r in D))
print("B_correct values:", collections.Counter(repr(r["B_correct"]) for r in D))

# ================= RATES =================
BRIEF = {  # model-key -> (A_pct, B_pct, delta_pp) as printed in the claim
    "google/gemini-3.6-flash":   (97.85, 89.54, -8.31, 325),
    "z-ai/glm-5.2":              (93.21, 75.00, -18.21, 324),
    "qwen/qwen3.6-35b-a3b":      (88.62, 72.62, -16.00, 325),
    "google/gemma-4-26b-a4b-it": (79.38, 59.69, -19.69, 325),
}

print("\n=== per-model unweighted proportions over cells ===")
print("%-26s %5s %6s %8s %8s %9s   %s" % ("model", "n", "A_num", "A%", "B%", "delta_pp", "check-vs-claim"))
ok_rates = True
rows_out = {}
for m in models:
    S = [r for r in D if r["model"] == m]
    n = len(S)
    a = sum(int(r["A_correct"]) for r in S)
    b = sum(int(r["B_correct"]) for r in S)
    pa, pb = 100.0 * a / n, 100.0 * b / n
    d = pb - pa
    rows_out[m] = (n, a, b, pa, pb, d)
    ca, cb, cd, cn = BRIEF[m]
    good = (abs(pa - ca) < 0.005 and abs(pb - cb) < 0.005 and abs(d - cd) < 0.005 and n == cn)
    ok_rates &= good
    print("%-26s %5d %6d %8.4f %8.4f %9.4f   %s" % (m, n, a, pa, pb, d, "MATCH" if good else "MISMATCH"))

# pooled
n = len(D)
a = sum(int(r["A_correct"]) for r in D)
b = sum(int(r["B_correct"]) for r in D)
print("POOLED n=%d A=%d (%.4f%%) B=%d (%.4f%%) delta=%.4fpp" % (n, a, 100.0*a/n, b, 100.0*b/n, 100.0*(b-a)/n))

# pooled recomputed EXCLUDING the unbalanced cell, i.e. complete-case 324 items x 4
complete_items = [i for i in items if all((i, m) in present for m in models)]
Dc = [r for r in D if r["question_id"] in set(complete_items)]
nc = len(Dc)
ac = sum(int(r["A_correct"]) for r in Dc); bc = sum(int(r["B_correct"]) for r in Dc)
print("POOLED complete-case (items present in all 4 models): items=%d cells=%d A=%.4f%% B=%.4f%% delta=%.4fpp"
      % (len(complete_items), nc, 100.0*ac/nc, 100.0*bc/nc, 100.0*(bc-ac)/nc))

# rounding to the 1-dp figures in the prose brief
PROSE = {"google/gemini-3.6-flash": (97.8, 89.5, -8.3),
         "z-ai/glm-5.2": (93.2, 75.0, -18.2),
         "qwen/qwen3.6-35b-a3b": (88.6, 72.6, -16.0),
         "google/gemma-4-26b-a4b-it": (79.4, 59.7, -19.7)}
print("\n=== rounding to prose brief (1 dp) ===")
for m in models:
    n, a, b, pa, pb, d = rows_out[m]
    pra, prb, prd = PROSE[m]
    print("%-26s A %.1f vs %.1f | B %.1f vs %.1f | d %.1f vs %.1f  %s"
          % (m, round(pa,1), pra, round(pb,1), prb, round(d,1), prd,
             "OK" if (round(pa,1)==pra and round(pb,1)==prb and round(d,1)==prd) else "OFF"))

# ================= DISCORDANT PAIRS =================
CLAIM_BC = {"google/gemini-3.6-flash": (31, 4),
            "google/gemma-4-26b-a4b-it": (82, 18),
            "qwen/qwen3.6-35b-a3b": (67, 15),
            "z-ai/glm-5.2": (67, 8)}
print("\n=== 2x2 paired tables (a=both right, b=A right/B wrong, c=A wrong/B right, d=both wrong) ===")
print("%-26s %5s %5s %5s %5s %5s   %s" % ("model", "a", "b", "c", "d", "n", "b/c vs claim"))
ok_bc = True
tb = tc = 0
for m in models:
    S = [r for r in D if r["model"] == m]
    aa = sum(1 for r in S if r["A_correct"] == 1 and r["B_correct"] == 1)
    bb = sum(1 for r in S if r["A_correct"] == 1 and r["B_correct"] == 0)
    cc = sum(1 for r in S if r["A_correct"] == 0 and r["B_correct"] == 1)
    dd = sum(1 for r in S if r["A_correct"] == 0 and r["B_correct"] == 0)
    tb += bb; tc += cc
    cb_, cc_ = CLAIM_BC[m]
    good = (bb == cb_ and cc == cc_)
    ok_bc &= good
    print("%-26s %5d %5d %5d %5d %5d   %s (claim %d/%d)" % (m, aa, bb, cc, dd, aa+bb+cc+dd,
                                                            "MATCH" if good else "MISMATCH", cb_, cc_))
print("POOLED b=%d c=%d  (claim 247/45) %s" % (tb, tc, "MATCH" if (tb, tc) == (247, 45) else "MISMATCH"))

# net check: b - c should equal A_num - B_num per model
print("\nnet consistency (b-c == A_correct_total - B_correct_total):")
for m in models:
    S = [r for r in D if r["model"] == m]
    bb = sum(1 for r in S if r["A_correct"] == 1 and r["B_correct"] == 0)
    cc = sum(1 for r in S if r["A_correct"] == 0 and r["B_correct"] == 1)
    da = sum(int(r["A_correct"]) for r in S) - sum(int(r["B_correct"]) for r in S)
    print("  %-26s b-c=%d  netA-B=%d  %s" % (m, bb-cc, da, "ok" if bb-cc == da else "BAD"))

# ================= CLUSTER STRUCTURE =================
print("\n=== cluster structure ===")
csize = collections.Counter()
for i in items:
    csize[list(i2c[i])[0]] += 1
print("clusters:", len(csize), "items/cluster min=%d max=%d mean=%.2f" %
      (min(csize.values()), max(csize.values()), sum(csize.values())/len(csize)))
sing = sum(1 for v in csize.values() if v == 1)
print("singleton clusters:", sing)

print("\nOVERALL: rates_match=%s discordant_match=%s" % (ok_rates, ok_bc))

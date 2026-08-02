"""Does the 83%-completion prefix undermine the 'flips are directional' claim?

Three probes:
  A. Is the null's own denominator (the 11:1 correct:wrong base rate) an
     artifact of the easy covered prefix?
  B. Is GIFT's OWN coverage correlated with GIFT's OWN accuracy? (RUN_STATUS
     only measures the OR-side skew; the GIFT-side skew is the one that would
     inflate b relative to c.)
  C. Difficulty-stratified reweighting of the discordant counts to the full
     dataset's difficulty mix.
"""
import json, math, random
from collections import defaultdict

BASE = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/"
MODELS = ["google/gemma-4-26b-a4b-it", "z-ai/glm-5.2",
          "qwen/qwen3.6-35b-a3b", "google/gemini-3.6-flash"]
SHORT = {"google/gemma-4-26b-a4b-it": "gemma-4-26b", "z-ai/glm-5.2": "glm-5.2",
         "qwen/qwen3.6-35b-a3b": "qwen3.6-35b", "google/gemini-3.6-flash": "gemini-3.6"}

paired = [r for r in json.load(open(BASE + "cross_arm_A.json")) if r["analysis_include"]]
allcells = json.load(open(BASE + "ca_ref_wb_00_cells.json"))
meta = json.load(open(BASE + "dataset_meta.json"))
cov = json.load(open(BASE + "gift_coverage.json"))
covered_items = set(cov["complete_all_models"])

paired_items = {r["question_id"] for r in paired}
defect = covered_items - paired_items
print("covered(all-4)=%d  paired-analysed=%d  dropped-as-defect=%d" %
      (len(covered_items), len(paired_items), len(defect)))

# defective item ids across the whole dataset, so the 'missing' side is
# filtered the same way
excl_ids = set()
for k, v in meta.items():
    if isinstance(v, list) and v and isinstance(v[0], str):
        pass
print("dataset_meta keys:", list(meta.keys()))

orcells = [r for r in allcells if r["exp"] == "expA_or_310726"]
giftcells = [r for r in allcells if r["exp"] == "expA_gift_310726"]

# reconstruct the defect exclusion list from the covered side, then apply the
# stated rule (14 items dropped from both conditions) to the whole dataset.
DEFECT14 = None
for k, v in meta.items():
    if "defect" in k.lower() or "drop" in k.lower() or "excl" in k.lower():
        print("  meta[%s] = %s" % (k, str(v)[:300]))

out = {}

# ------------------------------------------------------- A. base-rate artifact
print("\n[A] IS THE NULL'S 11:1 BASE RATE AN ARTIFACT OF THE EASY PREFIX?")
or_by_item = defaultdict(dict)
for r in orcells:
    or_by_item[r["question_id"]][r["model"]] = r["correct"]

cov_ok = cov_n = mis_ok = mis_n = 0
for q, mm in or_by_item.items():
    for m, ok in mm.items():
        if q in covered_items:
            cov_n += 1; cov_ok += ok
        else:
            mis_n += 1; mis_ok += ok
print("  OR on GIFT-covered items   : %4d/%4d = %.1f%%  -> ok:wrong = %.2f:1" %
      (cov_ok, cov_n, 100 * cov_ok / cov_n, cov_ok / (cov_n - cov_ok)))
print("  OR on NEVER-covered items  : %4d/%4d = %.1f%%  -> ok:wrong = %.2f:1" %
      (mis_ok, mis_n, 100 * mis_ok / mis_n, mis_ok / (mis_n - mis_ok)))
print("  OR full dataset            : %4d/%4d = %.1f%%  -> ok:wrong = %.2f:1" %
      (cov_ok + mis_ok, cov_n + mis_n, 100 * (cov_ok + mis_ok) / (cov_n + mis_n),
       (cov_ok + mis_ok) / (cov_n + mis_n - cov_ok - mis_ok)))
print("  => the claim's headline number 11.08 IS the covered-subset base rate.")
print("     On the full dataset the same null would predict only ~%.1fx, and on"
      % ((cov_ok + mis_ok) / (cov_n + mis_n - cov_ok - mis_ok)))
print("     the unreached portion only ~%.1fx. The '11x' is a statement about"
      % (mis_ok / (mis_n - mis_ok)))
print("     which items GIFT happened to reach, not about retrieval.")
out["base_rate"] = dict(covered=cov_ok / cov_n, missing=mis_ok / mis_n,
                        full=(cov_ok + mis_ok) / (cov_n + mis_n),
                        null_ratio_covered=cov_ok / (cov_n - cov_ok),
                        null_ratio_missing=mis_ok / (mis_n - mis_ok),
                        null_ratio_full=(cov_ok + mis_ok) / (cov_n + mis_n - cov_ok - mis_ok))

# --------------------------- B. GIFT-side coverage <-> GIFT-accuracy correlation
print("\n[B] IS GIFT'S OWN COVERAGE CORRELATED WITH GIFT'S OWN ACCURACY?")
print("    GIFT scored %d cells over %d items, but only %d items are complete on"
      % (len(giftcells), len({r['question_id'] for r in giftcells}), len(covered_items)))
print("    all four models. The cells on PARTIALLY covered items are GIFT's own")
print("    out-of-sample: same arm, same models, items the analysis never uses.")
gi = defaultdict(list)
for r in giftcells:
    gi[r["question_id"]].append(r)
full_ok = full_n = part_ok = part_n = 0
part_items = set()
for q, rs in gi.items():
    for r in rs:
        if q in covered_items:
            full_n += 1; full_ok += r["correct"]
        else:
            part_n += 1; part_ok += r["correct"]; part_items.add(q)
print("  GIFT on complete(all-4) items : %4d/%4d = %.1f%%" % (full_ok, full_n, 100 * full_ok / full_n))
print("  GIFT on partially-covered     : %4d/%4d = %.1f%%  (%d items)" %
      (part_ok, part_n, 100 * part_ok / part_n, len(part_items)))
# paired OR comparison on exactly those partial cells
orlook = {(r["question_id"], r["model"]): r["correct"] for r in orcells}
pa = pb = pc = pd = 0
for q in part_items:
    for r in gi[q]:
        o = orlook.get((q, r["model"]))
        if o is None:
            continue
        g = r["correct"]
        if g and o: pa += 1
        elif g and not o: pb += 1
        elif o: pc += 1
        else: pd += 1
pn = pa + pb + pc + pd
if pn:
    print("  Paired on those partial cells : n=%d  GIFT=%.1f%% OR=%.1f%% delta=%+.1fpp"
          % (pn, 100 * (pa + pb) / pn, 100 * (pa + pc) / pn, 100 * (pb - pc) / pn))
    print("                                  a=%d b(rec)=%d c(brk)=%d d=%d  b/c=%s"
          % (pa, pb, pc, pd, "%.2f" % (pb / pc) if pc else "inf"))
out["gift_side"] = dict(full_acc=full_ok / full_n, part_acc=part_ok / part_n,
                        part_items=len(part_items),
                        partial_table=dict(a=pa, b=pb, c=pc, d=pd))

# ------------------------------------ C. difficulty-stratified reweighting
print("\n[C] REWEIGHT THE DISCORDANT COUNTS TO THE FULL-DATASET DIFFICULTY MIX")
print("    Stratum = how many of the 4 models OpenRouter got right on that item")
print("    (0-4). Computed from OR alone, so it is available for every item.")
diff = {q: sum(mm.values()) for q, mm in or_by_item.items()}
# full-dataset stratum weights, restricted to items that pass the same defect
# filter where knowable: use all non-covered items + the analysed covered items
analysed = paired_items
full_pool = analysed | (set(or_by_item) - covered_items)
wfull = defaultdict(int)
for q in full_pool:
    wfull[diff[q]] += 1
wcov = defaultdict(int)
for q in analysed:
    wcov[diff[q]] += 1
print("  stratum  covered_items  full_items  cov_share  full_share")
for s in range(5):
    print("     %d       %4d          %4d       %.3f      %.3f" %
          (s, wcov[s], wfull[s], wcov[s] / len(analysed), wfull[s] / len(full_pool)))

strat = defaultdict(lambda: [0, 0, 0, 0])
for r in paired:
    s = diff[r["question_id"]]
    g, o = r["gift_correct"], r["or_correct"]
    t = strat[s]
    if g and o: t[0] += 1
    elif g: t[1] += 1
    elif o: t[2] += 1
    else: t[3] += 1
print("\n  stratum   a    b(rec) c(brk)  d   rec_rate   brk_rate")
for s in range(5):
    a_, b_, c_, d_ = strat[s]
    rr = b_ / (b_ + d_) if (b_ + d_) else float("nan")
    br = c_ / (a_ + c_) if (a_ + c_) else float("nan")
    print("     %d    %4d   %4d   %4d %4d   %s   %s" %
          (s, a_, b_, c_, d_,
           "%.3f" % rr if rr == rr else "  -  ",
           "%.3f" % br if br == br else "  -  "))

# transport: within-stratum recovery/breakage rates applied to the full mix
tb = tc = 0.0
for s in range(5):
    a_, b_, c_, d_ = strat[s]
    if not wcov[s]:
        continue
    scale = (wfull[s] / len(full_pool)) / (wcov[s] / len(analysed))
    tb += b_ * scale
    tc += c_ * scale
print("\n  Reweighted to the full-dataset difficulty mix:")
print("    b_hat=%.1f  c_hat=%.1f  b/c=%.2f  (observed on covered: 46/24=1.92)"
      % (tb, tc, tb / tc))
print("    delta_hat = %+.2fpp  (observed on covered: +1.77pp)"
      % (100 * (tb - tc) / (len(full_pool) * 4)))
out["reweighted"] = dict(b_hat=tb, c_hat=tc, ratio=tb / tc,
                         delta_hat=(tb - tc) / (len(full_pool) * 4))

json.dump(out, open(BASE + "ca_ref_wb_02_coverage.json", "w"), indent=1)
print("\nwritten ca_ref_wb_02_coverage.json")

"""
INDEPENDENT recomputation of the per-model-contrasts claim.
Stdlib only. No numpy/scipy/pandas.

Claim under test:
  3 of 6 pairwise contrasts survive Holm at alpha=0.05, all three gemini vs other.
  gemini-glm  = -9.90pp, CI [-15.03,-4.98], p_boot=0.0002, Holm=0.0012
  gemini-gemma= -11.38pp, CI [-18.24,-4.13], p_boot=0.0028, Holm=0.0140
  gemini-qwen = -7.69pp, CI [-12.92,-2.15], p_boot=0.0091, Holm=0.0364
Method claimed: cluster bootstrap B=20000 over 208 clusters, Davison-Hinkley
CI-inversion two-sided p, Holm-Bonferroni with monotonicity.
"""
import json, math, random, collections, sys

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
raw = json.load(open(PATH))
rows = [r for r in raw if r.get("analysis_include") is True]

MODELS = ["google/gemini-3.6-flash", "z-ai/glm-5.2",
          "qwen/qwen3.6-35b-a3b", "google/gemma-4-26b-a4b-it"]
SHORT = {"google/gemini-3.6-flash": "gemini", "z-ai/glm-5.2": "glm",
         "qwen/qwen3.6-35b-a3b": "qwen", "google/gemma-4-26b-a4b-it": "gemma"}
MI = {m: i for i, m in enumerate(MODELS)}

# ---------- 0. shape audit ----------
print("=" * 100)
print("0. SHAPE AUDIT")
print("=" * 100)
print(f"total rows in file      : {len(raw)}")
print(f"analysis_include==True  : {len(rows)}")
print(f"distinct question_id    : {len(set(r['question_id'] for r in rows))}")
print(f"distinct cluster        : {len(set(r['cluster'] for r in rows))}")
print(f"distinct model          : {sorted(set(r['model'] for r in rows))}")
percell = collections.Counter(r["model"] for r in rows)
for m in MODELS:
    print(f"   n cells {SHORT[m]:7s} = {percell[m]}")
# which items are not complete across 4 models
bym = collections.defaultdict(set)
for r in rows:
    bym[r["question_id"]].add(r["model"])
incomplete = {q: sorted(SHORT[m] for m in MODELS if m not in v) for q, v in bym.items() if len(v) != 4}
print(f"items NOT observed on all 4 models: {len(incomplete)}  -> {incomplete}")

# ---------- 1. observed marginals ----------
print()
print("=" * 100)
print("1. OBSERVED MARGINALS (recomputed from scratch)")
print("=" * 100)
n = [0] * 4; sa = [0] * 4; sb = [0] * 4
for r in rows:
    i = MI[r["model"]]; n[i] += 1; sa[i] += r["A_correct"]; sb[i] += r["B_correct"]
A = [sa[i] / n[i] for i in range(4)]
Bp = [sb[i] / n[i] for i in range(4)]
# DROP = A - B  (positive = model got worse). Claim's sign convention:
# contrast gemini-glm = -9.90 == drop_gemini - drop_glm, so drop = A - B.
DROP = [100.0 * (sa[i] - sb[i]) / n[i] for i in range(4)]
for i, m in enumerate(MODELS):
    print(f"{SHORT[m]:7s} n={n[i]:4d}  A={100*A[i]:6.2f}%  B={100*Bp[i]:6.2f}%  drop={DROP[i]:+6.2f}pp")

PAIRS = [(0, 1), (0, 3), (0, 2), (2, 3), (1, 2), (1, 3)]
NAMES = {p: f"{SHORT[MODELS[p[0]]]} - {SHORT[MODELS[p[1]]]}" for p in PAIRS}
OBS = {p: DROP[p[0]] - DROP[p[1]] for p in PAIRS}
print()
print("observed contrasts (drop_i - drop_j, negative = i loses LESS):")
for p in PAIRS:
    print(f"   {NAMES[p]:16s} = {OBS[p]:+7.4f} pp")

# ---------- 2. cluster bootstrap ----------
# collapse each cluster to a 12-vector: (n, sumA, sumB) per model
tmp = collections.defaultdict(lambda: [0] * 12)
for r in rows:
    i = MI[r["model"]]; v = tmp[r["cluster"]]
    v[3 * i] += 1; v[3 * i + 1] += r["A_correct"]; v[3 * i + 2] += r["B_correct"]
CL = [tuple(v) for v in tmp.values()]
K = len(CL)


def drops(acc):
    out = []
    for i in range(4):
        d = acc[3 * i]
        out.append(100.0 * (acc[3 * i + 1] - acc[3 * i + 2]) / d if d else None)
    return out


def pctl(sv, q):
    m = len(sv); x = q / 100.0 * (m - 1)
    lo = int(math.floor(x)); hi = min(lo + 1, m - 1)
    return sv[lo] + (x - lo) * (sv[hi] - sv[lo])


def holm(praw_by_key, keys):
    """Holm-Bonferroni with monotonicity enforcement."""
    order = sorted(keys, key=lambda k: praw_by_key[k])
    m = len(keys); out = {}; run = 0.0
    for r_, k in enumerate(order):
        run = max(run, (m - r_) * praw_by_key[k])
        out[k] = min(1.0, run)
    return out


def run_boot(Bn, seed):
    rnd = random.Random(seed)
    rep = {p: [] for p in PAIRS}
    degenerate = 0
    for _ in range(Bn):
        acc = [0] * 12
        for c in rnd.choices(CL, k=K):
            for j in range(12):
                acc[j] += c[j]
        d = drops(acc)
        if any(x is None for x in d):
            degenerate += 1
            continue
        for p in PAIRS:
            rep[p].append(d[p[0]] - d[p[1]])
    res = {}
    for p in PAIRS:
        v = rep[p]; sv = sorted(v); Beff = len(v)
        le = sum(1 for x in v if x <= 0); ge = sum(1 for x in v if x >= 0)
        pdh = min(1.0, 2.0 * min((le + 1) / (Beff + 1), (ge + 1) / (Beff + 1)))
        mu = sum(v) / Beff
        se = math.sqrt(sum((x - mu) ** 2 for x in v) / (Beff - 1))
        res[p] = {"lo": pctl(sv, 2.5), "hi": pctl(sv, 97.5), "p": pdh,
                  "se": se, "bias": mu - OBS[p], "n_le": le, "n_ge": ge, "Beff": Beff}
    return res, degenerate


print()
print("=" * 100)
print("2. CLUSTER BOOTSTRAP  B=20000, K=%d clusters, seed 424242 (my own seed)" % K)
print("=" * 100)
R, deg = run_boot(20000, 424242)
H = holm({p: R[p]["p"] for p in PAIRS}, PAIRS)
print(f"degenerate replicates dropped: {deg}")
print(f"{'contrast':>16s} {'obs':>8s} {'boot SE':>8s} {'95% CI':>22s} {'p_boot':>9s} {'p_Holm':>8s}  {'#<=0':>6s} {'#>=0':>6s}")
for p in sorted(PAIRS, key=lambda q: R[q]["p"]):
    r = R[p]
    print(f"{NAMES[p]:>16s} {OBS[p]:+8.3f} {r['se']:8.3f}  [{r['lo']:+7.3f},{r['hi']:+7.3f}] "
          f"{r['p']:9.5f} {H[p]:8.4f}  {r['n_le']:6d} {r['n_ge']:6d}")
surv = [p for p in PAIRS if H[p] < 0.05]
print(f"\n-> survive Holm at 0.05: {len(surv)}  {[NAMES[p] for p in surv]}")

# ---------- 3. seed stability of the Holm decision ----------
print()
print("=" * 100)
print("3. SEED STABILITY  (10 independent bootstraps, B=20000 each)")
print("=" * 100)
print(f"{'seed':>8s} " + " ".join(f"{NAMES[p]:>16s}" for p in PAIRS) + "   nsurv")
cnt_surv = collections.Counter()
hold = collections.defaultdict(list)
for s in range(101, 111):
    Rs, _ = run_boot(20000, s)
    Hs = holm({p: Rs[p]["p"] for p in PAIRS}, PAIRS)
    ns = sum(1 for p in PAIRS if Hs[p] < 0.05)
    cnt_surv[ns] += 1
    for p in PAIRS:
        hold[p].append(Hs[p])
    print(f"{s:>8d} " + " ".join(f"{Hs[p]:16.4f}" for p in PAIRS) + f"   {ns:5d}")
print(f"\nnumber-of-survivors distribution over 10 seeds: {dict(cnt_surv)}")
for p in PAIRS:
    v = sorted(hold[p])
    print(f"   {NAMES[p]:16s} Holm across seeds: min={v[0]:.4f} max={v[-1]:.4f}")

# ---------- 4. high-precision bootstrap ----------
print()
print("=" * 100)
print("4. HIGH-PRECISION BOOTSTRAP  B=200000, seed 7")
print("=" * 100)
Rh, _ = run_boot(200000, 7)
Hh = holm({p: Rh[p]["p"] for p in PAIRS}, PAIRS)
for p in sorted(PAIRS, key=lambda q: Rh[q]["p"]):
    r = Rh[p]
    print(f"{NAMES[p]:>16s} {OBS[p]:+8.3f}  CI [{r['lo']:+7.3f},{r['hi']:+7.3f}]  "
          f"p={r['p']:.6f}  Holm={Hh[p]:.5f}  bias={r['bias']:+.4f}")
print(f"-> survive Holm at 0.05: {sum(1 for p in PAIRS if Hh[p] < 0.05)}")

json.dump({"n": n, "A": A, "B": Bp, "drop": DROP,
           "boot20000_seed424242": {NAMES[p]: {**R[p], "holm": H[p], "obs": OBS[p]} for p in PAIRS},
           "boot200000_seed7": {NAMES[p]: {**Rh[p], "holm": Hh[p], "obs": OBS[p]} for p in PAIRS}},
          open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/prim_refute_model_contrasts.json", "w"), indent=1)
print("\nwrote prim_refute_model_contrasts.json")

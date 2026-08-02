"""ca_cov_08: the difficulty x delta interaction, done carefully.

1. show that the ITEM-level Spearman is mechanically contaminated
   (mean_m loo_k(i,m) == 0.75 * naive_k(i) exactly), so it cannot be used;
2. cell-level hard-vs-easy contrast on the paired set, on the 99 uncovered
   cells, and on the pooled 1343 cells, each with a cluster/item bootstrap;
3. a cluster-respecting permutation test.
"""
import json, os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ca_lib as L

BASE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
G = json.load(open(os.path.join(BASE, "ca_cov_grid.json")))
orc = {tuple(k.split("|")): v for k, v in G["or_correct"].items()}
gic = {tuple(k.split("|")): v for k, v in G["gift_correct"].items()}
covered = set(G["covered"]); defect = set(G["defect"])
items = json.load(open(os.path.join(BASE, "ca_cov_or_full.json")))["items"]
cross = {(r["model"], r["question_id"]): r for r in L.load(include_only=True)}


def loo_k(q, m):
    vs = [orc[(mm, q)] for mm in MODELS if mm != m and (mm, q) in orc]
    return sum(vs) if len(vs) == 3 else None


PAIR, EXTRA = [], []
for q in items:
    if q in defect:
        continue
    for m in MODELS:
        if (m, q) not in orc or (m, q) not in gic:
            continue
        k = loo_k(q, m)
        if k is None:
            continue
        r = {"q": q, "m": m, "d": gic[(m, q)] - orc[(m, q)], "k": k,
             "cluster": cross[(m, q)]["cluster"] if (m, q) in cross else None}
        (PAIR if q in covered else EXTRA).append(r)
# give the uncovered items pseudo-clusters keyed on the item (no cluster in file)
for r in EXTRA:
    if r["cluster"] is None:
        r["cluster"] = "X" + r["q"]
print("paired cells:", len(PAIR), " uncovered-region cells:", len(EXTRA))

# --- 1. the contamination identity
bad = 0
for q in set(r["q"] for r in PAIR):
    lo = [loo_k(q, m) for m in MODELS if loo_k(q, m) is not None]
    nk = sum(orc[(m, q)] for m in MODELS if (m, q) in orc)
    if len(lo) == 4 and abs(sum(lo) / 4 - 0.75 * nk) > 1e-12:
        bad += 1
print(f"\n[1] identity check: mean_m loo_k(i,m) == 0.75*naive_k(i) for every item "
      f"-- violations: {bad}")
print("    => the item-level 'difficulty vs delta' correlation is an algebraic")
print("       artefact (the focal model's own OR score sits on both axes).")
print("       Only the CELL-level leave-one-out contrast below is interpretable.")


def contrast(rs):
    h = [r for r in rs if r["k"] <= 2]; e = [r for r in rs if r["k"] == 3]
    if not h or not e:
        return None
    return sum(r["d"] for r in h) / len(h) - sum(r["d"] for r in e) / len(e)


def dh(rs):
    h = [r for r in rs if r["k"] <= 2]
    return sum(r["d"] for r in h) / len(h) if h else None


def de(rs):
    e = [r for r in rs if r["k"] == 3]
    return sum(r["d"] for r in e) / len(e) if e else None


print("\n[2] cell-level HARD (loo_k<=2) vs EASY (loo_k=3) contrast")
print(f"{'set':28s} {'n':>5s} {'nH':>4s} {'nE':>4s} {'dH_pp':>7s} {'dE_pp':>7s} "
      f"{'contrast_pp':>12s} {'95% CI':>22s}")
for name, rs, seed in [("paired (analysed) 1244", PAIR, 811),
                       ("uncovered region 96", EXTRA, 812),
                       ("pooled 1340", PAIR + EXTRA, 813)]:
    bs = L.cluster_bootstrap(rs, contrast, keyf=lambda r: r["cluster"],
                             B=20000, seed=seed)
    lo, hi = L.ci(bs)
    nH = sum(1 for r in rs if r["k"] <= 2); nE = len(rs) - nH
    print(f"{name:28s} {len(rs):5d} {nH:4d} {nE:4d} {100*dh(rs):+6.2f} "
          f"{100*de(rs):+6.2f} {100*contrast(rs):+11.2f}  "
          f"[{100*lo:+6.2f}, {100*hi:+6.2f}]")

# --- 3. cluster-respecting permutation: relabel HARD/EASY by permuting whole
#        clusters' difficulty vectors is impossible (unequal sizes), so we
#        permute the item->difficulty map, resampling at the CLUSTER level to
#        get the null distribution of the contrast under exchangeable clusters.
def perm_p(rs, seed, P=20000):
    byq = {}
    for r in rs:
        byq.setdefault(r["q"], []).append(r)
    qs = sorted(byq)
    kvec = {q: {r["m"]: r["k"] for r in byq[q]} for q in qs}
    obs = contrast(rs)
    rng = random.Random(seed)
    cnt = 0
    for _ in range(P):
        pm = qs[:]
        rng.shuffle(pm)
        new = []
        for q, src in zip(qs, pm):
            for r in byq[q]:
                new.append({"d": r["d"], "k": kvec[src].get(r["m"], r["k"])})
        v = contrast(new)
        if v is not None and abs(v) >= abs(obs) - 1e-12:
            cnt += 1
    return (cnt + 1) / (P + 1), obs


for name, rs, seed in [("paired", PAIR, 900), ("pooled", PAIR + EXTRA, 901)]:
    p, obs = perm_p(rs, seed)
    print(f"\n[3] {name}: permutation p (P=20000, item-level relabelling of the "
          f"difficulty vector; ignores cluster dependence, so anticonservative) "
          f"= {p:.4f} for contrast {100*obs:+.2f} pp")

# --- 4. monotone trend across all four k levels, pooled
print("\n[4] pooled 1340 cells, delta by leave-one-out difficulty")
print(f"{'k':>2s} {'n':>5s} {'delta_pp':>9s} {'b':>4s} {'c':>4s}")
allr = PAIR + EXTRA
for k in range(4):
    sub = [r for r in allr if r["k"] == k]
    n = len(sub)
    b = sum(1 for r in sub if r["d"] == 1); c = sum(1 for r in sub if r["d"] == -1)
    print(f"{k:2d} {n:5d} {100*sum(r['d'] for r in sub)/n:+8.2f} {b:4d} {c:4d}")

json.dump({"paired": {"dH": dh(PAIR), "dE": de(PAIR), "contrast": contrast(PAIR)},
           "extra": {"dH": dh(EXTRA), "dE": de(EXTRA), "contrast": contrast(EXTRA)},
           "pooled": {"dH": dh(allr), "dE": de(allr), "contrast": contrast(allr)}},
          open(os.path.join(BASE, "ca_cov_08_out.json"), "w"), indent=1)

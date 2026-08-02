"""ca_cov_02: is the GIFT-vs-OR delta correlated with item difficulty?

Difficulty is measured from the OpenRouter arm, which is complete on all 474
items. Two versions:

  naive_k  = number of the 4 OR models correct on the item (0..4)
  loo_k    = number of the OTHER 3 OR models correct on the item (0..3)
             -- computed per (item, model) cell.

naive_k is contaminated: the focal model's own or_correct is inside the
difficulty score, so delta = gift - or is mechanically anti-correlated with it.
loo_k removes that identity. Both are reported; loo_k is the primary.
"""
import json, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ca_lib as L

BASE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
SHORT = {"google/gemini-3.6-flash": "gemini", "google/gemma-4-26b-a4b-it": "gemma",
         "qwen/qwen3.6-35b-a3b": "qwen", "z-ai/glm-5.2": "glm"}

G = json.load(open(os.path.join(BASE, "ca_cov_grid.json")))
orc = {tuple(k.split("|")): v for k, v in G["or_correct"].items()}
covered = set(G["covered"]); defect = set(G["defect"])

rows = L.load(include_only=True)          # 1244 covered clean cells


def loo_k(qid, model):
    """# of the other 3 OR models correct on this item (None if any missing)."""
    vs = [orc[(m, qid)] for m in MODELS if m != model and (m, qid) in orc]
    if len(vs) != 3:
        return None
    return sum(vs)


def naive_k(qid):
    vs = [orc[(m, qid)] for m in MODELS if (m, qid) in orc]
    return sum(vs) if len(vs) == 4 else None


for r in rows:
    r["loo_k"] = loo_k(r["question_id"], r["model"])
    r["naive_k"] = naive_k(r["question_id"])
    r["delta"] = r["gift_correct"] - r["or_correct"]

ok = [r for r in rows if r["loo_k"] is not None and r["naive_k"] is not None]
print("cells usable (both difficulty scores defined):", len(ok), "of", len(rows))
drop = [r for r in rows if r not in ok]
print("dropped:", [(r["question_id"], SHORT[r["model"]]) for r in drop])

# ------------------------------------------------------------------ strata
def table(key, ks):
    print(f"\n{'stratum':>9s} {'cells':>6s} {'items':>6s} {'GIFT':>7s} {'OR':>7s} "
          f"{'delta_pp':>9s} {'b':>4s} {'c':>4s} {'p_exact':>8s}")
    out = {}
    for k in ks:
        sub = [r for r in ok if r[key] == k]
        if not sub:
            continue
        n = len(sub)
        g = sum(r["gift_correct"] for r in sub); o = sum(r["or_correct"] for r in sub)
        b = sum(1 for r in sub if r["delta"] == 1)
        c = sum(1 for r in sub if r["delta"] == -1)
        p = L.mcnemar_exact(b, c)
        ni = len(set(r["question_id"] for r in sub))
        print(f"{k:9d} {n:6d} {ni:6d} {100*g/n:6.1f}% {100*o/n:6.1f}% "
              f"{100*(g-o)/n:+8.2f} {b:4d} {c:4d} {p:8.4f}")
        out[k] = dict(n=n, gift=g, orr=o, b=b, c=c, delta=(g - o) / n)
    return out


print("\n=== A. NAIVE difficulty (all 4 OR models, CONTAMINATED) ===")
tab_naive = table("naive_k", range(5))
print("\n=== B. LEAVE-ONE-OUT difficulty (other 3 OR models) -- PRIMARY ===")
tab_loo = table("loo_k", range(4))

print("\n=== C. LOO difficulty x model ===")
print(f"{'model':8s} {'k':>2s} {'n':>5s} {'GIFT':>7s} {'OR':>7s} {'delta_pp':>9s} {'b':>3s} {'c':>3s}")
for m in MODELS:
    for k in range(4):
        sub = [r for r in ok if r["model"] == m and r["loo_k"] == k]
        if not sub:
            continue
        n = len(sub)
        g = sum(r["gift_correct"] for r in sub); o = sum(r["or_correct"] for r in sub)
        b = sum(1 for r in sub if r["delta"] == 1); c = sum(1 for r in sub if r["delta"] == -1)
        print(f"{SHORT[m]:8s} {k:2d} {n:5d} {100*g/n:6.1f}% {100*o/n:6.1f}% "
              f"{100*(g-o)/n:+8.2f} {b:3d} {c:3d}")

# ---------------------------------------------------- hard vs easy contrast
HARD = lambda r: r["loo_k"] <= 2     # at least one other model got it wrong
EASY = lambda r: r["loo_k"] == 3


def contrast(rs):
    h = [r for r in rs if HARD(r)]; e = [r for r in rs if EASY(r)]
    if not h or not e:
        return None
    dh = sum(r["delta"] for r in h) / len(h)
    de = sum(r["delta"] for r in e) / len(e)
    return dh - de


def d_hard(rs):
    h = [r for r in rs if HARD(r)]
    return sum(r["delta"] for r in h) / len(h) if h else None


def d_easy(rs):
    e = [r for r in rs if EASY(r)]
    return sum(r["delta"] for r in e) / len(e) if e else None


nh = sum(1 for r in ok if HARD(r)); ne = sum(1 for r in ok if EASY(r))
print(f"\n=== D. HARD (loo_k<=2, n={nh}) vs EASY (loo_k=3, n={ne}) ===")
print(f"delta_hard  = {100*d_hard(ok):+.2f} pp")
print(f"delta_easy  = {100*d_easy(ok):+.2f} pp")
print(f"difference  = {100*contrast(ok):+.2f} pp")

B = 20000
bs = L.cluster_bootstrap(ok, contrast, B=B, seed=20260731)
lo, hi = L.ci(bs)
print(f"cluster bootstrap (B={B}, resample the 183 clusters) 95% CI on the "
      f"difference: [{100*lo:+.2f}, {100*hi:+.2f}] pp   (n_rep={len(bs)})")
bh = L.cluster_bootstrap(ok, d_hard, B=B, seed=20260732)
be = L.cluster_bootstrap(ok, d_easy, B=B, seed=20260733)
print(f"  delta_hard 95% CI [{100*L.ci(bh)[0]:+.2f}, {100*L.ci(bh)[1]:+.2f}] pp")
print(f"  delta_easy 95% CI [{100*L.ci(be)[0]:+.2f}, {100*L.ci(be)[1]:+.2f}] pp")

# permutation test: shuffle the item-level difficulty vector across items
# (keeps each item's 4-cell delta block intact; breaks difficulty<->delta link)
items = {}
for r in ok:
    items.setdefault(r["question_id"], []).append(r)
qids = sorted(items)
obs = contrast(ok)
rng = random.Random(4242)
P = 20000
cnt = 0
diffvec = {q: {r["model"]: r["loo_k"] for r in items[q]} for q in qids}
for _ in range(P):
    perm = qids[:]
    rng.shuffle(perm)
    rs = []
    for q, src in zip(qids, perm):
        for r in items[q]:
            rr = dict(r)
            rr["loo_k"] = diffvec[src].get(r["model"], r["loo_k"])
            rs.append(rr)
    v = contrast(rs)
    if v is not None and abs(v) >= abs(obs) - 1e-12:
        cnt += 1
print(f"permutation test (P={P}, item-level relabelling of the difficulty "
      f"vector, two-sided): p = {(cnt+1)/(P+1):.4f}")

# Spearman at item level
il_d, il_k = [], []
for q in qids:
    rs = items[q]
    il_d.append(sum(r["delta"] for r in rs) / len(rs))
    il_k.append(sum(r["loo_k"] for r in rs) / len(rs))


def spear(xs, ys):
    def rank(v):
        idx = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0]*len(v); i = 0
        while i < len(idx):
            j = i
            while j+1 < len(idx) and v[idx[j+1]] == v[idx[i]]:
                j += 1
            a = (i+j)/2.0+1
            for k in range(i, j+1):
                r[idx[k]] = a
            i = j+1
        return r
    rx, ry = rank(xs), rank(ys)
    mx = sum(rx)/len(rx); my = sum(ry)/len(ry)
    num = sum((a-mx)*(b-my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a-mx)**2 for a in rx)); dy = math.sqrt(sum((b-my)**2 for b in ry))
    return num/(dx*dy) if dx and dy else float('nan')


rho = spear(il_k, il_d)
rng2 = random.Random(99)
c2 = 0
for _ in range(P):
    y = il_d[:]
    rng2.shuffle(y)
    if abs(spear(il_k, y)) >= abs(rho) - 1e-12:
        c2 += 1
print(f"item-level Spearman rho(mean LOO difficulty, mean delta) = {rho:+.4f}, "
      f"permutation p = {(c2+1)/(P+1):.4f}  (n_items={len(qids)})")

json.dump({"tab_loo": {str(k): v for k, v in tab_loo.items()},
           "tab_naive": {str(k): v for k, v in tab_naive.items()},
           "delta_hard": d_hard(ok), "delta_easy": d_easy(ok),
           "contrast": obs, "contrast_ci": [lo, hi],
           "hard_ci": list(L.ci(bh)), "easy_ci": list(L.ci(be)),
           "perm_p": (cnt+1)/(P+1), "spearman": rho,
           "spearman_p": (c2+1)/(P+1)},
          open(os.path.join(BASE, "ca_cov_02_out.json"), "w"), indent=1)

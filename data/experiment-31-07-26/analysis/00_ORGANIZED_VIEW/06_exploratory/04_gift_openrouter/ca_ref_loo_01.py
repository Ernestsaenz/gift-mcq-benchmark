"""ca_ref_loo_01 -- independent recomputation to test the 'leave-one-out difficulty'
claim from the coverage-bias line of work.

Stdlib only. Every p-value is named with its method.
"""
import json, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ca_lib as L

BASE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
SHORT = {"google/gemini-3.6-flash": "gemini", "google/gemma-4-26b-a4b-it": "gemma",
         "qwen/qwen3.6-35b-a3b": "qwen", "z-ai/glm-5.2": "glm"}

raw = json.load(open(os.path.join(BASE, "cross_arm_A.json")))
rows = [r for r in raw if r.get("analysis_include")]
print("=== 0. base counts ===")
print("rows in file            :", len(raw))
print("analysis_include        :", len(rows))
print("items                   :", len(set(r["question_id"] for r in rows)))
print("clusters                :", len(set(r["cluster"] for r in rows)))
print("models                  :", len(set(r["model"] for r in rows)))
cells_per_item = {}
for r in rows:
    cells_per_item.setdefault(r["question_id"], set()).add(r["model"])
sizes = {}
for q, ms in cells_per_item.items():
    sizes[len(ms)] = sizes.get(len(ms), 0) + 1
print("cells-per-item histogram:", sizes)

print("\n=== 1. per-model accuracy + discordance (confirm OBSERVED) ===")
print(f"{'model':8s} {'n':>5s} {'GIFT':>7s} {'OR':>7s} {'delta_pp':>9s} {'b':>4s} {'c':>4s} {'mcn_exact_p':>12s}")
tot_b = tot_c = 0
for m in MODELS:
    sub = [r for r in rows if r["model"] == m]
    n = len(sub)
    g = sum(r["gift_correct"] for r in sub); o = sum(r["or_correct"] for r in sub)
    b = sum(1 for r in sub if r["gift_correct"] == 1 and r["or_correct"] == 0)
    c = sum(1 for r in sub if r["gift_correct"] == 0 and r["or_correct"] == 1)
    tot_b += b; tot_c += c
    print(f"{SHORT[m]:8s} {n:5d} {100*g/n:6.1f}% {100*o/n:6.1f}% {100*(g-o)/n:+8.2f} "
          f"{b:4d} {c:4d} {L.mcnemar_exact(b,c):12.4f}")
n = len(rows)
g = sum(r["gift_correct"] for r in rows); o = sum(r["or_correct"] for r in rows)
x2u, pu = L.mcnemar_chi2(tot_b, tot_c, cc=False)
x2c, pc = L.mcnemar_chi2(tot_b, tot_c, cc=True)
print(f"{'POOLED':8s} {n:5d} {100*g/n:6.1f}% {100*o/n:6.1f}% {100*(g-o)/n:+8.2f} "
      f"{tot_b:4d} {tot_c:4d} {L.mcnemar_exact(tot_b,tot_c):12.6f}")
print(f"  pooled unclustered McNemar chi2 uncorrected = {x2u:.4f} (p={pu:.5f}); "
      f"continuity-corrected = {x2c:.4f} (p={pc:.5f})")

# ------------------------------------------------------------------ difficulty
G = json.load(open(os.path.join(BASE, "ca_cov_grid.json")))
orc = {tuple(k.split("|")): v for k, v in G["or_correct"].items()}
gic = {tuple(k.split("|")): v for k, v in G["gift_correct"].items()}
covered = set(G["covered"]); defect = set(G["defect"])

# cross-check the grid against the shipped cross_arm rows
mism = 0
for r in rows:
    k = (r["model"], r["question_id"])
    if orc.get(k) != r["or_correct"] or gic.get(k) != r["gift_correct"]:
        mism += 1
print(f"\ngrid-vs-cross_arm_A mismatches on the {len(rows)} analysed cells: {mism}")


def naive_k(q):
    vs = [orc[(m, q)] for m in MODELS if (m, q) in orc]
    return sum(vs) if len(vs) == 4 else None


def loo_or(q, m):
    vs = [orc[(mm, q)] for mm in MODELS if mm != m and (mm, q) in orc]
    return sum(vs) if len(vs) == 3 else None


def loo_gift(q, m):
    vs = [gic[(mm, q)] for mm in MODELS if mm != m and (mm, q) in gic]
    return sum(vs) if len(vs) == 3 else None


for r in rows:
    q, m = r["question_id"], r["model"]
    r["naive_k"] = naive_k(q)
    r["loo_k"] = loo_or(q, m)
    r["loo_g"] = loo_gift(q, m)
    r["delta"] = r["gift_correct"] - r["or_correct"]

ok = [r for r in rows if r["naive_k"] is not None and r["loo_k"] is not None]
print("cells with both difficulty scores defined:", len(ok))

# ------------------------------------------------- 2. the identity, and what it implies
print("\n=== 2. the 'verified identity' ===")
bad = 0
qs = sorted(set(r["question_id"] for r in ok))
for q in qs:
    lo = [loo_or(q, m) for m in MODELS]
    nk = naive_k(q)
    if None in lo or nk is None:
        continue
    if abs(sum(lo) / 4.0 - 0.75 * nk) > 1e-12:
        bad += 1
print(f"items checked = {len(qs)}; violations of  mean_m loo_k(i,m) == 0.75*naive_k(i) : {bad}")
print("NOTE: sum_m loo_k(i,m) = sum_m (naive_k(i) - or_correct(i,m)) = 4*naive_k - naive_k")
print("      = 3*naive_k, so the identity is an ALGEBRAIC TAUTOLOGY whenever all four")
print("      cells exist. '0 violations' is arithmetic self-check, not evidence.")
print("      CONSEQUENCE: mean LOO difficulty is a strictly increasing linear transform of")
print("      naive_k, so ANY rank statistic on the item-level difficulty axis is IDENTICAL")
print("      under naive and under leave-one-out. LOO cannot fix an item-level Spearman.")


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


items = {}
for r in ok:
    items.setdefault(r["question_id"], []).append(r)
qids = sorted(items)
il_d = [sum(r["delta"] for r in items[q])/len(items[q]) for q in qids]
il_naive = [items[q][0]["naive_k"] for q in qids]
il_loo = [sum(r["loo_k"] for r in items[q])/len(items[q]) for q in qids]
rho_naive = spear(il_naive, il_d)
rho_loo = spear(il_loo, il_d)
print(f"\nitem-level Spearman rho(NAIVE naive_k, mean delta) = {rho_naive:+.6f}  (n_items={len(qids)})")
print(f"item-level Spearman rho(mean LOO  loo_k, mean delta) = {rho_loo:+.6f}")
print(f"difference = {rho_naive - rho_loo:.3e}   <-- identical, exactly as the identity forces")

P = 20000
rng = random.Random(99)
cnt = 0
for _ in range(P):
    y = il_d[:]; rng.shuffle(y)
    if abs(spear(il_naive, y)) >= abs(rho_naive) - 1e-12:
        cnt += 1
print(f"permutation p (P={P}, shuffle mean-delta across items, two-sided) = {(cnt+1)/(P+1):.5f}")

# ------------------------------------------------- 3. cell-level strata
def table(key, ks, rs):
    out = {}
    print(f"{'k':>3s} {'cells':>6s} {'GIFT%':>7s} {'OR%':>7s} {'delta_pp':>9s} {'b':>4s} {'c':>4s} {'mcn_exact_p':>11s}")
    for k in ks:
        sub = [r for r in rs if r[key] == k]
        if not sub:
            continue
        nn = len(sub)
        gg = sum(r["gift_correct"] for r in sub); oo = sum(r["or_correct"] for r in sub)
        b = sum(1 for r in sub if r["delta"] == 1); c = sum(1 for r in sub if r["delta"] == -1)
        print(f"{k:3d} {nn:6d} {100*gg/nn:6.1f}% {100*oo/nn:6.1f}% {100*(gg-oo)/nn:+8.2f} "
              f"{b:4d} {c:4d} {L.mcnemar_exact(b,c):11.4f}")
        out[k] = dict(n=nn, delta=(gg-oo)/nn, b=b, c=c, gift=gg, orr=oo)
    return out


print("\n=== 3A. NAIVE difficulty strata (contaminated) ===")
tn = table("naive_k", range(5), ok)
print("\n=== 3B. LEAVE-ONE-OUT (OR arm) difficulty strata ===")
tl = table("loo_k", range(4), ok)
print("NOTE loo_k=0 -- the HARDEST stratum -- is present and is NOT reported in the claim.")

# per-stratum cluster bootstrap CI
print("\n=== 3C. cluster bootstrap (B=20000, resample the clusters) on each LOO stratum ===")
for k in range(4):
    def st(rs, k=k):
        sub = [r for r in rs if r["loo_k"] == k]
        return sum(r["delta"] for r in sub)/len(sub) if sub else None
    bs = L.cluster_bootstrap(ok, st, B=20000, seed=1000+k)
    lo, hi = L.ci(bs)
    sub = [r for r in ok if r["loo_k"] == k]
    print(f"loo_k={k}  n={len(sub):4d}  delta={100*sum(r['delta'] for r in sub)/len(sub):+7.2f} pp   "
          f"95% CI [{100*lo:+7.2f}, {100*hi:+7.2f}] pp  (n_rep={len(bs)})")

# hard vs easy contrast
def contrast(rs, key="loo_k"):
    h = [r for r in rs if r[key] <= 2]; e = [r for r in rs if r[key] == 3]
    if not h or not e:
        return None
    return sum(r["d" if "d" in rs[0] else "delta"] for r in h)/len(h) - \
           sum(r["d" if "d" in rs[0] else "delta"] for r in e)/len(e)


def contrast_loo(rs):
    h = [r for r in rs if r["loo_k"] <= 2]; e = [r for r in rs if r["loo_k"] == 3]
    if not h or not e:
        return None
    return sum(r["delta"] for r in h)/len(h) - sum(r["delta"] for r in e)/len(e)


obs = contrast_loo(ok)
bs = L.cluster_bootstrap(ok, contrast_loo, B=20000, seed=777)
lo, hi = L.ci(bs)
frac_le0 = sum(1 for v in bs if v <= 0)/len(bs)
print(f"\nHARD(loo_k<=2) vs EASY(loo_k=3) contrast = {100*obs:+.2f} pp")
print(f"  cluster bootstrap 95% CI = [{100*lo:+.2f}, {100*hi:+.2f}] pp   "
      f"(bootstrap mass at or below 0 = {frac_le0:.4f}; two-sided bootstrap p ~ {2*min(frac_le0,1-frac_le0):.4f})")

json.dump({"tab_naive": {str(k): v for k, v in tn.items()},
           "tab_loo": {str(k): v for k, v in tl.items()},
           "rho_naive": rho_naive, "rho_loo": rho_loo,
           "rho_perm_p": (cnt+1)/(P+1),
           "contrast": obs, "contrast_ci": [lo, hi],
           "contrast_boot_p": 2*min(frac_le0, 1-frac_le0)},
          open(os.path.join(BASE, "ca_ref_loo_01_out.json"), "w"), indent=1)

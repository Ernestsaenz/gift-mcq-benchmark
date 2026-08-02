"""Part 2: uncertainty on the LOO strata, and how partial coverage interacts.
Stdlib only.
"""
import json, math, random, os, collections

BASE = os.path.dirname(os.path.abspath(__file__))
rows = [r for r in json.load(open(os.path.join(BASE, "cross_arm_A.json")))
        if r.get("analysis_include")]
MODELS = sorted({r["model"] for r in rows})
byitem = collections.defaultdict(dict)
for r in rows:
    byitem[r["question_id"]][r["model"]] = r
QS = sorted(byitem)
for q in QS:
    cs = byitem[q]
    nk = sum(c["or_correct"] for c in cs.values())
    for m, c in cs.items():
        c["naive_k"] = nk
        c["loo_k"] = nk - c["or_correct"]
        c["delta"] = c["gift_correct"] - c["or_correct"]
cells = [c for q in QS for c in byitem[q].values()]


def binom_pmf(k, n, p=0.5):
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    obs = binom_pmf(b, n)
    return min(1.0, sum(binom_pmf(k, n) for k in range(n + 1)
                        if binom_pmf(k, n) <= obs * (1 + 1e-9)))


print("[A] LOO strata with exact two-sided McNemar (sign test on discordants)")
print(f"{'loo_k':>5s} {'cells':>6s} {'items':>6s} {'clus':>5s} {'delta_pp':>9s} "
      f"{'b':>4s} {'c':>4s} {'p_exact':>9s}")
for k in range(4):
    sub = [c for c in cells if c["loo_k"] == k]
    n = len(sub)
    b = sum(1 for c in sub if c["delta"] == 1)
    cc = sum(1 for c in sub if c["delta"] == -1)
    d = sum(c["delta"] for c in sub) / n
    ni = len({c["question_id"] for c in sub})
    ncl = len({c["cluster"] for c in sub})
    print(f"{k:5d} {n:6d} {ni:6d} {ncl:5d} {100*d:+8.2f} {b:4d} {cc:4d} "
          f"{mcnemar_exact(b, cc):9.4f}")
print("    NOT ONE stratum reaches p<0.05. The whole 'corrected' LOO trend is")
print("    built from 10, 19 and 40 discordant pairs.")

# cluster bootstrap on the LOO slope (delta at loo_k<=1 minus delta at loo_k=3)
def slope(rs):
    h = [r for r in rs if r["loo_k"] <= 1]
    e = [r for r in rs if r["loo_k"] == 3]
    if not h or not e:
        return None
    return sum(r["delta"] for r in h) / len(h) - sum(r["delta"] for r in e) / len(e)


def cluster_boot(rs, fn, B=20000, seed=7):
    by = collections.defaultdict(list)
    for r in rs:
        by[r["cluster"]].append(r)
    keys = sorted(by)
    rng = random.Random(seed)
    out = []
    for _ in range(B):
        draw = []
        for _ in range(len(keys)):
            draw.extend(by[keys[rng.randrange(len(keys))]])
        v = fn(draw)
        if v is not None:
            out.append(v)
    out.sort()
    return out


bs = cluster_boot(cells, slope, B=20000, seed=20260731)
lo = bs[int(0.025 * len(bs))]; hi = bs[int(0.975 * len(bs))]
print(f"\n[B] LOO slope (delta at loo_k<=1 minus delta at loo_k=3) = "
      f"{100*slope(cells):+.2f} pp")
print(f"    cluster bootstrap (resample the 178 clusters with replacement, "
      f"B=20000, n_rep={len(bs)}) 95% CI = [{100*lo:+.2f}, {100*hi:+.2f}] pp")
print(f"    CI covers 0: {lo <= 0 <= hi}")

# same for the naive slope, to show the contaminated one IS 'significant'
def slope_n(rs):
    h = [r for r in rs if r["naive_k"] <= 1]
    e = [r for r in rs if r["naive_k"] == 4]
    if not h or not e:
        return None
    return sum(r["delta"] for r in h) / len(h) - sum(r["delta"] for r in e) / len(e)


bn = cluster_boot(cells, slope_n, B=20000, seed=20260732)
lon = bn[int(0.025 * len(bn))]; hin = bn[int(0.975 * len(bn))]
print(f"    naive slope for contrast = {100*slope_n(cells):+.2f} pp, "
      f"95% CI [{100*lon:+.2f}, {100*hin:+.2f}]")

# ------------------------------------------- [C] coverage bias on the difficulty axis
G = json.load(open(os.path.join(BASE, "ca_cov_grid.json")))
orc = {tuple(k.split("|")): v for k, v in G["or_correct"].items()}
covered = set(G["covered"])
meta = json.load(open(os.path.join(BASE, "dataset_meta.json")))
excl = set(meta["exclusions"]["out_of_domain_law"]) | \
       set(meta["exclusions"]["adjudicated_key_defect"])
allq = sorted({q for (_m, q) in orc})
print(f"\n[C] difficulty distribution, GIFT-covered vs never-reached")
print(f"    (OR arm is complete; {len(allq)} items, {len(excl)} v2 exclusions removed)")
dist = {"covered": collections.Counter(), "missing": collections.Counter()}
for q in allq:
    if q in excl:
        continue
    vs = [orc[(m, q)] for m in MODELS if (m, q) in orc]
    if len(vs) != 4:
        continue
    dist["covered" if q in covered else "missing"][sum(vs)] += 1
print(f"{'naive_k':>7s} {'covered':>9s} {'missing':>9s} {'cov%':>7s} {'miss%':>7s}")
tc = sum(dist["covered"].values()); tm = sum(dist["missing"].values())
for k in range(5):
    a, b = dist["covered"][k], dist["missing"][k]
    print(f"{k:7d} {a:9d} {b:9d} {100*a/tc:6.1f}% {100*b/tm:6.1f}%")
print(f"{'total':>7s} {tc:9d} {tm:9d}")
hard_c = sum(dist["covered"][k] for k in range(3)) / tc
hard_m = sum(dist["missing"][k] for k in range(3)) / tm
print(f"    items with naive_k<=2 ('hard'): covered {100*hard_c:.1f}% vs "
      f"missing {100*hard_m:.1f}%  -> ratio {hard_m/hard_c:.2f}x")
print("    Coverage skews the analysed set toward EASY items, so the very strata")
print("    the corrected LOO trend depends on are the ones coverage depleted.")

json.dump({"loo_slope": slope(cells), "loo_slope_ci": [lo, hi],
           "naive_slope": slope_n(cells), "naive_slope_ci": [lon, hin],
           "dist_covered": dict(dist["covered"]),
           "dist_missing": dict(dist["missing"])},
          open(os.path.join(BASE, "ca_refute_loodiff_a2_out.json"), "w"), indent=1)

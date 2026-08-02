"""ca_cov_07: synthesis. Bootstrap CIs for the preferred extrapolators,
projected discordance / McNemar power on the full dataset, region check, and
the final bound table.
"""
import json, os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ca_lib as L

BASE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
SHORT = {"google/gemini-3.6-flash": "gemini", "google/gemma-4-26b-a4b-it": "gemma",
         "qwen/qwen3.6-35b-a3b": "qwen", "z-ai/glm-5.2": "glm"}

G = json.load(open(os.path.join(BASE, "ca_cov_grid.json")))
orc = {tuple(k.split("|")): v for k, v in G["or_correct"].items()}
gic = {tuple(k.split("|")): v for k, v in G["gift_correct"].items()}
covered = set(G["covered"]); defect = set(G["defect"])
items = json.load(open(os.path.join(BASE, "ca_cov_or_full.json")))["items"]
cross = {(r["model"], r["question_id"]): r for r in L.load(include_only=True)}


def loo_k(q, m):
    vs = [orc[(mm, q)] for mm in MODELS if mm != m and (mm, q) in orc]
    return sum(vs) if len(vs) == 3 else None


POP = []
for q in items:
    if q in defect:
        continue
    for m in MODELS:
        if (m, q) not in orc:
            continue
        POP.append({"q": q, "m": m, "or": orc[(m, q)], "gift": gic.get((m, q)),
                    "k": loo_k(q, m), "paired": q in covered,
                    "region": items[q]["region"],
                    "cluster": cross[(m, q)]["cluster"] if (m, q) in cross else None})
PAIR = [r for r in POP if r["paired"]]
NONP = [r for r in POP if not r["paired"]]
MISS = [r for r in POP if r["gift"] is None]
EXTRA = [r for r in POP if not r["paired"] and r["gift"] is not None]
N = len(POP)


def kmk(r):
    return (r["m"], r["k"])


def make_stat(mode):
    def stat(rows):
        agg = {}
        for r in rows:
            s = kmk(r) if mode == "m_k" else (r["m"], "E" if r["k"] == 3 else "H")
            a = agg.setdefault(s, [0, 0]); a[0] += r["gift"] - r["or"]; a[1] += 1
        crude = sum(r["gift"] - r["or"] for r in rows) / len(rows)
        scale = len(PAIR) / len(rows)
        tot = 0.0
        for r in MISS:
            s = kmk(r) if mode == "m_k" else (r["m"], "E" if r["k"] == 3 else "H")
            tot += agg[s][0] / agg[s][1] if (s in agg and agg[s][1] >= 5) else crude
        base = sum(r["gift"] - r["or"] for r in rows) * scale + \
            sum(r["gift"] - r["or"] for r in EXTRA)
        return (base + tot) / N
    return stat


print("=== BOOTSTRAP CIs (cluster bootstrap over the 183 paired clusters, B=20000) ===")
out = {}
for mode in ["m_he", "m_k"]:
    st = make_stat(mode)
    pt = st(PAIR)
    bs = L.cluster_bootstrap(PAIR, st, keyf=lambda r: r["cluster"], B=20000, seed=606060 + len(mode))
    lo, hi = L.ci(bs)
    out[mode] = {"pt": pt, "ci": [lo, hi]}
    print(f"  strata={mode:6s}  point {100*pt:+.2f} pp  95% CI [{100*lo:+.2f}, {100*hi:+.2f}]")

obs_stat = lambda rs: sum(r["gift"] - r["or"] for r in rs) / len(rs)
bs0 = L.cluster_bootstrap(PAIR, obs_stat, keyf=lambda r: r["cluster"], B=20000, seed=707070)
lo0, hi0 = L.ci(bs0)
print(f"  observed paired      point {100*obs_stat(PAIR):+.2f} pp  "
      f"95% CI [{100*lo0:+.2f}, {100*hi0:+.2f}]")

# ------------------------------------------- projected discordance & McNemar
print("\n=== PROJECTED FULL-DATASET DISCORDANCE (m_k transfer of b- and c-rates) ===")
rb, rc = {}, {}
for r in PAIR:
    s = kmk(r)
    a = rb.setdefault(s, [0, 0]); a[1] += 1
    if r["gift"] and not r["or"]:
        a[0] += 1
    a2 = rc.setdefault(s, [0, 0]); a2[1] += 1
    if r["or"] and not r["gift"]:
        a2[0] += 1
b_obs = sum(1 for r in PAIR + EXTRA if r["gift"] and not r["or"])
c_obs = sum(1 for r in PAIR + EXTRA if r["or"] and not r["gift"])
b_p = c_p = 0.0
crude_b = sum(1 for r in PAIR if r["gift"] and not r["or"]) / len(PAIR)
crude_c = sum(1 for r in PAIR if r["or"] and not r["gift"]) / len(PAIR)
for r in MISS:
    s = kmk(r)
    b_p += rb[s][0] / rb[s][1] if s in rb and rb[s][1] >= 5 else crude_b
    c_p += rc[s][0] / rc[s][1] if s in rc and rc[s][1] >= 5 else crude_c
B_tot, C_tot = b_obs + b_p, c_obs + c_p
print(f"observed on 1343 cells        : b={b_obs}  c={c_obs}")
print(f"projected on the 496 missing  : b={b_p:.1f}  c={c_p:.1f}")
print(f"projected full-dataset totals : b={B_tot:.1f}  c={C_tot:.1f}")
x2, p2 = L.mcnemar_chi2(round(B_tot), round(C_tot))
x2c, p2c = L.mcnemar_chi2(round(B_tot), round(C_tot), cc=True)
print(f"McNemar chi2 (uncorrected)={x2:.2f} p={p2:.4f};  "
      f"continuity-corrected={x2c:.2f} p={p2c:.4f};  "
      f"exact p={L.mcnemar_exact(round(B_tot), round(C_tot)):.4f}")
print("  (for reference the analysed 1244 cells give b=46 c=24, "
      "uncorrected chi2=6.91, cc chi2=6.30, exact p=0.0115)")

# ------------------------------------------------------- hard-cell exposure
hp = sum(1 for r in PAIR if r["k"] <= 2) / len(PAIR)
hn = sum(1 for r in NONP if r["k"] is not None and r["k"] <= 2) / \
    len([r for r in NONP if r["k"] is not None])
hf = sum(1 for r in POP if r["k"] is not None and r["k"] <= 2) / \
    len([r for r in POP if r["k"] is not None])
print(f"\n=== HARD-CELL EXPOSURE (LOO k<=2) ===")
print(f"analysed paired set : {100*hp:.1f}%   non-paired remainder: {100*hn:.1f}%   "
      f"full dataset: {100*hf:.1f}%")
print(f"the analysed subset under-samples hard cells by {100*(hf-hp):.1f} pp of cell mass")

# --------------------------------------------------------------- region check
print("\n=== GIFT-vs-OR delta by region, paired set only ===")
print(f"{'region':22s} {'n':>4s} {'delta_pp':>9s} {'b':>3s} {'c':>3s} {'cov_share':>10s}")
for rg in sorted(set(r["region"] for r in POP)):
    sub = [r for r in PAIR if r["region"] == rg]
    tot = [r for r in POP if r["region"] == rg]
    if not sub:
        continue
    n = len(sub)
    d = sum(r["gift"] - r["or"] for r in sub) / n
    b = sum(1 for r in sub if r["gift"] and not r["or"])
    c = sum(1 for r in sub if r["or"] and not r["gift"])
    print(f"{rg:22s} {n:4d} {100*d:+8.2f} {b:3d} {c:3d} {100*n/len(tot):9.0f}%")

# ------------------------------------------------------------- final bounds
print("\n=== FINAL BOUND TABLE (full-dataset pooled cross-arm delta, pp) ===")
g6 = json.load(open(os.path.join(BASE, "ca_cov_06_out.json")))["grid"]
o5 = json.load(open(os.path.join(BASE, "ca_cov_05_out.json")))
o4 = json.load(open(os.path.join(BASE, "ca_cov_04_out.json")))
rows = [
    ("published (analysed 1244 cells, no extrapolation)", obs_stat(PAIR),
     [lo0, hi0]),
    ("MCAR transfer (assumes coverage is random -- it is not)", g6["none"][1], None),
    ("difficulty transfer, model x k4  [preferred]", out["m_k"]["pt"], out["m_k"]["ci"]),
    ("difficulty transfer, model x hard/easy", out["m_he"]["pt"], out["m_he"]["ci"]),
    ("difficulty x region transfer (sparse strata)", g6["m_he_reg"][1], None),
    ("constant-log-odds transfer", o5["E6"], None),
    ("observed uncovered delta (+5.05pp) applied to all unseen cells",
     o4["all_variants"].get("dummy", None) or
     json.load(open(os.path.join(BASE, "ca_cov_05_out.json")))["bound_scenarios"]
     ["observed uncovered delta (the 99 cells) applied everywhere"], None),
    ("Manski lower (GIFT wrong on every unseen cell)", o4["manski"][0], None),
    ("Manski upper (GIFT right on every unseen cell)", o4["manski"][1], None),
]
for name, v, ci in rows:
    s = f"  {name:62s} {100*v:+6.2f}"
    if ci:
        s += f"   95% CI [{100*ci[0]:+.2f}, {100*ci[1]:+.2f}]"
    print(s)

pts = [g6["none"][1], out["m_k"]["pt"], out["m_he"]["pt"], g6["m_he_reg"][1],
       o5["E6"], g6["k"][1], g6["he_reg"][1]]
print(f"\nspan of assumption-based point estimates: "
      f"[{100*min(pts):+.2f}, {100*max(pts):+.2f}] pp")
allci = [out["m_k"]["ci"][0], out["m_he"]["ci"][0]] + [min(pts)]
print(f"widest sampling CI across the assumption-based estimators: "
      f"[{100*min(out['m_k']['ci'][0], out['m_he']['ci'][0]):+.2f}, "
      f"{100*max(out['m_k']['ci'][1], out['m_he']['ci'][1]):+.2f}] pp")

json.dump({"boot": out, "obs_ci": [lo0, hi0],
           "proj_b": B_tot, "proj_c": C_tot,
           "hard_share": {"paired": hp, "nonpaired": hn, "full": hf},
           "span": [min(pts), max(pts)]},
          open(os.path.join(BASE, "ca_cov_07_out.json"), "w"), indent=1)

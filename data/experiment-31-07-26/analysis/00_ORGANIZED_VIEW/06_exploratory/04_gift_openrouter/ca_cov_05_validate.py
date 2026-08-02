"""ca_cov_05: (a) validate the transfer assumption against the 99 directly
observed uncovered cells; (b) redo the extrapolation on the LOG-ODDS scale,
which is the natural scale when the covered stratum sits near the ceiling;
(c) per-model extrapolated deltas; (d) an informative (non-Manski) bound.
"""
import json, os, sys, math
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
                    "cluster": cross[(m, q)]["cluster"] if (m, q) in cross else None})
PAIR = [r for r in POP if r["paired"]]
EXTRA = [r for r in POP if not r["paired"] and r["gift"] is not None]
MISS = [r for r in POP if r["gift"] is None]
N = len(POP)


def S(r):
    return (r["m"], "E" if r["k"] == 3 else "H")


# ---------------------------------------------------------------- (a) check
agg = {}
for r in PAIR:
    a = agg.setdefault(S(r), [0, 0, 0])
    a[0] += r["gift"] - r["or"]; a[1] += 1
    a[2] += r["gift"]
pred = sum(agg[S(r)][0] / agg[S(r)][1] for r in EXTRA if r["k"] is not None)
nE = len([r for r in EXTRA if r["k"] is not None])
obs = sum(r["gift"] - r["or"] for r in EXTRA if r["k"] is not None)
print("=== (a) TRANSFER-ASSUMPTION CHECK on the 99 observed uncovered cells ===")
print(f"cells with defined difficulty: {nE}")
print(f"predicted delta (model x hard/easy transfer from the paired set): "
      f"{100*pred/nE:+.2f} pp")
print(f"observed  delta                                                 : "
      f"{100*obs/nE:+.2f} pp")
print(f"residual (observed - predicted)                                  : "
      f"{100*(obs-pred)/nE:+.2f} pp")
crude = sum(r["gift"] - r["or"] for r in PAIR) / len(PAIR)
print(f"for comparison, the crude/MCAR prediction would have been        : "
      f"{100*crude:+.2f} pp")
print("-> the stratified transfer is closer to the truth than the crude one,"
      " but still under-predicts.")

# sign test on the residual: is the observed delta on EXTRA bigger than on PAIR?
b = sum(1 for r in EXTRA if r["gift"] and not r["or"])
c = sum(1 for r in EXTRA if r["or"] and not r["gift"])
print(f"EXTRA discordance b={b} c={c}, exact McNemar p={L.mcnemar_exact(b,c):.4f}")
bp = sum(1 for r in PAIR if r["gift"] and not r["or"])
cp = sum(1 for r in PAIR if r["or"] and not r["gift"])
print(f"PAIR  discordance b={bp} c={cp}")
print(f"Fisher exact on the 2x2 of discordant directions "
      f"(PAIR {bp}/{cp} vs EXTRA {b}/{c}): "
      f"p={L.fisher_exact_2x2(bp, cp, b, c):.4f}  "
      "-> no evidence the win/loss MIX differs between covered and uncovered")

# --------------------------------------------------------- (b) log-odds scale
def lg(p):
    return math.log(p / (1 - p))


print("\n=== (b) LOG-ODDS-SCALE transfer (Haldane 0.5 correction) ===")
print(f"{'stratum':12s} {'n_cov':>5s} {'ORcov':>7s} {'GIFTcov':>8s} {'logOR':>7s} "
      f"{'n_unobs':>7s} {'ORunobs':>8s} {'GIFTpred':>9s} {'delta_pp':>9s}")
tot_lo = 0.0
UNOBS = [r for r in MISS + EXTRA if r["k"] is not None]
strata = sorted(set(S(r) for r in PAIR), key=lambda s: (s[0], s[1]))
rows_out = []
for s in strata:
    cov = [r for r in PAIR if S(r) == s]
    unc = [r for r in UNOBS if S(r) == s]
    if not cov or not unc:
        continue
    n1 = len(cov)
    po = (sum(r["or"] for r in cov) + 0.5) / (n1 + 1)
    pg = (sum(r["gift"] for r in cov) + 0.5) / (n1 + 1)
    beta = lg(pg) - lg(po)
    n2 = len(unc)
    po2 = (sum(r["or"] for r in unc) + 0.5) / (n2 + 1)
    pg2 = 1 / (1 + math.exp(-(lg(po2) + beta)))
    d = pg2 - (sum(r["or"] for r in unc) / n2)
    tot_lo += d * n2
    rows_out.append((s, n1, po, pg, beta, n2, po2, pg2, d))
    print(f"{SHORT[s[0]]+'-'+s[1]:12s} {n1:5d} {100*po:6.1f}% {100*pg:7.1f}% "
          f"{beta:+7.3f} {n2:7d} {100*po2:7.1f}% {100*pg2:8.1f}% {100*d:+8.2f}")
G_pair = sum(r["gift"] for r in PAIR); O_pair = sum(r["or"] for r in PAIR)
nk = len([r for r in MISS + EXTRA if r["k"] is None])
E6 = ((G_pair - O_pair) + tot_lo + crude * nk) / N
print(f"E6 full-dataset delta, constant-log-odds transfer: {100*E6:+.2f} pp")

# ------------------------------------------------------------ (c) per model
print("\n=== (c) PER-MODEL: observed paired vs difficulty-reweighted full-set ===")
print(f"{'model':8s} {'n_pair':>6s} {'obs_pp':>8s} {'n_unobs':>7s} "
      f"{'E2_pp':>7s} {'E3_pp':>7s} {'E6_pp':>7s}")
per = {}
for m in MODELS:
    P_ = [r for r in PAIR if r["m"] == m]
    U_ = [r for r in MISS if r["m"] == m]
    X_ = [r for r in EXTRA if r["m"] == m]
    ALL = [r for r in POP if r["m"] == m]
    obs_m = sum(r["gift"] - r["or"] for r in P_) / len(P_)
    a2 = {}
    for r in P_:
        aa = a2.setdefault(S(r), [0, 0]); aa[0] += r["gift"] - r["or"]; aa[1] += 1
    t_miss = sum(a2[S(r)][0] / a2[S(r)][1] if r["k"] is not None else obs_m for r in U_)
    t_extra = sum(a2[S(r)][0] / a2[S(r)][1] if r["k"] is not None else obs_m for r in X_)
    e2 = (sum(r["gift"] - r["or"] for r in P_) + t_miss + t_extra) / len(ALL)
    e3 = (sum(r["gift"] - r["or"] for r in P_) + sum(r["gift"] - r["or"] for r in X_)
          + t_miss) / len(ALL)
    d_lo = {s: v for s, *v in [(x[0],) + tuple(x[1:]) for x in rows_out]}
    t6 = 0.0
    for r in U_ + X_:
        if r["k"] is None:
            t6 += obs_m; continue
        s = S(r)
        rec = [x for x in rows_out if x[0] == s]
        t6 += (rec[0][7] - rec[0][6]) if rec else obs_m
    e6 = (sum(r["gift"] - r["or"] for r in P_) + t6) / len(ALL)
    per[SHORT[m]] = {"obs": obs_m, "E2": e2, "E3": e3, "E6": e6,
                     "n_pair": len(P_), "n_unobs": len(U_) + len(X_)}
    print(f"{SHORT[m]:8s} {len(P_):6d} {100*obs_m:+7.2f} {len(U_)+len(X_):7d} "
          f"{100*e2:+6.2f} {100*e3:+6.2f} {100*e6:+6.2f}")

# ------------------------------------------------- (d) an informative bound
print("\n=== (d) INFORMATIVE BOUND on the full-dataset delta ===")
O_pair_ = O_pair
G_extra = sum(r["gift"] for r in EXTRA); O_extra = sum(r["or"] for r in EXTRA)
obs_part = (G_pair - O_pair_) + (G_extra - O_extra)
nm = len(MISS)
o_miss = sum(r["or"] for r in MISS)
print(f"observed contribution (1343 cells): {obs_part:+d} net wins")
print(f"unobserved cells: {nm}, OR correct on {o_miss} of them "
      f"({100*o_miss/nm:.1f}%)")
cands = {}
for name, d in [
        ("GIFT = OR (no effect at all on the unseen part)", 0.0),
        ("crude/MCAR transfer", crude),
        ("difficulty-stratified transfer (E2/E3)", None),
        ("log-odds transfer (E6)", None),
        ("worst per-model paired delta applied everywhere",
         min(sum(r["gift"] - r["or"] for r in PAIR if r["m"] == m) /
             len([x for x in PAIR if x["m"] == m]) for m in MODELS)),
        ("best per-model paired delta applied everywhere",
         max(sum(r["gift"] - r["or"] for r in PAIR if r["m"] == m) /
             len([x for x in PAIR if x["m"] == m]) for m in MODELS)),
        ("observed uncovered delta (the 99 cells) applied everywhere",
         sum(r["gift"] - r["or"] for r in EXTRA) / len(EXTRA)),
]:
    if d is None:
        continue
    cands[name] = (obs_part + d * nm) / N
    print(f"  {name:56s} -> {100*cands[name]:+6.2f} pp")

json.dump({"check": {"n": nE, "pred": pred / nE, "obs": obs / nE, "crude": crude},
           "E6": E6, "per_model": per, "bound_scenarios": cands},
          open(os.path.join(BASE, "ca_cov_05_out.json"), "w"), indent=1)

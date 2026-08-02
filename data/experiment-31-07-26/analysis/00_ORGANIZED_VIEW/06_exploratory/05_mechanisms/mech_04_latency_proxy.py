"""(iv) Is latency usable as an effort proxy at all?

Tests:
  1. Do the JSON A_/B_tokens and A_/B_latency_ms reconcile with the DB
     (final provider_attempt)?  Sanity gate.
  2. Within model & condition, Spearman rank correlation latency ~ tokens.
     If latency tracked effort, this should be high in BOTH conditions.
  3. Implied throughput = completion_tokens / (latency_ms/1000) = tok/s.
     Compare the median tok/s per model between run A and run B.  A large
     between-run shift means latency is contaminated by serving conditions,
     not by deliberation.
  4. Decompose paired log-latency change:
        log(B_lat/A_lat) = log(B_tok/A_tok) + log(A_tps/B_tps)
     and report how much of the median latency change is the throughput term.
  5. Wall-clock drift within each run (latency vs. request order/time).
"""
import json, math
from collections import defaultdict
from mech_lib_effort import (load, MODELS, SHORT, median, mean, quantile,
                             spearman, pearson, cluster_bootstrap,
                             boot_p_two_sided, t_sf2)

rows = load()
db = json.load(open("mech_db_cells.json"))
cells = {}
for c in db["cells"]:
    exp, model, qid = c["key"]
    cells[(exp, model, qid)] = c

EXP = {"A": "expA_or_310726", "B": "expB_or_310726"}

# ---------------------------------------------------------------- 1. reconcile
mismatch_tok = mismatch_lat = matched = missing = 0
for r in rows:
    for cond in "AB":
        c = cells.get((EXP[cond], r["model"], r["question_id"]))
        if c is None:
            missing += 1
            continue
        matched += 1
        if c["completion_tokens"] != r[cond + "_tokens"]:
            mismatch_tok += 1
        if c["latency_ms"] != r[cond + "_latency_ms"]:
            mismatch_lat += 1
print("=" * 96)
print("(iv) LATENCY AS AN EFFORT PROXY")
print("=" * 96)
print(f"[reconcile] cell-conditions matched to DB final attempt: {matched} "
      f"(missing {missing}); token mismatches={mismatch_tok}, "
      f"latency mismatches={mismatch_lat}")
print("  -> JSON *_tokens == provider_attempts.completion_tokens (generated "
      "tokens only, prompt excluded)")

# finish_reason / truncation audit
fr = defaultdict(lambda: defaultdict(int))
for r in rows:
    for cond in "AB":
        c = cells.get((EXP[cond], r["model"], r["question_id"]))
        if c:
            fr[(r["model"], cond)][c["finish_reason"]] += 1
print()
print("[truncation audit] finish_reason among the 1299 analysis cells")
print(f"{'model':<18} {'cond':<5} {'stop':>6} {'length':>7} {'error':>6}")
for m in MODELS:
    for cond in "AB":
        d = fr[(m, cond)]
        print(f"{SHORT[m]:<18} {cond:<5} {d.get('stop',0):>6} "
              f"{d.get('length',0):>7} {d.get('error',0):>6}")

# ------------------------------------------------- 2. latency ~ tokens (rank)
print()
print("-" * 96)
print("[2] Spearman rank correlation  latency_ms ~ completion_tokens, "
      "within model x condition")
print("    p from the t approximation  t = r*sqrt((n-2)/(1-r^2)), df = n-2")
print("-" * 96)
print(f"{'model':<18} {'cond':<5} {'n':>5} {'rho':>8} {'p':>12} "
      f"{'rho(pearson)':>13}")
for m in MODELS:
    for cond in "AB":
        rs = [r for r in rows if r["model"] == m]
        x = [r[cond + "_tokens"] for r in rs]
        y = [r[cond + "_latency_ms"] for r in rs]
        rho = spearman(x, y)
        n = len(x)
        t = rho * math.sqrt((n - 2) / max(1e-12, 1 - rho * rho))
        print(f"{SHORT[m]:<18} {cond:<5} {n:>5} {rho:>8.3f} {t_sf2(t, n-2):>12.3g} "
              f"{pearson(x, y):>13.3f}")

# ------------------------------------------------------------- 3. throughput
print()
print("-" * 96)
print("[3] Implied throughput  tok/s = completion_tokens / (latency_ms/1000)")
print("    median per model x condition, plus the A->B shift")
print("-" * 96)
print(f"{'model':<18} {'tps_A':>8} {'tps_B':>8} {'B/A':>7} "
      f"{'medLat_A':>9} {'medLat_B':>9} {'latB/latA':>10} "
      f"{'medTok_A':>9} {'medTok_B':>9} {'tokB/tokA':>10}")
tps_tab = {}
for m in MODELS:
    rs = [r for r in rows if r["model"] == m]
    tpsA = median([r["A_tokens"] / (r["A_latency_ms"] / 1000.0) for r in rs])
    tpsB = median([r["B_tokens"] / (r["B_latency_ms"] / 1000.0) for r in rs])
    tps_tab[m] = (tpsA, tpsB)
    lA, lB = median([r["A_latency_ms"] for r in rs]), median([r["B_latency_ms"] for r in rs])
    tA, tB = median([r["A_tokens"] for r in rs]), median([r["B_tokens"] for r in rs])
    print(f"{SHORT[m]:<18} {tpsA:>8.1f} {tpsB:>8.1f} {tpsB/tpsA:>7.3f} "
          f"{lA:>9.0f} {lB:>9.0f} {lB/lA:>10.3f} "
          f"{tA:>9.0f} {tB:>9.0f} {tB/tA:>10.3f}")

print()
print("    per-cell throughput ratio B/A (paired), cluster-bootstrap 95% CI")


def med_tps_ratio(rs):
    return median([(r["B_tokens"] / (r["B_latency_ms"] / 1000.0)) /
                   (r["A_tokens"] / (r["A_latency_ms"] / 1000.0)) for r in rs])


for m in MODELS:
    rs = [r for r in rows if r["model"] == m]
    pt, lo, hi, reps = cluster_bootstrap(rs, med_tps_ratio, B=3000, seed=41)
    print(f"      {SHORT[m]:<18} median tps_B/tps_A = {pt:.3f}  "
          f"95% CI [{lo:.3f},{hi:.3f}]  p_boot(vs 1)={boot_p_two_sided(reps,1.0):.4g}")

# --------------------------------------------------- 4. latency decomposition
print()
print("-" * 96)
print("[4] Decomposition of the paired log latency change")
print("      log(latB/latA) = log(tokB/tokA) + log(tpsA/tpsB)")
print("    medians of each term (natural log), and the % of the latency move")
print("    attributable to the throughput term")
print("-" * 96)
print(f"{'model':<18} {'med dlogLat':>12} {'med dlogTok':>12} "
      f"{'med dlogTPSinv':>15} {'throughput share':>17}")
for m in MODELS:
    rs = [r for r in rows if r["model"] == m]
    dl = [math.log(r["B_latency_ms"] / r["A_latency_ms"]) for r in rs]
    dt = [math.log(r["B_tokens"] / r["A_tokens"]) for r in rs]
    dp = [dl[i] - dt[i] for i in range(len(rs))]
    share = median(dp) / median(dl) if median(dl) != 0 else float("nan")
    print(f"{SHORT[m]:<18} {median(dl):>12.4f} {median(dt):>12.4f} "
          f"{median(dp):>15.4f} {share*100:>16.1f}%")

# --------------------------------------------------------- 5. wall-clock drift
print()
print("-" * 96)
print("[5] Wall-clock structure of each run: is latency time-dependent?")
print("    (created_at of the final attempt; Spearman latency ~ request time,")
print("     and tok/s ~ request time, within model x run)")
print("-" * 96)


def ts(s):
    # ISO8601 with +00:00
    from datetime import datetime
    return datetime.fromisoformat(s).timestamp()


print(f"{'model':<18} {'cond':<5} {'run span (min)':>15} {'rho(lat,t)':>11} "
      f"{'rho(tps,t)':>11} {'tps p10':>8} {'tps p50':>8} {'tps p90':>8}")
for m in MODELS:
    for cond in "AB":
        rs = [r for r in rows if r["model"] == m]
        recs = []
        for r in rs:
            c = cells.get((EXP[cond], m, r["question_id"]))
            if c and c["created_at"]:
                recs.append((ts(c["created_at"]), r[cond + "_latency_ms"],
                             r[cond + "_tokens"]))
        if len(recs) < 20:
            continue
        t0 = min(x[0] for x in recs)
        tt = [x[0] - t0 for x in recs]
        lat = [x[1] for x in recs]
        tps = [x[2] / (x[1] / 1000.0) for x in recs]
        span = (max(tt) - min(tt)) / 60.0
        print(f"{SHORT[m]:<18} {cond:<5} {span:>15.1f} "
              f"{spearman(tt, lat):>11.3f} {spearman(tt, tps):>11.3f} "
              f"{quantile(tps,.10):>8.1f} {quantile(tps,.50):>8.1f} "
              f"{quantile(tps,.90):>8.1f}")

# ---------------------------------------------- 6. what if we used latency?
print()
print("-" * 96)
print("[6] Counterfactual: median paired ratio using LATENCY instead of TOKENS")
print("    (what an analyst would have concluded from latency alone)")
print("-" * 96)


def med_lat_ratio(rs):
    return median([r["B_latency_ms"] / r["A_latency_ms"] for r in rs])


for m in MODELS:
    rs = [r for r in rows if r["model"] == m]
    pt, lo, hi, reps = cluster_bootstrap(rs, med_lat_ratio, B=3000, seed=42)
    ptt, lot, hit, _ = cluster_bootstrap(
        rs, lambda z: median([x["B_tokens"] / x["A_tokens"] for x in z]),
        B=3000, seed=42)
    print(f"{SHORT[m]:<18} latency ratio {pt:.3f} [{lo:.3f},{hi:.3f}]   vs   "
          f"token ratio {ptt:.3f} [{lot:.3f},{hit:.3f}]")

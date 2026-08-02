import json, os, math, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "sens_speccurve_results.json")))
res = R["results"]
print("N specifications:", len(res))

d = [r["delta_pp"] for r in res]
p = [r["p"] for r in res]
print("\n=== DELTA (pp, B minus A) over all specs ===")
print(f"median {st.median(d):+.3f}   mean {st.fmean(d):+.3f}   min {min(d):+.3f}   max {max(d):+.3f}")
print(f"IQR {sorted(d)[len(d)//4]:+.3f} .. {sorted(d)[3*len(d)//4]:+.3f}")
print("all negative:", all(x < 0 for x in d))
uniq = sorted(set(round(x, 6) for x in d))
print("distinct point estimates:", len(uniq), " range", f"{min(uniq):+.3f} .. {max(uniq):+.3f}")

print("\n=== P-VALUES ===")
print(f"median p {st.median(p):.3e}  min {min(p):.3e}  max {max(p):.3e}")
for thr in (0.05, 0.01, 0.001):
    k = sum(1 for x in p if x < thr)
    print(f"p<{thr}: {k}/{len(p)} = {100*k/len(p):.1f}%")

print("\n=== specs NOT reaching p<0.05 ===")
for r in sorted(res, key=lambda r: -r["p"]):
    if r["p"] >= 0.05:
        print(f"  {r['exclusion']:12s} {r['outcome']:8s} {r['unit']:8s} {r['inference']:18s} {r['pooling']:9s}"
              f" delta={r['delta_pp']:+7.2f}  p={r['p']:.4f}")

print("\n=== specs NOT reaching p<0.001 (but p<0.05) ===")
for r in sorted(res, key=lambda r: -r["p"]):
    if 0.001 <= r["p"] < 0.05:
        print(f"  {r['exclusion']:12s} {r['outcome']:8s} {r['unit']:8s} {r['inference']:18s} {r['pooling']:9s}"
              f" delta={r['delta_pp']:+7.2f}  p={r['p']:.5f}")


def group(key):
    g = {}
    for r in res:
        g.setdefault(r[key], []).append(r)
    print(f"\n--- by {key} ---")
    for k in sorted(g):
        v = g[k]
        dd = [x["delta_pp"] for x in v]
        pp = [x["p"] for x in v]
        print(f"  {k:18s} n={len(v):3d}  delta median {st.median(dd):+7.3f} "
              f"[{min(dd):+7.3f},{max(dd):+7.3f}]  p median {st.median(pp):.2e} "
              f" frac p<.05 {sum(1 for x in pp if x<0.05)/len(pp):.2f}"
              f"  frac p<.001 {sum(1 for x in pp if x<0.001)/len(pp):.2f}")


for k in ("exclusion", "outcome", "unit", "inference", "pooling"):
    group(k)

print("\n=== per (exclusion,outcome) cell-level summary ===")
for k, v in R["detail"].items():
    print(f"  {k:22s} N={v['n_cells']:5d} items={v['n_items']:4d} clusters={v['n_clusters']:4d} "
          f"accA={v['accA']:.2f}% accB={v['accB']:.2f}% delta={v['accB']-v['accA']:+.2f}pp "
          f"disc b(A>B)={v['disc_b']:4d} c(B>A)={v['disc_c']:3d} "
          f"boot95CI=[{v['boot_ci_cell'][0]:+.2f},{v['boot_ci_cell'][1]:+.2f}]")

print("\n=== per-model deltas (cell unit) ===")
MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it", "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
for k, v in R["detail"].items():
    s = "  ".join(f"{m.split('/')[-1]}:{x:+6.2f}" for m, x in zip(MODELS, v["per_model_delta"]))
    print(f"  {k:22s} {s}")
print("\n  per-model exact McNemar p (primary|lenient):")
v = R["detail"]["primary|lenient"]
for m, x in zip(MODELS, v["per_model_mcnemar"]):
    print(f"    {m:30s} p={x:.3e}")

print("\n=== logistic odds ratios (unit=cell, pooled) ===")
for r in res:
    if r["inference"] == "logit_robustSE" and r["pooling"] == "pooled":
        print(f"  {r['exclusion']:12s} {r['outcome']:8s} OR={r['OR']:.4f} "
              f"logOR={r['logOR']:+.4f} (robust SE {r['se']:.4f}) p={r['p']:.3e}")

print("\n=== bootstrap 95% CIs (unit=cell, pooled) ===")
for r in res:
    if r["inference"] == "cluster_bootstrap" and r["pooling"] == "pooled" and r["unit"] == "cell":
        print(f"  {r['exclusion']:12s} {r['outcome']:8s} delta={r['delta_pp']:+.2f} "
              f"CI=[{r['ci'][0]:+.2f},{r['ci'][1]:+.2f}]")

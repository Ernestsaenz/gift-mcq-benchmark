"""
Cluster bootstrap for the A->B (verbatim -> none-of-the-above) delta.
Pure standard library. No numpy/scipy.

Resampling units compared:
  L3 CLUSTER bootstrap : resample the 208 clinical-context clusters with replacement.
                         Correct unit -- respects items nested in clusters AND the
                         item x model crossing (a drawn cluster brings all its items,
                         and each item brings all 4 model rows).
  L2 ITEM bootstrap    : resample the 325 items with replacement. Keeps item x model
                         pairing, IGNORES clustering.
  L1 analytic          : (a) paired SE = sd(d_i)/sqrt(n), d_i = B_i - A_i  [ignores clustering]
                         (b) naive two-proportion binomial SE = sqrt(pA*qA/n + pB*qB/n)
                             [ignores clustering AND the A/B pairing]
"""
import json, math, random, collections

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
SEED = 20260731
NBOOT = 20000

rows = [r for r in json.load(open(PATH)) if r.get("analysis_include") is True]
MODELS = ["google/gemini-3.6-flash", "z-ai/glm-5.2", "qwen/qwen3.6-35b-a3b", "google/gemma-4-26b-a4b-it"]
SHORT  = {"google/gemini-3.6-flash":"gemini-3.6-flash", "z-ai/glm-5.2":"glm-5.2",
          "qwen/qwen3.6-35b-a3b":"qwen3.6-35b-a3b", "google/gemma-4-26b-a4b-it":"gemma-4-26b-a4b-it"}
MI = {m:i for i,m in enumerate(MODELS)}
NM = 4

# ---------- aggregate to resampling units ----------
# unit vector layout, 12 slots: for model i -> [3i]=n, [3i+1]=sumA, [3i+2]=sumB
def blank(): return [0]*12

item_vec    = collections.defaultdict(blank)   # question_id -> vec
cluster_vec = collections.defaultdict(blank)   # cluster     -> vec
item2cluster = {}
for r in rows:
    i = MI[r["model"]]
    for tgt in (item_vec[r["question_id"]], cluster_vec[r["cluster"]]):
        tgt[3*i]   += 1
        tgt[3*i+1] += r["A_correct"]
        tgt[3*i+2] += r["B_correct"]
    item2cluster[r["question_id"]] = r["cluster"]

CLUSTERS = [tuple(v) for v in cluster_vec.values()]
ITEMS    = [tuple(v) for v in item_vec.values()]
K, NI = len(CLUSTERS), len(ITEMS)

# ---------- statistic: from a 12-vector -> per-model deltas (pp) + pooled delta (pp) ----------
def stats_from(v):
    d = []
    tn = tA = tB = 0
    for i in range(NM):
        n, a, b = v[3*i], v[3*i+1], v[3*i+2]
        d.append(100.0*(b-a)/n if n else float("nan"))
        tn += n; tA += a; tB += b
    pooled = 100.0*(tB-tA)/tn if tn else float("nan")
    return d, pooled

def total(units):
    v = blank()
    for u in units:
        for j in range(12): v[j] += u[j]
    return v

OBS_D, OBS_POOLED = stats_from(total(CLUSTERS))

# ---------- percentile (linear interpolation between order statistics, numpy 'linear') ----------
def pct(sv, p):
    n = len(sv)
    if n == 1: return sv[0]
    x = p/100.0*(n-1)
    lo = int(math.floor(x)); hi = lo+1
    if hi >= n: return sv[-1]
    return sv[lo] + (x-lo)*(sv[hi]-sv[lo])

def mean(a): return sum(a)/len(a)
def sd(a):
    m = mean(a); n = len(a)
    return math.sqrt(sum((x-m)**2 for x in a)/(n-1))

# ---------- bootstrap engine ----------
def run_boot(units, nboot, seed, tag):
    rnd = random.Random(seed)
    U = units; U_n = len(U)
    per   = [[] for _ in range(NM)]
    pool  = []
    # pairwise model-delta differences, computed inside the SAME replicate
    pairs = [(i,j) for i in range(NM) for j in range(i+1, NM)]
    pdiff = {p: [] for p in pairs}
    rng_choices = rnd.choices
    rr = range(U_n)
    for _ in range(nboot):
        a0=a1=a2=a3=a4=a5=a6=a7=a8=a9=a10=a11=0
        for c in rng_choices(U, k=U_n):
            a0+=c[0];  a1+=c[1];  a2+=c[2]
            a3+=c[3];  a4+=c[4];  a5+=c[5]
            a6+=c[6];  a7+=c[7];  a8+=c[8]
            a9+=c[9];  a10+=c[10]; a11+=c[11]
        d0 = 100.0*(a2-a1)/a0
        d1 = 100.0*(a5-a4)/a3
        d2 = 100.0*(a8-a7)/a6
        d3 = 100.0*(a11-a10)/a9
        per[0].append(d0); per[1].append(d1); per[2].append(d2); per[3].append(d3)
        tn = a0+a3+a6+a9
        pool.append(100.0*((a2+a5+a8+a11)-(a1+a4+a7+a10))/tn)
        dd = (d0,d1,d2,d3)
        for (i,j) in pairs: pdiff[(i,j)].append(dd[i]-dd[j])
    return {"tag":tag, "per":per, "pool":pool, "pdiff":pdiff, "pairs":pairs}

def summarise(vals, obs):
    sv = sorted(vals)
    lo, hi = pct(sv,2.5), pct(sv,97.5)
    return {"obs":obs, "se":sd(vals), "lo":lo, "hi":hi, "width":hi-lo,
            "mean":mean(vals), "bias":mean(vals)-obs,
            "p_ge0":sum(1 for x in vals if x>=0)/len(vals),
            "p_le0":sum(1 for x in vals if x<=0)/len(vals)}

print("="*100)
print("DATA CHECK")
print("="*100)
print(f"cells={len(rows)}  items={NI}  clusters={K}  models={NM}")
csz = collections.Counter(len(set(r['question_id'] for r in rows if r['cluster']==c)) for c in cluster_vec)
print("items-per-cluster distribution:", dict(sorted(csz.items())))
sing = sum(1 for c in cluster_vec if len(set(r['question_id'] for r in rows if r['cluster']==c))==1)
print(f"singleton clusters: {sing}/{K}  -> items in multi-item clusters: {NI-sing}/{NI} ({100*(NI-sing)/NI:.1f}%)")
print()
for i,m in enumerate(MODELS):
    n,a,b = 0,0,0
    for v in CLUSTERS: n+=v[3*i]; a+=v[3*i+1]; b+=v[3*i+2]
    print(f"{SHORT[m]:20s} n={n}  A={100*a/n:6.2f}%  B={100*b/n:6.2f}%  delta={100*(b-a)/n:+7.2f}pp")
print(f"{'POOLED (cells)':20s} n={len(rows)}  delta={OBS_POOLED:+7.2f}pp")
print()

print("running CLUSTER bootstrap  (%d clusters, B=%d, seed=%d) ..." % (K, NBOOT, SEED))
BC = run_boot(CLUSTERS, NBOOT, SEED, "cluster")
print("running ITEM bootstrap     (%d items,    B=%d, seed=%d) ..." % (NI, NBOOT, SEED+1))
BI = run_boot(ITEMS, NBOOT, SEED+1, "item")

# ---------- analytic naive SEs ----------
# per-model d_i and A/B counts
dvec = {i:[] for i in range(NM)}
counts = {i:[0,0,0] for i in range(NM)}   # n, sumA, sumB
alld = []
for r in rows:
    i = MI[r["model"]]
    d = r["B_correct"] - r["A_correct"]
    dvec[i].append(d); alld.append(d)
    counts[i][0]+=1; counts[i][1]+=r["A_correct"]; counts[i][2]+=r["B_correct"]

naive = {}
for i in range(NM):
    n,a,b = counts[i]
    pA, pB = a/n, b/n
    se_paired = 100.0*sd(dvec[i])/math.sqrt(n)
    se_binom  = 100.0*math.sqrt(pA*(1-pA)/n + pB*(1-pB)/n)
    naive[i] = (se_paired, se_binom, n)
n = len(alld); tA = sum(counts[i][1] for i in range(NM)); tB = sum(counts[i][2] for i in range(NM))
pA, pB = tA/n, tB/n
naive["pool"] = (100.0*sd(alld)/math.sqrt(n), 100.0*math.sqrt(pA*(1-pA)/n + pB*(1-pB)/n), n)

Z = 1.959963984540054
def ci_from_se(est, se): return (est - Z*se, est + Z*se)

# ---------- report ----------
print()
print("="*100)
print("1. PER-MODEL AND POOLED A->B DELTA  --  CLUSTER BOOTSTRAP (percentile CI, B=%d)" % NBOOT)
print("="*100)
print(f"{'':20s} {'delta':>8s} {'SE_clus':>8s} {'95% CI (percentile)':>24s} {'width':>7s} {'bias':>7s} {'P(d*>=0)':>9s}")
rowsout = {}
for i,m in enumerate(MODELS):
    s = summarise(BC["per"][i], OBS_D[i]); rowsout[i]=s
    print(f"{SHORT[m]:20s} {s['obs']:+8.2f} {s['se']:8.3f}  [{s['lo']:+7.2f},{s['hi']:+7.2f}] {s['width']:7.2f} {s['bias']:+7.3f} {s['p_ge0']:9.5f}")
sp = summarise(BC["pool"], OBS_POOLED); rowsout["pool"]=sp
print(f"{'POOLED':20s} {sp['obs']:+8.2f} {sp['se']:8.3f}  [{sp['lo']:+7.2f},{sp['hi']:+7.2f}] {sp['width']:7.2f} {sp['bias']:+7.3f} {sp['p_ge0']:9.5f}")

print()
print("="*100)
print("2. HOW MUCH DO THE NAIVE PROCEDURES UNDERSTATE UNCERTAINTY?")
print("="*100)
print("   SE_clus = cluster bootstrap | SE_item = item bootstrap (no clustering)")
print("   SE_pair = sd(d_i)/sqrt(n) analytic paired | SE_bin = sqrt(pA*qA/n+pB*qB/n) naive binomial")
print()
hdr = f"{'':20s} {'SE_clus':>8s} {'SE_item':>8s} {'SE_pair':>8s} {'SE_bin':>8s} | {'clus/item':>9s} {'clus/pair':>9s} {'clus/bin':>9s} | {'DEff_item':>9s} {'DEff_bin':>9s}"
print(hdr)
ratios = {}
for key,label in [(0,SHORT[MODELS[0]]),(1,SHORT[MODELS[1]]),(2,SHORT[MODELS[2]]),(3,SHORT[MODELS[3]]),("pool","POOLED")]:
    sc = rowsout[key]["se"]
    si = sd(BI["per"][key]) if key!="pool" else sd(BI["pool"])
    sp_, sb, _ = naive[key]
    ratios[key] = (sc,si,sp_,sb)
    print(f"{label:20s} {sc:8.3f} {si:8.3f} {sp_:8.3f} {sb:8.3f} | {sc/si:9.3f} {sc/sp_:9.3f} {sc/sb:9.3f} | {(sc/si)**2:9.3f} {(sc/sb)**2:9.3f}")

print()
print("   CI widths (pp) and understatement of the 95% interval:")
print(f"{'':20s} {'clusBoot':>9s} {'itemBoot':>9s} {'Wald-pair':>10s} {'Wald-bin':>9s} | {'shrink vs item':>15s} {'shrink vs bin':>14s}")
for key,label in [(0,SHORT[MODELS[0]]),(1,SHORT[MODELS[1]]),(2,SHORT[MODELS[2]]),(3,SHORT[MODELS[3]]),("pool","POOLED")]:
    obs = rowsout[key]["obs"]
    wc = rowsout[key]["width"]
    ivals = BI["per"][key] if key!="pool" else BI["pool"]
    isv = sorted(ivals); wi = pct(isv,97.5)-pct(isv,2.5)
    sp_, sb, _ = naive[key]
    wp, wb = 2*Z*sp_, 2*Z*sb
    print(f"{label:20s} {wc:9.2f} {wi:9.2f} {wp:10.2f} {wb:9.2f} | {100*(1-wi/wc):14.1f}% {100*(1-wb/wc):13.1f}%")

print()
print("   Naive Wald intervals written out (for contrast):")
for key,label in [(0,SHORT[MODELS[0]]),(1,SHORT[MODELS[1]]),(2,SHORT[MODELS[2]]),(3,SHORT[MODELS[3]]),("pool","POOLED")]:
    obs = rowsout[key]["obs"]; sp_, sb, _ = naive[key]
    lo1,hi1 = ci_from_se(obs, sp_); lo2,hi2 = ci_from_se(obs, sb)
    print(f"{label:20s} Wald-paired [{lo1:+7.2f},{hi1:+7.2f}]   Wald-binomial [{lo2:+7.2f},{hi2:+7.2f}]   clusterBoot [{rowsout[key]['lo']:+7.2f},{rowsout[key]['hi']:+7.2f}]")

print()
print("="*100)
print("3. BETWEEN-MODEL DIFFERENCE IN DELTA  (delta_i - delta_j), CLUSTER BOOTSTRAP")
print("="*100)
print("   Each replicate resamples clusters ONCE and forms both models' deltas from the")
print("   same resampled items, so the strong item-level correlation is preserved.")
print("   p_boot = 2*min(P(diff*<=0), P(diff*>=0))  [two-sided bootstrap CI-inversion p]")
print()
print(f"{'contrast':>44s} {'diff':>8s} {'SE':>7s} {'95% CI':>22s} {'p_boot':>10s} {'SE_item':>8s} {'ratio':>6s}")
pairres = {}
for (i,j) in BC["pairs"]:
    vals = BC["pdiff"][(i,j)]
    obs = OBS_D[i]-OBS_D[j]
    s = summarise(vals, obs)
    p = 2*min(s["p_le0"], s["p_ge0"]); p = min(p,1.0)
    plab = f"{p:.5f}" if p>0 else f"<{2/NBOOT:.5f}"
    si = sd(BI["pdiff"][(i,j)])
    name = f"{SHORT[MODELS[i]]} - {SHORT[MODELS[j]]}"
    pairres[(i,j)] = (s,p,si)
    print(f"{name:>44s} {obs:+8.2f} {s['se']:7.3f}  [{s['lo']:+7.2f},{s['hi']:+7.2f}] {plab:>10s} {si:8.3f} {s['se']/si:6.3f}")

print()
print("="*100)
print("4. HEADLINE CONTRAST: gemini delta MINUS gemma delta")
print("="*100)
gi, gg = MODELS.index("google/gemini-3.6-flash"), MODELS.index("google/gemma-4-26b-a4b-it")
s,p,si = pairres[(min(gi,gg),max(gi,gg))]
sign = 1 if (gi<gg) else -1
print(f"   observed: {OBS_D[gi]:+.2f}pp - ({OBS_D[gg]:+.2f}pp) = {OBS_D[gi]-OBS_D[gg]:+.2f}pp")
print(f"   cluster-bootstrap SE = {s['se']:.3f}pp, 95% CI = [{s['lo']:+.2f},{s['hi']:+.2f}] (as ordered above), p_boot = {p:.5f}" if p>0 else
      f"   cluster-bootstrap SE = {s['se']:.3f}pp, 95% CI = [{s['lo']:+.2f},{s['hi']:+.2f}], p_boot < {2/NBOOT:.5f}")

# ---------- ICC of the per-item delta, one-way ANOVA, explains the modest inflation ----------
print()
print("="*100)
print("5. WHY THE INFLATION IS ONLY MODEST: ICC OF THE PER-ITEM DELTA WITHIN CLUSTER")
print("="*100)
print("   One-way random-effects ANOVA on d = B_correct - A_correct, groups = 208 clusters.")
print("   ICC = (MSB - MSW) / (MSB + (m0-1)*MSW),  m0 = Satterthwaite avg cluster size.")
for key,label in [(0,SHORT[MODELS[0]]),(1,SHORT[MODELS[1]]),(2,SHORT[MODELS[2]]),(3,SHORT[MODELS[3]]),("pool","POOLED")]:
    if key=="pool": sel = [(r["cluster"], r["B_correct"]-r["A_correct"]) for r in rows]
    else:           sel = [(r["cluster"], r["B_correct"]-r["A_correct"]) for r in rows if MI[r["model"]]==key]
    g = collections.defaultdict(list)
    for c,d in sel: g[c].append(d)
    N = len(sel); k = len(g); gm = sum(d for _,d in sel)/N
    SSB = sum(len(v)*(mean(v)-gm)**2 for v in g.values())
    SSW = sum(sum((x-mean(v))**2 for x in v) for v in g.values())
    if N-k <= 0 or k-1 <= 0: continue
    MSB, MSW = SSB/(k-1), SSW/(N-k)
    m0 = (N - sum(len(v)**2 for v in g.values())/N)/(k-1)
    icc = (MSB-MSW)/(MSB+(m0-1)*MSW) if (MSB+(m0-1)*MSW)!=0 else float('nan')
    deff_theory = 1 + (m0-1)*icc
    sc, sitem, _, _ = ratios[key]
    print(f"{label:20s} k={k:3d} N={N:4d} m0={m0:6.3f} ICC={icc:+.4f}  DEff_theory={deff_theory:.3f}  DEff_observed(clus/item)^2={(sc/sitem)**2:.3f}")

# ---------- persist ----------
out = {
 "n_cells":len(rows),"n_items":NI,"n_clusters":K,"n_boot":NBOOT,"seed":SEED,
 "observed":{SHORT[m]:OBS_D[i] for i,m in enumerate(MODELS)} | {"pooled":OBS_POOLED},
 "cluster_boot":{(SHORT[MODELS[k]] if k!="pool" else "pooled"):
     {kk:vv for kk,vv in rowsout[k].items()} for k in [0,1,2,3,"pool"]},
 "naive_se":{(SHORT[MODELS[k]] if k!="pool" else "pooled"):
     {"se_paired":naive[k][0],"se_binomial":naive[k][1],"n":naive[k][2]} for k in [0,1,2,3,"pool"]},
 "item_boot_se":{(SHORT[MODELS[k]] if k!="pool" else "pooled"):
     (sd(BI["per"][k]) if k!="pool" else sd(BI["pool"])) for k in [0,1,2,3,"pool"]},
 "pairwise":{f"{SHORT[MODELS[i]]}-{SHORT[MODELS[j]]}":
     {"diff":OBS_D[i]-OBS_D[j],"se":pairres[(i,j)][0]["se"],
      "lo":pairres[(i,j)][0]["lo"],"hi":pairres[(i,j)][0]["hi"],
      "p_boot":pairres[(i,j)][1],"se_item":pairres[(i,j)][2]} for (i,j) in BC["pairs"]},
}
op="/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/prim_cluster_bootstrap_results.json"
json.dump(out, open(op,"w"), indent=1)
print("\nwrote", op)

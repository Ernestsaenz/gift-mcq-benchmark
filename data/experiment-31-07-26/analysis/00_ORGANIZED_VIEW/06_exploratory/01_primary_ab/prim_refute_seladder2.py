"""
Stress tests on the SE-ladder claim:
  (1) Monte-Carlo stability of the 80.5% / 19.5% variance-share split at B=20000.
  (2) Seed-free analytic analogue via the linearization (Huber-White) route.
  (3) Is clustering inert BECAUSE of singleton dominance, or because ICC~0?
      - ICC of d within cluster (one-way random effects)
      - structural ceiling: DEff clustering could reach given the size distribution
        if ICC were 1 on the multi-item clusters
      - counterfactual: permute items across clusters keeping the size distribution
        fixed, to see what a null clustering structure looks like.
"""
import json, math, random, collections

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
rows = [r for r in json.load(open(PATH)) if r.get("analysis_include") is True]
MODELS = ["google/gemini-3.6-flash", "z-ai/glm-5.2",
          "qwen/qwen3.6-35b-a3b", "google/gemma-4-26b-a4b-it"]
MI = {m: i for i, m in enumerate(MODELS)}
NM = 4

def blank(): return [0]*12
item_vec = collections.defaultdict(blank)
clus_vec = collections.defaultdict(blank)
item2clus = {}
for r in rows:
    i = MI[r["model"]]
    for tgt in (item_vec[r["question_id"]], clus_vec[r["cluster"]]):
        tgt[3*i] += 1; tgt[3*i+1] += r["A_correct"]; tgt[3*i+2] += r["B_correct"]
    item2clus[r["question_id"]] = r["cluster"]
ITEMS = [tuple(v) for v in item_vec.values()]
CLUS = [tuple(v) for v in clus_vec.values()]
N = len(rows)
TA = sum(r["A_correct"] for r in rows); TB = sum(r["B_correct"] for r in rows)
delta0 = (TB-TA)/N
SE_CELL = None

def mean(a): return sum(a)/len(a)
def sd(a):
    m = mean(a); return math.sqrt(sum((x-m)**2 for x in a)/(len(a)-1))

d_cells = [r["B_correct"]-r["A_correct"] for r in rows]
SE_CELL = 100.0*sd(d_cells)/math.sqrt(N)

def boot_pool(units, nboot, seed):
    rnd = random.Random(seed); U = units; n = len(U); out = []
    ch = rnd.choices
    for _ in range(nboot):
        a = [0]*12
        for c in ch(U, k=n):
            for j in range(12): a[j] += c[j]
        tn = a[0]+a[3]+a[6]+a[9]
        out.append(100.0*((a[2]+a[5]+a[8]+a[11])-(a[1]+a[4]+a[7]+a[10]))/tn)
    return out

print("SE_cell(paired) = %.4f pp" % SE_CELL)
print("\n(1) MC STABILITY OF THE SHARE at B=20000, 8 independent seed pairs")
print("%6s %9s %9s %9s %9s %9s" % ("seed", "SE_item", "SE_clus", "DEff_it", "DEff_cl", "share_it%"))
shares = []; sis = []; scs = []
for s in range(8):
    ip = boot_pool(ITEMS, 20000, 900000+s)
    cp = boot_pool(CLUS, 20000, 800000+s)
    si, sc = sd(ip), sd(cp)
    di, dc = (si/SE_CELL)**2, (sc/SE_CELL)**2
    sh = 100*(di-1)/(dc-1)
    shares.append(sh); sis.append(si); scs.append(sc)
    print("%6d %9.4f %9.4f %9.4f %9.4f %9.1f" % (900000+s, si, sc, di, dc, sh))
print("  SE_item : mean %.4f  sd %.4f" % (mean(sis), sd(sis)))
print("  SE_clus : mean %.4f  sd %.4f" % (mean(scs), sd(scs)))
print("  share   : mean %.1f%% sd %.1f pp  range [%.1f, %.1f]"
      % (mean(shares), sd(shares), min(shares), max(shares)))

print("\n(2) SEED-FREE LINEARIZATION ANALOGUE")
def lin_se(groups):
    tot = 0.0
    for g, v in groups.items():
        n_g = sum(v[3*i] for i in range(NM))
        S_g = sum(v[3*i+2]-v[3*i+1] for i in range(NM))
        tot += (S_g - delta0*n_g)**2
    K = len(groups)
    return 100.0*math.sqrt((K/(K-1.0))*tot/(N*N))
cellg = {k: None for k in range(N)}
se_lin_item = lin_se(item_vec)
se_lin_clus = lin_se(clus_vec)
di = (se_lin_item/SE_CELL)**2; dc = (se_lin_clus/SE_CELL)**2
print("  SE_item(lin)=%.4f  SE_clus(lin)=%.4f  DEff_it=%.4f DEff_cl=%.4f  share_item=%.1f%%"
      % (se_lin_item, se_lin_clus, di, dc, 100*(di-1)/(dc-1)))

print("\n(3a) ICC of d within cluster (one-way random effects, pooled cells)")
g = collections.defaultdict(list)
for r in rows: g[r["cluster"]].append(r["B_correct"]-r["A_correct"])
Nn = N; k = len(g); gm = delta0
SSB = sum(len(v)*(mean(v)-gm)**2 for v in g.values())
SSW = sum(sum((x-mean(v))**2 for x in v) for v in g.values())
MSB, MSW = SSB/(k-1), SSW/(Nn-k)
m0 = (Nn - sum(len(v)**2 for v in g.values())/Nn)/(k-1)
icc = (MSB-MSW)/(MSB+(m0-1)*MSW)
print("  k=%d N=%d m0=%.3f MSB=%.4f MSW=%.4f  ICC=%+.4f  DEff_theory=1+(m0-1)*ICC=%.3f"
      % (k, Nn, m0, MSB, MSW, icc, 1+(m0-1)*icc))

print("\n(3b) STRUCTURAL CEILING: what if items within a cluster were perfectly correlated?")
# ICC=1 -> each cluster contributes as one observation; DEff = N * sum(n_c^2)/ (sum n_c)^2 ... use
# Kish-type: DEff_max = sum_c n_c^2 / N  * (K/... ) ; simpler: effective n = N^2 / sum n_c^2
sizes = []
for c, v in clus_vec.items():
    sizes.append(sum(v[3*i] for i in range(NM)))
n_eff_max = N*N/sum(s*s for s in sizes)
print("  cluster cell-size distribution: %s" % sorted(sizes, reverse=True)[:14])
print("  with ICC=1 the effective n would be %.1f  ->  DEff ceiling from clustering = %.3f"
      % (n_eff_max, N/n_eff_max))
print("  observed marginal DEff from clustering (DEff_cl/DEff_it) = %.3f" % (dc/di))
print("  -> observed inflation uses %.1f%% of the structurally available headroom"
      % (100*(dc/di-1)/(N/n_eff_max-1)))

print("\n(3c) COUNTERFACTUAL: reassign items to clusters at random, size distribution FIXED")
# If singleton-dominance were the reason clustering is inert, a random reassignment
# (which has ICC=0 by construction) would reproduce the observed cluster SE.
sizes_items = sorted((len(set(r['question_id'] for r in rows if r['cluster']==c)))
                     for c in clus_vec)
qids = list(item_vec.keys())
rnd = random.Random(4242)
null_ses = []
for rep in range(400):
    rnd.shuffle(qids)
    pos = 0; groups = {}
    for gi, sz in enumerate(sizes_items):
        v = blank()
        for q in qids[pos:pos+sz]:
            iv = item_vec[q]
            for j in range(12): v[j] += iv[j]
        groups[gi] = v; pos += sz
    null_ses.append(lin_se(groups))
null_ses.sort()
print("  null (ICC=0) cluster-robust SE: mean %.4f  2.5%%=%.4f  97.5%%=%.4f"
      % (mean(null_ses), null_ses[10], null_ses[-10]))
print("  OBSERVED cluster-robust SE (lin) = %.4f" % se_lin_clus)
above = sum(1 for x in null_ses if x >= se_lin_clus)/len(null_ses)
print("  permutation p (P[null SE >= observed]) = %.3f" % above)
print("  item-robust (no clustering) SE   = %.4f" % se_lin_item)

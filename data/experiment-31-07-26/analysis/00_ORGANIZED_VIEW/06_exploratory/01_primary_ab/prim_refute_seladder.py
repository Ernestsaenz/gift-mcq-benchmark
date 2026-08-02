"""
INDEPENDENT recomputation of the three-level SE ladder claim.
Pure stdlib. Written from scratch (does not import prim_01_cluster_bootstrap).

Levels:
  L1 cell-independent : two candidate baselines
        (a) paired      SE = sd(d_cell)/sqrt(Ncell),  d = B_correct - A_correct
        (b) binomial    SE = sqrt(pA*qA/n + pB*qB/n)  (also ignores A/B pairing)
  L2 item bootstrap   : resample 325 items w/ replacement (item carries its model rows)
  L3 cluster bootstrap: resample 208 clusters w/ replacement
Plus the linearization (Huber-White cluster-robust) variance decomposition.
"""
import json, math, random, collections

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
rows = [r for r in json.load(open(PATH)) if r.get("analysis_include") is True]

MODELS = ["google/gemini-3.6-flash", "z-ai/glm-5.2",
          "qwen/qwen3.6-35b-a3b", "google/gemma-4-26b-a4b-it"]
SHORT = {"google/gemini-3.6-flash": "gemini-3.6-flash", "z-ai/glm-5.2": "glm-5.2",
         "qwen/qwen3.6-35b-a3b": "qwen3.6-35b-a3b",
         "google/gemma-4-26b-a4b-it": "gemma-4-26b-a4b-it"}
MI = {m: i for i, m in enumerate(MODELS)}
NM = 4

items = sorted(set(r["question_id"] for r in rows))
clusters = sorted(set(r["cluster"] for r in rows))
print("cells=%d items=%d clusters=%d models=%d" % (len(rows), len(items), len(clusters),
                                                   len(set(r["model"] for r in rows))))

# ---- observed marginals --------------------------------------------------
print("\n--- OBSERVED (clean subset) ---")
tot = [0, 0, 0]
for m in MODELS:
    sub = [r for r in rows if r["model"] == m]
    n = len(sub); a = sum(r["A_correct"] for r in sub); b = sum(r["B_correct"] for r in sub)
    tot[0] += n; tot[1] += a; tot[2] += b
    print("%-20s n=%4d A=%6.2f%% B=%6.2f%% d=%+7.2fpp" % (SHORT[m], n, 100*a/n, 100*b/n, 100*(b-a)/n))
N, TA, TB = tot
DELTA = 100.0*(TB-TA)/N
print("%-20s n=%4d A=%6.2f%% B=%6.2f%% d=%+7.2fpp" % ("POOLED", N, 100*TA/N, 100*TB/N, DELTA))

# ---- unit aggregation ----------------------------------------------------
def blank(): return [0]*12
item_vec = collections.defaultdict(blank)
clus_vec = collections.defaultdict(blank)
item_of_cluster = collections.defaultdict(set)
for r in rows:
    i = MI[r["model"]]
    for tgt in (item_vec[r["question_id"]], clus_vec[r["cluster"]]):
        tgt[3*i] += 1
        tgt[3*i+1] += r["A_correct"]
        tgt[3*i+2] += r["B_correct"]
    item_of_cluster[r["cluster"]].add(r["question_id"])

ITEMS = [tuple(v) for v in item_vec.values()]
CLUS  = [tuple(v) for v in clus_vec.values()]

# ---- cluster size distribution ------------------------------------------
size_items = collections.Counter(len(v) for v in item_of_cluster.values())
print("\n--- cluster size distribution (ITEMS per cluster) ---")
print(dict(sorted(size_items.items())))
multi_sizes = sorted(len(v) for v in item_of_cluster.values() if len(v) > 1)
n_single = sum(1 for v in item_of_cluster.values() if len(v) == 1)
n_multi_items = sum(multi_sizes)
print("singleton clusters = %d / %d ; multi-item clusters = %d holding %d items (%.1f%% of items)"
      % (n_single, len(clusters), len(multi_sizes), n_multi_items,
         100*n_multi_items/len(items)))
print("multi-item cluster sizes (items):", multi_sizes)
cells_multi = sum(sum(clus_vec[c][3*i] for i in range(NM))
                  for c in clusters if len(item_of_cluster[c]) > 1)
print("cells in multi-item clusters = %d / %d (%.1f%% of cells)" % (cells_multi, N, 100*cells_multi/N))

# ---- helpers -------------------------------------------------------------
def mean(a): return sum(a)/len(a)
def sd(a):
    m = mean(a); return math.sqrt(sum((x-m)**2 for x in a)/(len(a)-1))

# ---- L1 analytic ---------------------------------------------------------
print("\n--- L1 cell-independent baselines ---")
base = {}
for key in list(range(NM)) + ["pool"]:
    sub = rows if key == "pool" else [r for r in rows if MI[r["model"]] == key]
    d = [r["B_correct"] - r["A_correct"] for r in sub]
    n = len(sub)
    pA = sum(r["A_correct"] for r in sub)/n
    pB = sum(r["B_correct"] for r in sub)/n
    se_pair = 100.0*sd(d)/math.sqrt(n)
    se_bin = 100.0*math.sqrt(pA*(1-pA)/n + pB*(1-pB)/n)
    base[key] = (se_pair, se_bin)
    lab = "POOLED" if key == "pool" else SHORT[MODELS[key]]
    print("%-20s SE_paired=%.4f  SE_binomial=%.4f" % (lab, se_pair, se_bin))

# ---- bootstrap engine ----------------------------------------------------
def boot(units, nboot, seed):
    rnd = random.Random(seed)
    U = units; n = len(U)
    per = [[] for _ in range(NM)]; pool = []
    ch = rnd.choices
    for _ in range(nboot):
        acc = [0]*12
        for c in ch(U, k=n):
            for j in range(12):
                acc[j] += c[j]
        tn = ta = tb = 0
        for i in range(NM):
            nn, a, b = acc[3*i], acc[3*i+1], acc[3*i+2]
            per[i].append(100.0*(b-a)/nn if nn else float("nan"))
            tn += nn; ta += a; tb += b
        pool.append(100.0*(tb-ta)/tn)
    return per, pool

B = 20000
print("\nrunning bootstraps B=%d ..." % B)
IP, IPOOL = boot(ITEMS, B, 20260732)   # seed claimed for the item bootstrap
CP, CPOOL = boot(CLUS,  B, 20260731)

print("\n--- SE LADDER (pp) ---")
print("%-20s %9s %9s %9s | %8s %8s | %9s" %
      ("", "SE_pairCell", "SE_item", "SE_clus", "DEff_it", "DEff_cl", "clus/item"))
for key in list(range(NM)) + ["pool"]:
    lab = "POOLED" if key == "pool" else SHORT[MODELS[key]]
    s1 = base[key][0]
    si = sd(IPOOL) if key == "pool" else sd(IP[key])
    sc = sd(CPOOL) if key == "pool" else sd(CP[key])
    print("%-20s %9.4f %9.4f %9.4f | %8.4f %8.4f | %9.4f" %
          (lab, s1, si, sc, (si/s1)**2, (sc/s1)**2, sc/si))

s1 = base["pool"][0]; si = sd(IPOOL); sc = sd(CPOOL)
d_it, d_cl = (si/s1)**2, (sc/s1)**2
print("\nPOOLED variance-inflation shares using (DEff-1) fractions:")
print("  item x model share = (%.4f-1)/(%.4f-1) = %.1f%%" % (d_it, d_cl, 100*(d_it-1)/(d_cl-1)))
print("  clustering  share  = %.1f%%" % (100*(d_cl-d_it)/(d_cl-1)))

# same but with the BINOMIAL baseline
s1b = base["pool"][1]
d_itb, d_clb = (si/s1b)**2, (sc/s1b)**2
print("  [if baseline were the naive BINOMIAL SE=%.4f: DEff_item=%.3f DEff_clus=%.3f]"
      % (s1b, d_itb, d_clb))

# ---- MC stability of the bootstrap SEs ----------------------------------
print("\n--- Monte-Carlo stability of pooled SEs across 5 seeds ---")
for s in (11, 22, 33, 44, 55):
    _, ip = boot(ITEMS, 5000, s)
    _, cp = boot(CLUS, 5000, s+1000)
    print("  seed %2d: SE_item=%.4f SE_clus=%.4f  shares item=%.1f%%" %
          (s, sd(ip), sd(cp),
           100*(((sd(ip)/s1)**2)-1)/(((sd(cp)/s1)**2)-1)))

# ---- linearization / cluster-robust decomposition ------------------------
# delta_hat = 100 * sum_cells (B-A) / N  -> ratio estimator with random N under
# cluster resampling. Linearized influence for cluster c: (S_c - delta0*n_c)
# with delta0 = (TB-TA)/N on the 0-1 scale.
print("\n--- linearization decomposition over clusters ---")
delta0 = (TB-TA)/N
contrib = {}
for c in clusters:
    v = clus_vec[c]
    n_c = sum(v[3*i] for i in range(NM))
    S_c = sum(v[3*i+2] - v[3*i+1] for i in range(NM))
    contrib[c] = ((S_c - delta0*n_c)**2, n_c, S_c, len(item_of_cluster[c]))
tot_var = sum(x[0] for x in contrib.values())
mult = sum(x[0] for c, x in contrib.items() if x[3] > 1)
print("grand mean d = %.4f" % delta0)
print("sum of squared cluster residuals = %.4f" % tot_var)
print("share of that from the %d MULTI-item clusters = %.1f%%  (they hold %.1f%% of cells)"
      % (len(multi_sizes), 100*mult/tot_var, 100*cells_multi/N))
print("share from the %d SINGLETON clusters = %.1f%%" % (n_single, 100*(tot_var-mult)/tot_var))

# cluster-robust SE from the linearization, for reference
K = len(clusters)
var_lin = (K/(K-1.0))*tot_var/(N*N)
print("linearization cluster-robust SE = %.4f pp" % (100*math.sqrt(var_lin)))
var_lin_item = None
NIu = len(items)
tot_item = 0.0
for q in items:
    v = item_vec[q]
    n_q = sum(v[3*i] for i in range(NM))
    S_q = sum(v[3*i+2] - v[3*i+1] for i in range(NM))
    tot_item += (S_q - delta0*n_q)**2
var_lin_item = (NIu/(NIu-1.0))*tot_item/(N*N)
print("linearization item-robust    SE = %.4f pp" % (100*math.sqrt(var_lin_item)))
print("cell-level (no clustering) robust SE = %.4f pp" %
      (100*math.sqrt((N/(N-1.0))*sum(((r["B_correct"]-r["A_correct"])-delta0)**2 for r in rows)/(N*N))))

print("\ntop clusters by |contribution| :")
ranked = sorted(contrib.items(), key=lambda kv: -kv[1][0])[:12]
for c, (sq, n_c, S_c, ni) in ranked:
    print("  cluster %-4s items=%2d cells=%3d meand=%+.4f  contrib=%6.2f%%"
          % (c, ni, n_c, S_c/n_c, 100*sq/tot_var))
print("\nlargest clusters by cells:")
for c, (sq, n_c, S_c, ni) in sorted(contrib.items(), key=lambda kv: -kv[1][1])[:12]:
    print("  cluster %-4s items=%2d cells=%3d meand=%+.4f  contrib=%6.2f%%"
          % (c, ni, n_c, S_c/n_c, 100*sq/tot_var))

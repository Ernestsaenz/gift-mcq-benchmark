"""Part 3: leave-one-cluster-out influence on the three gemini contrasts,
plus a leave-one-cluster-out re-run of the full Holm decision for the most
influential clusters. Stdlib only."""
import json, math, random, collections

PATH = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
rows = [r for r in json.load(open(PATH)) if r.get("analysis_include") is True]
MODELS = ["google/gemini-3.6-flash", "z-ai/glm-5.2",
          "qwen/qwen3.6-35b-a3b", "google/gemma-4-26b-a4b-it"]
SHORT = {"google/gemini-3.6-flash": "gemini", "z-ai/glm-5.2": "glm",
         "qwen/qwen3.6-35b-a3b": "qwen", "google/gemma-4-26b-a4b-it": "gemma"}
MI = {m: i for i, m in enumerate(MODELS)}
PAIRS = [(0, 1), (0, 3), (0, 2), (2, 3), (1, 2), (1, 3)]
NAMES = {p: f"{SHORT[MODELS[p[0]]]} - {SHORT[MODELS[p[1]]]}" for p in PAIRS}

tmp = collections.defaultdict(lambda: [0] * 12)
for r in rows:
    i = MI[r["model"]]; v = tmp[r["cluster"]]
    v[3 * i] += 1; v[3 * i + 1] += r["A_correct"]; v[3 * i + 2] += r["B_correct"]
keys = sorted(tmp)
CL = [tuple(tmp[k]) for k in keys]
K = len(CL)


def drops(acc):
    return [100.0 * (acc[3 * i + 1] - acc[3 * i + 2]) / acc[3 * i] if acc[3 * i] else None
            for i in range(4)]


def contrasts_of(cls):
    acc = [0] * 12
    for c in cls:
        for j in range(12):
            acc[j] += c[j]
    d = drops(acc)
    return {p: d[p[0]] - d[p[1]] for p in PAIRS}


def holm(pd_, ks):
    order = sorted(ks, key=lambda k: pd_[k]); m = len(ks); out = {}; run = 0.0
    for r_, k in enumerate(order):
        run = max(run, (m - r_) * pd_[k]); out[k] = min(1.0, run)
    return out


def pctl(sv, q):
    m = len(sv); x = q / 100.0 * (m - 1); lo = int(math.floor(x)); hi = min(lo + 1, m - 1)
    return sv[lo] + (x - lo) * (sv[hi] - sv[lo])


def boot_holm(cls, Bn, seed):
    kk = len(cls); rnd = random.Random(seed)
    rep = {p: [] for p in PAIRS}
    for _ in range(Bn):
        acc = [0] * 12
        for c in rnd.choices(cls, k=kk):
            for j in range(12):
                acc[j] += c[j]
        d = drops(acc)
        if any(x is None for x in d):
            continue
        for p in PAIRS:
            rep[p].append(d[p[0]] - d[p[1]])
    praw = {}
    for p in PAIRS:
        v = rep[p]; Bf = len(v)
        le = sum(1 for x in v if x <= 0); ge = sum(1 for x in v if x >= 0)
        praw[p] = min(1.0, 2 * min((le + 1) / (Bf + 1), (ge + 1) / (Bf + 1)))
    return praw, holm(praw, PAIRS)


FULL = contrasts_of(CL)
GEM = [(0, 1), (0, 3), (0, 2)]

print("=" * 100)
print("LEAVE-ONE-CLUSTER-OUT INFLUENCE ON THE THREE GEMINI CONTRASTS (K=%d)" % K)
print("=" * 100)
loo = {p: [] for p in PAIRS}
for x in range(K):
    sub = CL[:x] + CL[x + 1:]
    c = contrasts_of(sub)
    for p in PAIRS:
        loo[p].append((c[p], keys[x]))
for p in GEM:
    vals = sorted(loo[p])
    signflip = sum(1 for v, _ in vals if v >= 0)
    print(f"\n{NAMES[p]:16s} full={FULL[p]:+7.3f}pp")
    print(f"   LOO range: [{vals[0][0]:+7.3f}, {vals[-1][0]:+7.3f}]   "
          f"# LOO estimates with sign flip (>=0): {signflip}")
    print(f"   most attenuating cluster: {vals[-1][1]} -> {vals[-1][0]:+7.3f}  "
          f"(shift {vals[-1][0]-FULL[p]:+.3f}pp)")
    print(f"   most amplifying  cluster: {vals[0][1]} -> {vals[0][0]:+7.3f}  "
          f"(shift {vals[0][0]-FULL[p]:+.3f}pp)")

# re-run the whole Holm decision dropping the single most attenuating cluster for
# the marginal contrast (gemini - qwen)
worst = max(loo[(0, 2)])[1]
idx = keys.index(worst)
sub = CL[:idx] + CL[idx + 1:]
print()
print("=" * 100)
print(f"RE-RUN FULL HOLM DECISION AFTER DROPPING THE MOST ATTENUATING CLUSTER FOR gemini-qwen "
      f"(cluster {worst}), B=50000")
print("=" * 100)
praw, H = boot_holm(sub, 50000, 909)
c2 = contrasts_of(sub)
for p in sorted(PAIRS, key=lambda q: praw[q]):
    print(f"   {NAMES[p]:>16s} obs={c2[p]:+7.3f}  p={praw[p]:.5f}  Holm={H[p]:.5f}"
          + ("  *" if H[p] < 0.05 else ""))
print(f"-> survive Holm: {sum(1 for p in PAIRS if H[p] < 0.05)}   "
      f"gemini contrasts surviving: {sum(1 for p in GEM if H[p] < 0.05)}/3")

# and drop the 3 most attenuating clusters for gemini-qwen simultaneously
drop3 = [k for _, k in sorted(loo[(0, 2)], reverse=True)[:3]]
sub3 = [c for k, c in zip(keys, CL) if k not in drop3]
print()
print(f"DROPPING THE 3 MOST ATTENUATING CLUSTERS FOR gemini-qwen {drop3}, B=50000")
praw3, H3 = boot_holm(sub3, 50000, 910)
c3 = contrasts_of(sub3)
for p in sorted(PAIRS, key=lambda q: praw3[q]):
    print(f"   {NAMES[p]:>16s} obs={c3[p]:+7.3f}  p={praw3[p]:.5f}  Holm={H3[p]:.5f}"
          + ("  *" if H3[p] < 0.05 else ""))
print(f"-> survive Holm: {sum(1 for p in PAIRS if H3[p] < 0.05)}   "
      f"gemini contrasts surviving: {sum(1 for p in GEM if H3[p] < 0.05)}/3")

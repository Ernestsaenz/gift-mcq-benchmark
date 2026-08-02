"""
Part 2: does the INTERPRETATION ("gemini loses significantly less than every other
model") survive methods that do not depend on the bootstrap, and scales other than
raw percentage points?  Stdlib only.
"""
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


def holm(pd_, keys):
    order = sorted(keys, key=lambda k: pd_[k]); m = len(keys); out = {}; run = 0.0
    for r_, k in enumerate(order):
        run = max(run, (m - r_) * pd_[k]); out[k] = min(1.0, run)
    return out


tmp = collections.defaultdict(lambda: [0] * 12)
for r in rows:
    i = MI[r["model"]]; v = tmp[r["cluster"]]
    v[3 * i] += 1; v[3 * i + 1] += r["A_correct"]; v[3 * i + 2] += r["B_correct"]
CL = [tuple(v) for v in tmp.values()]
K = len(CL)
tot = [0] * 12
for c in CL:
    for j in range(12):
        tot[j] += c[j]
DROP = [100.0 * (tot[3 * i + 1] - tot[3 * i + 2]) / tot[3 * i] for i in range(4)]
OBS = {p: DROP[p[0]] - DROP[p[1]] for p in PAIRS}

# ---------- A. cluster sign-flip permutation (independent of the bootstrap) ----------
print("=" * 100)
print("A. CLUSTER SIGN-FLIP PERMUTATION, 50000 flips/pair, seed 5150")
print("   H0: the two models' cluster-level A->B loss profiles are exchangeable")
print("=" * 100)
NP = 50000
pperm = {}
for p in PAIRS:
    i, j = p
    per = [(c[3 * i + 1] - c[3 * i + 2], c[3 * i], c[3 * j + 1] - c[3 * j + 2], c[3 * j]) for c in CL]
    Ni = sum(x[1] for x in per); Nj = sum(x[3] for x in per)
    obs = abs(100.0 * sum(x[0] for x in per) / Ni - 100.0 * sum(x[2] for x in per) / Nj)
    rr = random.Random(5150 + i * 10 + j); cnt = 0
    for _ in range(NP):
        ai = aj = 0
        for si, ni, sj, nj in per:
            if rr.getrandbits(1):
                ai += si; aj += sj
            else:
                ai += sj; aj += si
        if abs(100.0 * ai / Ni - 100.0 * aj / Nj) >= obs - 1e-12:
            cnt += 1
    pperm[p] = (cnt + 1) / (NP + 1)
Hp = holm(pperm, PAIRS)
for p in sorted(PAIRS, key=lambda q: pperm[q]):
    print(f"{NAMES[p]:>16s}  obs={OBS[p]:+7.3f}pp   p_perm={pperm[p]:.5f}   Holm={Hp[p]:.5f}"
          + ("   *" if Hp[p] < 0.05 else ""))
print(f"-> survive Holm at 0.05 (permutation): {sum(1 for p in PAIRS if Hp[p] < 0.05)}")

# ---------- B. alternative scales ----------
print()
print("=" * 100)
print("B. IS THE RESULT AN ARTIFACT OF THE PERCENTAGE-POINT SCALE? (gemini A=97.9%, gemma A=79.4%)")
print("=" * 100)
# per-model 2x2 paired table over items
tab = {}
for i, m in enumerate(MODELS):
    n11 = n10 = n01 = n00 = 0
    for r in rows:
        if MI[r["model"]] != i:
            continue
        a, b = r["A_correct"], r["B_correct"]
        if a and b: n11 += 1
        elif a and not b: n10 += 1
        elif (not a) and b: n01 += 1
        else: n00 += 1
    tab[i] = (n11, n10, n01, n00)
    N = n11 + n10 + n01 + n00
    ret = n11 / (n11 + n10)
    print(f"{SHORT[m]:7s} n11={n11:3d} n10={n10:3d} n01={n01:3d} n00={n00:3d} | "
          f"A={100*(n11+n10)/N:5.1f}% B={100*(n11+n01)/N:5.1f}% "
          f"retention P(B+|A+)={100*ret:5.1f}%  rel.drop={100*(n10-n01)/(n11+n10):5.1f}%")
print()
print("gemini has the HIGHEST A accuracy, i.e. the MOST headroom to fall, yet the")
print("SMALLEST absolute drop -- so the pp scale is conservative against gemini, not for it.")


# ---------- C. same bootstrap, three alternative estimands ----------
def pctl(sv, q):
    m = len(sv); x = q / 100.0 * (m - 1); lo = int(math.floor(x)); hi = min(lo + 1, m - 1)
    return sv[lo] + (x - lo) * (sv[hi] - sv[lo])


ESTIMANDS = {
    "raw pp drop (A-B)": lambda nA, sA, sB, n11, n10, n01: 100.0 * (sA - sB) / nA,
    "retention P(B+|A+)": lambda nA, sA, sB, n11, n10, n01: 100.0 * n11 / (n11 + n10) if (n11 + n10) else None,
    "relative drop (A-B)/A": lambda nA, sA, sB, n11, n10, n01: 100.0 * (sA - sB) / sA if sA else None,
    "log-odds A minus log-odds B": lambda nA, sA, sB, n11, n10, n01: (
        math.log(((sA + .5) / (nA - sA + .5))) - math.log(((sB + .5) / (nA - sB + .5)))),
}

# cluster vectors with the 2x2 cells
tmp2 = collections.defaultdict(lambda: [0] * 20)
for r in rows:
    i = MI[r["model"]]; v = tmp2[r["cluster"]]
    a, b = r["A_correct"], r["B_correct"]
    v[5 * i] += 1; v[5 * i + 1] += a; v[5 * i + 2] += b
    v[5 * i + 3] += 1 if (a and b) else 0
    v[5 * i + 4] += 1 if (a and not b) else 0
CL2 = [tuple(v) for v in tmp2.values()]


def stat(acc, f):
    out = []
    for i in range(4):
        nA = acc[5 * i]; sA = acc[5 * i + 1]; sB = acc[5 * i + 2]
        n11 = acc[5 * i + 3]; n10 = acc[5 * i + 4]; n01 = sB - n11
        out.append(f(nA, sA, sB, n11, n10, n01) if nA else None)
    return out


print()
print("=" * 100)
print("C. SAME CLUSTER BOOTSTRAP (B=20000, seed 31337) ON FOUR DIFFERENT ESTIMANDS")
print("   question: do the 3 gemini contrasts still survive Holm on every scale?")
print("=" * 100)
summary = {}
for label, f in ESTIMANDS.items():
    tot2 = [0] * 20
    for c in CL2:
        for j in range(20):
            tot2[j] += c[j]
    ob = stat(tot2, f)
    obsp = {p: ob[p[0]] - ob[p[1]] for p in PAIRS}
    rnd = random.Random(31337)
    rep = {p: [] for p in PAIRS}
    for _ in range(20000):
        acc = [0] * 20
        for c in rnd.choices(CL2, k=K):
            for j in range(20):
                acc[j] += c[j]
        d = stat(acc, f)
        if any(x is None for x in d):
            continue
        for p in PAIRS:
            rep[p].append(d[p[0]] - d[p[1]])
    praw = {}
    ci = {}
    for p in PAIRS:
        v = rep[p]; Bf = len(v)
        le = sum(1 for x in v if x <= 0); ge = sum(1 for x in v if x >= 0)
        praw[p] = min(1.0, 2 * min((le + 1) / (Bf + 1), (ge + 1) / (Bf + 1)))
        sv = sorted(v); ci[p] = (pctl(sv, 2.5), pctl(sv, 97.5))
    Hx = holm(praw, PAIRS)
    ns = sum(1 for p in PAIRS if Hx[p] < 0.05)
    gem = [p for p in PAIRS if 0 in p]
    ngem = sum(1 for p in gem if Hx[p] < 0.05)
    print(f"\n-- estimand: {label}")
    for p in sorted(PAIRS, key=lambda q: praw[q]):
        print(f"   {NAMES[p]:>16s} obs={obsp[p]:+8.3f}  CI[{ci[p][0]:+8.3f},{ci[p][1]:+8.3f}]  "
              f"p={praw[p]:.5f} Holm={Hx[p]:.5f}" + ("  *" if Hx[p] < 0.05 else ""))
    print(f"   => {ns} survive Holm; {ngem}/3 of the gemini contrasts survive")
    summary[label] = {"n_surv": ns, "n_gem_surv": ngem,
                      "detail": {NAMES[p]: {"obs": obsp[p], "ci": ci[p], "p": praw[p], "holm": Hx[p]} for p in PAIRS}}

print()
print("=" * 100)
print("SUMMARY ACROSS SCALES")
print("=" * 100)
for k, v in summary.items():
    print(f"   {k:32s}: {v['n_surv']} total survive, {v['n_gem_surv']}/3 gemini contrasts survive")
print(f"   {'cluster sign-flip permutation':32s}: {sum(1 for p in PAIRS if Hp[p]<0.05)} total survive, "
      f"{sum(1 for p in PAIRS if 0 in p and Hp[p]<0.05)}/3 gemini contrasts survive")

json.dump({"p_perm": {NAMES[p]: pperm[p] for p in PAIRS},
           "holm_perm": {NAMES[p]: Hp[p] for p in PAIRS},
           "tables": {SHORT[MODELS[i]]: tab[i] for i in range(4)},
           "scales": summary},
          open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/prim_refute_model_contrasts2.json", "w"), indent=1)
print("\nwrote prim_refute_model_contrasts2.json")

#!/usr/bin/env python
"""Does the cross-arm A headline survive the corrected out-of-domain exclusion list?"""
import json, math, collections, itertools, random

AN = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/"
J = json.load(open(AN + "cross_arm_A.json"))
cells = [c for c in J if c["analysis_include"]]
EXTRA = {"b213", "b293", "b361", "b396", "b407", "b433", "b445", "b451"}

def chi2sf1(x): return math.erfc(math.sqrt(x / 2.0)) if x > 0 else 1.0
def lch(n, k): return math.lgamma(n+1) - math.lgamma(k+1) - math.lgamma(n-k+1)
def pmf(n, k): return math.exp(lch(n, k) - n * math.log(2.0))
def exact2(k, n):
    if n == 0: return 1.0
    pk = pmf(n, k)
    return min(1.0, sum(pmf(n, i) for i in range(n+1) if pmf(n, i) <= pk * (1+1e-12)))

def report(rows, label):
    n = len(rows)
    g = sum(r["gift_correct"] for r in rows); o = sum(r["or_correct"] for r in rows)
    b = sum(1 for r in rows if r["gift_correct"] and not r["or_correct"])
    c = sum(1 for r in rows if not r["gift_correct"] and r["or_correct"])
    nd = b + c
    cu = ((b-c)**2)/nd if nd else float('nan')
    cc = ((abs(b-c)-1)**2)/nd if nd else float('nan')
    print("%-22s items=%3d cells=%4d clus=%3d | GIFT %6.2f%% OR %6.2f%% d=%+5.2fpp | b=%2d c=%2d "
          "chi2u=%6.3f p=%.4f | chi2c=%6.3f p=%.4f | exact p=%.4f"
          % (label, len(set(r["question_id"] for r in rows)), n,
             len(set(r["cluster"] for r in rows)),
             100.0*g/n, 100.0*o/n, 100.0*(g-o)/n, b, c, cu, chi2sf1(cu), cc, chi2sf1(cc),
             exact2(b, nd) if nd else float('nan')))
    return dict(n=n, b=b, c=c, d=100.0*(g-o)/n)

print("=== POOLED ===")
report(cells, "as shipped (311)")
corr = [r for r in cells if r["question_id"] not in EXTRA]
report(corr, "corrected (306)")

print("\n=== the 5 dropped items only ===")
only = [r for r in cells if r["question_id"] in EXTRA]
report(only, "the 5 law/mgmt items")
for q in sorted(set(r["question_id"] for r in only)):
    rs = [r for r in only if r["question_id"] == q]
    print("   %-6s gift=%s or=%s" % (q, "".join(str(r["gift_correct"]) for r in sorted(rs, key=lambda x: x["model"])),
                                        "".join(str(r["or_correct"]) for r in sorted(rs, key=lambda x: x["model"]))))
print("   model order:", sorted(set(r["model"] for r in only)))

print("\n=== PER MODEL, as shipped vs corrected ===")
for m in sorted(set(r["model"] for r in cells)):
    report([r for r in cells if r["model"] == m], m.split("/")[-1] + " 311")
    report([r for r in corr  if r["model"] == m], m.split("/")[-1] + " 306")

# cluster arm-flip exact DP on the corrected set
def cluster_exact(rows):
    d = collections.defaultdict(int)
    for r in rows: d[r["cluster"]] += r["gift_correct"] - r["or_correct"]
    nz = [v for v in d.values() if v]; T = sum(d.values())
    off = sum(abs(v) for v in nz); dist = [0.0]*(2*off+1); dist[off] = 1.0
    for v in nz:
        nd = [0.0]*(2*off+1)
        for i, p in enumerate(dist):
            if p: nd[i+v] += p*.5; nd[i-v] += p*.5
        dist = nd
    return T, sum(p for i, p in enumerate(dist) if abs(i-off) >= abs(T))
for rows, lab in ((cells, "as shipped (311)"), (corr, "corrected (306)")):
    T, p = cluster_exact(rows)
    print("\ncluster arm-flip EXACT (DP)  %-18s T=%+d  p=%.5f" % (lab, T, p))

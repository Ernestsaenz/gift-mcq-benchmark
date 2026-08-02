"""Which heterogeneity p-value should be believed?

On the unfiltered set the cluster-robust Cochran Q / chi-square route reports
p=0.0015 for `year` while the permutation Q reports p=0.032. The Cochran route
uses a CR0-type cluster-robust variance per level, and some year levels contain
only 6-8 clusters, where CR0 is badly downward biased -> Q inflated -> p too
small.

This script measures that directly: generate the exact permutation null (shuffle
the level label across whole clusters, which is a true H0 of homogeneity),
recompute the Cochran-Q chi-square p-value on every draw, and report its actual
type-I error rate. A well-calibrated p-value rejects 5% of the time at .05.
"""
import random
import sys
from collections import defaultdict

sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/"
                   "tier1_mcq/data/experiment-31-07-26/analysis")
from sens_strata_lib import load, delta  # noqa
from sens_strata_hetero import chi2_sf  # noqa

B = 4000
SEED = 20260731


def cochran_from_clusters(S, N, labels, levels):
    """Cochran Q + chi-square p, computed from per-cluster (sum delta, n cells).
    Valid because these stratifiers are constant within cluster."""
    ss = defaultdict(float); nn = defaultdict(int)
    members = defaultdict(list)
    for s, n, l in zip(S, N, labels):
        ss[l] += s; nn[l] += n
        members[l].append((s, n))
    d = {}; v = {}
    for l in levels:
        if nn[l] == 0 or len(members[l]) < 2:
            continue
        dk = ss[l] / nn[l]
        G = len(members[l])
        q = sum((s - n * dk) ** 2 for s, n in members[l])
        vk = (G / (G - 1.0)) * q / (nn[l] ** 2)
        if vk <= 0:
            continue
        d[l] = dk; v[l] = vk
    if len(d) < 2:
        return None, None, None
    W = sum(1 / v[l] for l in d)
    dIV = sum(d[l] / v[l] for l in d) / W
    Q = sum((d[l] - dIV) ** 2 / v[l] for l in d)
    df = len(d) - 1
    return Q, df, chi2_sf(Q, df)


def main():
    for subset in ["analysis", "all"]:
        rows = load(subset)
        for sname, key in [("year", lambda r: str(r["year"])),
                           ("region", lambda r: r["region"]),
                           ("has_context", lambda r: str(r["has_context"]))]:
            agg = defaultdict(lambda: [0.0, 0]); lab = {}
            for r in rows:
                agg[r["cluster"]][0] += delta(r)
                agg[r["cluster"]][1] += 1
                lab[r["cluster"]] = key(r)
            ks = list(agg)
            S = [agg[k][0] for k in ks]; N = [agg[k][1] for k in ks]
            L = [lab[k] for k in ks]
            levels = sorted(set(L))
            Qo, df, po = cochran_from_clusters(S, N, L, levels)
            rnd = random.Random(SEED)
            perm = list(L)
            ps = []
            qs = []
            for _ in range(B):
                rnd.shuffle(perm)
                q, dfp, p = cochran_from_clusters(S, N, perm, levels)
                if p is not None:
                    ps.append(p); qs.append(q)
            r05 = sum(1 for p in ps if p <= 0.05) / len(ps)
            r01 = sum(1 for p in ps if p <= 0.01) / len(ps)
            # exact permutation p for the SAME Cochran Q statistic
            pexact = (sum(1 for q in qs if q >= Qo - 1e-12) + 1) / (len(qs) + 1)
            # min cluster count per level
            cl = defaultdict(int)
            for l in L:
                cl[l] += 1
            print("%-9s %-12s Cochran Q=%7.3f df=%d  chi2 p=%.5f | "
                  "EXACT permutation p for the same Q = %.5f"
                  % (subset, sname, Qo, df, po, pexact))
            print("             chi2 calibration under the permutation H0 "
                  "(B=%d): rejects %.3f at .05 and %.3f at .01  "
                  "(nominal .05 / .01)" % (len(ps), r05, r01))
            print("             clusters per level: min=%d, levels=%s"
                  % (min(cl.values()),
                     ", ".join("%s:%d" % (l, cl[l]) for l in levels)))
            print()


if __name__ == "__main__":
    main()

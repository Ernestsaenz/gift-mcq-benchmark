"""Calibration of the obs/floor ratio itself + cluster-structure diagnostics.

The claim reads obs/floor on a scale where 1.0 = "significant" and treats
values near 1 as "underpowered" and values near 0 as "genuine homogeneity".
That reading assumes 0 is where HOMOGENEOUS data land. It is not.

Under exact homogeneity the statistic R = max_k d_k - min_k d_k is strictly
positive and its typical value depends on K and the level-size profile. So the
HOMOGENEOUS BASELINE of obs/floor is median(R_null)/q95(R_null), a stratifier-
specific number well above 0. This script computes it, and computes the false-
alarm rate of the claim's own rule: P(obs/floor >= observed | exact homogeneity).

Both quantities come from the same whole-block permutation null, B=20000.
"""
import json
import random
import sys
from collections import defaultdict

sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/"
                   "tier1_mcq/data/experiment-31-07-26/analysis")
from sens_strata_lib import load, stratifiers, delta, qlen_tertile_map  # noqa
from sens_strata_floor_refute import (load_mode, cl_blocks, rng_stat, q,  # noqa
                                      perm_p, pct_of, B_PERM, SEED, MINC)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "claim"
    rows = load_mode(mode)
    strats, cuts = stratifiers(rows)
    print("MODE=%s cells=%d clusters=%d\n"
          % (mode, len(rows), len(set(r["cluster"] for r in rows))))

    print("=" * 100)
    print("C1  WHERE DOES PERFECTLY HOMOGENEOUS DATA LAND ON THE obs/floor SCALE?")
    print("=" * 100)
    print("  %-13s %3s %8s %9s | %10s %10s | %11s"
          % ("stratifier", "K", "obs/fl", "perm p",
             "H0 median", "H0 p90", "obs vs H0med"))
    print("  %-13s %3s %8s %9s | %10s %10s | %11s"
          % ("", "", "", "", "ratio", "ratio", ""))
    rowsout = {}
    for name, key, unit in strats:
        S, N, L = cl_blocks(rows, key)
        levels = sorted(set(L))
        nn = defaultdict(int)
        for n, l in zip(N, L):
            nn[l] += n
        K = sum(1 for l in levels if nn[l] >= MINC)
        obs = rng_stat(S, N, L, levels)
        rnd = random.Random(SEED + 5)
        perm = list(L)
        null = []
        for _ in range(B_PERM):
            rnd.shuffle(perm)
            null.append(rng_stat(S, N, perm, levels))
        fl = q(null, 0.95)
        med = q(null, 0.50)
        p90 = q(null, 0.90)
        ratio = obs / fl
        print("  %-13s %3d %8.2f %9.4f | %10.2f %10.2f | %11s"
              % (name, K, ratio, perm_p(obs, null), med / fl, p90 / fl,
                 "%+.2f" % (ratio - med / fl)))
        rowsout[name] = (K, ratio, med / fl, perm_p(obs, null))

    print("\n  READ: 'H0 median ratio' is what a PERFECTLY HOMOGENEOUS covariate")
    print("  with this K and this level-size profile produces. It is the correct")
    print("  reference point, not 0. The last column is the only comparable")
    print("  quantity: observed ratio MINUS its own homogeneous baseline.")

    print("\n" + "=" * 100)
    print("C2  FALSE-ALARM RATE OF THE CLAIM'S OWN DECISION RULE")
    print("=" * 100)
    print("  If the covariate is EXACTLY homogeneous, how often does the design")
    print("  still produce an obs/floor at least as large as the one observed?")
    print("  (= the permutation p-value; B=%d)\n" % B_PERM)
    for name in rowsout:
        K, ratio, base, p = rowsout[name]
        verdict = ("claim calls this UNDERPOWERED" if ratio >= 0.6
                   else "claim calls this GENUINE HOMOGENEITY")
        print("    %-13s ratio=%.2f -> %-34s ; but truly homogeneous data hit"
              " this ratio %.1f%% of the time" % (name, ratio, verdict, 100 * p))

    print("\n" + "=" * 100)
    print("C3  WHY THE TWO K=2 FLOORS DIFFER 1.7x (effective units, not 'power')")
    print("=" * 100)
    for name, key, unit in strats:
        if name not in ("has_context", "negated_stem"):
            continue
        byl = defaultdict(lambda: [0, set()])
        for r in rows:
            l = key(r)
            byl[l][0] += 1
            byl[l][1].add(r["cluster"])
        sizes = defaultdict(list)
        for c, n in [(c, sum(1 for r in rows if r["cluster"] == c))
                     for c in set(r["cluster"] for r in rows)]:
            sizes[n].append(c)
        print("  %-13s" % name, end="")
        for l in sorted(byl):
            print("  %s: %d cells / %d clusters (mean %.1f cells/cluster)"
                  % (l, byl[l][0], len(byl[l][1]),
                     byl[l][0] / float(len(byl[l][1]))), end="")
        print()
    print("\n  The has_context floor (0.114) exceeds the negated_stem floor")
    print("  (0.066) despite has_context being the MORE balanced split, because")
    print("  context items sit in a few large clusters -> fewer effective units.")
    print("  Level count and cluster structure, not 'detectability', set the floor.")


if __name__ == "__main__":
    main()

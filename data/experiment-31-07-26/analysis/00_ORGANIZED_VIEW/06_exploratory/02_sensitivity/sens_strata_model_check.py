"""Is the (out-of-family but large) MODEL heterogeneity a baseline-accuracy
artifact, and is the model ordering stable across strata?

- retention rho_m = P(B correct | A correct) per model: scale-free.
- within-item permutation of the 4 model labels (conditions out every item,
  cluster, exam, region, year and length effect exactly).
- model ordering stability: rank of each model's delta inside every region /
  year / has_context level with >= 40 cells.
"""
import random
import sys
from collections import defaultdict

sys.path.insert(0, "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/"
                   "tier1_mcq/data/experiment-31-07-26/analysis")
from sens_strata_lib import load, delta, cluster_bootstrap_levels  # noqa

B = 20000
SEED = 20260731


def within_item_perm(rows, val, name):
    byit = defaultdict(list)
    for r in rows:
        byit[r["question_id"]].append(r)
    models = sorted(set(r["model"] for r in rows))

    def stat(assign):
        ss = defaultdict(float); nn = defaultdict(float)
        for q, rs in byit.items():
            for r, m in zip(rs, assign[q]):
                num, den = val(r)
                if den:
                    ss[m] += num; nn[m] += den
        ts = sum(ss.values()); tn = sum(nn.values())
        Q = sum(ss[m] ** 2 / nn[m] for m in models if nn[m]) - ts * ts / tn
        ds = [ss[m] / nn[m] for m in models if nn[m]]
        return Q, max(ds) - min(ds), {m: ss[m] / nn[m] for m in models if nn[m]}

    obs = {q: [r["model"] for r in rs] for q, rs in byit.items()}
    Qo, Ro, est = stat(obs)
    rnd = random.Random(SEED)
    cur = {q: list(v) for q, v in obs.items()}
    cnt = 0
    for _ in range(B):
        for q in cur:
            rnd.shuffle(cur[q])
        if stat(cur)[0] >= Qo - 1e-12:
            cnt += 1
    p = (cnt + 1) / (B + 1)
    print("  %s : Q=%.4f  range=%.4f  within-item permutation p=%.5f (B=%d)"
          % (name, Qo, Ro, p, B))
    for m in sorted(est, key=lambda m: est[m]):
        print("      %-28s %.4f" % (m, est[m]))
    return p, est


def main():
    for subset in ["analysis", "all"]:
        rows = load(subset)
        print("#" * 100)
        print("MODEL CHECK  subset=%s  (%d cells)" % (subset, len(rows)))
        print("#" * 100)
        print(" per model: acc(A), acc(B), delta with 95%% cluster-bootstrap CI")
        boot = cluster_bootstrap_levels(rows, lambda r: r["model"], 10000, SEED)
        g = defaultdict(list)
        for r in rows:
            g[r["model"]].append(r)
        for m in sorted(g, key=lambda m: sum(delta(r) for r in g[m]) / len(g[m])):
            rs = g[m]
            n = len(rs)
            a = sum(r["A_correct"] for r in rs) / n
            b = sum(r["B_correct"] for r in rs) / n
            lo, hi, _ = boot[m]
            print("   %-28s n=%4d acc(A)=%.4f acc(B)=%.4f delta=%+.4f "
                  "CI[%+.4f,%+.4f]" % (m, n, a, b, b - a, lo, hi))
        print()
        within_item_perm(rows, lambda r: (delta(r), 1), "DELTA scale")
        aok = [r for r in rows if r["A_correct"] == 1]
        # within-item permutation on retention requires all 4 cells; restrict to
        # items where every model got A right (otherwise the label swap is not
        # exchangeable). Report how many items that is.
        full = [q for q, rs in _by(rows).items()
                if all(r["A_correct"] == 1 for r in rs)]
        sub = [r for r in rows if r["question_id"] in set(full)]
        print("  retention-scale within-item permutation restricted to the %d "
              "items where ALL models answered A correctly (%d cells):"
              % (len(full), len(sub)))
        within_item_perm(sub, lambda r: (r["B_correct"], 1), "RETENTION scale")

        print("\n  model ordering stability: delta rank (1=largest drop) inside "
              "each level with >=40 cells")
        for sname, keyf in [("region", lambda r: r["region"]),
                            ("year", lambda r: str(r["year"])),
                            ("has_context", lambda r: str(r["has_context"]))]:
            lv = defaultdict(list)
            for r in rows:
                lv[keyf(r)].append(r)
            models = sorted(set(r["model"] for r in rows))
            hdr = "    %-22s " % sname + " ".join("%-9s" % m.split("/")[-1][:9]
                                                  for m in models)
            print(hdr)
            worst = defaultdict(int)
            best = defaultdict(int)
            nlev = 0
            for l in sorted(lv, key=lambda l: -len(lv[l])):
                rs = lv[l]
                if len(rs) < 40:
                    continue
                nlev += 1
                dd = {}
                for m in models:
                    mr = [r for r in rs if r["model"] == m]
                    dd[m] = sum(delta(r) for r in mr) / len(mr) if mr else None
                order = sorted([m for m in models if dd[m] is not None],
                               key=lambda m: dd[m])
                rank = {m: i + 1 for i, m in enumerate(order)}
                worst[order[0]] += 1
                best[order[-1]] += 1
                print("      %-20s " % str(l)[:20]
                      + " ".join("%+0.3f(%d)" % (dd[m], rank[m]) if dd[m] is not None
                                 else "   n/a   " for m in models))
            print("      -> largest drop in %d/%d levels: %s"
                  % (max(worst.values()), nlev,
                     max(worst, key=worst.get)))
            print("      -> smallest drop in %d/%d levels: %s"
                  % (max(best.values()), nlev, max(best, key=best.get)))
        print()


def _by(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["question_id"]].append(r)
    return d


if __name__ == "__main__":
    main()

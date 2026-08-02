"""Shared helpers for strata-robustness sensitivity analyses.

Stdlib only. No numpy/scipy/pandas.

DESIGN RECAP
------------
Unit of observation = one (question_id, model) *cell*. Each cell contributes a
paired binary outcome pair (A_correct, B_correct) and hence a within-cell delta
    delta = B_correct - A_correct  in {-1, 0, +1}.
The estimand in a stratum k is
    d_k = mean(B_correct | k) - mean(A_correct | k) = mean(delta | k),
i.e. the accuracy change induced by swapping the correct option's TEXT for
"Ninguna de las respuestas anteriores es correcta.".

Items are nested in clinical-context CLUSTERS; every item is answered by 4
models. The resampling / permutation unit is therefore the cluster (for
covariates that are constant within cluster) or the item (for covariates that
vary within cluster). Never the cell.
"""

import json
import math
import random
from collections import Counter, defaultdict

DATA = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
        "data/experiment-31-07-26/analysis/paired_clean.json")


def load(subset="analysis"):
    """subset in {'analysis','all','plus_nota_a','plus_defect'}."""
    with open(DATA) as fh:
        rows = json.load(fh)
    if subset == "analysis":
        return [r for r in rows if r["analysis_include"]]
    if subset == "all":
        return rows
    if subset == "plus_nota_a":          # reinstate the 91 letter-(a) items only
        return [r for r in rows if not r["excl_item_defect"]]
    if subset == "plus_defect":          # reinstate the 14 adjudicated items only
        return [r for r in rows if not r["excl_nota_position_a"]]
    raise ValueError(subset)


# ---------------------------------------------------------------- stratifiers

def qlen_tertile_map(rows):
    """Tertile cutpoints computed over UNIQUE ITEMS (not cells), so that the
    4-model replication does not weight long items 4x in the cutpoint."""
    per_item = {}
    for r in rows:
        per_item[r["question_id"]] = r["qlen"]
    vals = sorted(per_item.values())
    n = len(vals)
    c1 = vals[int(round(n / 3.0)) - 1]
    c2 = vals[int(round(2 * n / 3.0)) - 1]
    def lab(q):
        if q <= c1:
            return "T1 short (<=%d)" % c1
        if q <= c2:
            return "T2 mid (%d-%d)" % (c1 + 1, c2)
        return "T3 long (>%d)" % c2
    return lab, (c1, c2)


def stratifiers(rows):
    """Returns ordered dict-like list of (name, keyfunc, perm_unit)."""
    lab, cuts = qlen_tertile_map(rows)
    return [
        ("region",       lambda r: r["region"],            "cluster"),
        ("year",         lambda r: str(r["year"]),         "cluster"),
        ("exam_part",    lambda r: r["exam_part"],         "cluster"),
        ("has_context",  lambda r: str(r["has_context"]),  "cluster"),
        ("negated_stem", lambda r: str(r["negated_stem"]), "item"),
        ("qlen_tertile", lambda r: lab(r["qlen"]),         "item"),
    ], cuts


# ------------------------------------------------------------------ estimates

def delta(r):
    return r["B_correct"] - r["A_correct"]


def stratum_table(rows, key):
    """Per-level summary: cells, items, clusters, A-rate, B-rate, delta,
    discordant counts n10 (A right/B wrong) and n01 (A wrong/B right)."""
    g = defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    out = {}
    for lev, rs in g.items():
        n = len(rs)
        a = sum(r["A_correct"] for r in rs)
        b = sum(r["B_correct"] for r in rs)
        n10 = sum(1 for r in rs if r["A_correct"] == 1 and r["B_correct"] == 0)
        n01 = sum(1 for r in rs if r["A_correct"] == 0 and r["B_correct"] == 1)
        out[lev] = dict(
            n_cells=n,
            n_items=len(set(r["question_id"] for r in rs)),
            n_clusters=len(set(r["cluster"] for r in rs)),
            A=a / n, B=b / n, d=(b - a) / n, n10=n10, n01=n01,
        )
    return out


# ------------------------------------------------------- permutation machinery
# Q = weighted between-level sum of squares of the cell-level delta:
#     Q = sum_k S_k^2 / n_k  -  S^2 / n
# with S_k = sum of deltas in level k and n_k = number of cells. This is exactly
# the between-group SS of a one-way ANOVA on delta, i.e. a Q-statistic style
# heterogeneity measure with inverse-variance-proportional (size) weights.
# Its permutation null is obtained by reassigning the LEVEL LABEL to whole
# clusters (or whole items), which preserves the within-cluster correlation and
# the cluster-size distribution.

def _units(rows, key, unit):
    """Collapse to permutation units. Returns (unit_S, unit_n, unit_label)."""
    idx = "cluster" if unit == "cluster" else "question_id"
    S = defaultdict(float)
    N = defaultdict(int)
    L = {}
    mixed = 0
    for r in rows:
        u = r[idx]
        S[u] += delta(r)
        N[u] += 1
        lv = key(r)
        if u in L and L[u] != lv:
            mixed += 1
        L.setdefault(u, lv)
    keys = list(S)
    return ([S[u] for u in keys], [N[u] for u in keys], [L[u] for u in keys],
            mixed)


def _Q_and_range(S, N, labels, levels):
    tot_s = 0.0
    tot_n = 0
    ss = defaultdict(float)
    nn = defaultdict(int)
    for s, n, l in zip(S, N, labels):
        ss[l] += s
        nn[l] += n
        tot_s += s
        tot_n += n
    Q = 0.0
    ds = []
    for l in levels:
        n = nn[l]
        if n:
            Q += ss[l] * ss[l] / n
            ds.append(ss[l] / n)
    Q -= tot_s * tot_s / tot_n
    rng = (max(ds) - min(ds)) if len(ds) > 1 else 0.0
    return Q, rng


def permute_stats(rows, key, unit, B, rng_seed, min_cells=0):
    """Returns dict with observed Q/range and the B permuted values.

    min_cells: levels with fewer than this many cells are pooled into '(small)'
    for the RANGE statistic only (Q always uses all levels). 0 = no pooling.
    """
    S, N, labels, mixed = _units(rows, key, unit)
    levels = sorted(set(labels))
    Qobs, Robs = _Q_and_range(S, N, labels, levels)
    rnd = random.Random(rng_seed)
    perm = list(labels)
    Qs, Rs = [], []
    for _ in range(B):
        rnd.shuffle(perm)
        q, r = _Q_and_range(S, N, perm, levels)
        Qs.append(q)
        Rs.append(r)
    return dict(Qobs=Qobs, Robs=Robs, Qnull=Qs, Rnull=Rs,
                n_units=len(S), n_levels=len(levels), mixed_units=mixed)


def perm_p(obs, null):
    return (sum(1 for v in null if v >= obs - 1e-12) + 1) / (len(null) + 1)


# ------------------------------------------------------------ cluster bootstrap

def cluster_bootstrap_levels(rows, key, B, rng_seed):
    """Percentile CI for d_k in every level, resampling CLUSTERS with
    replacement (the outermost independent unit)."""
    byc = defaultdict(list)
    for r in rows:
        byc[r["cluster"]].append((key(r), delta(r)))
    cl = list(byc)
    levels = sorted(set(key(r) for r in rows))
    draws = {l: [] for l in levels}
    draws["__ALL__"] = []
    rnd = random.Random(rng_seed)
    n = len(cl)
    for _ in range(B):
        s = defaultdict(float)
        c = defaultdict(int)
        ts = 0.0
        tc = 0
        for _ in range(n):
            for lv, dl in byc[cl[rnd.randrange(n)]]:
                s[lv] += dl
                c[lv] += 1
                ts += dl
                tc += 1
        for l in levels:
            draws[l].append(s[l] / c[l] if c[l] else None)
        draws["__ALL__"].append(ts / tc)
    out = {}
    for l, v in draws.items():
        v = sorted(x for x in v if x is not None)
        if len(v) < 100:
            out[l] = (None, None, len(v))
            continue
        lo = v[int(0.025 * len(v))]
        hi = v[min(len(v) - 1, int(0.975 * len(v)))]
        out[l] = (lo, hi, len(v))
    return out


def holm(pvals):
    """pvals: dict name->p. Returns dict name->adjusted p (Holm-Bonferroni)."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    adj = {}
    run = 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        adj[k] = run
    return adj

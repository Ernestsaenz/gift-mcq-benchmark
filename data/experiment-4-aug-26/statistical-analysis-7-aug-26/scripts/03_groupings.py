#!/usr/bin/env python3
"""
03_groupings.py — Agent 3 deliverable: model-level groupings (open vs closed
weights; big vs small).

Scope note (see STATS_SPEC.md and results/MODEL_TAXONOMY.md for the full
reasoning): of the two requested groupings,

  * OPEN vs CLOSED weights is computed and reported, but the closed group
    contains exactly one model (google/gemini-3.6-flash) versus three open
    models. n_models=1 in the closed arm means model-level and group-level
    variation cannot be separated — every number below is a descriptive
    "gemini vs the other three" comparison, not a valid test of a
    weight-licensing factor. This is stated inline in every result, not only
    here.

  * BIG vs SMALL is declared INFEASIBLE and is NOT computed. See
    results/MODEL_TAXONOMY.md for the full justification: two of the four
    models (glm-5.2, gemini-3.6-flash) have no defensible parameter count
    established anywhere in this repo, and restricting to the two MoE models
    with published counts (gemma, qwen) does not rescue a binary label,
    because total-parameter and active-parameter counts rank them in
    OPPOSITE order (qwen has more total params, gemma has more active
    params). No parameter count is invented, looked up, or estimated here.

Design facts this script depends on (verified against the source CSVs below,
see inline asserts):
  - 500 questions x 3 arms x 4 models = 6000 run-1 cells, all scored.
  - question_id is the SAME 500-question set across all three arms
    (openrouter_A, openrouter_B, tailscale_A); question is therefore a valid
    cluster variable across arms as well as within an arm (up to 12 cells
    per question in the pooled analysis, 4 in a single-arm analysis).
  - Clustering approach: cluster-robust logistic regression (GEE, exchangeable
    working correlation, cluster = question_id), per STATS_SPEC.md. A
    question-level Monte Carlo sign-flip permutation test is run alongside it
    as an assumption-light cross-check (precedented in this repo:
    data/experiment-31-07-26/analysis/comparison_workflows/GROUP_COMPARISONS_STATS.md
    uses the same "cluster sign-flip" device for the same four models).
  - Effect sizes (risk difference with cluster-bootstrap CI; odds ratio with
    GEE-robust CI) are reported alongside every p-value, per STATS_SPEC.
  - Holm-Bonferroni is applied within an explicitly named family for each
    outcome (primary strict_correct family = {pooled, arm A, arm B,
    arm tailscale_A, condition_A_all_arms}; secondary flip-rate family =
    the same five scopes). The Vertex-exclusion sensitivity variant is
    reported alongside, not folded into the Holm family (it is a
    robustness check on the same hypothesis, not an additional
    hypothesis).
  - Added 2026-08-07 at the team lead's request, after STATS_SPEC.md was
    updated to establish that condition B is a none-of-the-above (NOTA)
    manipulation rather than a generically "harder" condition: a
    `condition_A_all_arms` scope (openrouter_A + tailscale_A) in both Holm
    families for completeness, PLUS a separate, explicitly non-formal
    "condition gap" descriptive statistic (does the open/closed gap widen
    from condition A to condition B?), computed on openrouter_A vs
    openrouter_B only so provider is held fixed. That gap statistic is a
    bootstrap point-estimate + CI, deliberately NOT a p-value/interaction
    test and NOT part of any Holm family — see cluster_bootstrap_condition_gap().

Outputs (this script's only write targets, per file-ownership scope):
  - results/groupings_open_closed_primary.csv   (strict_correct, run-1, 6000 cells)
  - results/groupings_open_closed_secondary.csv (flip rate, replicate cells)
  - results/groupings_summary.json              (machine-readable rollup)
  - results/MODEL_TAXONOMY.md and results/GROUPING_TESTS.md are written by a
    separate step (not by this script) since they are prose deliverables;
    this script prints the numbers they cite so they can be checked against
    each other.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

import statsmodels.api as sm
from statsmodels.genmod.cov_struct import Exchangeable
from statsmodels.genmod.families import Binomial
from statsmodels.genmod.generalized_estimating_equations import GEE

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve()
ANALYSIS_DIR = HERE.parents[1]           # .../statistical-analysis-7-aug-26
EXP_DIR = ANALYSIS_DIR.parent            # .../experiment-4-aug-26
RESULTS_DIR = ANALYSIS_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

RUN1_PATH = EXP_DIR / "consolidate-triplicates-7-aug-26" / "exports" / "run1-6000-with-replicate-status.csv"
REPL_PATH = EXP_DIR / "consolidate-triplicates-7-aug-26" / "exports" / "replicate-cell-level-1796.csv"

# ---------------------------------------------------------------------------
# Model taxonomy (see results/MODEL_TAXONOMY.md for the audit trail)
# ---------------------------------------------------------------------------
CLOSED_MODELS = ["google/gemini-3.6-flash"]
OPEN_MODELS = ["google/gemma-4-26b-a4b-it", "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
ALL_MODELS = CLOSED_MODELS + OPEN_MODELS
ARMS = ["openrouter_A", "openrouter_B", "tailscale_A"]

GROUP_OF = {m: "closed" for m in CLOSED_MODELS}
GROUP_OF.update({m: "open" for m in OPEN_MODELS})

RNG_SEED = 20260807
N_BOOT = 5000
N_PERM = 20000


def group_col(df: pd.DataFrame) -> pd.Series:
    return df["model"].map(GROUP_OF)


# ---------------------------------------------------------------------------
# Effect sizes: risk difference (cluster/question bootstrap CI) and odds
# ratio (from GEE)
# ---------------------------------------------------------------------------
def cluster_bootstrap_risk_difference(df: pd.DataFrame, cluster_col: str, outcome_col: str,
                                       group_col_name: str, group_a: str, group_b: str,
                                       n_boot: int = N_BOOT, seed: int = RNG_SEED) -> dict:
    """Risk difference = P(outcome | group_a) - P(outcome | group_b), with a
    cluster (question-level) bootstrap 95% CI: resample whole clusters with
    replacement, recompute both group proportions and their difference each
    time. This respects the fact that up to 12 (pooled) or 4 (per-arm) rows
    share a question and are not independent draws."""
    rng = np.random.default_rng(seed)
    clusters = df[cluster_col].unique()
    n_clusters = len(clusters)

    a_mask = df[group_col_name] == group_a
    b_mask = df[group_col_name] == group_b
    obs_rd = df.loc[a_mask, outcome_col].mean() - df.loc[b_mask, outcome_col].mean()

    # Precompute per-cluster arrays for fast resampling
    by_cluster_a = df[a_mask].groupby(cluster_col)[outcome_col].apply(list).reindex(clusters, fill_value=[])
    by_cluster_b = df[b_mask].groupby(cluster_col)[outcome_col].apply(list).reindex(clusters, fill_value=[])
    a_lists = by_cluster_a.to_numpy()
    b_lists = by_cluster_b.to_numpy()

    boot_rds = np.empty(n_boot)
    idx_range = np.arange(n_clusters)
    for i in range(n_boot):
        pick = rng.choice(idx_range, size=n_clusters, replace=True)
        a_vals = np.concatenate([a_lists[j] for j in pick if len(a_lists[j])]) if any(len(a_lists[j]) for j in pick) else np.array([])
        b_vals = np.concatenate([b_lists[j] for j in pick if len(b_lists[j])]) if any(len(b_lists[j]) for j in pick) else np.array([])
        boot_rds[i] = (a_vals.mean() if a_vals.size else np.nan) - (b_vals.mean() if b_vals.size else np.nan)

    lo, hi = np.nanpercentile(boot_rds, [2.5, 97.5])
    return {
        "risk_difference": float(obs_rd),
        "rd_ci_lo": float(lo),
        "rd_ci_hi": float(hi),
        "n_boot": n_boot,
        "n_clusters": int(n_clusters),
    }


def zero_cell_2x2(df: pd.DataFrame, outcome_col: str, group_col_name: str) -> bool:
    """True iff the unclustered 2x2 table (group x outcome) has an empty
    cell — i.e. one group is 0% or 100% on this outcome. GEE logit is
    degenerate (infinite coefficient, unstable SE) in that case; the caller
    should not trust the OR/p from it."""
    tab = pd.crosstab(df[group_col_name], df[outcome_col])
    return bool((tab == 0).any().any()) or tab.shape[0] < 2 or tab.shape[1] < 2


def gee_logit(df: pd.DataFrame, cluster_col: str, outcome_col: str, group_col_name: str,
              ref: str, other_covariates: list[str] | None = None) -> dict:
    """Cluster-robust logistic regression, GEE with exchangeable working
    correlation, cluster = question_id. Returns OR + Wald CI + p for the
    group term (relative to `ref`). If the group x outcome table has an
    empty cell (perfect separation — e.g. a group with 0 or all successes),
    the fit is degenerate: this function returns NaNs with `degenerate=True`
    rather than a nonsensical infinite OR, and the caller should rely on the
    risk-difference bootstrap and sign-flip permutation instead."""
    if zero_cell_2x2(df, outcome_col, group_col_name):
        return {
            "or": float("nan"), "or_ci_lo": float("nan"), "or_ci_hi": float("nan"),
            "p_wald": float("nan"), "coef": float("nan"), "se": float("nan"),
            "n_obs": int(len(df)), "n_clusters": int(df[cluster_col].nunique()),
            "degenerate": True,
        }
    work = df.copy()
    work["_group_cat"] = pd.Categorical(work[group_col_name], categories=[ref] + [g for g in work[group_col_name].unique() if g != ref])
    formula_terms = ["C(_group_cat, Treatment(reference='%s'))" % ref]
    if other_covariates:
        for c in other_covariates:
            formula_terms.append(f"C({c})")
    formula = f"{outcome_col} ~ " + " + ".join(formula_terms)
    model = GEE.from_formula(formula, groups=cluster_col, data=work,
                              family=Binomial(), cov_struct=Exchangeable())
    res = model.fit()
    # Identify the group coefficient (the one row containing "_group_cat")
    group_rows = [p for p in res.params.index if "_group_cat" in p]
    assert len(group_rows) == 1, f"expected exactly one non-reference group level, got {group_rows}"
    term = group_rows[0]
    coef = res.params[term]
    se = res.bse[term]
    p = res.pvalues[term]
    ci_lo, ci_hi = coef - 1.96 * se, coef + 1.96 * se
    return {
        "or": float(np.exp(coef)),
        "or_ci_lo": float(np.exp(ci_lo)),
        "or_ci_hi": float(np.exp(ci_hi)),
        "p_wald": float(p),
        "coef": float(coef),
        "se": float(se),
        "n_obs": int(res.nobs),
        "n_clusters": int(work[cluster_col].nunique()),
        "degenerate": False,
    }


def cluster_signflip_permutation(df: pd.DataFrame, cluster_col: str, outcome_col: str,
                                  group_col_name: str, group_a: str, group_b: str,
                                  n_perm: int = N_PERM, seed: int = RNG_SEED) -> dict:
    """Question-level Monte Carlo sign-flip test. For each question, compute
    d_q = mean(outcome | group_a, question q) - mean(outcome | group_b, question q).
    Under the null of no systematic group effect, the sign of d_q is
    exchangeable across questions. Test statistic = sum(d_q); Monte Carlo
    p-value from n_perm random sign flips. Same device used for the same
    four models in
    experiment-31-07-26/analysis/comparison_workflows/GROUP_COMPARISONS_STATS.md.
    """
    a = df[df[group_col_name] == group_a].groupby(cluster_col)[outcome_col].mean()
    b = df[df[group_col_name] == group_b].groupby(cluster_col)[outcome_col].mean()
    d = (a - b).dropna()
    d_vals = d.to_numpy()
    n_nonzero = int(np.sum(d_vals != 0))
    obs_stat = np.abs(d_vals.sum())

    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=(n_perm, d_vals.size))
    perm_stats = np.abs((signs * d_vals).sum(axis=1))
    p_perm = float((np.sum(perm_stats >= obs_stat) + 1) / (n_perm + 1))

    return {
        "sum_d": float(d_vals.sum()),
        "mean_d": float(d_vals.mean()),
        "n_questions_with_nonzero_diff": n_nonzero,
        "n_questions_total": int(d_vals.size),
        "p_signflip": p_perm,
        "n_perm": n_perm,
    }


def cluster_bootstrap_condition_gap(df: pd.DataFrame, cluster_col: str, outcome_col: str,
                                     group_col_name: str, condition_col: str,
                                     group_a: str = "open", group_b: str = "closed",
                                     cond_a_val: str = "A", cond_b_val: str = "B",
                                     n_boot: int = N_BOOT, seed: int = RNG_SEED) -> dict:
    """Descriptive effect size ONLY — not a formal interaction test (per
    team-lead instruction: report a descriptive stratified comparison with
    CIs, not a formal test, unless the model natively supports one).

    Condition B is a none-of-the-above (NOTA) manipulation (STATS_SPEC.md):
    the substantive correct option is replaced by a fixed NOTA string in
    every question. This computes whether the open-vs-closed risk
    difference (open − closed) widens or narrows between condition A
    (ordinary items) and condition B (NOTA items):
        gap = RD_condition_B − RD_condition_A
    A more negative gap means the open group loses more ground relative to
    the closed group under the NOTA manipulation specifically. CI via
    question-cluster bootstrap; resampling whole questions preserves the
    A/B pairing (both conditions use the identical 500 questions)."""
    rng = np.random.default_rng(seed)
    clusters = df[cluster_col].unique()
    n_clusters = len(clusters)

    def rd(sub: pd.DataFrame) -> float:
        return (sub.loc[sub[group_col_name] == group_a, outcome_col].mean()
                - sub.loc[sub[group_col_name] == group_b, outcome_col].mean())

    obs_rd_a = rd(df[df[condition_col] == cond_a_val])
    obs_rd_b = rd(df[df[condition_col] == cond_b_val])
    obs_gap = obs_rd_b - obs_rd_a

    combos = {}
    for cval, cname in [(cond_a_val, "A"), (cond_b_val, "B")]:
        for gval, gname in [(group_a, "open"), (group_b, "closed")]:
            mask = (df[condition_col] == cval) & (df[group_col_name] == gval)
            combos[(cname, gname)] = (
                df[mask].groupby(cluster_col)[outcome_col].apply(list)
                .reindex(clusters, fill_value=[]).to_numpy()
            )

    idx_range = np.arange(n_clusters)
    boot_gaps = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.choice(idx_range, size=n_clusters, replace=True)
        vals = {}
        for key, arr in combos.items():
            parts = [arr[j] for j in pick if len(arr[j])]
            vals[key] = np.concatenate(parts) if parts else np.array([])
        rd_a_boot = ((vals[("A", "open")].mean() if vals[("A", "open")].size else np.nan)
                     - (vals[("A", "closed")].mean() if vals[("A", "closed")].size else np.nan))
        rd_b_boot = ((vals[("B", "open")].mean() if vals[("B", "open")].size else np.nan)
                     - (vals[("B", "closed")].mean() if vals[("B", "closed")].size else np.nan))
        boot_gaps[i] = rd_b_boot - rd_a_boot

    lo, hi = np.nanpercentile(boot_gaps, [2.5, 97.5])
    return {
        "rd_condition_A": float(obs_rd_a),
        "rd_condition_B": float(obs_rd_b),
        "gap_B_minus_A": float(obs_gap),
        "gap_ci_lo": float(lo),
        "gap_ci_hi": float(hi),
        "n_boot": n_boot,
        "n_clusters": int(n_clusters),
        "note": "descriptive effect size only (question-cluster bootstrap CI); NOT a formal interaction test, no p-value, not part of any Holm family",
    }


def holm_adjust(pvals: list[float]) -> list[float]:
    """Holm-Bonferroni step-down adjustment. Returns adjusted p-values in the
    original order."""
    idx = np.argsort(pvals)
    m = len(pvals)
    adj = np.empty(m)
    running_max = 0.0
    for rank, i in enumerate(idx):
        val = (m - rank) * pvals[i]
        running_max = max(running_max, val)
        adj[i] = min(running_max, 1.0)
    return adj.tolist()


# ---------------------------------------------------------------------------
# Analysis 1 — PRIMARY: open vs closed on run-1 strict_correct (6000 cells)
# ---------------------------------------------------------------------------
def run_open_closed_primary(df6000: pd.DataFrame) -> list[dict]:
    rows = []
    scopes = [("pooled_arm_adjusted", df6000, ["arm"])] + [
        (arm, df6000[df6000["arm"] == arm], None) for arm in ARMS
    ] + [
        # Descriptive completeness only: pools BOTH condition-A arms
        # (openrouter_A + tailscale_A), which mixes provider with condition.
        # The clean condition contrast (provider held fixed) is
        # openrouter_A vs openrouter_B, already covered by the two rows
        # above and used for the gap-widening figure computed in main().
        ("condition_A_all_arms", df6000[df6000["condition"] == "A"], ["arm"]),
    ]
    for scope_name, sub, covars in scopes:
        n_cells = len(sub)
        n_cells_open = int((sub["_group"] == "open").sum())
        n_cells_closed = int((sub["_group"] == "closed").sum())
        n_models_open = sub.loc[sub["_group"] == "open", "model"].nunique()
        n_models_closed = sub.loc[sub["_group"] == "closed", "model"].nunique()

        rd = cluster_bootstrap_risk_difference(sub, "question_id", "strict_correct", "_group", "open", "closed")
        gee = gee_logit(sub, "question_id", "strict_correct", "_group", ref="closed", other_covariates=covars)
        perm = cluster_signflip_permutation(sub, "question_id", "strict_correct", "_group", "open", "closed")

        rows.append({
            "grouping": "open_vs_closed",
            "outcome": "strict_correct_run1",
            "scope": scope_name,
            "n_cells": n_cells,
            "n_cells_open": n_cells_open,
            "n_cells_closed": n_cells_closed,
            "n_models_open": int(n_models_open),
            "n_models_closed": int(n_models_closed),
            "prop_open": float(sub.loc[sub["_group"] == "open", "strict_correct"].mean()),
            "prop_closed": float(sub.loc[sub["_group"] == "closed", "strict_correct"].mean()),
            **rd,
            "or": gee["or"], "or_ci_lo": gee["or_ci_lo"], "or_ci_hi": gee["or_ci_hi"],
            "p_gee_wald": gee["p_wald"],
            "or_degenerate": gee.get("degenerate", False),
            "p_signflip": perm["p_signflip"],
            "n_questions_signflip": perm["n_questions_total"],
            "n_perm": perm["n_perm"],
            "confound_note": (
                "closed group = exactly 1 model (gemini); this is a descriptive gemini-vs-other-three "
                "comparison, not a valid test of a weight-licensing factor (n_models_closed=1)."
                + (" ADDITIONALLY: this scope pools openrouter_A and tailscale_A, i.e. condition A across "
                   "BOTH providers — it mixes provider (transport + prompt-delivery differences, see STATS_SPEC) "
                   "with condition. Reported for descriptive completeness only; the clean condition-A-vs-B "
                   "comparison (provider held fixed at OpenRouter) uses the separate openrouter_A/openrouter_B "
                   "rows above, not this one."
                   if scope_name == "condition_A_all_arms" else "")
            ),
        })
    return rows


# ---------------------------------------------------------------------------
# Analysis 2 — SECONDARY: open vs closed on flip rate (replicate cells)
# ---------------------------------------------------------------------------
def run_open_closed_secondary(repl: pd.DataFrame) -> list[dict]:
    rows = []
    scopes = [("pooled_arm_adjusted", repl, ["arm"])] + [
        (arm, repl[repl["arm"] == arm], None) for arm in sorted(repl["arm"].unique())
    ] + [
        # Descriptive completeness only — see note in run_open_closed_primary.
        ("condition_A_all_arms", repl[repl["condition"] == "A"], ["arm"]),
    ]
    for scope_name, sub, covars in scopes:
        for sensitivity, sub2 in [
            ("main", sub),
            ("excl_vertex_gemini_B", sub[~((sub["model"] == "google/gemini-3.6-flash") &
                                            (sub["arm"] == "openrouter_B") &
                                            (sub["upstream"] == "google-vertex"))]),
        ]:
            if sub2["_group"].nunique() < 2:
                continue
            if (sub2["_group"] == "closed").sum() == 0 or (sub2["_group"] == "open").sum() == 0:
                continue
            n_cells = len(sub2)
            n_cells_open = int((sub2["_group"] == "open").sum())
            n_cells_closed = int((sub2["_group"] == "closed").sum())
            n_models_open = sub2.loc[sub2["_group"] == "open", "model"].nunique()
            n_models_closed = sub2.loc[sub2["_group"] == "closed", "model"].nunique()
            n_vertex_excluded = int(len(sub) - len(sub2))

            rd = cluster_bootstrap_risk_difference(sub2, "question_id", "strict_correct", "_group", "open", "closed")
            try:
                gee = gee_logit(sub2, "question_id", "strict_correct", "_group", ref="closed", other_covariates=covars)
            except Exception as e:  # pragma: no cover - defensive: GEE can fail to converge on sparse strata
                gee = {"or": np.nan, "or_ci_lo": np.nan, "or_ci_hi": np.nan, "p_wald": np.nan}
            perm = cluster_signflip_permutation(sub2, "question_id", "strict_correct", "_group", "open", "closed")

            rows.append({
                "grouping": "open_vs_closed",
                "outcome": "flip_rate_replicates",
                "scope": scope_name,
                "sensitivity": sensitivity,
                "n_vertex_excluded": n_vertex_excluded,
                "n_cells": n_cells,
                "n_cells_open": n_cells_open,
                "n_cells_closed": n_cells_closed,
                "n_models_open": int(n_models_open),
                "n_models_closed": int(n_models_closed),
                "prop_open": float(sub2.loc[sub2["_group"] == "open", "strict_correct"].mean()),
                "prop_closed": float(sub2.loc[sub2["_group"] == "closed", "strict_correct"].mean()),
                **rd,
                "or": gee["or"], "or_ci_lo": gee["or_ci_lo"], "or_ci_hi": gee["or_ci_hi"],
                "p_gee_wald": gee["p_wald"],
                "or_degenerate": gee.get("degenerate", False),
                "p_signflip": perm["p_signflip"],
                "n_questions_signflip": perm["n_questions_total"],
                "n_perm": perm["n_perm"],
                "confound_note": ("closed group = exactly 1 model (gemini), and gemini is also the ONLY "
                                   "model affected by the Vertex temperature-drop deviation in openrouter_B "
                                   "replicates (91 of its cells). The open/closed contrast on flip rate is "
                                   "therefore doubly confounded: model identity AND protocol deviation both "
                                   "land on the same side of the contrast. See sensitivity='excl_vertex_gemini_B'."
                                   + (" ADDITIONALLY: this scope pools openrouter_A and tailscale_A (condition A "
                                      "across both providers) — descriptive completeness only; the clean "
                                      "condition-A-vs-B comparison (provider held fixed) uses the openrouter_A/"
                                      "openrouter_B rows, not this one."
                                      if scope_name == "condition_A_all_arms" else "")),
            })
    return rows


def main():
    df6000 = pd.read_csv(RUN1_PATH)
    assert len(df6000) == 6000, f"expected 6000 run-1 cells, got {len(df6000)}"
    assert set(df6000["model"].unique()) == set(ALL_MODELS)
    assert set(df6000["arm"].unique()) == set(ARMS)
    assert df6000["strict_correct"].isna().sum() == 0
    df6000["_group"] = group_col(df6000)

    repl = pd.read_csv(REPL_PATH)
    repl = repl[repl["status"] == "scored"].copy()
    assert len(repl) == 1788, f"expected 1788 scored replicates, got {len(repl)}"
    repl["_group"] = group_col(repl)
    # replicate-cell-level-1796.csv carries `arm` but not `condition`; derive
    # it the same way the exports README documents (tailscale_A -> A).
    repl["condition"] = repl["arm"].map({"openrouter_A": "A", "openrouter_B": "B", "tailscale_A": "A"})
    assert repl["condition"].isna().sum() == 0
    repl["strict_correct"] = repl["strict_correct"].astype(bool).astype(int)
    n_vertex_total = int(((repl["model"] == "google/gemini-3.6-flash") &
                           (repl["arm"] == "openrouter_B") &
                           (repl["upstream"] == "google-vertex")).sum())
    assert n_vertex_total == 91, f"expected 91 Vertex-served gemini_B replicate rows, got {n_vertex_total}"

    df6000["strict_correct"] = df6000["strict_correct"].astype(int)

    primary_rows = run_open_closed_primary(df6000)
    secondary_rows = run_open_closed_secondary(repl)

    # Descriptive-only condition A-vs-B "gap widening" figures (per team-lead
    # request 2026-08-07, after STATS_SPEC.md was updated to establish that
    # condition B is a none-of-the-above/NOTA manipulation, not a generic
    # "harder" condition). Restricted to OpenRouter arms only so provider is
    # held fixed and condition is the only thing varying — STATS_SPEC.md
    # names openrouter_A vs openrouter_B "the cleanest contrast in the
    # study" for exactly this reason. NOT a formal interaction test: no
    # p-value, not part of any Holm family, point estimate + bootstrap CI
    # only.
    or_only_primary = df6000[df6000["arm"].isin(["openrouter_A", "openrouter_B"])]
    condition_gap_primary = cluster_bootstrap_condition_gap(
        or_only_primary, "question_id", "strict_correct", "_group", "condition")

    or_only_secondary = repl[repl["arm"].isin(["openrouter_A", "openrouter_B"])]
    condition_gap_secondary = cluster_bootstrap_condition_gap(
        or_only_secondary, "question_id", "strict_correct", "_group", "condition")

    # Holm correction within named families
    primary_family = [r for r in primary_rows]  # pooled + 3 arms + condition_A_all_arms, strict_correct
    p_primary = [r["p_gee_wald"] for r in primary_family]
    p_primary_adj = holm_adjust(p_primary)
    primary_family_label = f"open_vs_closed:strict_correct_run1 (pooled + 3 arms + condition_A_all_arms, n={len(primary_family)})"
    for r, adj in zip(primary_family, p_primary_adj):
        r["p_gee_wald_holm"] = adj
        r["holm_family"] = primary_family_label

    secondary_main = [r for r in secondary_rows if r["sensitivity"] == "main"]
    family_label = f"open_vs_closed:flip_rate_replicates main (pooled + 3 arms + condition_A_all_arms, n={len(secondary_main)})"
    finite_rows = [r for r in secondary_main if np.isfinite(r["p_gee_wald"])]
    degenerate_rows = [r for r in secondary_main if not np.isfinite(r["p_gee_wald"])]
    p_sec_adj = holm_adjust([r["p_gee_wald"] for r in finite_rows])
    for r, adj in zip(finite_rows, p_sec_adj):
        r["p_gee_wald_holm"] = adj
        r["holm_family"] = family_label
    for r in degenerate_rows:
        r["p_gee_wald_holm"] = None
        r["holm_family"] = family_label + " — EXCLUDED from Holm set: GEE degenerate (zero-cell 2x2, perfect separation), see or_degenerate/confound_note"
    # sensitivity variant reported but not Holm-corrected as a separate hypothesis
    for r in secondary_rows:
        if r["sensitivity"] != "main":
            r["p_gee_wald_holm"] = None
            r["holm_family"] = "not corrected (robustness/sensitivity check on the main-row hypothesis, not an added hypothesis)"

    pd.DataFrame(primary_rows).to_csv(RESULTS_DIR / "groupings_open_closed_primary.csv", index=False)
    pd.DataFrame(secondary_rows).to_csv(RESULTS_DIR / "groupings_open_closed_secondary.csv", index=False)

    summary = {
        "generated_by": "scripts/03_groupings.py",
        "open_models": OPEN_MODELS,
        "closed_models": CLOSED_MODELS,
        "big_vs_small": {
            "status": "INFEASIBLE",
            "reason": ("2 of 4 models (z-ai/glm-5.2, google/gemini-3.6-flash) have no defensible "
                       "parameter count established in this repo; restricting to the two MoE models "
                       "with published counts (gemma 26B total/4B active, qwen 35B total/3B active) "
                       "does not rescue a binary big/small label because total- and active-parameter "
                       "counts rank the two models in OPPOSITE order. No test was run. "
                       "See results/MODEL_TAXONOMY.md."),
            "n_models_evaluable_for_size": 2,
            "n_models_total": 4,
        },
        "open_vs_closed": {
            "primary_strict_correct_run1": primary_rows,
            "secondary_flip_rate_replicates": secondary_rows,
            "n_vertex_served_gemini_B_replicate_cells": n_vertex_total,
            "condition_gap_descriptive": {
                "note": ("Descriptive only, per team-lead request 2026-08-07: does the open-vs-closed gap "
                         "widen under condition B (NOTA manipulation, see STATS_SPEC.md) vs condition A? "
                         "Restricted to openrouter_A vs openrouter_B so provider is held fixed (the clean "
                         "condition contrast per STATS_SPEC.md). NOT a formal interaction test: no p-value, "
                         "not Holm-corrected, not part of any hypothesis family."),
                "strict_correct_run1": condition_gap_primary,
                "flip_rate_replicates": condition_gap_secondary,
            },
        },
        "random_seed": RNG_SEED,
        "n_boot_risk_difference": N_BOOT,
        "n_perm_signflip": N_PERM,
    }
    with open(RESULTS_DIR / "groupings_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("Wrote:")
    print(" ", RESULTS_DIR / "groupings_open_closed_primary.csv")
    print(" ", RESULTS_DIR / "groupings_open_closed_secondary.csv")
    print(" ", RESULTS_DIR / "groupings_summary.json")
    print()
    print(pd.DataFrame(primary_rows)[["scope", "n_cells", "n_models_open", "n_models_closed",
                                        "prop_open", "prop_closed", "risk_difference", "rd_ci_lo", "rd_ci_hi",
                                        "or", "or_ci_lo", "or_ci_hi", "p_gee_wald", "p_gee_wald_holm", "p_signflip"]].to_string(index=False))
    print()
    print(pd.DataFrame(secondary_rows)[["scope", "sensitivity", "n_cells", "n_vertex_excluded",
                                          "prop_open", "prop_closed", "risk_difference", "rd_ci_lo", "rd_ci_hi",
                                          "or", "p_gee_wald", "p_gee_wald_holm", "p_signflip"]].to_string(index=False))
    print()
    print("Descriptive condition A-vs-B gap widening (openrouter arms only, NOT a formal test):")
    print("  strict_correct_run1:", condition_gap_primary)
    print("  flip_rate_replicates:", condition_gap_secondary)


if __name__ == "__main__":
    main()

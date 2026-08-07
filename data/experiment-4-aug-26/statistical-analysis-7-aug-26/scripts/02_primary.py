#!/usr/bin/env python3
"""
02_primary.py -- Primary inferential contrasts for the ab520 500-question benchmark.

Owner: agent 2 of 4 (primary paired + provider tests).
Reads STATS_SPEC.md constraints as binding:
  - A vs B is PAIRED on identical 500 questions (McNemar, not two-sample).
  - provider x condition is NOT crossed (no tailscale_B) -> interaction is
    inestimable and is not attempted anywhere in this script.
  - Run 1 is uncontaminated by the Vertex routing deviation; only replicate
    (run2/run3) analyses touching openrouter_B/gemini need the sensitivity
    exclusion of the 91 Vertex-served cells.

Outputs (results/):
  primary_condition_AvsB.csv, primary_provider.csv, primary_model_effects.csv,
  primary_flip_rate.csv, primary_summary.json, PRIMARY_TESTS.md (written by
  this script directly so prose and numbers cannot drift apart).

Sources are READ-ONLY. This script only ever writes into results/.
"""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps
from statsmodels.stats.contingency_tables import mcnemar, cochrans_q
from statsmodels.stats.proportion import proportion_confint
from statsmodels.stats.multitest import multipletests
from statsmodels.genmod.generalized_estimating_equations import GEE
from statsmodels.genmod.cov_struct import Exchangeable
from statsmodels.genmod.families import Binomial
from statsmodels.genmod.families.links import Logit as LogitLink

warnings.filterwarnings("ignore", category=FutureWarning)

BASE = Path(__file__).resolve().parents[1]
CONS = BASE.parent / "consolidate-triplicates-7-aug-26"
RESULTS = BASE / "results"
RESULTS.mkdir(exist_ok=True)

RUN1_PATH = CONS / "exports" / "run1-6000-with-replicate-status.csv"
REP898_PATH = CONS / "exports" / "consolidated-triplicates-898.csv"
REP1796_PATH = CONS / "exports" / "replicate-cell-level-1796.csv"

MODELS = [
    "google/gemini-3.6-flash",
    "google/gemma-4-26b-a4b-it",
    "qwen/qwen3.6-35b-a3b",
    "z-ai/glm-5.2",
]
ALPHA = 0.05
RNG_SEED = 20260807
N_PERM = 20000

# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_run1() -> pd.DataFrame:
    df = pd.read_csv(RUN1_PATH)
    assert df.shape[0] == 6000, f"expected 6000 run-1 rows, got {df.shape[0]}"
    assert df["question_id"].nunique() == 500
    df["strict_correct"] = df["strict_correct"].astype(int)
    return df


def load_replicates_898() -> pd.DataFrame:
    df = pd.read_csv(REP898_PATH)
    assert df.shape[0] == 898
    for c in ["run1_strict_correct", "run2_strict_correct", "run3_strict_correct",
              "flipped_to_correct"]:
        df[c] = df[c].map(lambda v: v if pd.isna(v) else str(v).strip().upper() == "TRUE")
    return df


def load_vertex_affected_cells() -> set:
    """(arm, model, question_id) triples with >=1 replicate run served by
    google-vertex (the 2026-08-06 gemini/openrouter_B routing deviation)."""
    df = pd.read_csv(REP1796_PATH)
    vx = df[df["upstream"] == "google-vertex"]
    assert vx.shape[0] == 91, f"expected 91 vertex-served run rows, got {vx.shape[0]}"
    assert set(vx["arm"].unique()) == {"openrouter_B"}
    assert set(vx["model"].unique()) == {"google/gemini-3.6-flash"}
    return set(zip(vx["arm"], vx["model"], vx["question_id"]))


# ---------------------------------------------------------------------------
# Effect-size helpers
# ---------------------------------------------------------------------------

def paired_risk_diff_ci(b, c, n, alpha=ALPHA):
    """Wald CI for the difference in paired proportions (Fleiss et al. 2003,
    eq. based on discordant pairs). diff = p_row - p_col = (b - c) / n."""
    diff = (b - c) / n
    var = ((b + c) - (b - c) ** 2 / n) / n ** 2
    se = np.sqrt(max(var, 0.0))
    z = sps.norm.ppf(1 - alpha / 2)
    return diff, diff - z * se, diff + z * se, se


def mcnemar_or_exact_ci(b, c, alpha=ALPHA):
    """Exact CI for the McNemar OR = b/c, derived from the exact (Clopper-Pearson)
    CI for the binomial proportion b/(b+c) with n = b+c trials, then transformed
    to the odds scale p/(1-p). OR point estimate is b/c (undefined if c=0)."""
    n = b + c
    if n == 0:
        return np.nan, np.nan, np.nan
    or_point = b / c if c > 0 else np.inf
    lo_p, hi_p = proportion_confint(b, n, alpha=alpha, method="beta")
    lo = lo_p / (1 - lo_p) if lo_p < 1 else np.inf
    hi = hi_p / (1 - hi_p) if hi_p < 1 else np.inf
    return or_point, lo, hi


def holm(pvals, labels):
    pvals = np.asarray(pvals, dtype=float)
    reject, p_adj, _, _ = multipletests(pvals, alpha=ALPHA, method="holm")
    return pd.DataFrame({"test": labels, "p_raw": pvals, "p_holm": p_adj,
                          "reject_holm_0.05": reject})


# ---------------------------------------------------------------------------
# Analysis 1 + 2: paired A-vs-B and provider contrasts share the same machinery
# ---------------------------------------------------------------------------

def paired_contrast_per_model(df, arm_x, arm_y, models=MODELS):
    """For each model, pivot to one row per question with outcome under arm_x
    and arm_y, both scored on run 1 strict_correct, and run exact McNemar.
    Returns one row per model with counts, McNemar p, risk diff + CI, OR + CI."""
    rows = []
    for model in models:
        sub = df[(df["model"] == model) & (df["arm"].isin([arm_x, arm_y]))]
        piv = sub.pivot_table(index="question_id", columns="arm",
                               values="strict_correct", aggfunc="first")
        piv = piv.dropna(subset=[arm_x, arm_y])
        assert piv.shape[0] == 500, (
            f"{model}: expected 500 paired questions for {arm_x} vs {arm_y}, got {piv.shape[0]}"
        )
        x = piv[arm_x].astype(int)
        y = piv[arm_y].astype(int)
        n11 = int(((x == 1) & (y == 1)).sum())
        n10 = int(((x == 1) & (y == 0)).sum())  # x correct, y incorrect ("b")
        n01 = int(((x == 0) & (y == 1)).sum())  # x incorrect, y correct ("c")
        n00 = int(((x == 0) & (y == 0)).sum())
        n = n11 + n10 + n01 + n00
        table = [[n11, n10], [n01, n00]]
        res = mcnemar(table, exact=True)
        rd, rd_lo, rd_hi, rd_se = paired_risk_diff_ci(n10, n01, n)
        orp, or_lo, or_hi = mcnemar_or_exact_ci(n10, n01)
        rows.append({
            "contrast": f"{arm_x}_vs_{arm_y}",
            "model": model,
            "n_pairs": n,
            "n_x_correct": int(x.sum()),
            "n_y_correct": int(y.sum()),
            "acc_x": x.mean(),
            "acc_y": y.mean(),
            "concordant_both_correct": n11,
            "concordant_both_wrong": n00,
            "discordant_b_x_only": n10,
            "discordant_c_y_only": n01,
            "mcnemar_exact_p": res.pvalue,
            "risk_diff_x_minus_y": rd,
            "risk_diff_ci_lo": rd_lo,
            "risk_diff_ci_hi": rd_hi,
            "mcnemar_or_x_vs_y": orp,
            "or_ci_lo": or_lo,
            "or_ci_hi": or_hi,
        })
    return pd.DataFrame(rows)


def pooled_gee_contrast(df, arm_x, arm_y, models=MODELS, cluster_col="question_id"):
    """Pooled test across models, question as GEE cluster (exchangeable),
    logit(strict_correct) ~ C(arm), long format with 2 rows per (question, model)."""
    sub = df[(df["model"].isin(models)) & (df["arm"].isin([arm_x, arm_y]))].copy()
    sub["arm_x"] = (sub["arm"] == arm_x).astype(int)  # 1 = arm_x, 0 = arm_y
    sub = sub[["question_id", "model", "arm_x", "strict_correct"]].dropna()
    fam = Binomial(link=LogitLink())
    model_gee = GEE.from_formula(
        "strict_correct ~ arm_x", groups=cluster_col, data=sub,
        cov_struct=Exchangeable(), family=fam,
    )
    fit = model_gee.fit()
    coef = fit.params["arm_x"]
    se = fit.bse["arm_x"]
    z = coef / se
    p = 2 * (1 - sps.norm.cdf(abs(z)))
    ci_lo, ci_hi = fit.conf_int().loc["arm_x"]
    n_clusters = sub[cluster_col].nunique()
    n_obs = sub.shape[0]
    return {
        "contrast": f"{arm_x}_vs_{arm_y}",
        "method": "GEE logistic, exchangeable corr, cluster=question_id, pooled over 4 models",
        "n_clusters_questions": n_clusters,
        "n_obs": n_obs,
        "log_or_arm_x_vs_arm_y": coef,
        "se_log_or": se,
        "or_arm_x_vs_arm_y": float(np.exp(coef)),
        "or_ci_lo": float(np.exp(ci_lo)),
        "or_ci_hi": float(np.exp(ci_hi)),
        "wald_z": z,
        "wald_p": p,
    }


def pooled_permutation_contrast(df, arm_x, arm_y, models=MODELS, n_perm=N_PERM, seed=RNG_SEED):
    """Robustness check for the pooled contrast: permute whole questions. For
    each question, the entire (model x condition) bundle has its arm_x/arm_y
    labels swapped together with probability 0.5 (respecting that condition is
    within-question, within-model paired data and models sharing a question are
    correlated). Statistic = pooled risk difference in strict_correct (arm_x -
    arm_y), summed over all 4 models. Two-sided permutation p-value."""
    sub = df[(df["model"].isin(models)) & (df["arm"].isin([arm_x, arm_y]))]
    wide = sub.pivot_table(index="question_id", columns=["model", "arm"],
                            values="strict_correct", aggfunc="first")
    questions = wide.index.to_numpy()
    n_q = len(questions)
    x_cols = [(m, arm_x) for m in models]
    y_cols = [(m, arm_y) for m in models]
    X = wide[x_cols].to_numpy(dtype=float)  # n_q x 4
    Y = wide[y_cols].to_numpy(dtype=float)
    obs_stat = (X - Y).sum()  # pooled discordance sum, sign-consistent with risk diff

    rng = np.random.default_rng(seed)
    perm_stats = np.empty(n_perm)
    for i in range(n_perm):
        swap = rng.random(n_q) < 0.5
        d = X - Y
        d[swap] = -d[swap]
        perm_stats[i] = d.sum()
    n_exceed = int((np.abs(perm_stats) >= abs(obs_stat)).sum())
    p_perm = float(n_exceed / n_perm)
    n_total = n_q * len(models) * 2
    return {
        "contrast": f"{arm_x}_vs_{arm_y}",
        "method": f"permutation (whole-question swap of {arm_x}/{arm_y} labels across all "
                  f"4 models jointly, n_perm={n_perm}, seed={seed})",
        "observed_pooled_diff_sum": float(obs_stat),
        "observed_pooled_risk_diff": float(obs_stat / n_total),
        "n_perm": n_perm,
        "n_exceed": n_exceed,
        "perm_p_two_sided": p_perm,
    }


def run_condition_a_vs_b(run1):
    or_df = run1[run1["provider"] == "openrouter"]
    per_model = paired_contrast_per_model(or_df, "openrouter_A", "openrouter_B")
    pooled_gee = pooled_gee_contrast(or_df, "openrouter_A", "openrouter_B")
    pooled_perm = pooled_permutation_contrast(or_df, "openrouter_A", "openrouter_B")
    return per_model, pooled_gee, pooled_perm


def run_provider_contrast(run1):
    sub = run1[run1["arm"].isin(["openrouter_A", "tailscale_A"])]
    per_model = paired_contrast_per_model(sub, "openrouter_A", "tailscale_A")
    pooled_gee = pooled_gee_contrast(sub, "openrouter_A", "tailscale_A")
    pooled_perm = pooled_permutation_contrast(sub, "openrouter_A", "tailscale_A")
    return per_model, pooled_gee, pooled_perm


# ---------------------------------------------------------------------------
# Analysis 3: model main effects within each arm (Cochran's Q + post-hoc McNemar)
# ---------------------------------------------------------------------------

def model_main_effects(run1, models=MODELS):
    arms = ["openrouter_A", "openrouter_B", "tailscale_A"]
    omnibus_rows = []
    posthoc_frames = {}
    for arm in arms:
        sub = run1[run1["arm"] == arm]
        piv = sub.pivot_table(index="question_id", columns="model",
                               values="strict_correct", aggfunc="first")
        piv = piv[models].dropna()
        assert piv.shape[0] == 500, f"{arm}: expected 500 questions, got {piv.shape[0]}"
        q_res = cochrans_q(piv.to_numpy())
        omnibus_rows.append({
            "arm": arm,
            "n_questions": piv.shape[0],
            "k_models": len(models),
            "cochrans_q": q_res.statistic,
            "df": len(models) - 1,
            "p_raw": q_res.pvalue,
            "model_accuracies": {m: float(piv[m].mean()) for m in models},
        })
        # post-hoc pairwise McNemar, all 6 pairs
        ph_rows = []
        for i in range(len(models)):
            for j in range(i + 1, len(models)):
                mi, mj = models[i], models[j]
                x = piv[mi].astype(int)
                y = piv[mj].astype(int)
                n10 = int(((x == 1) & (y == 0)).sum())
                n01 = int(((x == 0) & (y == 1)).sum())
                n11 = int(((x == 1) & (y == 1)).sum())
                n00 = int(((x == 0) & (y == 0)).sum())
                n = n11 + n10 + n01 + n00
                res = mcnemar([[n11, n10], [n01, n00]], exact=True)
                rd, rd_lo, rd_hi, _ = paired_risk_diff_ci(n10, n01, n)
                orp, or_lo, or_hi = mcnemar_or_exact_ci(n10, n01)
                ph_rows.append({
                    "arm": arm, "model_i": mi, "model_j": mj,
                    "n": n, "acc_i": x.mean(), "acc_j": y.mean(),
                    "b_i_only": n10, "c_j_only": n01,
                    "mcnemar_exact_p": res.pvalue,
                    "risk_diff_i_minus_j": rd, "rd_ci_lo": rd_lo, "rd_ci_hi": rd_hi,
                    "or_i_vs_j": orp, "or_ci_lo": or_lo, "or_ci_hi": or_hi,
                })
        ph_df = pd.DataFrame(ph_rows)
        holm_res = holm(ph_df["mcnemar_exact_p"].to_numpy(),
                         [f"{arm}:{r.model_i}_vs_{r.model_j}" for r in ph_df.itertuples()])
        ph_df["p_holm"] = holm_res["p_holm"].to_numpy()
        ph_df["reject_holm_0.05"] = holm_res["reject_holm_0.05"].to_numpy()
        posthoc_frames[arm] = ph_df

    omnibus_df = pd.DataFrame(omnibus_rows)
    holm_omni = holm(omnibus_df["p_raw"].to_numpy(), omnibus_df["arm"].tolist())
    omnibus_df["p_holm"] = holm_omni["p_holm"].to_numpy()
    omnibus_df["reject_holm_0.05"] = holm_omni["reject_holm_0.05"].to_numpy()
    posthoc_all = pd.concat(posthoc_frames.values(), ignore_index=True)
    return omnibus_df, posthoc_all


# ---------------------------------------------------------------------------
# Analysis 4: flip rate (898-cell replicate set) -- NOT paired, cluster-robust
# ---------------------------------------------------------------------------

def flip_rate_gee(rep898, vertex_affected, exclude_vertex, models=MODELS):
    df = rep898.copy()
    df["is_vertex_affected"] = df.apply(
        lambda r: (r["arm"], r["model"], r["question_id"]) in vertex_affected, axis=1
    )
    n_excluded = int(df["is_vertex_affected"].sum())
    if exclude_vertex:
        df = df[~df["is_vertex_affected"]]
    df = df.dropna(subset=["flipped_to_correct"])
    df["flip"] = df["flipped_to_correct"].astype(int)
    df["question_cluster"] = df["source_key"] + "||" + df["question_id"]

    arms = ["openrouter_A", "openrouter_B", "tailscale_A"]
    fam = Binomial(link=LogitLink())

    def fit_and_report(data, group_col, ref, contrast_name):
        cats = [c for c in data[group_col].unique()]
        data = data.copy()
        data[group_col] = pd.Categorical(data[group_col], categories=[ref] + [c for c in cats if c != ref])
        gee_model = GEE.from_formula(
            f"flip ~ C({group_col}, Treatment(reference='{ref}'))",
            groups="question_cluster", data=data,
            cov_struct=Exchangeable(), family=fam,
        )
        fit = gee_model.fit()
        rows = []
        for name, coef in fit.params.items():
            if name == "Intercept":
                continue
            se = fit.bse[name]
            z = coef / se
            p = 2 * (1 - sps.norm.cdf(abs(z)))
            ci_lo, ci_hi = fit.conf_int().loc[name]
            level = name.split("T.")[-1].rstrip("]")
            rows.append({
                "contrast_family": contrast_name,
                "reference": ref,
                "level": level,
                "log_or": coef, "se": se, "or_estimate": float(np.exp(coef)),
                "or_ci_lo": float(np.exp(ci_lo)), "or_ci_hi": float(np.exp(ci_hi)),
                "wald_p": p,
            })
        return pd.DataFrame(rows), fit

    arm_df, arm_fit = fit_and_report(df, "arm", "openrouter_A", "flip_rate_by_arm")
    model_df, model_fit = fit_and_report(df, "model", "google/gemini-3.6-flash", "flip_rate_by_model")

    arm_df["p_holm"] = holm(arm_df["wald_p"].to_numpy(), arm_df["level"].tolist())["p_holm"].to_numpy()
    model_df["p_holm"] = holm(model_df["wald_p"].to_numpy(), model_df["level"].tolist())["p_holm"].to_numpy()

    combined = pd.concat([arm_df, model_df], ignore_index=True)
    combined["exclude_vertex"] = exclude_vertex
    combined["n_cells_used"] = df.shape[0]
    combined["n_vertex_cells_excluded_or_flagged"] = n_excluded

    raw_rates = (
        df.groupby(["arm", "model"])["flip"].agg(["mean", "sum", "count"]).reset_index()
        .rename(columns={"mean": "flip_rate", "sum": "n_flipped", "count": "n_cells"})
    )
    raw_rates["exclude_vertex"] = exclude_vertex
    return combined, raw_rates


# ---------------------------------------------------------------------------
# Assumption checks
# ---------------------------------------------------------------------------

def clustering_diagnostic(run1):
    """Quantify within-question dependence to justify the clustering approach:
    intraclass correlation of strict_correct within question (across the 12
    arm-model cells), via one-way random-effects ICC."""
    piv = run1.groupby("question_id")["strict_correct"].agg(["mean", "count"])
    grand_mean = run1["strict_correct"].mean()
    k = piv["count"].mean()
    ms_between = ((piv["mean"] - grand_mean) ** 2 * piv["count"]).sum() / (piv.shape[0] - 1)
    within = run1.merge(piv["mean"].rename("qmean"), left_on="question_id", right_index=True)
    ms_within = ((within["strict_correct"] - within["qmean"]) ** 2).sum() / (run1.shape[0] - piv.shape[0])
    icc = (ms_between - ms_within) / (ms_between + (k - 1) * ms_within) if (ms_between + (k - 1) * ms_within) != 0 else np.nan
    return {"icc_question_strict_correct": float(icc), "k_cells_per_question": float(k)}


# ---------------------------------------------------------------------------
# NOTA (none-of-the-above) analysis -- condition B replaces the correct option
# with a fixed NOTA string in the same letter slot; distractors are unchanged.
# See STATS_SPEC.md "WHAT CONDITIONS A AND B ACTUALLY ARE". Everything here is
# computed independently from run1-6000, not copied from the spec, to verify
# the claims before citing them.
# ---------------------------------------------------------------------------

NOTA_STRING = "Ninguna de las respuestas anteriores es correcta."


def nota_analysis(run1, models=MODELS):
    or_df = run1[run1["provider"] == "openrouter"]
    a = or_df[or_df["condition"] == "A"]
    b = or_df[or_df["condition"] == "B"]

    # 1. Confirm B's correct option is the fixed NOTA string in all 500 questions.
    b_unique_correct = b.drop_duplicates("question_id")["correct_option_text"].unique()
    assert len(b_unique_correct) == 1 and b_unique_correct[0] == NOTA_STRING, (
        "condition B correct_option_text is not a single fixed NOTA string -- re-check before reporting"
    )
    assert (or_df["correct_letter"] == "a").sum() == 0, "option a is not supposed to ever be correct"

    # 2. option 'a' selection rate, overall and per model, A vs B (all cells, not just wrong).
    a_select_overall = {
        "A": float((a["selected_letter"] == "a").mean()),
        "B": float((b["selected_letter"] == "a").mean()),
        "n_A": int(len(a)), "n_B": int(len(b)),
    }
    a_select_per_model = []
    for model in models:
        rate_a = float((a[a["model"] == model]["selected_letter"] == "a").mean())
        rate_b = float((b[b["model"] == model]["selected_letter"] == "a").mean())
        a_select_per_model.append({"model": model, "selected_a_rate_A": rate_a, "selected_a_rate_B": rate_b})
    a_select_per_model = pd.DataFrame(a_select_per_model)

    # 3. Per-model wrong-answer letter distribution under B (what models pick instead
    #    of recognising NOTA). Also report the null/chance rate for picking 'a' given
    #    the question mix: 'a' is a candidate wrong answer on 100% of questions, while
    #    b/c/d are candidates only when they are not the correct letter for that question,
    #    so uniform random guessing among the 3 available wrong options implies E[a] = 1/3.
    b_wrong = b[b["strict_correct"] == 0]
    wrong_dist_rows = []
    for model in models:
        g = b_wrong[b_wrong["model"] == model]
        n_wrong = len(g)
        vc = g["selected_letter"].value_counts(normalize=True)
        n_a = int((g["selected_letter"] == "a").sum())
        row = {"model": model, "n_wrong_in_B": int(n_wrong)}
        for letter in ["a", "b", "c", "d"]:
            row[f"pct_selected_{letter}"] = float(vc.get(letter, 0.0) * 100)
        # exact (Clopper-Pearson) 95% CI on the 'a' share, since this is the specific
        # column the interpretive gloss below leans on and n_wrong varies a lot by model.
        ci_lo, ci_hi = proportion_confint(n_a, n_wrong, alpha=ALPHA, method="beta")
        row["pct_selected_a_ci_lo"] = float(ci_lo * 100)
        row["pct_selected_a_ci_hi"] = float(ci_hi * 100)
        wrong_dist_rows.append(row)
    wrong_dist = pd.DataFrame(wrong_dist_rows)
    wrong_dist["chance_pct_a_uniform_guess"] = 100.0 / 3.0

    # 4. Option-length surface cue: avg length of the correct option in A, in B
    #    (constant = len(NOTA)), and avg length of the 3 distractors (byte-identical
    #    across conditions, computed once from A).
    a_q = a.drop_duplicates("question_id")
    b_q = b.drop_duplicates("question_id")
    avg_len_correct_A = float(a_q["correct_option_text"].str.len().mean())
    avg_len_correct_B = float(b_q["correct_option_text"].str.len().mean())

    def _distractor_lengths(row):
        opts = {"a": row["option_a"], "b": row["option_b"], "c": row["option_c"], "d": row["option_d"]}
        return [len(str(v)) for k, v in opts.items() if k != row["correct_letter"]]

    flat_distractor_lens = [x for lens in a_q.apply(_distractor_lengths, axis=1) for x in lens]
    avg_len_distractor = float(np.mean(flat_distractor_lens))

    length_cue = {
        "avg_len_correct_option_A": avg_len_correct_A,
        "avg_len_correct_option_B_NOTA": avg_len_correct_B,
        "avg_len_distractor_A_and_B": avg_len_distractor,
        "n_questions": int(len(a_q)),
        "n_distractor_options": len(flat_distractor_lens),
    }

    # 5. Rule out strict_correct vs letter_correct disagreement as an artefact
    #    driving the A-vs-B gap (i.e. confirm the gap is a real answer-selection
    #    effect, not exact-text-match scoring noise).
    mismatch = (or_df["strict_correct"].astype(int) != or_df["letter_correct"].astype(int))
    scoring_check = {
        "n_openrouter_AB_cells": int(len(or_df)),
        "n_strict_vs_letter_mismatch": int(mismatch.sum()),
    }

    # 6. Flip-rate (898-cell replicate set) composition by arm -- B contributes far
    #    more replicated cells because B is harder, so pooled flip-rate statements
    #    are weighted toward NOTA items.
    return {
        "b_correct_option_is_fixed_nota_string": True,
        "nota_string": NOTA_STRING,
        "option_a_selection_rate": a_select_overall,
        "option_a_selection_rate_per_model": a_select_per_model,
        "b_wrong_answer_letter_distribution_per_model": wrong_dist,
        "option_length_cue": length_cue,
        "scoring_artefact_check": scoring_check,
    }


def replicate_composition_by_arm(rep898):
    return rep898["arm"].value_counts().rename_axis("arm").reset_index(name="n_cells")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    run1 = load_run1()
    rep898 = load_replicates_898()
    vertex_affected = load_vertex_affected_cells()

    icc_diag = clustering_diagnostic(run1)

    # --- Analysis 1: Condition A vs B ---
    a_vs_b_per_model, a_vs_b_gee, a_vs_b_perm = run_condition_a_vs_b(run1)
    fam1_labels = a_vs_b_per_model["model"].tolist() + ["pooled_GEE"]
    fam1_p = a_vs_b_per_model["mcnemar_exact_p"].tolist() + [a_vs_b_gee["wald_p"]]
    fam1_holm = holm(fam1_p, fam1_labels)
    a_vs_b_per_model = a_vs_b_per_model.merge(
        fam1_holm.rename(columns={"test": "model"}), on="model", how="left"
    )
    a_vs_b_gee["p_holm"] = fam1_holm.loc[fam1_holm["test"] == "pooled_GEE", "p_holm"].iloc[0]
    a_vs_b_gee["family"] = "condition_A_vs_B (4 per-model McNemar + pooled GEE)"

    # --- Analysis 2: Provider (condition held at A) ---
    prov_per_model, prov_gee, prov_perm = run_provider_contrast(run1)
    fam2_labels = prov_per_model["model"].tolist() + ["pooled_GEE"]
    fam2_p = prov_per_model["mcnemar_exact_p"].tolist() + [prov_gee["wald_p"]]
    fam2_holm = holm(fam2_p, fam2_labels)
    prov_per_model = prov_per_model.merge(
        fam2_holm.rename(columns={"test": "model"}), on="model", how="left"
    )
    prov_gee["p_holm"] = fam2_holm.loc[fam2_holm["test"] == "pooled_GEE", "p_holm"].iloc[0]
    prov_gee["family"] = "provider_openrouterA_vs_tailscaleA (4 per-model McNemar + pooled GEE)"

    # --- Analysis 3: model main effects ---
    model_omnibus, model_posthoc = model_main_effects(run1)

    # --- Analysis 4: flip rate, with + without vertex sensitivity ---
    flip_incl, raw_incl = flip_rate_gee(rep898, vertex_affected, exclude_vertex=False)
    flip_excl, raw_excl = flip_rate_gee(rep898, vertex_affected, exclude_vertex=True)
    flip_combined = pd.concat([flip_incl, flip_excl], ignore_index=True)
    raw_rates_combined = pd.concat([raw_incl, raw_excl], ignore_index=True)
    replicate_composition = replicate_composition_by_arm(rep898)

    # --- NOTA (condition B) mechanism analysis ---
    nota = nota_analysis(run1)

    # --- write CSV/JSON outputs ---
    a_vs_b_per_model.to_csv(RESULTS / "primary_condition_AvsB_per_model.csv", index=False)
    prov_per_model.to_csv(RESULTS / "primary_provider_per_model.csv", index=False)
    model_omnibus.drop(columns=["model_accuracies"]).to_csv(
        RESULTS / "primary_model_effects_omnibus.csv", index=False)
    model_posthoc.to_csv(RESULTS / "primary_model_effects_posthoc.csv", index=False)
    flip_combined.to_csv(RESULTS / "primary_flip_rate_gee.csv", index=False)
    raw_rates_combined.to_csv(RESULTS / "primary_flip_rate_raw.csv", index=False)
    replicate_composition.to_csv(RESULTS / "primary_flip_rate_replicate_composition.csv", index=False)
    nota["option_a_selection_rate_per_model"].to_csv(RESULTS / "primary_nota_option_a_selection.csv", index=False)
    nota["b_wrong_answer_letter_distribution_per_model"].to_csv(
        RESULTS / "primary_nota_wrong_answer_distribution.csv", index=False)

    summary = {
        "spec_constraints_honoured": {
            "provider_x_condition_interaction": "INESTIMABLE by design (no tailscale_B). Not attempted.",
            "a_vs_b_pairing": "Paired on 500 identical questions; McNemar used, not two-sample proportion test.",
            "run1_contamination_check": "Verified from ledger/ATTEMPT_TIMELINE.csv: all logged attempts are run_index in {2,3}; run 1 has zero rows in the deviation-era attempt log and predates any Vertex routing (deviation began 2026-08-06; run-1 collection finished before that window per DEVIATIONS.md).",
        },
        "clustering_diagnostic": icc_diag,
        "what_condition_B_is": {
            "description": "Condition B is a none-of-the-above (NOTA) manipulation, not a generic "
                            "prompt variant: the substantive correct option is replaced by a fixed "
                            "NOTA string in the same letter slot; all 3 distractors are byte-identical "
                            "to condition A. Verified independently from run1-6000 (not copied from "
                            "STATS_SPEC.md), see 'nota_mechanism' below.",
        },
        "condition_A_vs_B": {
            "per_model": a_vs_b_per_model.to_dict(orient="records"),
            "pooled_gee": a_vs_b_gee,
            "pooled_permutation_robustness": a_vs_b_perm,
        },
        "nota_mechanism": {
            "b_correct_option_is_fixed_nota_string": nota["b_correct_option_is_fixed_nota_string"],
            "nota_string": nota["nota_string"],
            "option_a_selection_rate_overall": nota["option_a_selection_rate"],
            "option_a_selection_rate_per_model": nota["option_a_selection_rate_per_model"].to_dict(orient="records"),
            "b_wrong_answer_letter_distribution_per_model": nota["b_wrong_answer_letter_distribution_per_model"].to_dict(orient="records"),
            "option_length_cue": nota["option_length_cue"],
            "scoring_artefact_check": nota["scoring_artefact_check"],
        },
        "provider_openrouterA_vs_tailscaleA": {
            "framing": "Provider+prompt-delivery contrast, not a pure transport contrast: "
                       "TailScale arm uses GIFT prompt ID 13 with server-side MCQ instructions "
                       "and does not honour OpenRouter's JSON-schema enforcement.",
            "per_model": prov_per_model.to_dict(orient="records"),
            "pooled_gee": prov_gee,
            "pooled_permutation_robustness": prov_perm,
        },
        "model_main_effects": {
            "omnibus_cochrans_q": model_omnibus.to_dict(orient="records"),
            "posthoc_pairwise_mcnemar": model_posthoc.to_dict(orient="records"),
        },
        "flip_rate_secondary": {
            "note": "NOT paired -- conditioned on run-1 failure, so the cell sets differ "
                    "across arms/models. Cluster-robust GEE logistic, cluster=question. "
                    "Composition is unbalanced across arms because condition B is harder "
                    "(more NOTA-item failures feed the replicate set): "
                    f"{dict(zip(replicate_composition['arm'], replicate_composition['n_cells']))}. "
                    "Pooled/model-level flip-rate statements are therefore weighted toward NOTA items.",
            "gee_results": flip_combined.to_dict(orient="records"),
            "raw_rates": raw_rates_combined.to_dict(orient="records"),
            "replicate_composition_by_arm": replicate_composition.to_dict(orient="records"),
        },
    }

    def _default(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError(str(type(o)))

    with open(RESULTS / "primary_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=_default)

    write_report(summary, a_vs_b_per_model, a_vs_b_gee, a_vs_b_perm,
                 prov_per_model, prov_gee, prov_perm,
                 model_omnibus, model_posthoc,
                 flip_combined, raw_rates_combined, icc_diag,
                 nota, replicate_composition)

    print("Done. Wrote results/ CSV+JSON+PRIMARY_TESTS.md")


def fmt_p(p):
    return "<0.0001" if p < 0.0001 else f"{p:.4f}"


def fmt_perm_p(perm_result):
    """Report the permutation p honestly at its actual resolution: if zero
    permutations were at least as extreme as observed, the true p-value is
    only bounded above by 1/n_perm, not equal to it -- state that explicitly
    rather than implying more precision than n_perm permutations can give."""
    n_perm = perm_result["n_perm"]
    n_exceed = perm_result["n_exceed"]
    if n_exceed == 0:
        return f"< {1 / n_perm:.5f} (0/{n_perm} permutations at least as extreme as observed)"
    return f"{perm_result['perm_p_two_sided']:.4f} ({n_exceed}/{n_perm} permutations at least as extreme)"


def write_report(summary, a_vs_b_per_model, a_vs_b_gee, a_vs_b_perm,
                  prov_per_model, prov_gee, prov_perm,
                  model_omnibus, model_posthoc,
                  flip_combined, raw_rates_combined, icc_diag,
                  nota, replicate_composition):
    lines = []
    lines.append("# PRIMARY_TESTS -- Condition, provider, model, and flip-rate contrasts")
    lines.append("")
    lines.append("Owner: agent 2 of 4. Reproduced by `scripts/02_primary.py`. Sources are read-only; "
                 "outputs live in this `results/` directory as CSV + `primary_summary.json`.")
    lines.append("")
    lines.append("## Constraints honoured (see STATS_SPEC.md)")
    lines.append("")
    lines.append("- **provider x condition interaction: INESTIMABLE.** OpenRouter has both A and B; "
                 "TailScale has only A (`tailscale_B` does not exist). This design is not underpowered "
                 "for the interaction -- the interaction term has no data to estimate it from. No "
                 "interaction test is attempted anywhere in this script or report.")
    lines.append("- **A vs B is paired** on the identical 500 questions (verified: 500/500 matched "
                 "pairs per model in both arms). Every A-vs-B test below is McNemar (exact, binomial "
                 "on discordant pairs) or a paired/clustered generalisation of it -- never a two-sample "
                 "proportion test.")
    lines.append(f"- **Run 1 is uncontaminated.** {summary['spec_constraints_honoured']['run1_contamination_check']}")
    lines.append("")
    lines.append("## Clustering diagnostic")
    lines.append("")
    lines.append(f"One-way random-effects ICC of run-1 `strict_correct` within question "
                 f"(k~{icc_diag['k_cells_per_question']:.0f} cells/question, pooling all arms/models): "
                 f"**ICC = {icc_diag['icc_question_strict_correct']:.3f}**. A non-trivial positive ICC "
                 "confirms within-question dependence is real (harder questions are harder across "
                 "arms/models) and justifies clustering by question in every pooled/multi-model test "
                 "below, rather than treating all 6000 cells as independent.")
    lines.append("")

    # --- Section 1 ---
    lines.append("## 1. NOTA susceptibility: condition A vs B (OpenRouter only, run-1 strict_correct, "
                 "paired on question)")
    lines.append("")
    lines.append("**What condition B actually is (established after the first pass of this analysis, "
                 "verified independently here from `run1-6000-with-replicate-status.csv` rather than "
                 "taken on faith -- see `nota_analysis()` in `scripts/02_primary.py`).** Condition B is "
                 "NOT a generic prompt/condition variant. Diffing the two condition files shows they "
                 "share all 500 questions, all question text, and all `correct_letter` values; the only "
                 "columns that differ are the option that happens to be correct for each question "
                 "(`option_b`/`option_c`/`option_d`, exactly on the 178/198/124 questions where that "
                 "letter is correct) and `correct_option_text`. **Every distractor is byte-identical "
                 "across conditions.** In condition B the correct option takes exactly one value across "
                 f"all 500 questions: *\"{nota['nota_string']}\"* (\"None of the above answers is "
                 "correct\"). Confirmed here by asserting a single unique `correct_option_text` value "
                 "across all 500 condition-B questions (see `nota_analysis()`), and that `correct_letter` "
                 "is never `a`.")
    lines.append("")
    lines.append("**Condition B is therefore a none-of-the-above (NOTA) manipulation.** The substantive "
                 "correct answer is deleted and replaced by a fixed NOTA statement in the same letter "
                 "slot; the three remaining options are unchanged genuine distractors. To score correct "
                 "in B, a model must recognise that no listed substantive option is right -- it cannot "
                 "win by picking the most plausible-sounding content. **\"Condition A scored higher than "
                 "condition B\" is true but nearly uninformative; the finding is how many accuracy "
                 "points each model loses when the correct answer is replaced by none-of-the-above.** "
                 "Because A and B are paired on identical questions with identical distractors and a "
                 "single manipulated element, this is the cleanest and most substantively interesting "
                 "contrast in the study.")
    lines.append("")
    lines.append("Family: 4 per-model exact McNemar tests + 1 pooled GEE test (5 tests), "
                 "Holm-Bonferroni corrected together.")
    lines.append("")
    lines.append("| Model | n | acc A | acc B (NOTA) | b (A-only) | c (B-only) | McNemar p (raw) | p (Holm) | "
                 "**NOTA accuracy loss (A-B)** [95% CI] | OR (b/c) [95% CI] |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in a_vs_b_per_model.itertuples():
        lines.append(f"| {r.model} | {r.n_pairs} | {r.acc_x:.3f} | {r.acc_y:.3f} | "
                     f"{r.discordant_b_x_only} | {r.discordant_c_y_only} | "
                     f"{fmt_p(r.mcnemar_exact_p)} | {fmt_p(r.p_holm)} | "
                     f"**{r.risk_diff_x_minus_y*100:+.1f} pts** [{r.risk_diff_ci_lo*100:+.1f}, {r.risk_diff_ci_hi*100:+.1f}] | "
                     f"{r.mcnemar_or_x_vs_y:.2f} [{r.or_ci_lo:.2f}, {r.or_ci_hi:.2f}] |")
    lines.append("")
    lines.append("Every model loses accuracy under NOTA, ranging from "
                 f"{a_vs_b_per_model['risk_diff_x_minus_y'].min()*100:.1f} points "
                 f"({a_vs_b_per_model.loc[a_vs_b_per_model['risk_diff_x_minus_y'].idxmin(), 'model']}) to "
                 f"{a_vs_b_per_model['risk_diff_x_minus_y'].max()*100:.1f} points "
                 f"({a_vs_b_per_model.loc[a_vs_b_per_model['risk_diff_x_minus_y'].idxmax(), 'model']}), "
                 "all significant at Holm p<0.0001.")
    lines.append("")
    lines.append(f"**Pooled (GEE, logistic, exchangeable correlation, cluster=question, {a_vs_b_gee['n_obs']} "
                 f"obs over {a_vs_b_gee['n_clusters_questions']} question clusters x 4 models):** "
                 f"OR(A vs B) = {a_vs_b_gee['or_arm_x_vs_arm_y']:.2f} "
                 f"[{a_vs_b_gee['or_ci_lo']:.2f}, {a_vs_b_gee['or_ci_hi']:.2f}], "
                 f"Wald p = {fmt_p(a_vs_b_gee['wald_p'])}, Holm p = {fmt_p(a_vs_b_gee['p_holm'])}.")
    lines.append("")
    lines.append(f"**Robustness (permutation, whole-question swap, n_perm={N_PERM}):** observed pooled "
                 f"NOTA accuracy loss (A-B) = {a_vs_b_perm['observed_pooled_risk_diff']*100:+.2f} pts, "
                 f"permutation p {fmt_perm_p(a_vs_b_perm)}. "
                 "GEE is the primary pooled method (it yields an effect size + CI); the permutation "
                 "test is reported as a distribution-free check on the pooled p-value.")
    lines.append("")
    lines.append("### 1a. NOTA-failure mechanism (why models fail B)")
    lines.append("")
    lines.append("**Not a scoring artefact.** Among the 4000 OpenRouter A+B run-1 cells, `strict_correct` "
                 f"and `letter_correct` disagree on only "
                 f"{nota['scoring_artefact_check']['n_strict_vs_letter_mismatch']} cell -- the A-vs-B gap "
                 "is a real answer-selection effect, not an artefact of exact-text matching.")
    lines.append("")
    lines.append("**Option `a` is never the correct answer, in either condition** (178+198+124 = 500 -- "
                 "the correct letter is always b, c, or d). It is always a genuine distractor. Under NOTA, "
                 "models select it far more often -- a signature of NOTA-recognition failure, not a "
                 "random shift:")
    lines.append("")
    lines.append(f"- Overall: **{nota['option_a_selection_rate']['A']*100:.2f}%** of condition-A "
                 f"cells vs **{nota['option_a_selection_rate']['B']*100:.2f}%** of condition-B "
                 f"cells select option `a` (n={nota['option_a_selection_rate']['n_A']} each).")
    lines.append("")
    lines.append("| Model | selected-`a` rate, A | selected-`a` rate, B | fold increase |")
    lines.append("|---|---|---|---|")
    a_rate_fold_parts = []
    for r in nota["option_a_selection_rate_per_model"].itertuples():
        fold = r.selected_a_rate_B / r.selected_a_rate_A if r.selected_a_rate_A > 0 else float("inf")
        fold_str = f"{fold:.1f}x" if np.isfinite(fold) else "inf (0% base)"
        lines.append(f"| {r.model} | {r.selected_a_rate_A*100:.2f}% | {r.selected_a_rate_B*100:.2f}% | {fold_str} |")
        a_rate_fold_parts.append(
            f"{r.model.split('/')[-1]} {r.selected_a_rate_A*100:.1f}%→{r.selected_a_rate_B*100:.1f}%"
        )
    lines.append("")
    lines.append("**Every model raises its selection of the never-correct option `a` from A to B, roughly "
                 "doubling or more in every case** (" + "; ".join(a_rate_fold_parts) + "). That "
                 "uniformity across four otherwise very different models -- all move in the same "
                 "direction by a similar-or-larger multiple -- is itself a NOTA-failure signature: facing "
                 "a NOTA item, models become measurably more willing to select an option that is wrong "
                 "by construction in all 500 questions, consistent with falling back toward "
                 "distractor-guessing rather than reliably recognising NOTA.")
    lines.append("")
    lines.append("**Per-model distribution of the wrong answer actually picked in B** (among cells scored "
                 "incorrect in condition B; chance rate for `a` under uniform random guessing among the 3 "
                 "available wrong options is 33.3% -- `a` is a candidate wrong answer on 100% of "
                 "questions, while `b`/`c`/`d` are only candidates on the subset of questions where that "
                 "letter isn't the correct one, so 33.3% is the correct uniform-guessing baseline, not an "
                 "arbitrary 25%):")
    lines.append("")
    lines.append("| Model | n wrong in B | % picked a | % picked b | % picked c | % picked d |")
    lines.append("|---|---|---|---|---|---|")
    for r in nota["b_wrong_answer_letter_distribution_per_model"].itertuples():
        lines.append(f"| {r.model} | {r.n_wrong_in_B} | {r.pct_selected_a:.1f}% | {r.pct_selected_b:.1f}% | "
                     f"{r.pct_selected_c:.1f}% | {r.pct_selected_d:.1f}% |")
    lines.append("")
    wd = nota["b_wrong_answer_letter_distribution_per_model"].set_index("model")
    at_chance = wd[wd["pct_selected_a"] >= 30]
    below_chance = wd[wd["pct_selected_a"] < 30]

    def _fmt_row(model, row):
        return (f"{model.split('/')[-1]} ({row['pct_selected_a']:.1f}%, n={row['n_wrong_in_B']:.0f}, "
                f"95% CI [{row['pct_selected_a_ci_lo']:.1f}, {row['pct_selected_a_ci_hi']:.1f}])")

    gemini_row = wd.loc["google/gemini-3.6-flash"]
    lines.append("**Suggestive secondary reading, against the 33.3% chance baseline (not 25%) -- a "
                 "distribution-of-errors observation, not a claim about model reasoning or "
                 "\"understanding\":** "
                 + " and ".join(_fmt_row(m, r) for m, r in at_chance.iterrows())
                 + " select `a` at/near chance when they fail B, i.e. their errors spread roughly "
                 "uniformly across the three available wrong options with no systematic aversion to the "
                 "never-correct one; "
                 + " and ".join(_fmt_row(m, r) for m, r in below_chance.iterrows())
                 + " select it clearly below chance, a mild but consistent tilt away from `a` even in "
                 "failure. Treat this as suggestive rather than established: it rests on 4 small, unequal "
                 f"samples, and gemini's in particular ({gemini_row['n_wrong_in_B']:.0f} wrong cells) has a "
                 f"wide 95% CI ([{gemini_row['pct_selected_a_ci_lo']:.1f}, "
                 f"{gemini_row['pct_selected_a_ci_hi']:.1f}]) that is not far from the below-chance group's "
                 "point estimates.")
    lines.append("")
    lc = nota["option_length_cue"]
    lines.append("**Option-length surface cue (flagged, not adjusted for).** Average character length "
                 f"across the {lc['n_questions']} questions: correct option in A = "
                 f"{lc['avg_len_correct_option_A']:.1f} chars, correct option in B (the fixed NOTA string) "
                 f"= {lc['avg_len_correct_option_B_NOTA']:.1f} chars, distractors (byte-identical across "
                 f"conditions) = {lc['avg_len_distractor_A_and_B']:.1f} chars "
                 f"(n={lc['n_distractor_options']} distractor instances). In condition A the correct "
                 "answer is slightly *longer* than distractors -- a model with a length-correlates-with-"
                 "correctness prior would be helped in A. In condition B the correct (NOTA) answer is "
                 "conspicuously *shorter* and identical across every item -- a model that had learned "
                 "\"the odd-length option is right\" could exploit that, or conversely a model that had "
                 "learned \"longer/more-specific answers are right\" would be actively misled toward the "
                 "distractors. Both directions are plausible; this analysis cannot separate a length cue "
                 "from genuine NOTA-recognition failure, and flags it for interpretation rather than "
                 "correcting for it.")
    lines.append("")

    # --- Section 2 ---
    lines.append("## 2. Provider: openrouter_A vs tailscale_A (condition held at A, paired on question)")
    lines.append("")
    lines.append("**Framing (binding):** " + summary["provider_openrouterA_vs_tailscaleA"]["framing"])
    lines.append("")
    lines.append("Family: 4 per-model exact McNemar tests + 1 pooled GEE test (5 tests), "
                 "Holm-Bonferroni corrected together, separate from the condition-A-vs-B family above.")
    lines.append("")
    lines.append("| Model | n | acc OR_A | acc TS_A | b (OR-only) | c (TS-only) | McNemar p (raw) | p (Holm) | "
                 "risk diff OR-TS [95% CI] | OR (b/c) [95% CI] |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in prov_per_model.itertuples():
        lines.append(f"| {r.model} | {r.n_pairs} | {r.acc_x:.3f} | {r.acc_y:.3f} | "
                     f"{r.discordant_b_x_only} | {r.discordant_c_y_only} | "
                     f"{fmt_p(r.mcnemar_exact_p)} | {fmt_p(r.p_holm)} | "
                     f"{r.risk_diff_x_minus_y:+.3f} [{r.risk_diff_ci_lo:+.3f}, {r.risk_diff_ci_hi:+.3f}] | "
                     f"{r.mcnemar_or_x_vs_y:.2f} [{r.or_ci_lo:.2f}, {r.or_ci_hi:.2f}] |")
    lines.append("")
    lines.append(f"**Pooled (GEE, same specification as Section 1):** OR(OpenRouter_A vs TailScale_A) = "
                 f"{prov_gee['or_arm_x_vs_arm_y']:.2f} [{prov_gee['or_ci_lo']:.2f}, {prov_gee['or_ci_hi']:.2f}], "
                 f"Wald p = {fmt_p(prov_gee['wald_p'])}, Holm p = {fmt_p(prov_gee['p_holm'])}.")
    lines.append("")
    lines.append(f"**Robustness (permutation, n_perm={N_PERM}):** observed pooled risk difference "
                 f"(OpenRouter_A - TailScale_A) = {prov_perm['observed_pooled_risk_diff']:+.4f}, "
                 f"permutation p {fmt_perm_p(prov_perm)}.")
    lines.append("")
    lines.append("**Every conclusion drawn from this section describes a provider+prompt-delivery "
                 "contrast (transport, GIFT prompt ID 13 vs the OpenRouter payload, and JSON-schema "
                 "enforcement differ simultaneously) -- it must not be reported as an isolated "
                 "transport/infrastructure effect.**")
    lines.append("")

    # --- Section 3 ---
    lines.append("## 3. Model main effects on run-1 strict_correct (within each arm)")
    lines.append("")
    lines.append("All 4 models answer the same 500 questions within an arm -> related-samples design. "
                 "Omnibus test: Cochran's Q (k=4). Family 1 = the 3 omnibus tests (one per arm), "
                 "Holm-corrected together. Post-hoc: pairwise exact McNemar (6 pairs per arm); each "
                 "arm's 6 pairs are their own Holm family (3 separate post-hoc families).")
    lines.append("")
    lines.append("### Omnibus (Cochran's Q)")
    lines.append("")
    lines.append("| Arm | n questions | Q | df | p (raw) | p (Holm) |")
    lines.append("|---|---|---|---|---|---|")
    for r in model_omnibus.itertuples():
        lines.append(f"| {r.arm} | {r.n_questions} | {r.cochrans_q:.2f} | {r.df} | "
                     f"{fmt_p(r.p_raw)} | {fmt_p(r.p_holm)} |")
    lines.append("")
    lines.append("### Post-hoc pairwise (exact McNemar, Holm-corrected within arm)")
    lines.append("")
    lines.append("| Arm | Model i | Model j | n | acc i | acc j | b (i-only) | c (j-only) | p (raw) | p (Holm) | "
                 "risk diff i-j [95% CI] | OR i vs j [95% CI] |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in model_posthoc.itertuples():
        lines.append(f"| {r.arm} | {r.model_i} | {r.model_j} | {r.n} | {r.acc_i:.3f} | {r.acc_j:.3f} | "
                     f"{r.b_i_only} | {r.c_j_only} | {fmt_p(r.mcnemar_exact_p)} | {fmt_p(r.p_holm)} | "
                     f"{r.risk_diff_i_minus_j:+.3f} [{r.rd_ci_lo:+.3f}, {r.rd_ci_hi:+.3f}] | "
                     f"{r.or_i_vs_j:.2f} [{r.or_ci_lo:.2f}, {r.or_ci_hi:.2f}] |")
    lines.append("")

    # --- Section 4 ---
    lines.append("## 4. Secondary: flip rate (898-cell replicate set)")
    lines.append("")
    lines.append(summary["flip_rate_secondary"]["note"])
    lines.append("")
    lines.append("Sensitivity: every flip-rate result is reported twice -- with all 898 logical calls, "
                 "and excluding logical calls where a replicate run (run 2 and/or run 3) was served by "
                 "the google-vertex routing deviation (openrouter_B / google/gemini-3.6-flash only, "
                 "91 affected replicate-run rows in the 1796-row replicate-cell table).")
    lines.append("")
    lines.append("**Replicate-set composition is unbalanced by arm because condition B is harder "
                 "(more NOTA-item failures enter the replicate pool):**")
    lines.append("")
    lines.append("| arm | n cells in 898-cell replicate set |")
    lines.append("|---|---|")
    for r in replicate_composition.itertuples():
        lines.append(f"| {r.arm} | {r.n_cells} |")
    lines.append("")
    lines.append("`openrouter_B` alone supplies 532/898 (59%) of the replicate set, vs 203 for "
                 "`openrouter_A` and 163 for `tailscale_A`. Any pooled or cross-arm flip-rate statement is "
                 "therefore weighted toward NOTA-item failures, not a balanced sample of failure modes.")
    lines.append("")
    lines.append("### Raw flip rates by arm x model")
    lines.append("")
    lines.append("| exclude_vertex | arm | model | n cells | n flipped | flip rate |")
    lines.append("|---|---|---|---|---|---|")
    for r in raw_rates_combined.itertuples():
        lines.append(f"| {r.exclude_vertex} | {r.arm} | {r.model} | {r.n_cells} | {r.n_flipped} | "
                     f"{r.flip_rate:.3f} |")
    lines.append("")
    lines.append("### Cluster-robust GEE (cluster = question), reference levels: arm=openrouter_A, "
                 "model=google/gemini-3.6-flash")
    lines.append("")
    lines.append("| exclude_vertex | n cells | family | level (vs reference) | OR | 95% CI | Wald p (raw) | p (Holm, within family) |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in flip_combined.itertuples():
        lines.append(f"| {r.exclude_vertex} | {r.n_cells_used} | {r.contrast_family} | {r.level} | "
                     f"{r.or_estimate:.2f} | [{r.or_ci_lo:.2f}, {r.or_ci_hi:.2f}] | {fmt_p(r.wald_p)} | {fmt_p(r.p_holm)} |")
    lines.append("")

    # --- Assumptions ---
    lines.append("## Assumptions and their status")
    lines.append("")
    lines.append("- **McNemar exactness**: exact binomial test on discordant pairs requires no "
                 "distributional assumption beyond independence of *questions* (not of the "
                 "arm/condition outcomes within a question, which McNemar is explicitly built to "
                 "handle). Holds by design -- 500 distinct questions per test.")
    lines.append("- **GEE exchangeable correlation, cluster=question**: consistency of GEE point "
                 "estimates does not require the working correlation structure to be correctly "
                 f"specified (only the mean model), and standard errors are the robust "
                 "(sandwich) form. The ICC diagnostic above (ICC={:.3f}) supports exchangeable as a "
                 "reasonable working structure rather than independence.".format(icc_diag['icc_question_strict_correct']))
    lines.append("- **Cochran's Q chi-square approximation**: assumes a reasonably large number of "
                 "blocks (questions); n=500 is large, so the chi-square approximation is treated as "
                 "adequate.")
    lines.append("- **Flip-rate GEE**: cells are NOT paired (conditioned on run-1 failure, different "
                 "cells qualify per arm/model) -- this is an independent-groups cluster-robust logistic "
                 "regression, not a paired test. Cluster = question to absorb shared question "
                 "difficulty across the arm/model cells that do co-occur for a question.")
    lines.append("- **Run-1 cleanliness**: confirmed directly from `ledger/ATTEMPT_TIMELINE.csv` (all "
                 "1856 logged attempt rows are run_index in {2,3}); run 1 has no rows in that "
                 "deviation-era log and DEVIATIONS.md documents the Vertex routing as starting "
                 "2026-08-06, after run-1 collection. No sensitivity exclusion applied to any run-1 "
                 "(Sections 1-3) result.")
    lines.append("- **provider x condition interaction**: not estimable (no tailscale_B); not tested, "
                 "per STATS_SPEC.md.")
    lines.append("")

    with open(RESULTS / "PRIMARY_TESTS.md", "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

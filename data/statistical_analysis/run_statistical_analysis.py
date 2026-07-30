from __future__ import annotations

# /// script
# dependencies = [
#   "numpy",
#   "pandas",
#   "scipy",
#   "statsmodels",
#   "tabulate",
# ]
# ///

import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
import statsmodels.api as sm
from scipy.stats import ttest_1samp
from statsmodels.stats.contingency_tables import cochrans_q, mcnemar
from statsmodels.stats.multitest import multipletests


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "runs" / "medrag_eval.sqlite"
OUT_DIR = ROOT / "reports" / "statistical_analysis"
EXPERIMENT = "bench_315_v2"
BOOTSTRAP_N = 10_000
BOOTSTRAP_SEED = 20260526

OPENROUTER = "openrouter"
TAILSCALE = "tailscale_medical_rag"

MODEL_LABELS = {
    "google/gemini-3.5-flash": "Gemini",
    "google/gemma-4-26b-a4b-it": "Gemma",
    "qwen/qwen3.6-35b-a3b": "Qwen 3.6",
    "qwen/qwen3.7-max": "Qwen 3.7 Max",
}


def source_type(model: str) -> str:
    return "closed_source" if model.startswith("google/gemini") else "open_source"


def size_class(model: str) -> str:
    if model.startswith("google/gemini") or model == "qwen/qwen3.7-max":
        return "big"
    return "small"


def load_final_results() -> pd.DataFrame:
    query = """
    WITH latest_attempt AS (
      SELECT a.*,
             ROW_NUMBER() OVER (
               PARTITION BY a.logical_call_id
               ORDER BY a.attempt_index DESC, a.id DESC
             ) rn
      FROM provider_attempts a
    ), latest_answer AS (
      SELECT p.*,
             ROW_NUMBER() OVER (
               PARTITION BY p.logical_call_id
               ORDER BY p.id DESC
             ) rn
      FROM parsed_answers p
    )
    SELECT
      lc.id AS logical_call_id,
      q.question_id,
      lc.provider,
      lc.model,
      lc.run_index,
      la.id AS provider_attempt_id,
      la.attempt_index,
      la.latency_ms,
      la.error_type,
      pa.parse_status,
      pa.selected_letter,
      s.strict_correct,
      s.letter_correct,
      s.text_correct
    FROM logical_calls lc
    JOIN experiments e ON e.id = lc.experiment_id
    JOIN questions q ON q.id = lc.question_id
    LEFT JOIN latest_attempt la ON la.logical_call_id = lc.id AND la.rn = 1
    LEFT JOIN latest_answer pa ON pa.logical_call_id = lc.id AND pa.rn = 1
    LEFT JOIN scores s ON s.parsed_answer_id = pa.id
    WHERE e.name = ?
    """
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(query, conn, params=(EXPERIMENT,))
    df["strict_correct"] = df["strict_correct"].astype(int)
    df["provider_label"] = df["provider"].map(
        {OPENROUTER: "OpenRouter", TAILSCALE: "TailScale"}
    )
    df["model_label"] = df["model"].map(MODEL_LABELS).fillna(df["model"])
    df["source_type"] = df["model"].map(source_type)
    df["size_class"] = df["model"].map(size_class)
    return df


def load_attempt_history() -> pd.DataFrame:
    query = """
    SELECT
      lc.id AS logical_call_id,
      q.question_id,
      lc.provider,
      lc.model,
      a.id AS attempt_id,
      a.attempt_index,
      a.latency_ms,
      a.error_type,
      p.parse_status
    FROM provider_attempts a
    JOIN logical_calls lc ON lc.id = a.logical_call_id
    JOIN experiments e ON e.id = lc.experiment_id
    JOIN questions q ON q.id = lc.question_id
    LEFT JOIN parsed_answers p ON p.provider_attempt_id = a.id
    WHERE e.name = ?
    """
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(query, conn, params=(EXPERIMENT,))
    df["provider_label"] = df["provider"].map(
        {OPENROUTER: "OpenRouter", TAILSCALE: "TailScale"}
    )
    df["model_label"] = df["model"].map(MODEL_LABELS).fillna(df["model"])
    return df


def accuracy_table(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby(["provider", "model", "provider_label", "model_label"], as_index=False)
        .agg(calls=("strict_correct", "size"), correct=("strict_correct", "sum"))
    )
    grouped["accuracy"] = grouped["correct"] / grouped["calls"]
    return grouped.sort_values(["provider", "model"])


def bootstrap_paired_diff_ci(
    wide: pd.DataFrame, left: str, right: str, seed_offset: int = 0
) -> tuple[float, float]:
    rng = np.random.default_rng(BOOTSTRAP_SEED + seed_offset)
    diffs = (wide[right].to_numpy() - wide[left].to_numpy()).astype(float)
    n = len(diffs)
    idx = rng.integers(0, n, size=(BOOTSTRAP_N, n))
    boot = diffs[idx].mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return float(lo), float(hi)


def provider_comparison(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for i, model in enumerate(sorted(df["model"].unique())):
        sub = df[df["model"] == model]
        wide = sub.pivot(index="question_id", columns="provider", values="strict_correct")
        b = int(((wide[OPENROUTER] == 1) & (wide[TAILSCALE] == 0)).sum())
        c = int(((wide[OPENROUTER] == 0) & (wide[TAILSCALE] == 1)).sum())
        test = mcnemar([[0, b], [c, 0]], exact=True)
        diff = float(wide[OPENROUTER].mean() - wide[TAILSCALE].mean())
        ci_low, ci_high = bootstrap_paired_diff_ci(wide, TAILSCALE, OPENROUTER, i)
        rows.append(
            {
                "model": model,
                "model_label": MODEL_LABELS.get(model, model),
                "openrouter_accuracy": float(wide[OPENROUTER].mean()),
                "tailscale_accuracy": float(wide[TAILSCALE].mean()),
                "paired_diff_openrouter_minus_tailscale": diff,
                "bootstrap_ci_low": ci_low,
                "bootstrap_ci_high": ci_high,
                "openrouter_only_correct_b": b,
                "tailscale_only_correct_c": c,
                "discordant_pairs": b + c,
                "mcnemar_exact": True,
                "mcnemar_statistic": float(test.statistic),
                "p_value": float(test.pvalue),
            }
        )
    out = pd.DataFrame(rows)
    out["p_holm"] = multipletests(out["p_value"], method="holm")[1]
    out["reject_holm_0_05"] = multipletests(out["p_value"], method="holm")[0]
    return out


def model_comparison(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    omnibus_rows = []
    pair_rows = []
    for provider in sorted(df["provider"].unique()):
        sub = df[df["provider"] == provider]
        wide = sub.pivot(index="question_id", columns="model", values="strict_correct")
        q_res = cochrans_q(wide)
        omnibus_rows.append(
            {
                "provider": provider,
                "provider_label": "OpenRouter" if provider == OPENROUTER else "TailScale",
                "cochran_q_statistic": float(q_res.statistic),
                "df": int(len(wide.columns) - 1),
                "p_value": float(q_res.pvalue),
            }
        )
        models = list(wide.columns)
        for i, left in enumerate(models):
            for right in models[i + 1 :]:
                b = int(((wide[left] == 1) & (wide[right] == 0)).sum())
                c = int(((wide[left] == 0) & (wide[right] == 1)).sum())
                test = mcnemar([[0, b], [c, 0]], exact=True)
                pair_rows.append(
                    {
                        "provider": provider,
                        "provider_label": "OpenRouter" if provider == OPENROUTER else "TailScale",
                        "model_a": left,
                        "model_a_label": MODEL_LABELS.get(left, left),
                        "model_b": right,
                        "model_b_label": MODEL_LABELS.get(right, right),
                        "accuracy_a": float(wide[left].mean()),
                        "accuracy_b": float(wide[right].mean()),
                        "paired_diff_b_minus_a": float(wide[right].mean() - wide[left].mean()),
                        "a_only_correct_b": b,
                        "b_only_correct_c": c,
                        "discordant_pairs": b + c,
                        "mcnemar_exact": True,
                        "p_value": float(test.pvalue),
                    }
                )
    pair_df = pd.DataFrame(pair_rows)
    corrected = []
    for provider, group in pair_df.groupby("provider", sort=False):
        holm = multipletests(group["p_value"], method="holm")
        tmp = group.copy()
        tmp["p_holm_within_provider"] = holm[1]
        tmp["reject_holm_0_05"] = holm[0]
        corrected.append(tmp)
    return pd.DataFrame(omnibus_rows), pd.concat(corrected, ignore_index=True)


def fit_gee(df: pd.DataFrame, formula: str):
    return smf.gee(
        formula=formula,
        groups="question_id",
        data=df,
        family=sm.families.Binomial(),
    ).fit()


def tidy_gee(result) -> pd.DataFrame:
    conf = result.conf_int()
    rows = []
    for name in result.params.index:
        coef = float(result.params[name])
        rows.append(
            {
                "term": name,
                "coef_log_odds": coef,
                "odds_ratio": float(np.exp(coef)),
                "robust_se": float(result.bse[name]),
                "z": float(result.tvalues[name]),
                "p_value": float(result.pvalues[name]),
                "ci_low_or": float(np.exp(conf.loc[name, 0])),
                "ci_high_or": float(np.exp(conf.loc[name, 1])),
            }
        )
    return pd.DataFrame(rows)


def adjusted_models(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    work = df.copy()
    work["provider_c"] = pd.Categorical(work["provider"], categories=[OPENROUTER, TAILSCALE])
    work["model_c"] = pd.Categorical(
        work["model"],
        categories=[
            "google/gemini-3.5-flash",
            "google/gemma-4-26b-a4b-it",
            "qwen/qwen3.6-35b-a3b",
            "qwen/qwen3.7-max",
        ],
    )
    result = fit_gee(work, "strict_correct ~ provider_c * model_c")
    terms = result.wald_test_terms(skip_single=False).table.reset_index()
    terms = terms.rename(columns={"index": "term"})
    terms["statistic"] = terms["statistic"].map(lambda value: float(np.asarray(value).squeeze()))
    terms["pvalue"] = terms["pvalue"].astype(float)
    meta = {
        "formula": "strict_correct ~ provider_c * model_c",
        "cluster": "question_id",
        "family": "Binomial",
        "reference_provider": OPENROUTER,
        "reference_model": "google/gemini-3.5-flash",
        "n_rows": int(len(work)),
        "n_clusters": int(work["question_id"].nunique()),
    }
    return tidy_gee(result), terms, meta


def exploratory_groups(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    desc = (
        df.groupby(["source_type", "size_class", "provider"], as_index=False)
        .agg(calls=("strict_correct", "size"), correct=("strict_correct", "sum"))
    )
    desc["accuracy"] = desc["correct"] / desc["calls"]

    source_work = df.copy()
    source_work["source_c"] = pd.Categorical(
        source_work["source_type"], categories=["open_source", "closed_source"]
    )
    source_work["provider_c"] = pd.Categorical(source_work["provider"], categories=[OPENROUTER, TAILSCALE])
    source_result = fit_gee(source_work, "strict_correct ~ source_c + provider_c")

    size_work = df.copy()
    size_work["size_c"] = pd.Categorical(size_work["size_class"], categories=["small", "big"])
    size_work["provider_c"] = pd.Categorical(size_work["provider"], categories=[OPENROUTER, TAILSCALE])
    size_result = fit_gee(size_work, "strict_correct ~ size_c * provider_c")
    return desc, tidy_gee(source_result), tidy_gee(size_result)


def latency_reliability(final_df: pd.DataFrame, attempts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    lat = (
        final_df.groupby(["provider", "model", "provider_label", "model_label"], as_index=False)
        .agg(
            n=("latency_ms", "size"),
            mean_ms=("latency_ms", "mean"),
            median_ms=("latency_ms", "median"),
            p90_ms=("latency_ms", lambda x: float(np.percentile(x, 90))),
            p95_ms=("latency_ms", lambda x: float(np.percentile(x, 95))),
            max_ms=("latency_ms", "max"),
        )
    )

    pair_rows = []
    for model in sorted(final_df["model"].unique()):
        wide = final_df[final_df["model"] == model].pivot(
            index="question_id", columns="provider", values="latency_ms"
        )
        ratios = wide[TAILSCALE] / wide[OPENROUTER]
        log_ratios = np.log(ratios)
        test = ttest_1samp(log_ratios, 0.0)
        se = log_ratios.std(ddof=1) / np.sqrt(len(log_ratios))
        mean_log_ratio = log_ratios.mean()
        ci_low = float(np.exp(mean_log_ratio - 1.96 * se))
        ci_high = float(np.exp(mean_log_ratio + 1.96 * se))
        pair_rows.append(
            {
                "model": model,
                "model_label": MODEL_LABELS.get(model, model),
                "openrouter_median_ms": float(wide[OPENROUTER].median()),
                "tailscale_median_ms": float(wide[TAILSCALE].median()),
                "median_latency_ratio_tailscale_over_openrouter": float(np.median(ratios)),
                "geomean_latency_ratio_tailscale_over_openrouter": float(np.exp(mean_log_ratio)),
                "geomean_ratio_ci_low": ci_low,
                "geomean_ratio_ci_high": ci_high,
                "paired_log_latency_t_statistic": float(test.statistic),
                "p_value": float(test.pvalue),
            }
        )
    pair_df = pd.DataFrame(pair_rows)
    pair_df["p_holm"] = multipletests(pair_df["p_value"], method="holm")[1]

    attempts_per_call = attempts.groupby("logical_call_id").size().rename("attempt_count")
    # `groupby().first()` skips nulls per column and can accidentally combine
    # the first attempt's error_type with a later attempt's parse_status.
    initial = attempts.sort_values(["logical_call_id", "attempt_index"]).drop_duplicates(
        "logical_call_id", keep="first"
    )
    call_meta = final_df[
        ["logical_call_id", "provider", "model", "provider_label", "model_label"]
    ].drop_duplicates()
    rel = call_meta.merge(attempts_per_call, on="logical_call_id").merge(
        initial[["logical_call_id", "error_type", "parse_status"]],
        on="logical_call_id",
        how="left",
        suffixes=("", "_initial"),
    )
    rel["needed_retry"] = rel["attempt_count"] > 1
    rel["initial_api_failed"] = rel["error_type"].notna()
    rel["initial_parse_failed"] = rel["parse_status"].notna() & ~rel["parse_status"].isin(["ok", "ok_conflict"])
    rel_summary = (
        rel.groupby(["provider", "model", "provider_label", "model_label"], as_index=False)
        .agg(
            logical_calls=("logical_call_id", "size"),
            total_attempts=("attempt_count", "sum"),
            mean_attempts=("attempt_count", "mean"),
            max_attempts=("attempt_count", "max"),
            calls_needing_retry=("needed_retry", "sum"),
            initial_api_failures=("initial_api_failed", "sum"),
            initial_parse_failures=("initial_parse_failed", "sum"),
        )
    )
    error_counts = (
        attempts.assign(error_or_parse=attempts["error_type"].fillna(attempts["parse_status"].fillna("none")))
        .groupby(["provider", "model", "provider_label", "model_label", "error_or_parse"], as_index=False)
        .size()
        .rename(columns={"size": "attempt_rows"})
    )
    return lat, pair_df, rel_summary.merge(
        error_counts.groupby(["provider", "model"], as_index=False)
        .apply(lambda g: json.dumps(dict(zip(g["error_or_parse"], g["attempt_rows"])), sort_keys=True), include_groups=False)
        .rename(columns={None: "attempt_status_counts"}),
        on=["provider", "model"],
        how="left",
    )


def final_completeness_text(final_df: pd.DataFrame) -> str:
    completed = int(
        (
            final_df["error_type"].isna()
            & final_df["parse_status"].isin(["ok", "ok_conflict"])
            & final_df["strict_correct"].notna()
        ).sum()
    )
    total = len(final_df)
    api_failed = int(final_df["error_type"].notna().sum())
    parse_failed = int((~final_df["parse_status"].isin(["ok", "ok_conflict"])).sum())
    return (
        f"Final completeness: {completed}/{total} completed; "
        f"latest API failures={api_failed}; latest parse failures={parse_failed}."
    )


def fmt_pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def write_outputs() -> None:
    final_df = load_final_results()
    attempts = load_attempt_history()
    acc = accuracy_table(final_df)
    provider = provider_comparison(final_df)
    cochran, model_pairs = model_comparison(final_df)
    gee_terms, gee_wald, gee_meta = adjusted_models(final_df)
    group_desc, source_gee, size_gee = exploratory_groups(final_df)
    latency, latency_pairs, reliability = latency_reliability(final_df, attempts)

    tables = {
        "final_accuracy_by_arm.csv": acc,
        "provider_mcnemar.csv": provider,
        "model_cochran_q.csv": cochran,
        "model_pairwise_mcnemar.csv": model_pairs,
        "gee_provider_model_coefficients.csv": gee_terms,
        "gee_provider_model_wald_terms.csv": gee_wald,
        "exploratory_group_descriptives.csv": group_desc,
        "exploratory_source_gee.csv": source_gee,
        "exploratory_size_gee.csv": size_gee,
        "latency_summary.csv": latency,
        "latency_provider_logratio.csv": latency_pairs,
        "reliability_summary.csv": reliability,
    }
    for filename, table in tables.items():
        table.to_csv(OUT_DIR / filename, index=False)

    summary = {
        "experiment": EXPERIMENT,
        "db_path": str(DB_PATH.relative_to(ROOT)),
        "rows": int(len(final_df)),
        "questions": int(final_df["question_id"].nunique()),
        "arms": int(final_df.groupby(["provider", "model"]).ngroups),
        "gee_meta": gee_meta,
    }
    (OUT_DIR / "analysis_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    interaction_p = gee_wald.loc[gee_wald["term"].str.contains("provider_c:model_c"), "pvalue"]
    interaction_text = "not available" if interaction_p.empty else f"{interaction_p.iloc[0]:.4g}"
    lines = [
        "# Statistical Analysis: bench_315_v2",
        "",
        "## Dataset",
        f"- Final analyzable rows: {len(final_df)}.",
        f"- Questions: {final_df['question_id'].nunique()}, crossed with 2 providers and 4 models.",
        "- Primary outcome: `strict_correct` on the latest attempt per logical call.",
        f"- {final_completeness_text(final_df)}",
        "",
        "## Accuracy by Arm",
        acc.assign(accuracy_pct=acc["accuracy"].map(fmt_pct))[
            ["provider_label", "model_label", "calls", "correct", "accuracy_pct"]
        ].to_markdown(index=False),
        "",
        "## Primary Provider Comparison",
        "McNemar tests compare OpenRouter vs TailScale within each model using paired question-level outcomes. Holm correction is across the four model-level comparisons.",
        provider.assign(
            openrouter_accuracy=provider["openrouter_accuracy"].map(fmt_pct),
            tailscale_accuracy=provider["tailscale_accuracy"].map(fmt_pct),
            paired_diff_openrouter_minus_tailscale=provider["paired_diff_openrouter_minus_tailscale"].map(lambda x: f"{100*x:+.1f} pp"),
            bootstrap_ci=lambda x: [
                f"[{100*l:+.1f}, {100*h:+.1f}] pp"
                for l, h in zip(x["bootstrap_ci_low"], x["bootstrap_ci_high"])
            ],
        )[
            [
                "model_label",
                "openrouter_accuracy",
                "tailscale_accuracy",
                "paired_diff_openrouter_minus_tailscale",
                "bootstrap_ci",
                "openrouter_only_correct_b",
                "tailscale_only_correct_c",
                "p_value",
                "p_holm",
                "reject_holm_0_05",
            ]
        ].to_markdown(index=False),
        "",
        "## Primary Model Comparison",
        "Cochran's Q tests compare all four paired model outcomes within each provider. Pairwise follow-ups use McNemar tests with Holm correction within provider.",
        cochran.to_markdown(index=False),
        "",
        model_pairs[
            [
                "provider_label",
                "model_a_label",
                "model_b_label",
                "accuracy_a",
                "accuracy_b",
                "paired_diff_b_minus_a",
                "discordant_pairs",
                "p_value",
                "p_holm_within_provider",
                "reject_holm_0_05",
            ]
        ].to_markdown(index=False),
        "",
        "## Full Adjusted Model",
        "GEE logistic regression with binomial family and question-level clustering: `strict_correct ~ provider * model`. Reference provider is OpenRouter; reference model is Gemini.",
        f"- Provider-by-model interaction Wald p-value: {interaction_text}.",
        gee_wald.to_markdown(index=False),
        "",
        gee_terms.to_markdown(index=False),
        "",
        "## Exploratory Group Analyses",
        "Source and size analyses are exploratory. Closed-source is represented only by Gemini, so source type is confounded with model identity. Size class is also confounded with model family.",
        group_desc.assign(accuracy=group_desc["accuracy"].map(fmt_pct)).to_markdown(index=False),
        "",
        "Source-type GEE coefficients:",
        source_gee.to_markdown(index=False),
        "",
        "Size-class/provider GEE coefficients:",
        size_gee.to_markdown(index=False),
        "",
        "## Latency",
        "Latency uses latest-attempt latency for final completed calls. Provider comparisons are paired by question and model using one-sample tests of log(TailScale/OpenRouter) latency ratios with Holm correction.",
        latency.to_markdown(index=False),
        "",
        latency_pairs.to_markdown(index=False),
        "",
        "## Reliability",
        "Reliability uses the full attempt history, not only final successful attempts.",
        reliability.to_markdown(index=False),
        "",
        "## Methodological Caveats",
        "- The effective independent unit for accuracy inference is the question, not the 2520 rows.",
        "- McNemar and Cochran's Q assume independent question-level pairs/blocks.",
        "- GEE uses robust SEs clustered by question; it does not require treating repeated arms as independent.",
        "- Open-source vs closed-source and size-class findings should be treated as exploratory because group labels are confounded with model identity and model family.",
        "- Latency is skewed; medians and upper percentiles are more interpretable than means.",
    ]
    (OUT_DIR / "statistical_report.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    write_outputs()

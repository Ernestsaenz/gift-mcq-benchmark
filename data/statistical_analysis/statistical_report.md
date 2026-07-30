# Statistical Analysis: bench_315_v2

## Dataset
- Final analyzable rows: 2520.
- Questions: 315, crossed with 2 providers and 4 models.
- Primary outcome: `strict_correct` on the latest attempt per logical call.
- Final completeness: 2520/2520 completed; latest API failures=0; latest parse failures=0.

## Accuracy by Arm
| provider_label   | model_label   |   calls |   correct | accuracy_pct   |
|:-----------------|:--------------|--------:|----------:|:---------------|
| OpenRouter       | Gemini        |     315 |       303 | 96.2%          |
| OpenRouter       | Gemma         |     315 |       232 | 73.7%          |
| OpenRouter       | Qwen 3.6      |     315 |       275 | 87.3%          |
| OpenRouter       | Qwen 3.7 Max  |     315 |       298 | 94.6%          |
| TailScale        | Gemini        |     315 |       301 | 95.6%          |
| TailScale        | Gemma         |     315 |       232 | 73.7%          |
| TailScale        | Qwen 3.6      |     315 |       265 | 84.1%          |
| TailScale        | Qwen 3.7 Max  |     315 |       297 | 94.3%          |

## Primary Provider Comparison
McNemar tests compare OpenRouter vs TailScale within each model using paired question-level outcomes. Holm correction is across the four model-level comparisons.
| model_label   | openrouter_accuracy   | tailscale_accuracy   | paired_diff_openrouter_minus_tailscale   | bootstrap_ci    |   openrouter_only_correct_b |   tailscale_only_correct_c |   p_value |   p_holm | reject_holm_0_05   |
|:--------------|:----------------------|:---------------------|:-----------------------------------------|:----------------|----------------------------:|---------------------------:|----------:|---------:|:-------------------|
| Gemini        | 96.2%                 | 95.6%                | +0.6 pp                                  | [-0.6, +1.9] pp |                           3 |                          1 | 0.625     | 1        | False              |
| Gemma         | 73.7%                 | 73.7%                | +0.0 pp                                  | [-3.2, +3.2] pp |                          14 |                         14 | 1         | 1        | False              |
| Qwen 3.6      | 87.3%                 | 84.1%                | +3.2 pp                                  | [+0.0, +6.7] pp |                          19 |                          9 | 0.0871586 | 0.348634 | False              |
| Qwen 3.7 Max  | 94.6%                 | 94.3%                | +0.3 pp                                  | [-1.9, +2.5] pp |                           7 |                          6 | 1         | 1        | False              |

## Primary Model Comparison
Cochran's Q tests compare all four paired model outcomes within each provider. Pairwise follow-ups use McNemar tests with Holm correction within provider.
| provider              | provider_label   |   cochran_q_statistic |   df |     p_value |
|:----------------------|:-----------------|----------------------:|-----:|------------:|
| openrouter            | OpenRouter       |               121     |    3 | 4.69962e-26 |
| tailscale_medical_rag | TailScale        |               117.454 |    3 | 2.72683e-25 |

| provider_label   | model_a_label   | model_b_label   |   accuracy_a |   accuracy_b |   paired_diff_b_minus_a |   discordant_pairs |     p_value |   p_holm_within_provider | reject_holm_0_05   |
|:-----------------|:----------------|:----------------|-------------:|-------------:|------------------------:|-------------------:|------------:|-------------------------:|:-------------------|
| OpenRouter       | Gemini          | Gemma           |     0.961905 |     0.736508 |              -0.225397  |                 79 | 5.24347e-18 |              3.14608e-17 | True               |
| OpenRouter       | Gemini          | Qwen 3.6        |     0.961905 |     0.873016 |              -0.0888889 |                 36 | 1.94157e-06 |              5.82472e-06 | True               |
| OpenRouter       | Gemini          | Qwen 3.7 Max    |     0.961905 |     0.946032 |              -0.015873  |                 19 | 0.359283    |              0.359283    | False              |
| OpenRouter       | Gemma           | Qwen 3.6        |     0.736508 |     0.873016 |               0.136508  |                 65 | 6.02754e-08 |              2.41102e-07 | True               |
| OpenRouter       | Gemma           | Qwen 3.7 Max    |     0.736508 |     0.946032 |               0.209524  |                 76 | 5.24923e-16 |              2.62462e-15 | True               |
| OpenRouter       | Qwen 3.6        | Qwen 3.7 Max    |     0.873016 |     0.946032 |               0.0730159 |                 37 | 0.000191076 |              0.000382153 | True               |
| TailScale        | Gemini          | Gemma           |     0.955556 |     0.736508 |              -0.219048  |                 73 | 5.72171e-19 |              3.43302e-18 | True               |
| TailScale        | Gemini          | Qwen 3.6        |     0.955556 |     0.84127  |              -0.114286  |                 50 | 2.09868e-07 |              8.39471e-07 | True               |
| TailScale        | Gemini          | Qwen 3.7 Max    |     0.955556 |     0.942857 |              -0.0126984 |                 22 | 0.523467    |              0.523467    | False              |
| TailScale        | Gemma           | Qwen 3.6        |     0.736508 |     0.84127  |               0.104762  |                 55 | 8.69937e-06 |              1.73987e-05 | True               |
| TailScale        | Gemma           | Qwen 3.7 Max    |     0.736508 |     0.942857 |               0.206349  |                 71 | 5.0578e-17  |              2.5289e-16  | True               |
| TailScale        | Qwen 3.6        | Qwen 3.7 Max    |     0.84127  |     0.942857 |               0.101587  |                 46 | 1.83154e-06 |              5.49463e-06 | True               |

## Full Adjusted Model
GEE logistic regression with binomial family and question-level clustering: `strict_correct ~ provider * model`. Reference provider is OpenRouter; reference model is Gemini.
- Provider-by-model interaction Wald p-value: 0.4147.
| term               |   statistic |      pvalue |   df_constraint |
|:-------------------|------------:|------------:|----------------:|
| Intercept          |   120.338   | 5.33514e-28 |               1 |
| provider_c         |     1.00103 | 0.317062    |               1 |
| model_c            |    83.9648  | 4.32868e-18 |               3 |
| provider_c:model_c |     2.85376 | 0.414726    |               3 |

| term                                                                     |   coef_log_odds |   odds_ratio |   robust_se |         z |     p_value |   ci_low_or |   ci_high_or |
|:-------------------------------------------------------------------------|----------------:|-------------:|------------:|----------:|------------:|------------:|-------------:|
| Intercept                                                                |       3.22883   |    25.25     |    0.294336 | 10.9699   | 5.33514e-28 |  14.1815    |    44.9573   |
| provider_c[T.tailscale_medical_rag]                                      |      -0.160773  |     0.851485 |    0.160691 | -1.00051  | 0.317062    |   0.621437  |     1.16669  |
| model_c[T.google/gemma-4-26b-a4b-it]                                     |      -2.20093   |     0.1107   |    0.298796 | -7.36599  | 1.75835e-13 |   0.0616329 |     0.198831 |
| model_c[T.qwen/qwen3.6-35b-a3b]                                          |      -1.30093   |     0.272277 |    0.288335 | -4.51189  | 6.42517e-06 |   0.154732  |     0.479118 |
| model_c[T.qwen/qwen3.7-max]                                              |      -0.364946  |     0.694234 |    0.319252 | -1.14313  | 0.252986    |   0.371328  |     1.29794  |
| provider_c[T.tailscale_medical_rag]:model_c[T.google/gemma-4-26b-a4b-it] |       0.160773  |     1.17442  |    0.18569  |  0.865816 | 0.386591    |   0.816138  |     1.68998  |
| provider_c[T.tailscale_medical_rag]:model_c[T.qwen/qwen3.6-35b-a3b]      |      -0.0994116 |     0.90537  |    0.217856 | -0.456319 | 0.648161    |   0.590727  |     1.3876   |
| provider_c[T.tailscale_medical_rag]:model_c[T.qwen/qwen3.7-max]          |       0.100253  |     1.10545  |    0.270281 |  0.370923 | 0.710695    |   0.650842  |     1.8776   |

## Exploratory Group Analyses
Source and size analyses are exploratory. Closed-source is represented only by Gemini, so source type is confounded with model identity. Size class is also confounded with model family.
| source_type   | size_class   | provider              |   calls |   correct | accuracy   |
|:--------------|:-------------|:----------------------|--------:|----------:|:-----------|
| closed_source | big          | openrouter            |     315 |       303 | 96.2%      |
| closed_source | big          | tailscale_medical_rag |     315 |       301 | 95.6%      |
| open_source   | big          | openrouter            |     315 |       298 | 94.6%      |
| open_source   | big          | tailscale_medical_rag |     315 |       297 | 94.3%      |
| open_source   | small        | openrouter            |     630 |       507 | 80.5%      |
| open_source   | small        | tailscale_medical_rag |     630 |       497 | 78.9%      |

Source-type GEE coefficients:
| term                                |   coef_log_odds |   odds_ratio |   robust_se |        z |     p_value |   ci_low_or |   ci_high_or |
|:------------------------------------|----------------:|-------------:|------------:|---------:|------------:|------------:|-------------:|
| Intercept                           |       1.75258   |     5.76946  |   0.112173  | 15.6239  | 5.00408e-55 |    4.63077  |      7.18815 |
| source_c[T.closed_source]           |       1.44193   |     4.22883  |   0.252255  |  5.71614 | 1.08971e-08 |    2.57929  |      6.93331 |
| provider_c[T.tailscale_medical_rag] |      -0.0959444 |     0.908515 |   0.0623313 | -1.53926 | 0.12374     |    0.804036 |      1.02657 |

Size-class/provider GEE coefficients:
| term                                              |   coef_log_odds |   odds_ratio |   robust_se |          z |     p_value |   ci_low_or |   ci_high_or |
|:--------------------------------------------------|----------------:|-------------:|------------:|-----------:|------------:|------------:|-------------:|
| Intercept                                         |       1.41633   |     4.12195  |   0.116495  | 12.1578    | 5.21122e-34 |    3.28052  |      5.17921 |
| size_c[T.big]                                     |       1.61497   |     5.02775  |   0.203854  |  7.92219   | 2.3337e-15  |    3.37173  |      7.49713 |
| provider_c[T.tailscale_medical_rag]               |      -0.0980858 |     0.906571 |   0.0740153 | -1.32521   | 0.185102    |    0.784151 |      1.0481  |
| size_c[T.big]:provider_c[T.tailscale_medical_rag] |      -0.0053585 |     0.994656 |   0.163122  | -0.0328496 | 0.973795    |    0.722475 |      1.36938 |

## Latency
Latency uses latest-attempt latency for final completed calls. Provider comparisons are paired by question and model using one-sample tests of log(TailScale/OpenRouter) latency ratios with Holm correction.
| provider              | model                     | provider_label   | model_label   |   n |   mean_ms |   median_ms |   p90_ms |   p95_ms |   max_ms |
|:----------------------|:--------------------------|:-----------------|:--------------|----:|----------:|------------:|---------:|---------:|---------:|
| openrouter            | google/gemini-3.5-flash   | OpenRouter       | Gemini        | 315 |   6882.86 |        4952 |   7972.4 |   9929.3 |   240176 |
| openrouter            | google/gemma-4-26b-a4b-it | OpenRouter       | Gemma         | 315 |   2564.39 |        1689 |   3295.8 |   4558.3 |    61880 |
| openrouter            | qwen/qwen3.6-35b-a3b      | OpenRouter       | Qwen 3.6      | 315 |  38438.1  |       35069 |  65174.4 |  79828.8 |   308133 |
| openrouter            | qwen/qwen3.7-max          | OpenRouter       | Qwen 3.7 Max  | 315 |  20254.7  |       16500 |  33728.2 |  44788   |   105221 |
| tailscale_medical_rag | google/gemini-3.5-flash   | TailScale        | Gemini        | 315 |  28394    |       25390 |  45388   |  48750.4 |   109326 |
| tailscale_medical_rag | google/gemma-4-26b-a4b-it | TailScale        | Gemma         | 315 |  17097.2  |       14364 |  25623   |  30680.7 |    73055 |
| tailscale_medical_rag | qwen/qwen3.6-35b-a3b      | TailScale        | Qwen 3.6      | 315 |  27481.9  |       23659 |  43707.6 |  52312.6 |    94667 |
| tailscale_medical_rag | qwen/qwen3.7-max          | TailScale        | Qwen 3.7 Max  | 315 |  31085.2  |       27779 |  43859.8 |  58943.2 |   112581 |

| model                     | model_label   |   openrouter_median_ms |   tailscale_median_ms |   median_latency_ratio_tailscale_over_openrouter |   geomean_latency_ratio_tailscale_over_openrouter |   geomean_ratio_ci_low |   geomean_ratio_ci_high |   paired_log_latency_t_statistic |      p_value |       p_holm |
|:--------------------------|:--------------|-----------------------:|----------------------:|-------------------------------------------------:|--------------------------------------------------:|-----------------------:|------------------------:|---------------------------------:|-------------:|-------------:|
| google/gemini-3.5-flash   | Gemini        |                   4952 |                 25390 |                                         4.98393  |                                          4.96966  |               4.69419  |                 5.2613  |                         55.1069  | 1.75604e-163 | 5.26812e-163 |
| google/gemma-4-26b-a4b-it | Gemma         |                   1689 |                 14364 |                                         8.90375  |                                          8.55266  |               7.9993   |                 9.1443  |                         62.8907  | 5.2788e-180  | 2.11152e-179 |
| qwen/qwen3.6-35b-a3b      | Qwen 3.6      |                  35069 |                 23659 |                                         0.696006 |                                          0.784105 |               0.730824 |                 0.84127 |                         -6.77413 | 6.17927e-11  | 6.17927e-11  |
| qwen/qwen3.7-max          | Qwen 3.7 Max  |                  16500 |                 27779 |                                         1.78148  |                                          1.70507  |               1.63263  |                 1.78072 |                         24.0905  | 2.38359e-73  | 4.76718e-73  |

## Reliability
Reliability uses the full attempt history, not only final successful attempts.
| provider              | model                     | provider_label   | model_label   |   logical_calls |   total_attempts |   mean_attempts |   max_attempts |   calls_needing_retry |   initial_api_failures |   initial_parse_failures | attempt_status_counts                                                                                                                |
|:----------------------|:--------------------------|:-----------------|:--------------|----------------:|-----------------:|----------------:|---------------:|----------------------:|-----------------------:|-------------------------:|:-------------------------------------------------------------------------------------------------------------------------------------|
| openrouter            | google/gemini-3.5-flash   | OpenRouter       | Gemini        |             315 |              878 |         2.7873  |              4 |                   280 |                    280 |                        0 | {"ok": 315, "request_error": 560, "timeout": 3}                                                                                      |
| openrouter            | google/gemma-4-26b-a4b-it | OpenRouter       | Gemma         |             315 |              879 |         2.79048 |              5 |                   280 |                    280 |                        0 | {"ok": 315, "request_error": 561, "timeout": 3}                                                                                      |
| openrouter            | qwen/qwen3.6-35b-a3b      | OpenRouter       | Qwen 3.6      |             315 |              903 |         2.86667 |              5 |                   281 |                    281 |                        0 | {"malformed_json": 1, "ok": 315, "request_error": 566, "timeout": 21}                                                                |
| openrouter            | qwen/qwen3.7-max          | OpenRouter       | Qwen 3.7 Max  |             315 |              889 |         2.82222 |              5 |                   281 |                    281 |                        0 | {"ok": 315, "request_error": 564, "timeout": 10}                                                                                     |
| tailscale_medical_rag | google/gemini-3.5-flash   | TailScale        | Gemini        |             315 |              758 |         2.40635 |              4 |                   280 |                    280 |                        0 | {"auth_error": 5, "failed_no_answer_found": 155, "ok": 315, "ok_conflict": 1, "request_error": 280, "server_error": 1, "timeout": 1} |
| tailscale_medical_rag | google/gemma-4-26b-a4b-it | TailScale        | Gemma         |             315 |              679 |         2.15556 |              6 |                   280 |                    280 |                        0 | {"auth_error": 3, "failed_no_answer_found": 77, "ok": 315, "request_error": 280, "timeout": 4}                                       |
| tailscale_medical_rag | qwen/qwen3.6-35b-a3b      | TailScale        | Qwen 3.6      |             315 |              751 |         2.38413 |              4 |                   281 |                    281 |                        0 | {"auth_error": 3, "failed_no_answer_found": 149, "ok": 315, "request_error": 280, "server_error": 3, "timeout": 1}                   |
| tailscale_medical_rag | qwen/qwen3.7-max          | TailScale        | Qwen 3.7 Max  |             315 |              778 |         2.46984 |              5 |                   284 |                    283 |                        1 | {"auth_error": 4, "failed_no_answer_found": 172, "ok": 315, "request_error": 280, "server_error": 6, "timeout": 1}                   |

## Methodological Caveats
- The effective independent unit for accuracy inference is the question, not the 2520 rows.
- McNemar and Cochran's Q assume independent question-level pairs/blocks.
- GEE uses robust SEs clustered by question; it does not require treating repeated arms as independent.
- Open-source vs closed-source and size-class findings should be treated as exploratory because group labels are confounded with model identity and model family.
- Latency is skewed; medians and upper percentiles are more interpretable than means.
